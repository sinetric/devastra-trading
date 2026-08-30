from pydantic import BaseModel

class Settings(BaseModel):
    APCA_API_KEY_ID: str
    APCA_API_SECRET_KEY: str

def get_settings():
    return Settings(
        APCA_API_KEY_ID="PKDAEDLCFQZDZDVVD75HVL7VSY", # temporary hardcoded value, consider using environment variables or a secure vault for production
        APCA_API_SECRET_KEY="DbGHrFbLK7CUL7qUY78zHeQiop51tb72Tj8fTNxWmm9d"
    )