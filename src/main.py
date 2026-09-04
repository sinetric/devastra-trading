import time
import traceback
import requests
from datetime import datetime

from src.utils import logger
from src.outbound.header import get_header
from src.outbound.market_data.stocks import fetch_watchlist_snapshots, rank_movers
from src.outbound.market_data.options_chain import fetch_all_option_snapshots, extract_bid_price
from src.outbound.market_data.historical import get_historical_bars
from src.outbound.strategy.volatility import get_volatility_stats
from src.outbound.strategy.implied_volatility import get_implied_volatility_result
from src.outbound.strategy.exit_strategy import evaluate_exit
from src.outbound.strategy.buy_choice import decide_buy
from src.outbound.strategy.position_sizing import calculate_qty
from src.outbound.trading.options import get_option_contract_symbol, submit_option_order
from src.outbound.models import Create_OCC_Format, Option_Submission, order_side
from src.outbound.storage.positions_db import record_purchase, get_open_positions, close_position
from src.outbound.account import get_account
from config.settings import get_settings

SETTINGS = get_settings()

SCAN_INTERVAL_SECONDS = SETTINGS.SCAN_INTERVAL_SECONDS       # how often to re-scan the watchlist while market is open
CLOSED_MARKET_SLEEP_SECONDS = SETTINGS.CLOSED_MARKET_SLEEP_SECONDS  # check less frequently while the market's closed

def is_market_open(settings) -> bool:
    response = requests.get(f"{settings.BASE_URL}/v2/clock", headers=get_header())
    response.raise_for_status()
    
    return response.json()["is_open"]


def scan_and_trade(settings) -> None:
    """One full cycle: pull watchlist snapshots, rank movers, decide/act on candidates, record fills."""
    snapshots = fetch_watchlist_snapshots()
    movers = rank_movers(snapshots, top_n=10)

    logger.log(f"Top movers: {movers}")

    decisions = decide_buy(movers)

    if not decisions:
        return

    # Fetch account state once per cycle rather than once per decision — cheap on
    # API calls, and buying_power is decremented locally below as trades are
    # "spent" within this cycle so back-to-back buys in the same scan don't
    # over-commit capital the account doesn't actually have anymore.
    try:
        account = get_account()
        remaining_buying_power = account.buying_power
        sizing_available = True
    except Exception as e:
        logger.log(f"Couldn't fetch account info, falling back to DEFAULT_ORDER_QTY: {e}", level="warning")
        sizing_available = False

    for decision in decisions:
        # candidates are already ranked by ev_per_premium — take the best one per underlying
        top_candidate = decision["candidates"][0]

        if sizing_available:
            qty = calculate_qty(
                top_candidate,
                account_equity=account.equity,
                buying_power=remaining_buying_power,
                settings=settings,
            )
            if qty <= 0:
                logger.log(
                    f"Skipping {top_candidate.contract_symbol} — position sizing came out to 0 "
                    f"(risk budget / conviction / buying power all say no).",
                    level="warning",
                )
                continue
        else:
            qty = settings.DEFAULT_ORDER_QTY

        submission = Option_Submission(
            symbol=top_candidate.contract_symbol,
            qty=qty,
            side=order_side.BUY,
        )

        response = submit_option_order(submission)

        # Only record a real fill as an open position — a dry run should exercise
        # the whole decision pipeline without polluting the actual trade ledger.
        # (Recorded on submission, not confirmed fill — fine for paper trading /
        # a hackathon demo, but a live-money version would want to check the
        # order's actual fill status before treating this as an open position.)
        if not response.get("dry_run"):
            record_purchase(top_candidate, qty=qty)

            if sizing_available:
                remaining_buying_power -= qty * top_candidate.premium * 100  # 100 shares/contract

        logger.log(
            f"Bought {top_candidate.contract_symbol} x{qty} @ ${top_candidate.premium:.2f} "
            f"(ev/premium={top_candidate.ev_per_premium:.1%}, order_status={response.get('status')})"
        )


def evaluate_exits(settings) -> None:
    """Scan every open position in the ledger and close out any that trip an exit rule."""
    open_positions = get_open_positions()

    if not open_positions:
        return

    for row_id, position in open_positions:
        days_to_expiry = (position.expiration_date - datetime.utcnow()).days

        if days_to_expiry < 0:
            # expired without us catching it in time — close it out untracked rather
            # than let it sit open forever; can't know the real settlement value here
            close_position(row_id, exit_premium=0.0, reasons=["expired_untracked"])
            logger.log(f"{position.contract_symbol} expired before we exited — closed at $0.", level="warning")
            continue

        try:
            underlying_snapshots = fetch_watchlist_snapshots(symbols=[position.underlying_symbol])
            current_spot = underlying_snapshots[position.underlying_symbol]["latestTrade"]["p"]

            contract_snapshots = fetch_all_option_snapshots(position.underlying_symbol)
            contract_snapshot = contract_snapshots.get(position.contract_symbol)
            if contract_snapshot is None:
                logger.log(f"No live snapshot for {position.contract_symbol} — skipping this cycle.", level="warning")
                continue

            current_premium = extract_bid_price(contract_snapshot)
            if current_premium is None:
                logger.log(f"No usable bid for {position.contract_symbol} — skipping this cycle.", level="warning")
                continue

            bars = get_historical_bars(position.underlying_symbol)
            vol_stats = get_volatility_stats(position.underlying_symbol, bars, lookback_days=730)

            iv_result = get_implied_volatility_result(
                contract_symbol=position.contract_symbol,
                underlying_symbol=position.underlying_symbol,
                market_price=current_premium,
                S=current_spot,
                K=position.strike_price,
                days_to_expiry=days_to_expiry,
                opt_type=position.option_type,
            )
        except Exception as e:
            # one bad position (stale snapshot, unsolvable IV, etc.) shouldn't stop
            # the rest of the ledger from being checked
            logger.log(f"Exit evaluation failed for {position.contract_symbol}: {e}", level="error")
            continue

        decision = evaluate_exit(
            position=position,
            current_premium=current_premium,
            current_spot_price=current_spot,
            current_realized_vol=vol_stats.annual_vol,
            current_implied_vol=iv_result.implied_vol,
        )

        if decision.should_exit:
            submission = Option_Submission(
                symbol=position.contract_symbol,
                qty=position.qty,
                side=order_side.SELL,
            )
            sell_response = submit_option_order(submission)

            # Same dry-run guard as the buy side — don't close out a real ledger
            # row over an order that was never actually sent.
            if not sell_response.get("dry_run"):
                close_position(row_id, exit_premium=current_premium, reasons=decision.triggered_reasons)

            logger.log(
                f"Closed {position.contract_symbol}: {decision.triggered_reasons} "
                f"(pnl={decision.pnl_pct:.1%}, premium=${current_premium:.2f})"
            )
        else:
            logger.log(
                f"Holding {position.contract_symbol} "
                f"(pnl={decision.pnl_pct:.1%}, dte={decision.days_to_expiry})",
                level="debug",
            )


def run():
    settings = SETTINGS
    logger.log("Bot started.")

    print(get_header())  # Debug: Print headers to verify API keys are loaded correctly

    while True:
        try:
            if (True if SETTINGS.RUN_DESPITE_MARKET_CLOSED else is_market_open(settings)):
                scan_and_trade(settings)
                evaluate_exits(settings)
                time.sleep(SCAN_INTERVAL_SECONDS)
            else:
                logger.log("Market closed, sleeping.", level="debug")
                time.sleep(CLOSED_MARKET_SLEEP_SECONDS)

        except Exception as e:
            # one bad iteration shouldn't kill the whole bot — log it and keep going
            logger.log(f"Error during scan: {e}", level="error")
            logger.log(traceback.format_exc(), level="error")
            time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        logger.log("Bot stopped by user.")
