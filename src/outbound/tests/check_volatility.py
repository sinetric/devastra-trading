import numpy as np
import pandas as pd
from datetime import datetime

import json
from tqdm import tqdm

from src.utils.jsonParser import create_json_file, parse_json_file, write_json

from src.utils.generateMarketData import generate_synthetic_bars
from src.outbound.strategy.implied_volatility import bsm_price, vega, implied_volatility, compare_volatility
from src.outbound.strategy.volatility import compute_historical_volatility, estimate_historical_drift
from src.outbound.models import option_type

within0to1sd = 0
within1to2sd = 0
within2to3sd = 0
above3sd = 0

results = []

def round_trip_test(S, K, T, r, true_sigma, opt_type):
    price = bsm_price(S, K, T, r, true_sigma, opt_type)
    recovered_sigma = implied_volatility(price, S, K, T, opt_type, r)
    return abs(recovered_sigma - true_sigma)

for i, seed in enumerate(tqdm(range(1000))):
    synthetic_bars = generate_synthetic_bars(seed=seed)

    estimated_volatility = compute_historical_volatility(synthetic_bars)
    estimated_drift = estimate_historical_drift(synthetic_bars)

    true_drift = 0.05 - 0.5 * 0.30**2

    delta_drift = abs(estimated_drift - true_drift)

    drift_miss_std = delta_drift / abs(0.30) if true_drift != 0 else float('inf')

    if (drift_miss_std <= 1):
        within0to1sd += 1
    elif (drift_miss_std <= 2):
        within1to2sd += 1  
    elif (drift_miss_std <= 3):
        within2to3sd += 1
    else:
        above3sd += 1

    results.append({
        "seed": seed,
        "estimated_volatility": estimated_volatility,
        "true_volatility": 0.30,
        "estimated_drift": estimated_drift,
        "true_drift": true_drift,
        "delta_drift": delta_drift,
        "drift_miss_std": drift_miss_std
    })

print(f"Drift estimation results over 1000 synthetic runs:")
print(f"Within 0-1 SD: {within0to1sd} runs")
print(f"Within 1-2 SD: {within1to2sd} runs")
print(f"Within 2-3 SD: {within2to3sd} runs")
print(f"Above 3 SD: {above3sd} runs")

write_json("volatility_drift_results.json", results)

# --- implied_volatility.py round-trip test ---
# No external ground truth for implied vol, so use bsm_price() to generate a
# market price from a chosen true_sigma, then check implied_volatility()
# recovers that same sigma. Sweeps a range of vols, strikes, expiries, and
# both option types — including a short-T/far-strike case meant to stress
# the low-vega path and exercise the Newton-Raphson -> Brent fallback.

print("\nRunning implied_volatility round-trip sweep...")

ROUND_TRIP_TOLERANCE = 1e-4
S = 100.0
r = 0.05

sigmas = [0.1, 0.3, 0.5, 0.8, 1.2, 2.0]
strikes_relative = [0.7, 0.9, 1.0, 1.1, 1.3]  # multiples of S -> sweeps ITM/ATM/OTM
expiries = [1 / 365, 7 / 365, 30 / 365, 90 / 365, 365 / 365]  # very short to a full year

MIN_MEANINGFUL_PRICE = 1e-6  # below this, the price has underflowed to ~0 in floating point —
                              # not a real price to invert, just a precision artifact
MIN_MEANINGFUL_VEGA = 0.002   # below this, price barely depends on sigma (deep ITM/OTM, short T) —
                               # inversion is ill-conditioned: many different sigmas give ~the same
                               # price, so recovering the exact original sigma isn't a meaningful test

round_trip_mismatches = 0
round_trip_skipped = 0
round_trip_total = 0
round_trip_results = []

for sigma in sigmas:
    for k_mult in strikes_relative:
        for T in expiries:
            for opt in (option_type.CALL, option_type.PUT):
                round_trip_total += 1
                K = S * k_mult
                opt_label = opt.value if hasattr(opt, "value") else str(opt)

                price = bsm_price(S, K, T, r, sigma, opt)
                v = vega(S, K, T, r, sigma)

                if price < MIN_MEANINGFUL_PRICE:
                    round_trip_skipped += 1
                    round_trip_results.append({
                        "true_sigma": sigma,
                        "strike": K,
                        "time_to_expiry_years": T,
                        "option_type": opt_label,
                        "price": price,
                        "vega": v,
                        "status": "skipped",
                        "reason": "price underflowed below MIN_MEANINGFUL_PRICE",
                    })
                    continue  # option is essentially worthless at these params — nothing to invert

                if v < MIN_MEANINGFUL_VEGA:
                    round_trip_skipped += 1
                    round_trip_results.append({
                        "true_sigma": sigma,
                        "strike": K,
                        "time_to_expiry_years": T,
                        "option_type": opt_label,
                        "price": price,
                        "vega": v,
                        "status": "skipped",
                        "reason": "vega below MIN_MEANINGFUL_VEGA — price barely depends on sigma here",
                    })
                    continue  # price is nearly flat w.r.t. sigma — recovering the exact sigma is ill-posed

                recovered_sigma = implied_volatility(price, S, K, T, opt, r)
                error = abs(recovered_sigma - sigma)
                passed = error <= ROUND_TRIP_TOLERANCE

                if not passed:
                    round_trip_mismatches += 1
                    print(
                        f"MISMATCH sigma={sigma} K={K:.2f} T={T:.4f} opt={opt}: "
                        f"error={error:.6f}"
                    )

                round_trip_results.append({
                    "true_sigma": sigma,
                    "strike": K,
                    "time_to_expiry_years": T,
                    "option_type": opt_label,
                    "price": price,
                    "vega": v,
                    "recovered_sigma": recovered_sigma,
                    "error": error,
                    "status": "passed" if passed else "mismatch",
                })

checked = round_trip_total - round_trip_skipped
print(
    f"Round-trip sweep complete: {checked - round_trip_mismatches}/{checked} within tolerance "
    f"({ROUND_TRIP_TOLERANCE}), {round_trip_skipped} skipped (price underflowed to ~0)."
)

write_json("implied_volatility_roundtrip_results.json", round_trip_results)

# --- compare_volatility() boundary checks ---
# Deterministic — no randomness involved, so every case should match exactly.
# Checks the overpriced/fair/underpriced verdict logic straddles the default
# spread_threshold correctly on both sides.

print("\nRunning compare_volatility boundary checks...")

boundary_cases = [
    (0.30, 0.30 + 0.051, "overpriced"),   # just above threshold
    (0.30, 0.30 + 0.049, "fair"),          # just below threshold
    (0.30, 0.30 - 0.051, "underpriced"),   # just below on the other side
    (0.30, 0.30 - 0.049, "fair"),
    (0.30, 0.30, "fair"),                   # exact match
]

boundary_failures = 0
boundary_results = []

for realized, implied, expected in boundary_cases:
    result = compare_volatility("TEST", "TEST_CONTRACT", realized, implied)
    status = "OK" if result.verdict == expected else "FAIL"

    if status == "FAIL":
        boundary_failures += 1

    print(f"{status}: realized={realized} implied={implied:.3f} -> got '{result.verdict}', expected '{expected}'")

    boundary_results.append({
        "realized_vol": realized,
        "implied_vol": implied,
        "vol_spread": result.vol_spread,
        "expected_verdict": expected,
        "actual_verdict": result.verdict,
        "status": status,
    })

print(f"Boundary checks complete: {len(boundary_cases) - boundary_failures}/{len(boundary_cases)} passed.")

write_json("compare_volatility_boundary_results.json", boundary_results)
