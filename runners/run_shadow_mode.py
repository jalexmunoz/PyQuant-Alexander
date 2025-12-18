# runners/run_shadow_mode.py
# v1.0.0 - Shadow Mode Daily Runner
#
# Purpose: Run Strategy 1 signals daily for shadow validation.
# NO actual trading - observation only.
#
# Usage: python runners/run_shadow_mode.py

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List

import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.strategies.trend_filter_strategy import (
    BASE_TARGETS,
    SMA_SHORT,
    SMA_LONG,
    TREND_ON,
    TREND_OFF,
)
from utils.data_fetcher import get_tradingview_ohlc
from utils.shadow_logger import ShadowLogger, SuggestedTrade

# =============================================================================
# CONFIGURATION
# =============================================================================

ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "LINKUSDT"]
PORTFOLIO_FILE = Path("Docs/portfolio_hot.csv")
USE_CACHE = False  # Always fetch fresh data for shadow mode


# =============================================================================
# DATA FUNCTIONS
# =============================================================================

def fetch_prices_and_smas() -> tuple[Dict[str, float], Dict[str, Dict[str, float]], bool]:
    """
    Fetch latest prices and calculate SMAs for all assets.
    
    Returns:
        Tuple of (prices_dict, sma_dict, success)
        - prices_dict: {symbol: close_price}
        - sma_dict: {symbol: {'sma50': value, 'sma200': value}}
        - success: True if all fetches succeeded
    """
    prices = {}
    smas = {}
    
    for symbol in ASSETS:
        try:
            df = get_tradingview_ohlc(
                symbol=symbol,
                exchange="BINANCE",
                n_bars=250,  # Need 200+ for SMA200
                use_cache=USE_CACHE
            )
            
            if df is None or df.empty:
                print(f"  [ERROR] No data for {symbol}")
                return {}, {}, False
            
            # Get latest close
            latest_close = float(df['close'].iloc[-1])
            prices[symbol] = latest_close
            
            # Calculate SMAs
            sma50 = float(df['close'].rolling(SMA_SHORT).mean().iloc[-1])
            sma200 = float(df['close'].rolling(SMA_LONG).mean().iloc[-1])
            
            smas[symbol] = {'sma50': sma50, 'sma200': sma200}
            
        except Exception as e:
            print(f"  [ERROR] Failed to fetch {symbol}: {e}")
            return {}, {}, False
    
    return prices, smas, True


def calculate_signals(smas: Dict[str, Dict[str, float]]) -> Dict[str, int]:
    """
    Calculate Strategy 1 signals based on SMA crossover.
    
    Signal = 1 (ON) if SMA50 > SMA200, else 0 (OFF)
    """
    signals = {}
    
    for symbol in ASSETS:
        sma_data = smas.get(symbol, {})
        sma50 = sma_data.get('sma50', 0)
        sma200 = sma_data.get('sma200', 0)
        
        signals[symbol] = TREND_ON if sma50 > sma200 else TREND_OFF
    
    return signals


def calculate_targets(signals: Dict[str, int]) -> Dict[str, float]:
    """
    Calculate target weights based on signals.
    
    Target = base_weight if signal ON, else 0
    """
    targets = {}
    
    for symbol in ASSETS:
        base_weight = BASE_TARGETS.get(symbol, 0.0)
        signal = signals.get(symbol, 0)
        targets[symbol] = base_weight if signal == TREND_ON else 0.0
    
    return targets


def load_current_portfolio() -> Dict[str, float]:
    """
    Load current portfolio weights from Docs/portfolio_hot.csv.
    
    Returns base targets if file doesn't exist.
    
    Expected CSV format:
        symbol,weight
        BTCUSDT,0.40
        ETHUSDT,0.40
        ...
    """
    if not PORTFOLIO_FILE.exists():
        print(f"  [INFO] {PORTFOLIO_FILE} not found, using base targets")
        return BASE_TARGETS.copy()
    
    try:
        df = pd.read_csv(PORTFOLIO_FILE)
        portfolio = {}
        
        for _, row in df.iterrows():
            symbol = row.get('symbol', '')
            weight = float(row.get('weight', 0))
            if symbol in ASSETS:
                portfolio[symbol] = weight
        
        # Fill missing assets with 0
        for symbol in ASSETS:
            if symbol not in portfolio:
                portfolio[symbol] = 0.0
        
        return portfolio
        
    except Exception as e:
        print(f"  [WARN] Failed to read {PORTFOLIO_FILE}: {e}")
        return BASE_TARGETS.copy()


def calculate_suggested_trades(
    targets: Dict[str, float],
    current: Dict[str, float],
    threshold: float = 0.01
) -> List[SuggestedTrade]:
    """
    Calculate suggested trades to align portfolio with targets.
    
    Parameters:
        targets: Target weights
        current: Current portfolio weights
        threshold: Minimum difference to suggest trade (1% default)
    
    Returns:
        List of SuggestedTrade objects
    """
    trades = []
    
    for symbol in ASSETS:
        target_w = targets.get(symbol, 0.0)
        current_w = current.get(symbol, 0.0)
        diff = target_w - current_w
        
        if abs(diff) >= threshold:
            action = "BUY" if diff > 0 else "SELL"
            trades.append(SuggestedTrade(
                asset=symbol.replace("USDT", ""),
                action=action,
                amount=abs(diff),
                reason=f"Target {target_w*100:.0f}% vs Current {current_w*100:.0f}%"
            ))
    
    return trades


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_shadow_mode() -> bool:
    """
    Run shadow mode for today.
    
    Returns True if successful.
    """
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M')
    
    print()
    print("=" * 50)
    print(f" SHADOW MODE - {date_str} {time_str}")
    print("=" * 50)
    
    # 1. Fetch data
    print("\nFetching data...")
    prices, smas, success = fetch_prices_and_smas()
    
    if not success:
        print("\nData Fetch: FAILED")
        print("Status: DATA_ERROR - Skipping signal generation")
        print("=" * 50)
        return False
    
    print("Data Fetch: OK")
    
    # 2. Calculate signals
    signals = calculate_signals(smas)
    
    print("\nSignals:")
    for symbol in ASSETS:
        signal = signals[symbol]
        sma_data = smas[symbol]
        signal_str = "ON " if signal == TREND_ON else "OFF"
        compare = ">" if signal == TREND_ON else "<"
        short_name = symbol.replace("USDT", "")
        print(f"  {short_name}: {signal_str} (SMA{SMA_SHORT}: {sma_data['sma50']:.0f} {compare} SMA{SMA_LONG}: {sma_data['sma200']:.0f})")
    
    # 3. Calculate targets
    targets = calculate_targets(signals)
    total_exposure = sum(targets.values())
    cash_weight = 1.0 - total_exposure
    
    print(f"\nTargets: ", end="")
    target_strs = []
    for symbol in ASSETS:
        short_name = symbol.replace("USDT", "")
        target_strs.append(f"{short_name} {targets[symbol]*100:.0f}%")
    print(" | ".join(target_strs))
    print(f"Exposure: {total_exposure*100:.0f}%")
    
    # 4. Load current portfolio and calculate suggested trades
    current_portfolio = load_current_portfolio()
    suggested_trades = calculate_suggested_trades(targets, current_portfolio)
    
    print(f"\nSuggested Trades: ", end="")
    if suggested_trades:
        print()
        for trade in suggested_trades:
            print(f"  {trade.action} {trade.asset}: {trade.amount*100:.1f}%")
    else:
        print("None (already aligned)")
    
    # 5. Log to CSV
    print()
    try:
        logger = ShadowLogger()
        log_path = logger.log_from_data(
            prices=prices,
            signals=signals,
            sma_values=smas,
            base_weights=BASE_TARGETS,
            suggested_trades=suggested_trades if suggested_trades else None
        )
        print(f"Logged: {log_path}")
    except Exception as e:
        print(f"[ERROR] Failed to write log: {e}")
    
    print("=" * 50)
    print()
    
    return True


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    success = run_shadow_mode()
    sys.exit(0 if success else 1)

