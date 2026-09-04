"""
Hardcoded watchlist of liquid, actively-traded US equities/ETFs with deep
options chains. Used in place of the /v1beta1/screener/stocks/movers
endpoint, which requires a paid SIP data subscription — this list gives us
a fixed universe to scan with free-tier (IEX feed) snapshot data instead.

Mostly mega-cap tech, large financials/industrials/consumer names, and the
three most heavily-traded broad-market ETFs. Not exhaustive, not a
recommendation — just a reasonable, liquid starting universe for a
hackathon-scale bot. Update freely as your strategy narrows in.
"""

WATCHLIST = [
    # Mega-cap tech
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD",
    "NFLX", "AVGO", "CRM", "ADBE", "INTC", "QCOM", "ORCL", "CSCO", "IBM",

    # Fintech / growth
    "UBER", "PYPL", "SHOP", "SQ", "COIN", "PLTR", "SOFI",

    # Autos / industrials
    "F", "GM", "BA",

    # Consumer
    "DIS", "NKE", "SBUX", "MCD", "WMT",

    # Financials
    "JPM", "BAC", "GS",

    # Energy
    "XOM", "CVX",

    # Broad-market ETFs (very high options volume/liquidity)
    "SPY", "QQQ", "IWM",
]
