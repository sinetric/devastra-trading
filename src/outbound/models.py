from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import List
import re

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
    """
    Shape actually required by Alpaca's POST /v2/orders. (Previous version
    of this model used `order_symbol`/a bare `side: str`/a stray `status`
    field that don't match Alpaca's order schema at all — fixed here since
    main.py now submits real orders off of this model.)
    """
    symbol: str
    qty: int
    side: order_side
    type: order_type = order_type.MARKET
    time_in_force: str = "day"
    limit_price: float | None = None

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

class Option_Chain_Contract(BaseModel):
    """
    One tradable option contract, decoded from its OCC symbol and paired
    with a usable market price for implied-vol inversion. Produced by
    market_data/options_chain.py.
    """
    contract_symbol: str
    underlying_symbol: str
    strike_price: float
    expiration_date: datetime
    days_to_expiry: int
    option_type: option_type
    market_price: float
    bid: float
    ask: float

class Decoded_OCC_Symbol(BaseModel):
    """
    A single option contract's identity, decoded directly from its OCC
    symbol (e.g. "AAPL260918C00230000") — not a search filter like
    Create_OCC_Format, an exact single-contract result.
    """
    contract_symbol: str
    root_symbol: str
    expiration_date: datetime
    option_type: option_type
    strike_price: float

# OCC symbol format: <root symbol><YYMMDD><C|P><strike * 1000, zero-padded to 8 digits>
_OCC_PATTERN = re.compile(r"^([A-Z]+)(\d{6})([CP])(\d{8})$")

def parse_occ_symbol(contract_symbol: str) -> Decoded_OCC_Symbol:
    """
    Decode an OCC contract symbol into its components. Raises ValueError
    if the symbol doesn't match the expected format.
    """
    match = _OCC_PATTERN.match(contract_symbol)
    if not match:
        raise ValueError(f"'{contract_symbol}' doesn't look like a valid OCC option symbol")

    root_symbol, date_str, type_char, strike_raw = match.groups()

    return Decoded_OCC_Symbol(
        contract_symbol=contract_symbol,
        root_symbol=root_symbol,
        expiration_date=datetime.strptime(date_str, "%y%m%d"),
        option_type=option_type.CALL if type_char == "C" else option_type.PUT,
        strike_price=int(strike_raw) / 1000.0,
    )

class Expected_Value_Result(BaseModel):
    """
    Monte Carlo expected value for a single contract — simulates future
    stock prices using realized (not implied) volatility under a
    risk-neutral drift, averages the resulting option payoff, and compares
    it against the actual premium. See strategy/expected_value.py for why
    that combination (not implied vol) is what makes this a real edge
    signal instead of just reproducing the market's own price.
    """
    contract_symbol: str
    underlying_symbol: str
    option_type: option_type
    strike_price: float
    days_to_expiry: int
    spot_price: float
    premium: float
    annual_vol_used: float
    risk_free_rate_used: float
    simulations: int
    expected_payoff: float
    expected_value: float
    is_profitable: bool

class Position(BaseModel):
    """
    An open options position — the minimal shape exit_strategy.py needs to
    evaluate whether to close it. How positions get created/stored/removed
    (the ledger) is separate from this decision logic.
    """
    contract_symbol: str
    underlying_symbol: str
    option_type: option_type
    strike_price: float
    expiration_date: datetime
    qty: int
    entry_premium: float
    entry_date: datetime

class Account_Snapshot(BaseModel):
    """
    Minimal slice of Alpaca's GET /v2/account response — just what
    strategy/position_sizing.py needs to size a trade. Alpaca returns
    these as strings; account.py converts them to float when building
    this model.
    """
    equity: float
    cash: float
    buying_power: float


class Exit_Decision(BaseModel):
    """
    Result of evaluating one open position against all exit rules. Any one
    triggered reason is sufficient grounds to close — reasons are combined
    with OR logic, not required to all agree.
    """
    contract_symbol: str
    should_exit: bool
    triggered_reasons: List[str]
    current_premium: float
    pnl_pct: float
    days_to_expiry: int

class Candidate_Result(BaseModel):
    """
    One entry candidate produced by trading/options.py select_candidates() —
    a contract that passed the underpriced-vol filter and the EV-margin
    filter, ranked against the others by ev_per_premium (expected return
    on the premium paid, not raw expected_value — a $0.50 EV on a $1
    premium beats a $0.50 EV on a $10 premium).
    """
    contract_symbol: str
    underlying_symbol: str
    option_type: option_type
    strike_price: float
    days_to_expiry: int
    premium: float
    vol_comparison: Volatility_Comparison
    ev_result: Expected_Value_Result
    ev_per_premium: float
