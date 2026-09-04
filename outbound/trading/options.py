import requests
import json
from config.settings import get_settings
from header import get_header
from models import CreateOCCFormat

SETTINGS = get_settings()

def get_option_contract_symbol(non_occ_format: CreateOCCFormat):
    BASE_URL = SETTINGS.BASE_URL
    headers = get_header()
    url = f"{BASE_URL}/v2/options/contracts"

    response = requests.get(
        url,
        headers = headers,
        params = {
            "underlying_symbols": non_occ_format.root_symbol,  # e.g., AAPL
            "expiration_date": non_occ_format.expr_date,   # optional filter
            "type": non_occ_format.option_type,                     # call or put
            "strike_price_gte": non_occ_format.strike_price_gte,
            "strike_price_lte": non_occ_format.strike_price_lte,
            "status": non_occ_format.status,
        }
    )

    return response
