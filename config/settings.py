from pydantic import BaseModel

class Settings(BaseModel):
    BASE_URL: str = "https://paper-api.alpaca.markets" # paper trading base URL
    ENABLE_DRY_RUNNING: bool = True # enable dry running for testing purposes (no trades will be executed)
    SCAN_INTERVAL_SECONDS: int = 5 # how often to re-scan the watchlist while market is open
    CLOSED_MARKET_SLEEP_SECONDS: int = 300 # check less frequently while the market's closed
    RUN_DESPITE_MARKET_CLOSED: bool = True # if True, the bot will run even when the market is closed (useful for testing)

def get_settings():
    return Settings()