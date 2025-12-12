# core/strategies/trend_filter_strategy.py
# v1.0.0 - Strategy 1: Daily Trend Filter
#
# Purpose: Implement trend-based position sizing for BTC/ETH/SOL/LINK
#
# Rules:
# - ON (1):  close > SMA200 AND close > SMA50  → Full target weight
# - OFF (0): close < SMA50                      → Reduce/exit position
# - HYSTERESIS: close > SMA50 AND close < SMA200 → Keep previous state
#
# This prevents whipsaws when price is between the two SMAs.

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Literal

# =============================================================================
# CONSTANTS
# =============================================================================

# Base target weights (when trend is ON)
BASE_TARGETS: Dict[str, float] = {
    "BTCUSDT": 0.40,   # 40% BTC
    "ETHUSDT": 0.40,   # 40% ETH
    "SOLUSDT": 0.15,   # 15% SOL
    "LINKUSDT": 0.05,  # 5% LINK
}

# SMA periods for trend detection
SMA_SHORT: int = 50
SMA_LONG: int = 200

# Trend states
TREND_ON: int = 1
TREND_OFF: int = 0


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def compute_sma(series: pd.Series, window: int) -> pd.Series:
    """
    Compute Simple Moving Average.
    
    Parameters
    ----------
    series : pd.Series
        Price series (typically close prices)
    window : int
        SMA period
        
    Returns
    -------
    pd.Series
        SMA values
    """
    return series.rolling(window=window, min_periods=window).mean()


def compute_trend_state(
    df: pd.DataFrame,
    price_col: str = "close",
    sma_short: int = SMA_SHORT,
    sma_long: int = SMA_LONG
) -> pd.Series:
    """
    Compute trend state for each day with hysteresis.
    
    Parameters
    ----------
    df : pd.DataFrame
        OHLCV DataFrame with at least 'close' column
    price_col : str
        Column name for price data (default: 'close')
    sma_short : int
        Short SMA period (default: 50)
    sma_long : int
        Long SMA period (default: 200)
        
    Returns
    -------
    pd.Series
        Trend state series with values:
        - 1 (ON):  close > SMA200 AND close > SMA50 (full trend)
        - 0 (OFF): close < SMA50 (downtrend/exit)
        - Previous state when in hysteresis zone (SMA50 < close < SMA200)
        
    Notes
    -----
    Hysteresis prevents whipsaws when price oscillates between SMAs.
    The state "sticks" to its previous value in the uncertain zone.
    """
    close = df[price_col]
    
    # Calculate SMAs
    sma_50 = compute_sma(close, sma_short)
    sma_200 = compute_sma(close, sma_long)
    
    # Initialize trend state series
    n = len(df)
    trend_state = pd.Series(index=df.index, dtype=float)
    
    # Define conditions
    # ON: close > SMA200 AND close > SMA50 (above both = bullish)
    condition_on = (close > sma_200) & (close > sma_50)
    
    # OFF: close < SMA50 (below short SMA = bearish)
    condition_off = close < sma_50
    
    # Hysteresis zone: SMA50 < close < SMA200 (between SMAs)
    # In this zone, we keep the previous state
    condition_hysteresis = (close >= sma_50) & (close <= sma_200)
    
    # Apply rules with forward fill for hysteresis
    # Start with NaN, fill based on conditions
    trend_state[condition_on] = TREND_ON
    trend_state[condition_off] = TREND_OFF
    # Hysteresis zone gets NaN initially, then forward-filled
    
    # Forward fill NaN values (propagates previous state through hysteresis zones)
    trend_state = trend_state.ffill()
    
    # Fill any remaining NaN at the start (before we have enough data for SMA200)
    # Default to OFF (conservative) until we have enough data
    trend_state = trend_state.fillna(TREND_OFF)
    
    return trend_state.astype(int)


def get_trend_signals(
    df: pd.DataFrame,
    price_col: str = "close"
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Get all trend-related signals for analysis/visualization.
    
    Parameters
    ----------
    df : pd.DataFrame
        OHLCV DataFrame
    price_col : str
        Column name for price data
        
    Returns
    -------
    Tuple[pd.Series, pd.Series, pd.Series, pd.Series]
        (sma_50, sma_200, trend_state, close)
    """
    close = df[price_col]
    sma_50 = compute_sma(close, SMA_SHORT)
    sma_200 = compute_sma(close, SMA_LONG)
    trend_state = compute_trend_state(df, price_col)
    
    return sma_50, sma_200, trend_state, close


def apply_trend_filter(
    base_weight: float,
    trend_state: int,
    off_multiplier: float = 0.0
) -> float:
    """
    Apply trend filter to a base target weight.
    
    Parameters
    ----------
    base_weight : float
        Base target weight (0.0-1.0)
    trend_state : int
        Current trend state (1=ON, 0=OFF)
    off_multiplier : float
        Multiplier when trend is OFF (default: 0.0 = exit completely)
        
    Returns
    -------
    float
        Adjusted target weight
        
    Examples
    --------
    >>> apply_trend_filter(0.40, 1)  # ON: full weight
    0.40
    >>> apply_trend_filter(0.40, 0)  # OFF: exit
    0.0
    >>> apply_trend_filter(0.40, 0, off_multiplier=0.5)  # OFF: half weight
    0.20
    """
    if trend_state == TREND_ON:
        return base_weight
    else:
        return base_weight * off_multiplier


def get_filtered_targets(
    trend_states: Dict[str, int],
    base_targets: Dict[str, float] = None,
    off_multiplier: float = 0.0
) -> Dict[str, float]:
    """
    Get filtered target weights based on current trend states.
    
    Parameters
    ----------
    trend_states : Dict[str, int]
        Current trend state per asset {"BTCUSDT": 1, "ETHUSDT": 0, ...}
    base_targets : Dict[str, float]
        Base target weights (default: BASE_TARGETS)
    off_multiplier : float
        Weight multiplier when trend is OFF (default: 0.0)
        
    Returns
    -------
    Dict[str, float]
        Filtered target weights
        
    Examples
    --------
    >>> states = {"BTCUSDT": 1, "ETHUSDT": 0, "SOLUSDT": 1, "LINKUSDT": 0}
    >>> get_filtered_targets(states)
    {'BTCUSDT': 0.40, 'ETHUSDT': 0.0, 'SOLUSDT': 0.15, 'LINKUSDT': 0.0}
    """
    if base_targets is None:
        base_targets = BASE_TARGETS
    
    filtered = {}
    for symbol, base_weight in base_targets.items():
        state = trend_states.get(symbol, TREND_OFF)  # Default to OFF if unknown
        filtered[symbol] = apply_trend_filter(base_weight, state, off_multiplier)
    
    return filtered


def compute_trend_for_symbol(
    symbol: str,
    df: pd.DataFrame,
    price_col: str = "close"
) -> int:
    """
    Compute current (latest) trend state for a single symbol.
    
    Parameters
    ----------
    symbol : str
        Symbol identifier (for logging)
    df : pd.DataFrame
        OHLCV DataFrame with price history
    price_col : str
        Column name for price data
        
    Returns
    -------
    int
        Current trend state (1=ON, 0=OFF)
    """
    if df.empty or len(df) < SMA_LONG:
        # Not enough data for SMA200
        return TREND_OFF
    
    trend_series = compute_trend_state(df, price_col)
    return int(trend_series.iloc[-1])


def get_current_targets(
    base_targets: Dict[str, float] = None,
    verbose: bool = True
) -> Tuple[Dict[str, float], Dict[str, int], Dict[str, Dict]]:
    """
    Fetch current market data and compute Strategy 1 dynamic targets.
    
    This is the main entry point for getting live trend-filtered targets.
    
    Parameters
    ----------
    base_targets : Dict[str, float]
        Base target weights (default: BASE_TARGETS)
    verbose : bool
        Print progress and results (default: True)
        
    Returns
    -------
    Tuple[Dict[str, float], Dict[str, int], Dict[str, Dict]]
        - filtered_targets: Dynamic target weights based on current trend
        - trend_states: Current trend state per asset (1=ON, 0=OFF)
        - price_info: Price/SMA info per asset for display
        
    Example
    -------
    >>> targets, states, info = get_current_targets()
    >>> print(targets)
    {'BTCUSDT': 0.0, 'ETHUSDT': 0.0, 'SOLUSDT': 0.0, 'LINKUSDT': 0.0}  # All OFF
    """
    # Import here to avoid circular imports at module load
    from utils.data_fetcher import get_tradingview_ohlc
    
    if base_targets is None:
        base_targets = BASE_TARGETS
    
    trend_states = {}
    price_info = {}
    
    for symbol in base_targets.keys():
        if verbose:
            print(f"   Fetching {symbol}...", end=" ")
        
        try:
            df = get_tradingview_ohlc(
                symbol=symbol,
                exchange="BINANCE",
                n_bars=250  # ~1 year of daily data, enough for SMA200
            )
            
            if not df.empty and len(df) >= SMA_LONG:
                sma_50, sma_200, trend_series, close = get_trend_signals(df)
                
                current_state = int(trend_series.iloc[-1])
                trend_states[symbol] = current_state
                
                price_info[symbol] = {
                    'close': close.iloc[-1],
                    'sma50': sma_50.iloc[-1],
                    'sma200': sma_200.iloc[-1],
                }
                
                state_str = "ON" if current_state == 1 else "OFF"
                if verbose:
                    print(f"[{state_str}] ${close.iloc[-1]:,.0f}")
            else:
                if verbose:
                    print(f"[OFF] (insufficient data: {len(df)} bars)")
                trend_states[symbol] = TREND_OFF
                price_info[symbol] = {'close': 0, 'sma50': 0, 'sma200': 0}
                
        except Exception as e:
            if verbose:
                print(f"[OFF] (error: {e})")
            trend_states[symbol] = TREND_OFF
            price_info[symbol] = {'close': 0, 'sma50': 0, 'sma200': 0}
    
    # Get filtered targets based on trend states
    filtered_targets = get_filtered_targets(trend_states, base_targets)
    
    return filtered_targets, trend_states, price_info


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__file__).rsplit("core", 1)[0])
    
    from utils.data_fetcher import get_tradingview_ohlc
    
    print("\n" + "="*80)
    print(" [STRATEGY 1] Daily Trend Filter - Current Status")
    print("="*80)
    print(f" SMA Short: {SMA_SHORT} | SMA Long: {SMA_LONG}")
    print(f" Base Targets: {BASE_TARGETS}")
    print("-"*80)
    
    # Fetch data and compute trend for each asset
    trend_states = {}
    
    for symbol in BASE_TARGETS.keys():
        print(f"\n Fetching {symbol}...")
        try:
            df = get_tradingview_ohlc(
                symbol=symbol,
                exchange="BINANCE",
                n_bars=250  # ~1 year of daily data
            )
            
            if not df.empty and len(df) >= SMA_LONG:
                sma_50, sma_200, trend_series, close = get_trend_signals(df)
                
                current_state = int(trend_series.iloc[-1])
                current_close = close.iloc[-1]
                current_sma50 = sma_50.iloc[-1]
                current_sma200 = sma_200.iloc[-1]
                
                trend_states[symbol] = current_state
                state_str = "ON" if current_state == 1 else "OFF"
                
                print(f"   Close: ${current_close:,.2f}")
                print(f"   SMA50: ${current_sma50:,.2f} | SMA200: ${current_sma200:,.2f}")
                print(f"   Trend: [{state_str}]")
            else:
                print(f"   [WARN] Insufficient data ({len(df)} bars, need {SMA_LONG})")
                trend_states[symbol] = TREND_OFF
                
        except Exception as e:
            print(f"   [ERROR] {e}")
            trend_states[symbol] = TREND_OFF
    
    # Get filtered targets
    filtered = get_filtered_targets(trend_states)
    
    print("\n" + "-"*80)
    print(" FILTERED TARGETS (based on current trend):")
    print("-"*80)
    print(f"{'Asset':<12} {'Base':>10} {'Trend':>8} {'Filtered':>10}")
    print("-"*80)
    
    total = 0
    for symbol in BASE_TARGETS.keys():
        base = BASE_TARGETS[symbol]
        state = trend_states.get(symbol, 0)
        filt = filtered[symbol]
        state_str = "ON" if state == 1 else "OFF"
        total += filt
        
        print(f"{symbol:<12} {base:>9.0%} {state_str:>8} {filt:>9.0%}")
    
    print("-"*80)
    print(f"{'TOTAL':<12} {'100%':>10} {'':<8} {total:>9.0%}")
    print(f"{'CASH':<12} {'':<10} {'':<8} {1-total:>9.0%}")
    print("="*80)

