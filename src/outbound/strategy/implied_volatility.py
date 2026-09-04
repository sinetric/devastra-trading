"""
Black-Scholes-Merton pricing and implied volatility extraction.

The BSM *price* formula (given sigma, compute price) is closed-form. Its
*inverse* (given a market price, solve for sigma) is not — sigma appears
nonlinearly inside the normal CDF (N) in both d1 and d2 simultaneously,
and N() has no elementary closed-form inverse. So implied volatility is
solved numerically:

  1. Try Newton-Raphson first — fast (near-quadratic convergence), using
     vega (dPrice/dSigma) as the derivative, which BSM also gives in
     closed form.
  2. Fall back to Brent's method (scipy.optimize.brentq) if Newton-Raphson
     fails to converge — slower, but guaranteed to converge given a
     bracket, which makes it a safe backup for low-vega edge cases
     (deep ITM/OTM, very short time-to-expiry) where Newton-Raphson's
     derivative-based steps get unstable.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq

from src.outbound.models import (
    Implied_Volatility_Result,
    Volatility_Comparison,
    option_type,
)
from config.settings import get_settings

SETTINGS = get_settings()

DEFAULT_RISK_FREE_RATE = SETTINGS.RISK_FREE_RATE

# Newton-Raphson tuning
NR_MAX_ITERATIONS = SETTINGS.NR_MAX_ITERATIONS
NR_PRICE_TOLERANCE = SETTINGS.NR_PRICE_TOLERANCE
NR_MIN_VEGA = SETTINGS.NR_MIN_VEGA          # below this, treat the derivative as too unstable to trust
SIGMA_LOWER_BOUND = SETTINGS.SIGMA_LOWER_BOUND
SIGMA_UPPER_BOUND = SETTINGS.SIGMA_UPPER_BOUND     # 500% annualized vol — already an extreme ceiling


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float) -> tuple[float, float]:
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return d1, d2


def bsm_price(S: float, K: float, T: float, r: float, sigma: float, opt_type: option_type) -> float:
    """Closed-form Black-Scholes-Merton price for a call or put."""
    d1, d2 = _d1_d2(S, K, T, r, sigma)

    if opt_type == option_type.CALL:
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """dPrice/dSigma — same for calls and puts. Used as the Newton-Raphson derivative."""
    d1, _ = _d1_d2(S, K, T, r, sigma)
    return S * norm.pdf(d1) * np.sqrt(T)


def _initial_guess(market_price: float, S: float, T: float) -> float:
    """Brenner-Subrahmanyam approximation — a decent starting point, not the answer itself."""
    return np.sqrt(2 * np.pi / T) * (market_price / S)


def _newton_raphson_iv(
    market_price: float, S: float, K: float, T: float, r: float, opt_type: option_type
) -> float | None:
    """Attempt Newton-Raphson. Returns the converged sigma, or None if it fails to converge."""
    sigma = np.clip(_initial_guess(market_price, S, T), SIGMA_LOWER_BOUND, SIGMA_UPPER_BOUND)

    for _ in range(NR_MAX_ITERATIONS):
        price_diff = bsm_price(S, K, T, r, sigma, opt_type) - market_price

        if abs(price_diff) < NR_PRICE_TOLERANCE:
            return float(sigma)

        v = vega(S, K, T, r, sigma)
        if v < NR_MIN_VEGA:
            return None  # derivative too small/unstable to trust — hand off to the bracketing fallback

        sigma = sigma - price_diff / v
        sigma = float(np.clip(sigma, SIGMA_LOWER_BOUND, SIGMA_UPPER_BOUND))

    return None  # hit max iterations without converging


def _brentq_iv(market_price: float, S: float, K: float, T: float, r: float, opt_type: option_type) -> float:
    """Bracketing fallback — slower, but guaranteed to converge within [SIGMA_LOWER_BOUND, SIGMA_UPPER_BOUND]."""

    def objective(sigma: float) -> float:
        return bsm_price(S, K, T, r, sigma, opt_type) - market_price

    return brentq(objective, SIGMA_LOWER_BOUND, SIGMA_UPPER_BOUND, xtol=NR_PRICE_TOLERANCE)


def implied_volatility(
    market_price: float, S: float, K: float, T: float, opt_type: option_type, r: float = DEFAULT_RISK_FREE_RATE
) -> float:
    """
    Solve for implied volatility given a market option price. Tries
    Newton-Raphson first, falls back to Brent's method if it doesn't
    converge cleanly.
    """
    if T <= 0:
        raise ValueError("time to expiry must be positive (contract already expired)")
    if market_price <= 0:
        raise ValueError("market_price must be positive")

    sigma = _newton_raphson_iv(market_price, S, K, T, r, opt_type)

    if sigma is not None:
        return sigma

    return _brentq_iv(market_price, S, K, T, r, opt_type)


def get_implied_volatility_result(
    contract_symbol: str,
    underlying_symbol: str,
    market_price: float,
    S: float,
    K: float,
    days_to_expiry: int,
    opt_type: option_type,
    r: float = DEFAULT_RISK_FREE_RATE,
) -> Implied_Volatility_Result:
    T = days_to_expiry / 365
    iv = implied_volatility(market_price, S, K, T, opt_type, r)

    return Implied_Volatility_Result(
        contract_symbol=contract_symbol,
        underlying_symbol=underlying_symbol,
        strike_price=K,
        days_to_expiry=days_to_expiry,
        option_type=opt_type,
        market_price=market_price,
        implied_vol=iv,
    )


def compare_volatility(
    underlying_symbol: str,
    contract_symbol: str,
    realized_vol: float,
    implied_vol: float,
    spread_threshold: float = SETTINGS.VOL_SPREAD_THRESHOLD,
) -> Volatility_Comparison:
    """
    Compare realized (historical) vol against implied (market-priced) vol.
    spread_threshold: how large |vol_spread| must be before calling it
    over/underpriced rather than roughly fair (default 5 vol points).
    """
    spread = implied_vol - realized_vol

    if spread > spread_threshold:
        verdict = "overpriced"   # market pricing in more movement than history shows
    elif spread < -spread_threshold:
        verdict = "underpriced"  # market pricing in less movement than history shows
    else:
        verdict = "fair"

    return Volatility_Comparison(
        underlying_symbol=underlying_symbol,
        contract_symbol=contract_symbol,
        realized_vol=realized_vol,
        implied_vol=implied_vol,
        vol_spread=spread,
        verdict=verdict,
    )
