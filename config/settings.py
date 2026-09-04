from pydantic import BaseModel

class Settings(BaseModel):
    BASE_URL: str = "https://paper-api.alpaca.markets" # paper trading base URL
    ENABLE_DRY_RUNNING: bool = True # enable dry running for testing purposes (no trades will be executed)

def get_settings():
    return Settings()