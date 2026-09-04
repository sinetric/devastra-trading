"""
Option chain fetching + market pricing.

Three things the volatility-comparison pipeline needs that nothing else in
the codebase provides yet:
  1. Decoding an OCC contract symbol (e.g. "AAPL260918C00230000") into its
     underlying, expiration, type, and strike — so we don't need a second
     API round-trip just to know what a contract *is*.
  2. Paging through /v1beta1/options/snapshots/{symbol} fully — it returns
     at most 100 contracts per call with a next_page_token, so a single
     unpaginated call silently truncates the chain.
  3. Picking a usable "market price" per contract — quote midpoint when
     both sides of the book exist, falling back to the last trade price
     for thin contracts with a one-sided or empty quote (common on the
     free indicative feed).
"""

from __future__ import annotations

import requests
from datetime import datetime

from src.outbound.header import get_header
from src.outbound.models import Option_Chain_Contract, parse_occ_symbol
from config.settings import get_settings

SETTINGS = get_settings()

DATA_BASE_URL = "https://data.alpaca.markets"


def _extract_market_price(snapshot: dict) -> float | None:
    """
    Prefer the quote midpoint (bid+ask)/2 when both sides exist — it's a
    better live estimate than a possibly-stale last trade. Falls back to
    latestTrade for thin/one-sided-quote contracts. Returns None if
    neither is usable.
    """
    quote = snapshot.get("latestQuote", {})
    bid, ask = quote.get("bp", 0), quote.get("ap", 0)

    if bid > 0 and ask > 0:
        return (bid + ask) / 2

    trade = snapshot.get("latestTrade", {})
    trade_price = trade.get("p", 0)
    if trade_price > 0:
        return trade_price

    return None


def extract_bid_price(snapshot: dict) -> float | None:
    """
    The price we'd actually receive selling right now — the bid, not the
    ask (that's the buy-side cost) and not the midpoint (optimistic for a
    sell). Falls back to the last trade price if there's no live bid.
    Used by main.py's exit scan to price open positions realistically.
    """
    quote = snapshot.get("latestQuote", {})
    bid = quote.get("bp", 0)
    if bid > 0:
        return bid

    trade = snapshot.get("latestTrade", {})
    trade_price = trade.get("p", 0)
    if trade_price > 0:
        return trade_price

    return None


def fetch_all_option_snapshots(underlying_symbol: str, feed: str | None = None) -> dict:
    """
    Fetch every contract snapshot for `underlying_symbol`, following
    next_page_token until exhausted. Returns the raw {contract_symbol: snapshot}
    dict as the API provides it.
    """
    feed = feed or SETTINGS.OPTIONS_DATA_FEED
    url = f"{DATA_BASE_URL}/v1beta1/options/snapshots/{underlying_symbol}"
    headers = get_header()

    all_snapshots: dict = {}
    page_token = None

    while True:
        params = {"feed": feed}
        if page_token:
            params["page_token"] = page_token

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        all_snapshots.update(data.get("snapshots", {}))

        page_token = data.get("next_page_token")
        if not page_token:
            break

    return all_snapshots


def get_option_chain(
    underlying_symbol: str,
    spot_price: float,
    max_days_to_expiry: int | None = None,
    strike_range_pct: float | None = None,
    feed: str | None = None,
) -> list[Option_Chain_Contract]:
    """
    Full pipeline: fetch every contract for `underlying_symbol`, decode
    each OCC symbol, extract a usable market price, and filter down to
    near-the-money / near-term contracts — the ones actually relevant to
    the strategy, out of what can be hundreds of listed contracts.
    """
    max_days_to_expiry = max_days_to_expiry if max_days_to_expiry is not None else SETTINGS.MAX_DAYS_TO_EXPIRY
    strike_range_pct = strike_range_pct if strike_range_pct is not None else SETTINGS.STRIKE_RANGE_PCT

    strike_lower = spot_price * (1 - strike_range_pct)
    strike_upper = spot_price * (1 + strike_range_pct)

    today = datetime.utcnow()
    raw_snapshots = fetch_all_option_snapshots(underlying_symbol, feed=feed)

    contracts: list[Option_Chain_Contract] = []

    for contract_symbol, snapshot in raw_snapshots.items():
        try:
            decoded = parse_occ_symbol(contract_symbol)
        except ValueError:
            continue  # skip anything that doesn't parse as a standard OCC symbol

        if not (strike_lower <= decoded.strike_price <= strike_upper):
            continue

        days_to_expiry = (decoded.expiration_date - today).days
        if days_to_expiry < 0 or days_to_expiry > max_days_to_expiry:
            continue

        market_price = _extract_market_price(snapshot)
        if market_price is None:
            continue  # no usable price (no quote, no trade) — nothing to invert

        quote = snapshot.get("latestQuote", {})

        contracts.append(Option_Chain_Contract(
            contract_symbol=contract_symbol,
            underlying_symbol=underlying_symbol,
            strike_price=decoded.strike_price,
            expiration_date=decoded.expiration_date,
            days_to_expiry=days_to_expiry,
            option_type=decoded.option_type,
            market_price=market_price,
            bid=quote.get("bp", 0),
            ask=quote.get("ap", 0),
        ))

    return contracts

