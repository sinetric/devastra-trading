from config.settings import get_settings
from dotenv import load_dotenv
import os

load_dotenv()

headers = {
    "accept": "application/json",
    "APCA-API-KEY-ID": os.getenv("APCA_API_KEY_ID"),
    "APCA-API-SECRET-KEY": os.getenv("APCA_API_SECRET_KEY")
}

def get_header():
    return headers