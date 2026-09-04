import numpy as np
import pandas as pd
from datetime import datetime

def generate_synthetic_bars(
    start_price: float = 100.0,
    true_annual_vol: float = 0.30,
    true_annual_drift: float = 0.05,
    num_days: int = 252,
    seed: int | None = 42,
) -> pd.DataFrame:
    """
    Synthetic daily close prices following GBM with a known volatility and
    drift — for testing volatility.py against values we already know are
    correct, since real market data has no "known correct" answer to check against.
    """
    rng = np.random.default_rng(seed)   # seeded = reproducible runs

    dt = 1 / 252  # one trading day, as a fraction of a year

    # standard GBM discretization:
    #   log_return = (mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z
    daily_mean = (true_annual_drift - 0.5 * true_annual_vol ** 2) * dt
    daily_std = true_annual_vol * np.sqrt(dt)

    z = rng.standard_normal(num_days)
    log_returns = daily_mean + daily_std * z

    log_prices = np.log(start_price) + np.cumsum(log_returns)
    closes = np.exp(log_prices)

    dates = pd.date_range(end=datetime.utcnow().date(), periods=num_days, freq="B")  # business days
    bars = pd.DataFrame({"close": closes}, index=dates)
    bars.index.name = "t"

    return bars