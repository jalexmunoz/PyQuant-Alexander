# test_tradingview.py
# Test script for TradingView data fetching

from tvDatafeed import TvDatafeed, Interval

# Initialize client (no auth)
tv = TvDatafeed()

# Fetch data
print("Fetching BTCUSDT 1h data from Binance...")
data = tv.get_hist('BTCUSDT', 'BINANCE', interval=Interval.in_1_hour, n_bars=100)
print(data)
