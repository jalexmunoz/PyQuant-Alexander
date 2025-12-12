# data_fetcher.py
# v0.3.0 - Multi-Source Data Fetcher (Binance + TradingView)
#
# Changelog:
# v0.3.0 - Added TradingView support via tvDatafeed
# v0.2.0 - Added Binance OHLC and .env loading
# v0.1.0 - Initial CoinGecko implementation

import pandas as pd
import requests
import os
import logging
from typing import Optional, Literal
from binance.client import Client
from dotenv import load_dotenv

# TradingView support (install: pip install tvdatafeed-enhanced)
try:
    from tvDatafeed import TvDatafeed, Interval
    TV_AVAILABLE = True
except ImportError:
    TV_AVAILABLE = False
    logging.warning("tvdatafeed-enhanced not installed. TradingView fetching disabled. Install: pip install tvdatafeed-enhanced")

# === Configuration ===
logging.basicConfig(level=logging.INFO)
load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

# Initialize clients
binance_client = None
tv_client = None

# Binance client (optional - TradingView is primary source)
if BINANCE_API_KEY and BINANCE_API_SECRET:
    try:
        binance_client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
        logging.info("✅ Binance client initialized.")
    except Exception as e:
        # Debug level - Binance is optional since we use TradingView
        logging.debug(f"Binance client unavailable: {e}")
else:
    logging.debug("Binance API keys not configured (optional - using TradingView)")

# TradingView client (no auth - anonymous mode)
if TV_AVAILABLE:
    try:
        tv_client = TvDatafeed()
        logging.info("✅ TradingView client initialized.")
    except Exception as e:
        logging.warning(f"⚠️ TradingView client failed: {e}")
        tv_client = None


# === CoinGecko Functions (Fallback) ===

def get_coingecko_price(coin_id: str, days: int = 180, vs_currency: str = "usd") -> pd.DataFrame:
    """Download historical prices from CoinGecko public API."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": vs_currency, "days": days}
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    prices = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
    prices["date"] = pd.to_datetime(prices["timestamp"], unit="ms")
    prices = prices[["date", "price"]].set_index("date")
    prices.rename(columns={"price": coin_id.capitalize()}, inplace=True)
    return prices


def get_coingecko_ohlc(coin_id: str, days: int = 365, vs_currency: str = "usd") -> pd.DataFrame:
    """Download OHLC data from CoinGecko."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": vs_currency, "days": days}
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("date")[["open", "high", "low", "close"]]
    return df


# === Binance Functions ===

def get_binance_ohlc(
    symbol: str,
    interval: str = Client.KLINE_INTERVAL_1DAY,
    start_date: str = "1 Jan, 2017"
) -> pd.DataFrame:
    """
    Download historical OHLCV from Binance.
    
    Parameters
    ----------
    symbol : str
        Binance pair format (e.g., "BTCUSDT", "ETHUSDT")
    interval : str
        Binance interval (e.g., '1d', '4h', '1m')
    start_date : str
        Start date for historical data
        
    Returns
    -------
    pd.DataFrame
        Indexed by date with columns: ['open', 'high', 'low', 'close', 'volume']
    """
    if not binance_client:
        logging.error("Binance client not initialized. Check API keys in .env")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    
    logging.info(f"Fetching Binance data for {symbol} from {start_date}...")
    
    try:
        klines = binance_client.get_historical_klines(symbol, interval, start_date)
        
        if not klines:
            logging.warning(f"No data returned from Binance for {symbol}")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        cols = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
        ]
        df = pd.DataFrame(klines, columns=cols)
        
        numeric_cols = ["open", "high", "low", "close", "volume"]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        df["date"] = pd.to_datetime(df["open_time"], unit="ms")
        df = df.set_index("date")[numeric_cols]

        logging.info(f"✅ Binance: {len(df)} records. Range: {df.index.min()} to {df.index.max()}")
        return df

    except Exception as e:
        logging.error(f"❌ Binance error for {symbol}: {e}")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])


# === TradingView Functions (NEW) ===

def get_tradingview_ohlc(
    symbol: str,
    exchange: str = "BINANCE",
    interval = None,  # Will use Interval.in_daily if TV_AVAILABLE
    n_bars: int = 5000
) -> pd.DataFrame:
    """
    Download historical OHLCV from TradingView.
    
    Parameters
    ----------
    symbol : str
        Trading symbol (e.g., "BTCUSDT", "ETHUSDT")
    exchange : str
        Exchange name in TradingView format (e.g., "BINANCE", "COINBASE")
    interval : Interval
        TradingView interval (Interval.in_daily, Interval.in_1_hour, etc.)
    n_bars : int
        Number of historical bars to fetch (max ~5000)
        
    Returns
    -------
    pd.DataFrame
        Indexed by datetime with columns: ['open', 'high', 'low', 'close', 'volume']
        
    Notes
    -----
    TradingView symbols format: "BTCUSDT" (not "BTC-USDT")
    Available exchanges: BINANCE, COINBASE, KRAKEN, BITSTAMP, etc.
    
    Examples
    --------
    >>> df = get_tradingview_ohlc("BTCUSDT", "BINANCE", Interval.in_daily, 1000)
    >>> df = get_tradingview_ohlc("ETHUSD", "COINBASE", Interval.in_4_hour, 2000)
    """
    if not TV_AVAILABLE or not tv_client:
        logging.error("TradingView client not available. Install: pip install tvDatafeed")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    
    # Set default interval if not provided
    if interval is None:
        interval = Interval.in_daily
    
    logging.info(f"Fetching TradingView data: {exchange}:{symbol} ({interval}, {n_bars} bars)...")
    
    try:
        # TvDatafeed.get_hist() returns a DataFrame indexed by datetime
        df = tv_client.get_hist(
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            n_bars=n_bars
        )
        
        if df is None or df.empty:
            logging.warning(f"No data returned from TradingView for {exchange}:{symbol}")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        
        # Standardize column names (TradingView uses lowercase)
        df.columns = df.columns.str.lower()
        
        # Select only OHLCV columns
        required_cols = ["open", "high", "low", "close", "volume"]
        df = df[required_cols]
        
        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        logging.info(f"✅ TradingView: {len(df)} records. Range: {df.index.min()} to {df.index.max()}")
        return df
    
    except Exception as e:
        logging.error(f"❌ TradingView error for {exchange}:{symbol}: {e}")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])


# === Unified Fetcher (NEW) ===

def get_ohlc(
    symbol: str,
    source: Literal["tradingview", "binance", "coingecko"] = "tradingview",
    start_date: Optional[str] = "2017-01-01",
    exchange: str = "BINANCE",
    interval: str = "1d"
) -> pd.DataFrame:
    """
    Unified interface to fetch OHLCV data from multiple sources.
    
    Parameters
    ----------
    symbol : str
        Trading pair symbol (format depends on source)
    source : str
        Data source: "tradingview", "binance", or "coingecko"
    start_date : str, optional
        Start date (format: "YYYY-MM-DD")
    exchange : str
        Exchange name (for TradingView only)
    interval : str
        Time interval ("1d", "4h", "1h", etc.)
        
    Returns
    -------
    pd.DataFrame
        OHLCV data indexed by date
        
    Examples
    --------
    >>> # TradingView (recommended for premium features)
    >>> df = get_ohlc("BTCUSDT", source="tradingview", exchange="BINANCE")
    
    >>> # Binance (direct API)
    >>> df = get_ohlc("BTCUSDT", source="binance", start_date="2020-01-01")
    
    >>> # CoinGecko (fallback, limited history)
    >>> df = get_ohlc("bitcoin", source="coingecko")
    """
    
    if source == "tradingview":
        # Map interval string to TradingView Interval enum
        interval_map = {
            "1d": Interval.in_daily,
            "4h": Interval.in_4_hour,
            "1h": Interval.in_1_hour,
            "15m": Interval.in_15_minute,
        }
        tv_interval = interval_map.get(interval, Interval.in_daily)
        
        # Calculate n_bars from start_date
        if start_date:
            days_back = (pd.Timestamp.now() - pd.Timestamp(start_date)).days
            n_bars = min(days_back, 5000)  # TradingView limit
        else:
            n_bars = 5000
        
        return get_tradingview_ohlc(symbol, exchange, tv_interval, n_bars)
    
    elif source == "binance":
        # Map interval to Binance format
        binance_interval = {
            "1d": Client.KLINE_INTERVAL_1DAY,
            "4h": Client.KLINE_INTERVAL_4HOUR,
            "1h": Client.KLINE_INTERVAL_1HOUR,
        }.get(interval, Client.KLINE_INTERVAL_1DAY)
        
        return get_binance_ohlc(symbol, binance_interval, start_date or "1 Jan, 2017")
    
    elif source == "coingecko":
        days = (pd.Timestamp.now() - pd.Timestamp(start_date)).days if start_date else 365
        return get_coingecko_ohlc(symbol, days=days)
    
    else:
        raise ValueError(f"Unknown source: {source}. Use 'tradingview', 'binance', or 'coingecko'")


# === Backward Compatibility Alias ===
# Para que el código existente siga funcionando sin cambios
def get_binance_data(symbol: str, start_date: str = "2017-01-01") -> pd.DataFrame:
    """Alias for backward compatibility. Use get_ohlc() for new code."""
    return get_ohlc(symbol, source="binance", start_date=start_date)
