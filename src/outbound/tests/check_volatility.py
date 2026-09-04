import numpy as np
import pandas as pd
from datetime import datetime

import json
from tqdm import tqdm

from src.utils.jsonParser import create_json_file, parse_json_file, write_json

from src.utils.generateMarketData import generate_synthetic_bars
from src.outbound.strategy.implied_volatility import implied_volatility
from src.outbound.strategy.volatility import compute_historical_volatility, estimate_historical_drift

within0to1sd = 0
within1to2sd = 0
within2to3sd = 0
above3sd = 0

results = []

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
