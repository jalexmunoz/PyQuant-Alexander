# test_yf.py
from utils.data_fetcher import get_binance_ohlc as get_ohlc

df = get_ohlc("BTC-USD", source="yahoo", start_date="2020-01-01")
print(df.head())
print(f"Rows: {len(df)}")