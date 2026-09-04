from pydantic import BaseModel
from enum import Enum

# defining enums

class OptionStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"

# BaseModel definitions

class CreateOCCFormat(BaseModel):
    root_symbol: str
    expr_date: str
    option_type: str
    strike_price_gte: float
    strike_price_lte: float
    status: OptionStatus