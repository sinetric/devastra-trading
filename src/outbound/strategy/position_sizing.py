"""
How many contracts to buy for a given candidate — instead of always
buying SETTINGS.DEFAULT_ORDER_QTY, quantity now scales on three things:

  1. Risk budget: never risk more than MAX_RISK_PER_TRADE_PCT of account
     equity on a single trade, regardless of how good the edge looks.
  2. Conviction: candidate.ev_per_premium is the model's own confidence
     signal (expected return on the premium paid) — a contract that just
     barely cleared MIN_EV_MARGIN_PCT gets sized small, one at or above
     HIGH_CONVICTION_EV_PCT gets sized up toward MAX_ORDER_QTY.
  3. Affordability: can't buy more contracts than current buying power
     actually covers.

Final size is the minimum of all three caps — a strong edge doesn't
override the risk budget, and the risk budget doesn't override what's
actually affordable.
"""

from __future__ import annotations

from src.outbound.models import Candidate_Result
from config.settings import get_settings, Settings

SETTINGS = get_settings()

CONTRACT_MULTIPLIER = 100  # one option contract = 100 shares of the underlying


def calculate_qty(
    candidate: Candidate_Result,
    account_equity: float,
    buying_power: float,
    settings: Settings | None = None,
) -> int:
    """
    Returns the number of contracts to buy for `candidate`, or 0 if every
    cap (risk budget, conviction floor, affordability) says not to take
    the trade at all. Callers should skip the order entirely on 0 rather
    than submit a zero-quantity order.
    """
    settings = settings or SETTINGS
    contract_cost = candidate.premium * CONTRACT_MULTIPLIER

    if contract_cost <= 0:
        return 0

    # 1. risk-based cap
    risk_budget = account_equity * settings.MAX_RISK_PER_TRADE_PCT
    risk_capped_qty = int(risk_budget // contract_cost)

    # 2. conviction scaling — linearly map ev_per_premium from
    #    [MIN_EV_MARGIN_PCT, HIGH_CONVICTION_EV_PCT] to [MIN_ORDER_QTY, MAX_ORDER_QTY]
    floor_edge = settings.MIN_EV_MARGIN_PCT
    ceil_edge = settings.HIGH_CONVICTION_EV_PCT

    if ceil_edge <= floor_edge:
        conviction_frac = 1.0  # degenerate config — treat every qualifying candidate as max conviction
    else:
        conviction_frac = (candidate.ev_per_premium - floor_edge) / (ceil_edge - floor_edge)
        conviction_frac = max(0.0, min(1.0, conviction_frac))  # clip — don't extrapolate past either end

    conviction_qty = round(
        settings.MIN_ORDER_QTY + conviction_frac * (settings.MAX_ORDER_QTY - settings.MIN_ORDER_QTY)
    )

    # 3. affordability cap
    affordable_qty = int(buying_power // contract_cost)

    qty = min(risk_capped_qty, conviction_qty, affordable_qty, settings.MAX_ORDER_QTY)

    return max(qty, 0)
