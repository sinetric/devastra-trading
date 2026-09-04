from src.outbound.market_data.options_chain import get_option_chain
from src.outbound.market_data.historical import get_historical_bars
from src.outbound.strategy.volatility import get_volatility_stats
from src.outbound.strategy.expected_value import get_expected_value_result

bars = get_historical_bars("AAPL")
vol_stats = get_volatility_stats("AAPL", bars, lookback_days=730)

chain = get_option_chain("AAPL", spot_price=228.50)

for contract in chain:
    ev_result = get_expected_value_result(
        contract_symbol=contract.contract_symbol,
        underlying_symbol="AAPL",
        spot_price=228.50,
        strike_price=contract.strike_price,
        days_to_expiry=contract.days_to_expiry,
        opt_type=contract.option_type,
        premium=contract.market_price,
        annual_vol=vol_stats.annual_vol,
    )
    if ev_result.is_profitable:
        print(f"Candidate: {contract.contract_symbol} EV={ev_result.expected_value:.3f}/share")