"""
Expected-value decision layer via Monte Carlo simulation.

compare_volatility() (implied_volatility.py) tells you whether an option
LOOKS mispriced — implied vol vs. realized vol, expressed as a verdict
label. This module turns that into an actual dollar figure: simulate many
possible future stock prices using REALIZED volatility (not the market's
implied volatility) under the risk-neutral drift assumption, average the
resulting option payoff, and subtract the premium actually being charged.

Why risk-neutral drift + realized vol, not the market's own implied vol:
using the market's own risk-neutral assumptions with the market's own
implied vol would just reproduce the market's own price — that's
tautological, since that's literally what "implied vol" means (the vol
that makes BSM output the current price). Expected value computed that
way converges to ~0 before costs, no matter what. The edge only appears
when the volatility used to simulate differs from what's already priced
in: if the stock has historically moved LESS than the option's premium
assumes (realized < implied), expected value comes out negative
(overpriced); if it's moved MORE (realized > implied), expected value
comes out positive (underpriced). Same hypothesis as compare_volatility(),
expressed as a dollar number instead of a verdict.
"""

from __future__ import annotations

import numpy as np

from src.outbound.models import Expected_Value_Result, option_type as OptionType
from config.settings import get_settings

SETTINGS = get_settings()


def simulate_terminal_prices(
    S: float,
    T: float,
    annual_vol: float,
    drift: float,
    n_sims: int,
    seed: int | None = None,
) -> np.ndarray:
    """
    Simulate `n_sims` terminal stock prices at time T under GBM:
        S_T = S * exp((drift - 0.5*sigma^2)*T + sigma*sqrt(T)*Z)
    Same discretization as generateMarketData.py's synthetic bars.
    """
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n_sims)
    log_returns = (drift - 0.5 * annual_vol ** 2) * T + annual_vol * np.sqrt(T) * z
    return S * np.exp(log_returns)


def compute_expected_payoff(simulated_prices: np.ndarray, strike: float, opt_type: OptionType) -> float:
    """Average option payoff across all simulated terminal prices."""
    if opt_type == OptionType.CALL:
        payoffs = np.maximum(simulated_prices - strike, 0)
    else:
        payoffs = np.maximum(strike - simulated_prices, 0)
    return float(payoffs.mean())


def compute_batch_expected_payoffs(
    simulated_prices: np.ndarray, strikes: np.ndarray, is_call: np.ndarray
) -> np.ndarray:
    """
    Same math as compute_expected_payoff(), but for every contract that
    shares one simulated price distribution (same underlying, same
    realized vol, same days-to-expiry — i.e. same S, T, sigma) at once.

    This is the actual answer to "can the Monte Carlo runs happen
    simultaneously": not a thread or process per contract (measured to be
    net overhead here — see select_candidates()'s docstring), but one
    broadcasted numpy computation that evaluates every contract's payoff
    across all simulated paths in a single vectorized pass. That's
    genuine simultaneity (SIMD-level), not OS-scheduled concurrency, and
    it doesn't pay a thread/process setup cost per call.

    simulated_prices: (n_sims,)
    strikes, is_call: (n_contracts,) — parallel arrays, one entry per contract
    returns: (n_contracts,) mean payoff per contract
    """
    diffs = simulated_prices[:, None] - strikes[None, :]      # (n_sims, n_contracts)
    call_payoffs = np.maximum(diffs, 0)
    put_payoffs = np.maximum(-diffs, 0)
    payoffs = np.where(is_call[None, :], call_payoffs, put_payoffs)
    return payoffs.mean(axis=0)


def get_expected_value_result(
    contract_symbol: str,
    underlying_symbol: str,
    spot_price: float,
    strike_price: float,
    days_to_expiry: int,
    opt_type: OptionType,
    premium: float,
    annual_vol: float,
    n_sims: int | None = None,
    risk_free_rate: float | None = None,
    seed: int | None = None,
) -> Expected_Value_Result:
    """
    Run the full expected-value pipeline for one contract and bundle the
    result into a typed Expected_Value_Result, including the
    is_profitable flag (expected_value > SETTINGS.EV_PROFIT_THRESHOLD).

    annual_vol should be REALIZED volatility (e.g. Volatility_Stats.annual_vol
    from volatility.py) — not implied vol — see module docstring for why.
    """
    n_sims = n_sims if n_sims is not None else SETTINGS.MONTE_CARLO_SIMULATIONS
    risk_free_rate = risk_free_rate if risk_free_rate is not None else SETTINGS.RISK_FREE_RATE

    if days_to_expiry <= 0:
        raise ValueError("days_to_expiry must be positive (contract already expired)")

    T = days_to_expiry / 365

    simulated_prices = simulate_terminal_prices(
        S=spot_price, T=T, annual_vol=annual_vol, drift=risk_free_rate, n_sims=n_sims, seed=seed
    )
    expected_payoff = compute_expected_payoff(simulated_prices, strike_price, opt_type)
    expected_value = expected_payoff - premium

    return Expected_Value_Result(
        contract_symbol=contract_symbol,
        underlying_symbol=underlying_symbol,
        option_type=opt_type,
        strike_price=strike_price,
        days_to_expiry=days_to_expiry,
        spot_price=spot_price,
        premium=premium,
        annual_vol_used=annual_vol,
        risk_free_rate_used=risk_free_rate,
        simulations=n_sims,
        expected_payoff=expected_payoff,
        expected_value=expected_value,
        is_profitable=expected_value > SETTINGS.EV_PROFIT_THRESHOLD,
    )
