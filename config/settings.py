from pydantic import BaseModel

class Settings(BaseModel):
    BASE_URL: str

def get_settings():
    return Settings(
        BASE_URL="https://paper-api.alpaca.markets", # paper trading base URL
    )