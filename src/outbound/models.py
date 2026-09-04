from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import List

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
# historical data results

class Historical_Bar(BaseModel):
    """
    One OHLCV bar as returned by Alpaca's /v2/stocks/{symbol}/bars endpoint.
    Field names are expanded from Alpaca's short JSON keys (t, o, h, l, c, v, n, vw)
    for readability. `populate_by_name` lets this be built either from the raw
    API response (via alias) or from expanded keyword arguments in our own code.
    """
    timestamp: datetime = Field(alias="t")
    open: float = Field(alias="o")
    high: float = Field(alias="h")
    low: float = Field(alias="l")
    close: float = Field(alias="c")
    volume: int = Field(alias="v")
    trade_count: int = Field(alias="n")
    vwap: float = Field(alias="vw")

    model_config = {
        "populate_by_name": True,
    }

class Historical_Bars_Result(BaseModel):
    """
    Typed wrapper around a symbol's historical bar series, as fetched/cached
    by market_data/historical.py. Internally that module works with a pandas
    DataFrame for the actual date-indexed numeric computation (log returns,
    rolling stats, etc.) — this model is the typed boundary for passing the
    result around the rest of the codebase (logging, API responses, tests),
    not a replacement for the DataFrame used during computation.
    """
    symbol: str
    lookback_days: int
    bars: List[Historical_Bar]

class Volatility_Stats(BaseModel):
    """
    Annualized volatility + drift for a symbol, derived from historical
    daily bars. See market_data volatility logic for how each field is
    computed.
    """
    symbol: str
    lookback_days: int
    daily_vol: float
    annual_vol: float
    annual_drift: float

class Implied_Volatility_Result(BaseModel):
    """Implied volatility backed out from a single option contract's market price via BSM inversion."""
    contract_symbol: str
    underlying_symbol: str
    strike_price: float
    days_to_expiry: int
    option_type: option_type
    market_price: float
    implied_vol: float

class Volatility_Comparison(BaseModel):
    """
    Realized (historical) vol vs. implied (market-priced) vol for a contract —
    the actual edge signal: a large positive spread means the option is priced
    for more movement than the stock has historically shown (looks expensive
    relative to history); negative means it looks cheap.
    """
    underlying_symbol: str
    contract_symbol: str
    realized_vol: float
    implied_vol: float
    vol_spread: float
    verdict: str
