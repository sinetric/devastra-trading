from src.utils import logger
from src.outbound.trading.options import select_candidates


def decide_buy(movers: list[dict]) -> list[dict]:
    """
    Evaluate the top market movers (as returned by rank_movers()) and decide
    which ones are worth acting on — runs select_candidates() per mover's
    underlying and keeps only the ones that produced at least one qualifying
    candidate. Doesn't buy anything itself: main.py is what turns a decision
    here into a Create_OCC_Format / Option_Submission / submit_option_order
    call, per the current task split.
    """
    decisions: list[dict] = []

    for mover in movers:
        symbol = mover["symbol"]
        spot_price = mover["price"]

        try:
            candidates = select_candidates(symbol, spot_price)
        except Exception as e:
            # one bad underlying (bad chain data, unsolvable IV, etc.) shouldn't
            # stop the rest of the movers from being evaluated
            logger.log(f"select_candidates failed for {symbol}: {e}", level="error")
            continue

        if not candidates:
            continue  # nothing on this underlying cleared the underpriced/EV bar

        decisions.append({
            "symbol": symbol,
            "mover": mover,
            "should_buy": True,
            "candidates": candidates,
        })

    return decisions
