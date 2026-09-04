import requests
import json
from collections import defaultdict
import numpy as np
from config.settings import get_settings
from src.outbound.header import get_header
from src.outbound.models import (
    Create_OCC_Format, OCC_Order, Option_Submission, Candidate_Result,
    Expected_Value_Result, option_type,
)
from src.utils import logger
from src.outbound.market_data.options_chain import get_option_chain
from src.outbound.market_data.historical import get_historical_bars
from src.outbound.strategy.volatility import get_volatility_stats
from src.outbound.strategy.implied_volatility import get_implied_volatility_result, compare_volatility
from src.outbound.strategy.expected_value import simulate_terminal_prices, compute_batch_expected_payoffs

SETTINGS = get_settings()

# fetching

def get_option_contract_symbol(non_occ_format: Create_OCC_Format) -> OCC_Order:
    BASE_URL = SETTINGS.BASE_URL
    headers = get_header()
    url = f"{BASE_URL}/v2/options/contracts"

    response = requests.get(
        url,
        headers = headers,
        params = {
            "underlying_symbols": non_occ_format.root_symbol,  # e.g., AAPL
            "expiration_date": non_occ_format.expr_date,   # optional filter
            "type": non_occ_format.option_type,                     # call or put
            "strike_price_gte": non_occ_format.strike_price_gte,
            "strike_price_lte": non_occ_format.strike_price_lte,
            "status": non_occ_format.status,
        }
    )
    contracts = response.json()["option_contracts"]
    symbol: OCC_Order = contracts[0]["symbol"]   # e.g. "AAPL260918C00230000"

    return symbol

# selecting

def _filter_underpriced(
    contract,
    underlying_symbol: str,
    spot_price: float,
    annual_vol: float,
    risk_free_rate: float | None,
):
    """
    Implied-vol solve + underpriced check for one contract. Kept cheap and
    per-contract (Newton-Raphson/Brent converges in single-digit iterations
    on real prices, sub-millisecond in practice), unlike the Monte Carlo
    step below which is genuinely worth batching. Returns (contract,
    Volatility_Comparison) or None.
    """
    if contract.ask <= 0:
        return None  # no real ask to buy at — nothing to price off of

    if contract.ask < SETTINGS.MIN_CONTRACT_PREMIUM:
        return None  # too cheap to trust — ev_per_premium would divide by a near-zero number and
                      # blow up into a noise-driven outlier that dominates ranking (see settings.py)

    try:
        iv_result = get_implied_volatility_result(
            contract_symbol=contract.contract_symbol,
            underlying_symbol=underlying_symbol,
            market_price=contract.ask,
            S=spot_price,
            K=contract.strike_price,
            days_to_expiry=contract.days_to_expiry,
            opt_type=contract.option_type,
            r=risk_free_rate if risk_free_rate is not None else SETTINGS.RISK_FREE_RATE,
        )
    except ValueError:
        return None  # unsolvable implied vol (bad/degenerate price) — skip rather than crash the scan

    vol_comparison = compare_volatility(
        underlying_symbol=underlying_symbol,
        contract_symbol=contract.contract_symbol,
        realized_vol=annual_vol,
        implied_vol=iv_result.implied_vol,
    )

    if vol_comparison.verdict != "underpriced":
        return None  # only buy options the market is pricing cheap relative to realized history

    return contract, vol_comparison


def select_candidates(
    underlying_symbol: str,
    spot_price: float,
    lookback_days: int = 730,
    top_n: int | None = None,
    min_ev_margin_pct: float | None = None,
    risk_free_rate: float | None = None,
) -> list[Candidate_Result]:
    """
    Full entry-side pipeline for one underlying: realized vol from history
    -> live option chain -> per-contract implied vol -> underpriced filter
    -> Monte Carlo EV -> profitability + margin filter -> ranked top N.

    Design choices (see conversation for the full reasoning):
      - Priced off `contract.ask`, not the bid/ask midpoint — the ask is
        what we'd actually pay to buy, so it's the realistic entry cost.
      - Only keeps contracts where compare_volatility() says "underpriced"
        (implied vol below realized vol) — that's the actual edge signal,
        not just "EV happens to be positive" (which can be simulation
        noise even near a fair price).
      - Ranked by ev_per_premium (expected_value / premium), not raw
        expected_value — a thin per-contract but proportionally larger
        expected return beats a big-dollar EV on an expensive contract.
      - Returns the top N, not a single winner, so the caller can
        diversify across a few candidates instead of concentrating risk
        into one contract.

    On "simultaneous" Monte Carlo: this used to farm per-contract work out
    to a ThreadPoolExecutor. Benchmarked that against plain sequential and
    against a ProcessPoolExecutor on a realistic-size chain (~24 contracts,
    50k sims each) — threads were *slower* than sequential (thread/GIL
    handoff overhead > the sub-millisecond of actual work per contract),
    and processes were about 2x slower still (process spawn + pickling
    cost dwarfs the work). So instead of OS-level concurrency, every
    contract that shares the same days-to-expiry (same S, T, sigma) now
    has its Monte Carlo run in ONE batched numpy call across all of them
    at once (see compute_batch_expected_payoffs) — genuinely simultaneous
    (vectorized/SIMD), not scheduled, and with no per-task setup cost.
    """
    top_n = top_n if top_n is not None else SETTINGS.TOP_N_CANDIDATES
    min_ev_margin_pct = min_ev_margin_pct if min_ev_margin_pct is not None else SETTINGS.MIN_EV_MARGIN_PCT
    r = risk_free_rate if risk_free_rate is not None else SETTINGS.RISK_FREE_RATE
    n_sims = SETTINGS.MONTE_CARLO_SIMULATIONS

    bars = get_historical_bars(underlying_symbol, lookback_days=lookback_days)
    vol_stats = get_volatility_stats(underlying_symbol, bars, lookback_days)

    chain = get_option_chain(underlying_symbol, spot_price)

    if not chain:
        return []

    survivors = [
        result for result in (
            _filter_underpriced(contract, underlying_symbol, spot_price, vol_stats.annual_vol, risk_free_rate)
            for contract in chain
        )
        if result is not None
    ]

    if not survivors:
        logger.log(
            f"{underlying_symbol}: {len(chain)} contracts in chain, 0 came back underpriced "
            f"(realized_vol={vol_stats.annual_vol:.1%}) — nothing to evaluate for EV.",
            level="debug",
        )
        return []

    # group by days-to-expiry: everything in a group shares S, T, sigma, so
    # one simulate_terminal_prices() + one batched payoff computation covers
    # the whole group instead of one Monte Carlo run per contract.
    groups: dict[int, list] = defaultdict(list)
    for contract, vol_comparison in survivors:
        groups[contract.days_to_expiry].append((contract, vol_comparison))

    candidates: list[Candidate_Result] = []

    for days_to_expiry, group in groups.items():
        T = days_to_expiry / 365
        simulated_prices = simulate_terminal_prices(
            S=spot_price, T=T, annual_vol=vol_stats.annual_vol, drift=r, n_sims=n_sims,
        )

        strikes = np.array([contract.strike_price for contract, _ in group])
        is_call = np.array([contract.option_type == option_type.CALL for contract, _ in group])

        expected_payoffs = compute_batch_expected_payoffs(simulated_prices, strikes, is_call)

        for (contract, vol_comparison), expected_payoff in zip(group, expected_payoffs):
            expected_payoff = float(expected_payoff)
            expected_value = expected_payoff - contract.ask
            is_profitable = expected_value > SETTINGS.EV_PROFIT_THRESHOLD

            if not is_profitable:
                continue

            ev_per_premium = expected_value / contract.ask

            if ev_per_premium < min_ev_margin_pct:
                continue  # technically profitable but too thin a margin to bother with

            ev_result = Expected_Value_Result(
                contract_symbol=contract.contract_symbol,
                underlying_symbol=underlying_symbol,
                option_type=contract.option_type,
                strike_price=contract.strike_price,
                days_to_expiry=days_to_expiry,
                spot_price=spot_price,
                premium=contract.ask,
                annual_vol_used=vol_stats.annual_vol,
                risk_free_rate_used=r,
                simulations=n_sims,
                expected_payoff=expected_payoff,
                expected_value=expected_value,
                is_profitable=is_profitable,
            )

            candidates.append(Candidate_Result(
                contract_symbol=contract.contract_symbol,
                underlying_symbol=underlying_symbol,
                option_type=contract.option_type,
                strike_price=contract.strike_price,
                days_to_expiry=days_to_expiry,
                premium=contract.ask,
                vol_comparison=vol_comparison,
                ev_result=ev_result,
                ev_per_premium=ev_per_premium,
            ))

    candidates.sort(key=lambda c: c.ev_per_premium, reverse=True)

    logger.log(
        f"{underlying_symbol}: {len(chain)} contracts in chain, {len(survivors)} underpriced, "
        f"{len(candidates)} passed EV+margin filter (realized_vol={vol_stats.annual_vol:.1%}).",
        level="debug",
    )

    return candidates[:top_n]

# posting

def submit_option_order(order: Option_Submission, dry_run: bool | None = None) -> dict:
    """
    Submit a buy/sell order for one option contract. Respects
    SETTINGS.ENABLE_DRY_RUNNING by default — pass dry_run explicitly to
    override it (tests do this to actually exercise the mocked HTTP call).
    In dry-run mode, nothing is sent to Alpaca; the intended order is
    logged and a synthetic "dry_run" response is returned so callers
    (main.py) can treat both paths the same way.
    """
    dry_run = SETTINGS.ENABLE_DRY_RUNNING if dry_run is None else dry_run

    BASE_URL = SETTINGS.BASE_URL
    HEADERS = get_header()
    URL = f"{BASE_URL}/v2/orders"
    payload = order.model_dump(mode="json", exclude_none=True)

    logger.log(f"{'[DRY RUN] ' if dry_run else ''}Submitting order: {payload}")

    if dry_run:
        return {"status": "dry_run", "dry_run": True, "order": payload}

    response = requests.post(URL, headers=HEADERS, json=payload)
    logger.log(f"Response Status Code: {response.status_code}")
    logger.log(f"Response Body: {response.json()}")

    return response.json()
