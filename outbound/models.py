from pydantic import BaseModel
from enum import Enum

# defining enums

class order_type(Enum):
    """
    market — fill immediately at best available price. Risky on options since spreads can be wide; no limit_price needed.
    limit — only fills at your limit_price or better. Requires limit_price.
    stop — becomes a market order once the contract trades at/through stop_price. Requires stop_price. Only valid for single-leg option orders (not multi-leg/spreads).
    stop_limit — becomes a limit order once stop_price is hit. Requires both stop_price and limit_price.
    [Claude-Generated explanation]
    """

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class order_side(Enum):
    """
    buy — submit a buy order.
    sell — submit a sell order.
    """
    BUY = "buy"
    SELL = "sell"

class option_type(Enum):
    """
    call — a call option gives the holder the right to buy the underlying asset.
    put — a put option gives the holder the right to sell the underlying asset.
    """
    CALL = "call"
    PUT = "put"

class option_status(Enum):
    """
    active — the option is currently active and can be traded.
    inactive — the option is not currently active but may become active in the future.
    expired — the option has expired and can no longer be traded.
    """
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"

class OCC_Order(BaseModel):
    order_symbol: str

class Option_Submission(BaseModel):
    order_symbol: str
    qty: int
    side: str
    strike_price: float
    status: option_status

# BaseModel definitions

class Create_OCC_Format(BaseModel):
    root_symbol: str
    expr_date: str
    option_type: option_type
    strike_price_gte: float
    strike_price_lte: float
    status: option_status