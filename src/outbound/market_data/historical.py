"""
Historical daily bars, cached locally as Parquet files per symbol.

Unlike the snapshot cache in stocks.py (which is time-based, since live
prices change every second), this is an incremental/append cache: once a
trading day closes, its bar never changes, so we only ever fetch the delta
since the last cached date instead of re-pulling the whole history.
"""

from __future__ import annotations

import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

from src.outbound.header import get_header
from src.utils import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CACHE_DIR = PROJECT_ROOT / "data" / "historical"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DATA_BASE_URL = "https://data.alpaca.markets"


def _cache_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}.parquet"


def _load_cache(symbol: str) -> pd.DataFrame | None:
    path = _cache_path(symbol)
    if path.exists():
        return pd.read_parquet(path)
    return None


def _save_cache(symbol: str, df: pd.DataFrame) -> None:
    df.to_parquet(_cache_path(symbol))


def _fetch_bars_from_api(symbol: str, start: str, end: str, timeframe: str = "1Day") -> pd.DataFrame:
    """Pull daily bars for `symbol` between `start` and `end` (YYYY-MM-DD) from Alpaca."""
    url = f"{DATA_BASE_URL}/v2/stocks/{symbol}/bars"

    response = requests.get(
        url,
        headers=get_header(),
        params={
            "timeframe": timeframe,
            "start": start,
            "end": end,
            "feed": "iex",  # free-plan-safe feed
        },
    )
    response.raise_for_status()

    bars = response.json().get("bars", [])
    df = pd.DataFrame(bars)

    if not df.empty:
        df["t"] = pd.to_datetime(df["t"])
        df = df.set_index("t")

    return df


def get_historical_bars(symbol: str, lookback_days: int = 730) -> pd.DataFrame:
    """
    Return `lookback_days` of daily bars for `symbol`.

    Uses a local Parquet cache under data/historical/<symbol>.parquet.
    On a cache hit, only fetches bars newer than the last cached date
    (or nothing at all, if already up to date) instead of refetching
    the whole lookback window every call.
    """
    today = datetime.utcnow().date()
    lookback_start = today - timedelta(days=lookback_days)

    cached = _load_cache(symbol)

    if cached is None or cached.empty:
        logger.log(f"No cache for {symbol}, fetching full history ({lookback_days}d).")
        df = _fetch_bars_from_api(symbol, start=lookback_start.isoformat(), end=today.isoformat())
        _save_cache(symbol, df)
        return df

    last_cached_date = cached.index.max().date()

    if last_cached_date >= today:
        return cached  # already up to date, nothing to fetch

    logger.log(f"Fetching new bars for {symbol} since {last_cached_date}.")
    new_data = _fetch_bars_from_api(
        symbol,
        start=(last_cached_date + timedelta(days=1)).isoformat(),
        end=today.isoformat(),
    )

    if new_data.empty:
        return cached

    combined = pd.concat([cached, new_data])
    combined = combined[~combined.index.duplicated(keep="last")]  # de-dupe any overlapping day
    combined = combined.sort_index()
    _save_cache(symbol, combined)

    return combined
