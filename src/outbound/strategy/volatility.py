"""
Historical volatility and drift estimation from cached daily bars.

Reasoning recap (see conversation for the full breakdown):
  1. Daily log returns: log_return[t] = ln(close[t] / close[t-1])
  2. Daily volatility: std dev of those log returns
  3. Annualized volatility: daily_vol * sqrt(252)  (252 trading days/year;
     std dev scales by sqrt(time) since variance adds linearly across
     independent days)
  4. Drift: mean log return, annualized the same way — the "naive"
     historical baseline. Swap in 0.0 for the risk-neutral assumption, or
     a signal-derived estimate (momentum, moving averages, etc.) once
     that logic exists — see drift_override on get_volatility_stats().
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.outbound.models import Volatility_Stats

TRADING_DAYS_PER_YEAR = 252


def compute_log_returns(bars: pd.DataFrame) -> pd.Series:
    """
    Daily log returns from a bars DataFrame's `close` column.
    Drops the first row (no prior close to compare against).
    """
    if "close" not in bars.columns:
        raise ValueError("bars DataFrame must have a 'close' column")

    log_returns = np.log(bars["close"] / bars["close"].shift(1))
    return log_returns.dropna()


def compute_historical_volatility(bars: pd.DataFrame) -> float:
    """
    Annualized historical volatility: std dev of daily log returns,
    scaled by sqrt(TRADING_DAYS_PER_YEAR).
    """
    log_returns = compute_log_returns(bars)

    if log_returns.empty:
        raise ValueError("not enough data to compute volatility (need at least 2 bars)")

    daily_vol = log_returns.std()
    return float(daily_vol * np.sqrt(TRADING_DAYS_PER_YEAR))


def estimate_historical_drift(bars: pd.DataFrame) -> float:
    """
    Naive annualized drift: mean daily log return, annualized.

    This assumes "the future looks like the historical average" — a weak
    signal on its own (short-window average return is noisy), but a
    reasonable placeholder until replaced with a deliberate signal-derived
    estimate.
    """
    log_returns = compute_log_returns(bars)

    if log_returns.empty:
        raise ValueError("not enough data to estimate drift (need at least 2 bars)")

    daily_drift = log_returns.mean()
    return float(daily_drift * TRADING_DAYS_PER_YEAR)


def get_volatility_stats(
    symbol: str,
    bars: pd.DataFrame,
    lookback_days: int,
    drift_override: float | None = None,
) -> Volatility_Stats:
    """
    Bundle volatility + drift for `symbol` into a typed Volatility_Stats
    result.

    drift_override: pass 0.0 for the risk-neutral assumption, or a
    signal-derived value, instead of the naive historical mean-return
    drift computed by default.
    """
    log_returns = compute_log_returns(bars)

    if log_returns.empty:
        raise ValueError(f"not enough bar data for {symbol} to compute volatility stats")

    daily_vol = float(log_returns.std())
    annual_vol = daily_vol * np.sqrt(TRADING_DAYS_PER_YEAR)

    annual_drift = (
        drift_override if drift_override is not None
        else float(log_returns.mean()) * TRADING_DAYS_PER_YEAR
    )

    return Volatility_Stats(
        symbol=symbol,
        lookback_days=lookback_days,
        daily_vol=daily_vol,
        annual_vol=annual_vol,
        annual_drift=annual_drift,
    )
