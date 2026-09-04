import requests
import json
from config.settings import get_settings
from src.outbound.header import get_header
from src.outbound.models import Create_OCC_Format, OCC_Order, Option_Submission, Candidate_Result
from src.utils import logger
from src.outbound.market_data.options_chain import get_option_chain
from src.outbound.market_data.historical import get_historical_bars
from src.outbound.strategy.volatility import get_volatility_stats
from src.outbound.strategy.implied_volatility import get_implied_volatility_result, compare_volatility
from src.outbound.strategy.expected_value import get_expected_value_result

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
    """
    top_n = top_n if top_n is not None else SETTINGS.TOP_N_CANDIDATES
    min_ev_margin_pct = min_ev_margin_pct if min_ev_margin_pct is not None else SETTINGS.MIN_EV_MARGIN_PCT

    bars = get_historical_bars(underlying_symbol, lookback_days=lookback_days)
    vol_stats = get_volatility_stats(underlying_symbol, bars, lookback_days)

    chain = get_option_chain(underlying_symbol, spot_price)

    candidates: list[Candidate_Result] = []

    for contract in chain:
        if contract.ask <= 0:
            continue  # no real ask to buy at — nothing to price off of

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
            continue  # unsolvable implied vol (bad/degenerate price) — skip rather than crash the scan

        vol_comparison = compare_volatility(
            underlying_symbol=underlying_symbol,
            contract_symbol=contract.contract_symbol,
            realized_vol=vol_stats.annual_vol,
            implied_vol=iv_result.implied_vol,
        )

        if vol_comparison.verdict != "underpriced":
            continue  # only buy options the market is pricing cheap relative to realized history

        ev_result = get_expected_value_result(
            contract_symbol=contract.contract_symbol,
            underlying_symbol=underlying_symbol,
            spot_price=spot_price,
            strike_price=contract.strike_price,
            days_to_expiry=contract.days_to_expiry,
            opt_type=contract.option_type,
            premium=contract.ask,
            annual_vol=vol_stats.annual_vol,
            risk_free_rate=risk_free_rate,
        )

        if not ev_result.is_profitable:
            continue

        ev_per_premium = ev_result.expected_value / ev_result.premium

        if ev_per_premium < min_ev_margin_pct:
            continue  # technically profitable but too thin a margin to bother with

        candidates.append(Candidate_Result(
            contract_symbol=contract.contract_symbol,
            underlying_symbol=underlying_symbol,
            option_type=contract.option_type,
            strike_price=contract.strike_price,
            days_to_expiry=contract.days_to_expiry,
            premium=contract.ask,
            vol_comparison=vol_comparison,
            ev_result=ev_result,
            ev_per_premium=ev_per_premium,
        ))

    candidates.sort(key=lambda c: c.ev_per_premium, reverse=True)

    return candidates[:top_n]

# posting

def submit_option_order(Option_Submission: Option_Submission):
    BASE_URL = SETTINGS.BASE_URL
    HEADERS = get_header()
    URL = f"{BASE_URL}/v2/orders"

    logger.log(f"Submitting an order:")
    logger.log(f"\norder_symbol: {Option_Submission.order_symbol}\nqty: {Option_Submission.qty}\nside: {Option_Submission.order_symbol}\n strike_price: {Option_Submission.qty}\nstatus: {Option_Submission.order_symbol}")

    response = requests.post(
        URL,
        headers = HEADERS ,
        json = Option_Submission.model_dump(mode="json", exclude_none=True)  # Convert Pydantic model to dict, excluding None values
    )
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")
    
    return response.json()
