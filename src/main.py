import time
import traceback
import requests

from src.utils import logger
from src.outbound.header import get_header
from src.outbound.market_data.stocks import fetch_watchlist_snapshots, rank_movers
from src.outbound.trading.options import get_option_contract_symbol, submit_option_order
from src.outbound.models import Create_OCC_Format, Option_Submission
from src.outbound.strategy import buy_choice
from config.settings import get_settings

SETTINGS = get_settings()

SCAN_INTERVAL_SECONDS = SETTINGS.SCAN_INTERVAL_SECONDS       # how often to re-scan the watchlist while market is open
CLOSED_MARKET_SLEEP_SECONDS = SETTINGS.CLOSED_MARKET_SLEEP_SECONDS  # check less frequently while the market's closed

def is_market_open(settings) -> bool:
    response = requests.get(f"{settings.BASE_URL}/v2/clock", headers=get_header())
    response.raise_for_status()
    
    return response.json()["is_open"]


def scan_and_trade(settings) -> None:
    """One full cycle: pull watchlist snapshots, rank movers, decide/act on candidates."""
    snapshots = fetch_watchlist_snapshots()
    movers = rank_movers(snapshots, top_n=10)

    logger.log(f"Top movers: {movers}")

    # ... your strategy logic decides what to trade from `movers` ...
    # then build a Create_OCC_Format, call get_option_contract_symbol, build an
    # Option_Submission, call submit_option_order

    decisions = buy_choice.decide_buy(movers)
    logger.log(decisions)

    # decide here which stocks to buy or not buy


def run():
    settings = SETTINGS
    logger.log("Bot started.")

    print(get_header())  # Debug: Print headers to verify API keys are loaded correctly

    while True:
        try:
            if (True if SETTINGS.RUN_DESPITE_MARKET_CLOSED else is_market_open(settings)):
                scan_and_trade(settings)
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
