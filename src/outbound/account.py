"""
Account-level info from Alpaca — currently just equity/cash/buying power,
which is all strategy/position_sizing.py needs to size a trade against
real (paper) account capital instead of a hardcoded quantity.
"""

import requests

from config.settings import get_settings
from src.outbound.header import get_header
from src.outbound.models import Account_Snapshot

SETTINGS = get_settings()


def get_account() -> Account_Snapshot:
    """
    GET /v2/account. Alpaca returns equity/cash/buying_power as strings —
    converted to float here so callers get real numbers.
    """
    BASE_URL = SETTINGS.BASE_URL
    response = requests.get(f"{BASE_URL}/v2/account", headers=get_header())
    response.raise_for_status()
    data = response.json()

    return Account_Snapshot(
        equity=float(data["equity"]),
        cash=float(data["cash"]),
        buying_power=float(data["buying_power"]),
    )
