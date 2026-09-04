"""
Exit decision logic for open positions.

Everything else in strategy/ answers "should I buy this contract." This
answers "should I close a position I already hold" — a separate question
nothing else in the codebase addresses. Four independent checks, combined
with OR logic: any single one triggering is sufficient reason to exit,
since each guards against a different failure mode (the trade thesis
disappearing, an unexpected loss, a stalled winner, or running an option
too close to expiration).

This module is a pure decision function — given a Position and the current
market state, it returns whether to exit and why. It does not track,
store, or create positions; that's a separate concern (a ledger of open
positions), left to whoever wires the actual trading loop around this.
"""

from __future__ import annotations

from datetime import datetime

from src.outbound.models import Position, Exit_Decision, option_type as OptionType
from src.outbound.strategy.implied_volatility import compare_volatility
from src.outbound.strategy.expected_value import get_expected_value_result
from config.settings import get_settings

SETTINGS = get_settings()


def evaluate_exit(
    position: Position,
    current_premium: float,
    current_spot_price: float,
    current_realized_vol: float,
    current_implied_vol: float,
) -> Exit_Decision:
    """
    Check all four exit conditions for one open position. Returns an
    Exit_Decision with should_exit=True if ANY condition triggers, listing
    every reason that fired (a position can trigger more than one at once).
    """
    reasons: list[str] = []

    pnl_pct = (current_premium - position.entry_premium) / position.entry_premium
    days_to_expiry = (position.expiration_date - datetime.utcnow()).days

    # 1. Take-profit
    if pnl_pct >= SETTINGS.TAKE_PROFIT_PCT:
        reasons.append(f"take_profit (pnl={pnl_pct:.1%} >= {SETTINGS.TAKE_PROFIT_PCT:.1%})")

    # 2. Stop-loss
    if pnl_pct <= -SETTINGS.STOP_LOSS_PCT:
        reasons.append(f"stop_loss (pnl={pnl_pct:.1%} <= -{SETTINGS.STOP_LOSS_PCT:.1%})")

    # 3. Time-based — force-close regardless of P&L once too close to expiry
    if days_to_expiry <= SETTINGS.EXIT_DAYS_BEFORE_EXPIRY:
        reasons.append(f"time_based (days_to_expiry={days_to_expiry} <= {SETTINGS.EXIT_DAYS_BEFORE_EXPIRY})")

    # 4. Signal-reversal — re-run the same checks that justified the buy;
    #    exit if the mispricing has closed or EV has gone negative, even
    #    if pnl_pct doesn't yet reflect it
    if days_to_expiry > 0:
        comparison = compare_volatility(
            position.underlying_symbol, position.contract_symbol,
            current_realized_vol, current_implied_vol,
        )
        if comparison.verdict != "underpriced":
            reasons.append(f"signal_reversal (verdict={comparison.verdict}, spread={comparison.vol_spread:.3f})")
        else:
            ev_result = get_expected_value_result(
                contract_symbol=position.contract_symbol,
                underlying_symbol=position.underlying_symbol,
                spot_price=current_spot_price,
                strike_price=position.strike_price,
                days_to_expiry=days_to_expiry,
                opt_type=position.option_type,
                premium=current_premium,
                annual_vol=current_realized_vol,
            )
            if not ev_result.is_profitable:
                reasons.append(f"signal_reversal (expected_value={ev_result.expected_value:.4f} no longer profitable)")

    return Exit_Decision(
        contract_symbol=position.contract_symbol,
        should_exit=len(reasons) > 0,
        triggered_reasons=reasons,
        current_premium=current_premium,
        pnl_pct=pnl_pct,
        days_to_expiry=days_to_expiry,
    )
