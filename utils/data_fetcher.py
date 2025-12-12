# data_fetcher.py
# v0.4.0 - Multi-Source Data Fetcher (Binance + TradingView) with Caching
#
# Changelog:
# v0.4.0 - Added retry logic, exponential backoff, on-disk caching (parquet)
# v0.3.0 - Added TradingView support via tvDatafeed
# v0.2.0 - Added Binance OHLC and .env loading
# v0.1.0 - Initial CoinGecko implementation

import pandas as pd
import requests
import os
import logging
import time
import hashlib
from pathlib import Path
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

# =============================================================================
# CACHING CONFIGURATION
# =============================================================================
CACHE_DIR = Path("Output/cache")
CACHE_ENABLED_DEFAULT = False  # OFF by default, runners enable explicitly

# Cache format priority: pickle (most reliable) > parquet (if available) > csv
# Pickle is default because it requires no extra dependencies and preserves dtypes
CACHE_FORMAT = "pickle"  # pickle, parquet, or csv

_CACHE_FORMAT_LOGGED = False  # Track if we've logged the format message

# =============================================================================
# RETRY CONFIGURATION
# =============================================================================
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_BASE = 1.0  # seconds (exponential: 1s, 2s, 4s)
INTER_SYMBOL_DELAY = 0.5  # seconds delay between symbol fetches

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


# =============================================================================
# CACHING FUNCTIONS
# =============================================================================

def _get_cache_key(
    provider: str,
    exchange: str,
    symbol: str,
    interval: str,
    n_bars: int
) -> str:
    """
    Generate cache key for stored data.
    
    Format: provider_exchange_symbol_interval_bars
    Example: tv_BINANCE_BTCUSDT_1D_5000
    """
    return f"{provider}_{exchange}_{symbol}_{interval}_{n_bars}"


def _get_cache_path(cache_key: str) -> Path:
    """Get full path to cache file based on current format."""
    ext_map = {"pickle": "pkl", "parquet": "parquet", "csv": "csv"}
    ext = ext_map.get(CACHE_FORMAT, "pkl")
    return CACHE_DIR / f"{cache_key}.{ext}"


def _load_from_cache(cache_key: str) -> Optional[pd.DataFrame]:
    """
    Load data from cache if exists and valid.
    
    Returns None if cache miss or invalid.
    """
    cache_path = _get_cache_path(cache_key)
    
    if not cache_path.exists():
        return None
    
    try:
        if CACHE_FORMAT == "pickle":
            df = pd.read_pickle(cache_path)
        elif CACHE_FORMAT == "parquet":
            df = pd.read_parquet(cache_path)
        else:  # csv
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        
        # Validate cache has data
        if df is not None and not df.empty:
            logging.info(f"  [CACHE HIT] {cache_key}: {len(df)} bars")
            return df
    except Exception as e:
        logging.warning(f"  [CACHE ERROR] Failed to load {cache_key}: {e}")
    
    return None


def _save_to_cache(df: pd.DataFrame, cache_key: str) -> None:
    """
    Save data to cache. Uses pickle by default (most reliable, no extra deps).
    
    Creates cache directory if needed.
    """
    global _CACHE_FORMAT_LOGGED
    
    if df is None or df.empty:
        return
    
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = _get_cache_path(cache_key)
        
        if CACHE_FORMAT == "pickle":
            df.to_pickle(cache_path)
        elif CACHE_FORMAT == "parquet":
            df.to_parquet(cache_path)
        else:  # csv
            df.to_csv(cache_path)
        
        # Log format once per session
        if not _CACHE_FORMAT_LOGGED:
            logging.info(f"  [CACHE] Using {CACHE_FORMAT} format")
            _CACHE_FORMAT_LOGGED = True
        
        logging.debug(f"  [CACHE SAVE] {cache_key}: {len(df)} bars")
        
    except Exception as e:
        logging.warning(f"  [CACHE WARN] Failed to save {cache_key}: {e}")


def clear_cache(symbol: Optional[str] = None) -> int:
    """
    Clear cached data files.
    
    Parameters:
        symbol: If provided, only clear cache for this symbol.
                If None, clear all cache.
    
    Returns:
        Number of files deleted.
    """
    if not CACHE_DIR.exists():
        return 0
    
    deleted = 0
    pattern = f"*{symbol}*" if symbol else "*"
    
    for cache_file in CACHE_DIR.glob(pattern):
        if cache_file.suffix in [".pkl", ".parquet", ".csv"]:
            cache_file.unlink()
            deleted += 1
    
    logging.info(f"[CACHE] Cleared {deleted} cached files")
    return deleted


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


# === TradingView Functions ===

def _reinitialize_tv_client() -> bool:
    """
    Re-initialize TradingView client (useful after connection drops).
    
    Returns True if successful.
    """
    global tv_client
    
    if not TV_AVAILABLE:
        return False
    
    try:
        tv_client = TvDatafeed()
        logging.debug("  [TV] Client re-initialized")
        return True
    except Exception as e:
        logging.warning(f"  [TV] Client re-init failed: {e}")
        return False


def get_tradingview_ohlc(
    symbol: str,
    exchange: str = "BINANCE",
    interval = None,  # Will use Interval.in_daily if TV_AVAILABLE
    n_bars: int = 5000,
    use_cache: bool = CACHE_ENABLED_DEFAULT,
    retries: int = DEFAULT_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE
) -> Optional[pd.DataFrame]:
    """
    Download historical OHLCV from TradingView with retry logic and caching.
    
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
    use_cache : bool
        If True, check cache before fetching and save results to cache.
        Default: False (runners should enable explicitly)
    retries : int
        Number of retry attempts on failure (default: 3)
    backoff_base : float
        Base delay for exponential backoff in seconds (default: 1.0)
        
    Returns
    -------
    pd.DataFrame or None
        Indexed by datetime with columns: ['open', 'high', 'low', 'close', 'volume']
        Returns None on complete failure (after all retries exhausted).
        
    Notes
    -----
    TradingView symbols format: "BTCUSDT" (not "BTC-USDT")
    Available exchanges: BINANCE, COINBASE, KRAKEN, BITSTAMP, etc.
    
    Retry Logic:
    - Exponential backoff: 1s, 2s, 4s (configurable)
    - Re-initializes TradingView client on connection errors
    
    Examples
    --------
    >>> df = get_tradingview_ohlc("BTCUSDT", "BINANCE", Interval.in_daily, 1000)
    >>> df = get_tradingview_ohlc("ETHUSD", "COINBASE", use_cache=True)
    """
    global tv_client
    
    if not TV_AVAILABLE:
        logging.error(f"[FETCH FAIL] {exchange}:{symbol} - TradingView not available")
        return None
    
    # Set default interval if not provided
    if interval is None:
        interval = Interval.in_daily
    
    # Determine interval string for cache key
    interval_str = "1D"  # default
    if TV_AVAILABLE:
        interval_map = {
            Interval.in_daily: "1D",
            Interval.in_4_hour: "4H",
            Interval.in_1_hour: "1H",
            Interval.in_15_minute: "15m",
            Interval.in_weekly: "1W",
        }
        interval_str = interval_map.get(interval, "1D")
    
    cache_key = _get_cache_key("tv", exchange, symbol, interval_str, n_bars)
    
    # Check cache first
    if use_cache:
        cached_df = _load_from_cache(cache_key)
        if cached_df is not None:
            return cached_df
    
    logging.info(f"Fetching TradingView: {exchange}:{symbol} ({interval_str}, {n_bars} bars)...")
    
    last_error = None
    
    for attempt in range(1, retries + 1):
        try:
            # Ensure client is available
            if tv_client is None:
                if not _reinitialize_tv_client():
                    logging.error(f"[FETCH FAIL] {exchange}:{symbol} - Cannot initialize TV client")
                    return None
            
            # Fetch data
            df = tv_client.get_hist(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                n_bars=n_bars
            )
            
            if df is None or df.empty:
                logging.warning(f"  [FETCH] {exchange}:{symbol} - No data returned (attempt {attempt}/{retries})")
                last_error = "No data returned"
                
                # Retry with backoff
                if attempt < retries:
                    delay = backoff_base * (2 ** (attempt - 1))
                    logging.info(f"  [RETRY] Waiting {delay:.1f}s before retry...")
                    time.sleep(delay)
                    _reinitialize_tv_client()  # Re-init client before retry
                continue
            
            # Success - process data
            df.columns = df.columns.str.lower()
            required_cols = ["open", "high", "low", "close", "volume"]
            df = df[required_cols]
            
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            logging.info(f"✅ TradingView: {exchange}:{symbol} - {len(df)} bars ({df.index.min().date()} to {df.index.max().date()})")
            
            # Save to cache
            if use_cache:
                _save_to_cache(df, cache_key)
            
            return df
            
        except Exception as e:
            last_error = str(e)
            logging.warning(f"  [FETCH ERROR] {exchange}:{symbol} attempt {attempt}/{retries}: {e}")
            
            if attempt < retries:
                delay = backoff_base * (2 ** (attempt - 1))
                logging.info(f"  [RETRY] Waiting {delay:.1f}s before retry...")
                time.sleep(delay)
                _reinitialize_tv_client()  # Re-init client on error
    
    # All retries exhausted
    logging.error(f"[FETCH FAIL] {exchange}:{symbol} - All {retries} attempts failed. Last error: {last_error}")
    return None


def get_tradingview_ohlc_batch(
    symbols: list,
    exchange: str = "BINANCE",
    interval = None,
    n_bars: int = 5000,
    use_cache: bool = True,
    inter_symbol_delay: float = INTER_SYMBOL_DELAY
) -> dict:
    """
    Fetch multiple symbols with delay between requests to reduce connection drops.
    
    Parameters
    ----------
    symbols : list
        List of symbols to fetch
    exchange : str
        Exchange name
    interval : Interval
        TradingView interval
    n_bars : int
        Number of bars per symbol
    use_cache : bool
        Enable caching (default: True for batch operations)
    inter_symbol_delay : float
        Delay in seconds between symbol fetches (default: 0.5s)
        
    Returns
    -------
    dict
        {symbol: DataFrame or None}
    """
    results = {}
    
    for i, symbol in enumerate(symbols):
        if i > 0 and inter_symbol_delay > 0:
            time.sleep(inter_symbol_delay)
        
        results[symbol] = get_tradingview_ohlc(
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            n_bars=n_bars,
            use_cache=use_cache
        )
    
    return results


# === Unified Fetcher ===

def get_ohlc(
    symbol: str,
    source: Literal["tradingview", "binance", "coingecko"] = "tradingview",
    start_date: Optional[str] = "2017-01-01",
    exchange: str = "BINANCE",
    interval: str = "1d",
    use_cache: bool = CACHE_ENABLED_DEFAULT
) -> Optional[pd.DataFrame]:
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
        
        return get_tradingview_ohlc(symbol, exchange, tv_interval, n_bars, use_cache=use_cache)
    
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
