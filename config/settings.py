from pydantic import BaseModel

class Settings(BaseModel):
    APCA_API_KEY_ID: str
    APCA_API_SECRET_KEY: str

def get_settings():
    return Settings(
        
    )