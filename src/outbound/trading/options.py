import requests
import json
from config.settings import get_settings
from src.outbound.header import get_header
from src.outbound.models import Create_OCC_Format, OCC_Order, Option_Submission
from src.utils import logger

SETTINGS = get_settings()

# fetching

def get_option_contract_symbol(non_occ_format: Create_OCC_Format) -> OCC_Order:
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
    contracts = response.json()["option_contracts"]
    symbol: OCC_Order = contracts[0]["symbol"]   # e.g. "AAPL260918C00230000"

    return symbol

# posting

def submit_option_order(Option_Submission: Option_Submission):
    BASE_URL = SETTINGS.BASE_URL
    HEADERS = get_header()
    URL = f"{BASE_URL}/v2/orders"

    logger.log(f"Submitting an order:")
    logger.log(f"\norder_symbol: {Option_Submission.order_symbol}\nqty: {Option_Submission.qty}\nside: {Option_Submission.order_symbol}\n strike_price: {Option_Submission.qty}\nstatus: {Option_Submission.order_symbol}")

    response = requests.post(
        URL,
        headers = HEADERS ,
        json = Option_Submission.model_dump(mode="json", exclude_none=True)  # Convert Pydantic model to dict, excluding None values
    )
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")
    
    return response.json()
