from pydantic import BaseModel

class Settings(BaseModel):
    BASE_URL: str = "https://paper-api.alpaca.markets" # paper trading base URL
    ENABLE_DRY_RUNNING: bool = False # enable dry running for testing purposes (no trades will be executed)
    SCAN_INTERVAL_SECONDS: int = 10 # how often to re-scan the watchlist while market is open
    CLOSED_MARKET_SLEEP_SECONDS: int = 300 # check less frequently while the market's closed
    RUN_DESPITE_MARKET_CLOSED: bool = True # if True, the bot will run even when the market is closed (useful for testing)

    # implied volatility solver (see strategy/implied_volatility.py)
    RISK_FREE_RATE: float = 0.05  # annualized; adjust to current T-bill rate for more precision
    NR_MAX_ITERATIONS: int = 100
    NR_PRICE_TOLERANCE: float = 1e-6
    NR_MIN_VEGA: float = 1e-8       # below this, Newton-Raphson's derivative is treated as too unstable to trust
    SIGMA_LOWER_BOUND: float = 1e-6
    SIGMA_UPPER_BOUND: float = 5.0  # 500% annualized vol — already an extreme ceiling
    VOL_SPREAD_THRESHOLD: float = 0.05  # default overpriced/underpriced cutoff in compare_volatility()

    # option chain fetching (see market_data/options_chain.py)
    OPTIONS_DATA_FEED: str = "indicative"  # free-plan-safe feed for options data
    MAX_DAYS_TO_EXPIRY: int = 45           # ignore contracts expiring further out than this
    STRIKE_RANGE_PCT: float = 0.15         # only keep strikes within +/- 15% of spot price

    # expected-value decision layer (see strategy/expected_value.py)
    MONTE_CARLO_SIMULATIONS: int = 50000  # number of simulated price paths per contract
    EV_PROFIT_THRESHOLD: float = 0.0      # minimum simulated expected profit (per share) to flag as a candidate

    # exit strategy (see strategy/exit_strategy.py) — any one triggering is enough to close
    TAKE_PROFIT_PCT: float = 0.50     # close once position value is up 50% from entry
    STOP_LOSS_PCT: float = 0.30       # close once position value is down 30% from entry
    EXIT_DAYS_BEFORE_EXPIRY: int = 3  # force-close this many days before expiration regardless of P&L

    # candidate selection (see trading/options.py select_candidates()) — entry-side ranking
    TOP_N_CANDIDATES: int = 5           # how many ranked candidates to return per scan
    MIN_EV_MARGIN_PCT: float = 0.05     # require expected_value/premium >= 5% — filters out barely-profitable noise
    MIN_CONTRACT_PREMIUM: float = 0.05  # skip contracts priced this cheap or below — ev_per_premium divides by
                                         # premium, so a near-zero/illiquid quote can produce an absurd ratio
                                         # (e.g. a real $0.02 quote once produced a "15,510% expected return")
                                         # that would dominate ranking and position sizing on pure noise

    # order execution (see main.py scan_and_trade()/evaluate_exits())
    DEFAULT_ORDER_QTY: int = 1  # fallback flat qty if account info can't be fetched or sizing fails

    # position sizing (see strategy/position_sizing.py) — qty scales with account risk
    # budget and how strong the edge is, instead of always buying DEFAULT_ORDER_QTY
    MAX_RISK_PER_TRADE_PCT: float = 0.02   # never risk more than 2% of account equity on one trade
    MIN_ORDER_QTY: int = 1                 # size at the weakest edge that still clears MIN_EV_MARGIN_PCT
    MAX_ORDER_QTY: int = 10                # size cap at/above HIGH_CONVICTION_EV_PCT, regardless of risk budget
    HIGH_CONVICTION_EV_PCT: float = 0.30   # ev_per_premium at/above this scales to MAX_ORDER_QTY

def get_settings():
    return Settings()