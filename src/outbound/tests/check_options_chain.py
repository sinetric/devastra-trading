import json
import responses
from datetime import datetime

from src.utils.jsonParser import write_json
from src.outbound.models import parse_occ_symbol, option_type
from src.outbound.market_data.options_chain import (
    _extract_market_price,
    fetch_all_option_snapshots,
    get_option_chain,
)
from src.outbound.market_data.stocks import fetch_watchlist_snapshots

# --- 1. parse_occ_symbol() — deterministic, no network needed ---

print("Running parse_occ_symbol checks...")

occ_cases = [
    ("AAPL260918C00230000", "AAPL", datetime(2026, 9, 18), option_type.CALL, 230.0),
    ("SPY251231P00450500", "SPY", datetime(2025, 12, 31), option_type.PUT, 450.5),
    ("F260101C00010000", "F", datetime(2026, 1, 1), option_type.CALL, 10.0),
]

occ_results = []
occ_failures = 0

for symbol, exp_root, exp_date, exp_type, exp_strike in occ_cases:
    decoded = parse_occ_symbol(symbol)

    checks = {
        "root_symbol": decoded.root_symbol == exp_root,
        "expiration_date": decoded.expiration_date == exp_date,
        "option_type": decoded.option_type == exp_type,
        "strike_price": decoded.strike_price == exp_strike,
    }
    passed = all(checks.values())

    if not passed:
        occ_failures += 1
        print(f"FAIL: {symbol} -> {checks}")

    occ_results.append({
        "symbol": symbol,
        "decoded_root": decoded.root_symbol,
        "decoded_expiration": decoded.expiration_date.isoformat(),
        "decoded_type": decoded.option_type.value,
        "decoded_strike": decoded.strike_price,
        "passed": passed,
    })

# failure path — should raise ValueError, not silently return nonsense
invalid_symbols = ["NOTVALID", "aapl260918c00230000", "AAPL2609C00230000", ""]
for bad_symbol in invalid_symbols:
    try:
        parse_occ_symbol(bad_symbol)
        occ_failures += 1
        print(f"FAIL: '{bad_symbol}' should have raised ValueError but didn't")
        occ_results.append({"symbol": bad_symbol, "expected": "ValueError", "passed": False})
    except ValueError:
        occ_results.append({"symbol": bad_symbol, "expected": "ValueError", "passed": True})

print(f"parse_occ_symbol checks complete: {len(occ_results) - occ_failures}/{len(occ_results)} passed.")
write_json("check_occ_parsing_results.json", occ_results)

# --- 2. _extract_market_price() — deterministic, fake snapshot dicts ---

print("\nRunning _extract_market_price checks...")

price_cases = [
    (
        {"latestQuote": {"bp": 5.0, "ap": 5.20}, "latestTrade": {"p": 5.10}},
        5.10,  # midpoint of bid/ask
    ),
    (
        {"latestQuote": {"bp": 0, "ap": 5.20}, "latestTrade": {"p": 5.10}},
        5.10,  # no bid -> falls back to last trade
    ),
    (
        {"latestQuote": {"bp": 0, "ap": 0}, "latestTrade": {"p": 0}},
        None,  # nothing usable at all
    ),
    (
        {"latestQuote": {}, "latestTrade": {}},
        None,  # missing fields entirely
    ),
]

price_results = []
price_failures = 0

for snapshot, expected in price_cases:
    result = _extract_market_price(snapshot)
    passed = result == expected

    if not passed:
        price_failures += 1
        print(f"FAIL: snapshot={snapshot} -> got {result}, expected {expected}")

    price_results.append({
        "snapshot": snapshot,
        "result": result,
        "expected": expected,
        "passed": passed,
    })

print(f"_extract_market_price checks complete: {len(price_results) - price_failures}/{len(price_results)} passed.")
write_json("check_market_price_extraction_results.json", price_results)

# --- 3. fetch_all_option_snapshots() pagination — mocked, not a live call ---

print("\nRunning pagination check...")

DATA_BASE_URL = "https://data.alpaca.markets"
PAGINATION_URL = f"{DATA_BASE_URL}/v1beta1/options/snapshots/AAPL"

pagination_passed = False

with responses.RequestsMock() as rsps:
    rsps.add(
        responses.GET, PAGINATION_URL,
        json={"snapshots": {"CONTRACT_A": {"dummy": True}}, "next_page_token": "page2"},
        status=200,
    )
    rsps.add(
        responses.GET, PAGINATION_URL,
        json={"snapshots": {"CONTRACT_B": {"dummy": True}}, "next_page_token": None},
        status=200,
    )

    result = fetch_all_option_snapshots("AAPL")
    pagination_passed = "CONTRACT_A" in result and "CONTRACT_B" in result and len(result) == 2

    if not pagination_passed:
        print(f"FAIL: expected both CONTRACT_A and CONTRACT_B, got {list(result.keys())}")

print(f"Pagination check {'passed' if pagination_passed else 'FAILED'}.")

# --- 4. get_option_chain() — real integration test against live data ---

print("\nRunning get_option_chain live integration check (AAPL)...")

TEST_SYMBOL = "AAPL"
STRIKE_RANGE_PCT = 0.15
MAX_DAYS_TO_EXPIRY = 45

snapshots = fetch_watchlist_snapshots(symbols=[TEST_SYMBOL])
spot_price = snapshots[TEST_SYMBOL]["latestTrade"]["p"]

chain = get_option_chain(TEST_SYMBOL, spot_price)

chain_results = []
chain_failures = 0

strike_lower = spot_price * (1 - STRIKE_RANGE_PCT)
strike_upper = spot_price * (1 + STRIKE_RANGE_PCT)

for contract in chain:
    checks = {
        "strike_within_range": strike_lower <= contract.strike_price <= strike_upper,
        "days_within_range": 0 <= contract.days_to_expiry <= MAX_DAYS_TO_EXPIRY,
        "price_positive": contract.market_price > 0,
    }
    passed = all(checks.values())

    if not passed:
        chain_failures += 1
        print(f"FAIL: {contract.contract_symbol} -> {checks}")

    chain_results.append({
        "contract_symbol": contract.contract_symbol,
        "strike_price": contract.strike_price,
        "days_to_expiry": contract.days_to_expiry,
        "market_price": contract.market_price,
        "passed": passed,
    })

print(f"Spot price used: {spot_price}")
print(f"get_option_chain check complete: {len(chain_results) - chain_failures}/{len(chain_results)} contracts within expected bounds.")
write_json("check_option_chain_results.json", chain_results)
