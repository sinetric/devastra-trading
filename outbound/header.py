from config.settings import get_settings

headers = {
    "accept": "application/json",
}

def get_header():
    settings = get_settings()
    headers["APCA-API-KEY-ID"] = settings.APCA_API_KEY_ID
    headers["APCA-API-SECRET-KEY"] = settings.APCA_API_SECRET_KEY
    
    return headers