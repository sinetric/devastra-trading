import requests
import time
import json
from typing import Optional
from src.utils.jsonParser import create_json_file, parse_json_file
from src.outbound.header import get_header
from src.outbound.market_data.watchlist import WATCHLIST

DATA_BASE_URL = "https://data.alpaca.markets"
SNAPSHOT_BATCH_SIZE = 100        # symbols per request — keeps query string/payload reasonable
REQUEST_DELAY_SECONDS = 0.35     # free plan allows 200 req/min (~0.3s apart); small pad for safety


def fetch_top_market_movers(dump_to_json, json_file_path):
    """
    NOTE: requires a paid Algo Trader Plus (SIP feed) subscription — will
    return an empty body / JSONDecodeError on the free plan. Kept here for
    reference / for later once the account is upgraded. Use
    fetch_watchlist_snapshots() + rank_movers() below in the meantime.
    """
    url = "https://data.alpaca.markets/v1beta1/screener/stocks/movers?top=10"
    headers = get_header()

    response = requests.get(url, headers=headers)

    if (dump_to_json and json_file_path):
        create_json_file(json_file_path, response)  # Create a JSON file with the response data

    return response.json()  # Return the JSON response directly


def _chunk_symbols(symbols: list[str], size: int):
    """Yield successive `size`-length slices of `symbols`."""
    for i in range(0, len(symbols), size):
        yield symbols[i:i + size]


def fetch_watchlist_snapshots(
    symbols: Optional[list[str]] = None,
    feed: str = "iex",
    dump_to_json: bool = False,
    json_file_path: Optional[str] = None,
) -> dict:
    """
    Fetch latest snapshots (latest trade, latest quote, daily bar, previous
    daily bar) for a list of symbols, batched to stay within request-size
    and rate limits. Free-plan-safe: defaults to the IEX feed and to our
    hardcoded WATCHLIST if no symbols are passed.

    Returns a dict keyed by symbol, e.g. {"AAPL": {...}, "MSFT": {...}}.
    """
    symbols = symbols or WATCHLIST
    headers = get_header()
    url = f"{DATA_BASE_URL}/v2/stocks/snapshots"
    
    all_snapshots: dict = {}
    batches = list(_chunk_symbols(symbols, SNAPSHOT_BATCH_SIZE))

    for i, batch in enumerate(batches):
        response = requests.get(
            url,
            headers=headers,
            params={
                "symbols": ",".join(batch),
                "feed": feed,
            },
        )
        response.raise_for_status()  # fail loudly on a bad batch instead of silently dropping it

        all_snapshots.update(response.json())

        # stay under the free plan's 200 requests/minute limit when there's more to fetch
        if i < len(batches) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)

    print(response.url)

    if dump_to_json and json_file_path:
        with open(json_file_path, "w") as f:
            json.dump(all_snapshots, f)

    return all_snapshots


def rank_movers(snapshots: dict, top_n: int = 10) -> list[dict]:
    """
    Given snapshot data keyed by symbol (as returned by
    fetch_watchlist_snapshots), compute % change from the previous close
    and return the top N movers by absolute % change, largest first.
    """
    movers = []

    for symbol, snap in snapshots.items():
        try:
            latest_price = snap["latestTrade"]["p"]
            prev_close = snap["prevDailyBar"]["c"]
            volume = snap["dailyBar"]["v"]
        except (KeyError, TypeError):
            continue  # incomplete data for this symbol — skip it, don't crash the whole batch

        if not prev_close:
            continue

        pct_change = (latest_price - prev_close) / prev_close
        movers.append({
            "symbol": symbol,
            "price": latest_price,
            "pct_change": round(pct_change * 100, 2),
            "volume": volume,
        })

    movers.sort(key=lambda m: abs(m["pct_change"]), reverse=True)
    return movers[:top_n]
