from pydantic import BaseModel

class Settings(BaseModel):
    BASE_URL: str = "https://paper-api.alpaca.markets" # paper trading base URL
    ENABLE_DRY_RUNNING: bool = True # enable dry running for testing purposes (no trades will be executed)
    SCAN_INTERVAL_SECONDS: int = 5 # how often to re-scan the watchlist while market is open
    CLOSED_MARKET_SLEEP_SECONDS: int = 300 # check less frequently while the market's closed
    RUN_DESPITE_MARKET_CLOSED: bool = True # if True, the bot will run even when the market is closed (useful for testing)

    # implied volatility solver (see strategy/implied_volatility.py)
    RISK_FREE_RATE: float = 0.05  # annualized; adjust to current T-bill rate for more precision
    NR_MAX_ITERATIONS: int = 100
    NR_PRICE_TOLERANCE: float = 1e-6
    NR_MIN_VEGA: float = 1e-8       # below this, Newton-Raphson's derivative is treated as too unstable to trust
    SIGMA_LOWER_BOUND: float = 1e-6
    SIGMA_UPPER_BOUND: float = 5.0  # 500% annualized vol — already an extreme ceiling
    VOL_SPREAD_THRESHOLD: float = 0.05  # default overpriced/underpriced cutoff in compare_volatility()

def get_settings():
    return Settings()