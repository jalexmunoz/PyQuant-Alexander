"""
analysis/walk_forward_test.py
PyQuant Alexander - Walk-Forward Validation Test

Purpose: Validate that optimized MA parameters are robust and not overfitted
by testing them on out-of-sample data.

Methodology:
1. Training Period: 2020-01-01 to 2023-12-31 (optimize parameters)
2. Validation Period: 2024-01-01 to today (test with fixed parameters)
3. Robustness Criteria: Validation return > 0 AND >= 50% of training efficiency
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from itertools import product


# =============================================================================
# CONFIGURATION
# =============================================================================

ASSETS = {
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "SOL-USD": "Solana",
    "LINK-USD": "Chainlink"
}

TRAINING_START = "2020-01-01"
TRAINING_END = "2023-12-31"
VALIDATION_START = "2024-01-01"
VALIDATION_END = datetime.now().strftime("%Y-%m-%d")

INITIAL_CAPITAL = 10000  # USD per asset
COMMISSION_RATE = 0.001  # 0.1% per trade

# Parameter ranges for optimization (same as optimize_strategy.py)
FAST_MA_RANGE = [10, 20, 30, 50]
SLOW_MA_RANGE = [50, 100, 150, 200]


# =============================================================================
# DATA FETCHING
# =============================================================================

def fetch_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    Fetch historical price data using yfinance.
    
    Parameters:
    -----------
    ticker : str
        Yahoo Finance ticker symbol
    start : str
        Start date (YYYY-MM-DD)
    end : str
        End date (YYYY-MM-DD)
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with Close price column
    """
    print(f"📥 Fetching data for {ticker} ({start} to {end})...")
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(start=start, end=end)
        
        if df.empty:
            print(f"⚠️  No data available for {ticker}")
            return pd.DataFrame()
        
        # Reset index to make Date a column
        df.reset_index(inplace=True)
        
        # Ensure we have Close price
        if 'Close' not in df.columns:
            print(f"❌ No 'Close' price data for {ticker}")
            return pd.DataFrame()
        
        print(f"✅ Loaded {len(df)} days of data for {ticker}")
        return df
        
    except Exception as e:
        print(f"❌ Error fetching {ticker}: {e}")
        return pd.DataFrame()


# =============================================================================
# STRATEGY LOGIC
# =============================================================================

def calculate_signals(df: pd.DataFrame, fast_ma: int, slow_ma: int) -> pd.DataFrame:
    """
    Calculate Fast MA, Slow MA and trading signals.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Price data with 'Close' column
    fast_ma : int
        Fast moving average period
    slow_ma : int
        Slow moving average period
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with added columns: FastMA, SlowMA, Signal, Position
    """
    df = df.copy()
    
    # Calculate moving averages
    df['FastMA'] = df['Close'].rolling(window=fast_ma).mean()
    df['SlowMA'] = df['Close'].rolling(window=slow_ma).mean()
    
    # Detect crossovers
    # Signal: 1 = BUY (FastMA > SlowMA), 0 = SELL (FastMA < SlowMA)
    df['Signal'] = (df['FastMA'] > df['SlowMA']).astype(int)
    
    # Position: 1 = LONG, 0 = NEUTRAL
    # Use shift(1) to avoid lookahead bias
    df['Position'] = df['Signal'].shift(1).fillna(0)
    
    # Calculate returns
    df['Returns'] = df['Close'].pct_change()
    df['Strategy_Returns'] = df['Position'] * df['Returns']
    
    return df


def backtest_strategy(
    df: pd.DataFrame, 
    fast_ma: int, 
    slow_ma: int, 
    initial_capital: float, 
    commission: float
) -> Dict:
    """
    Simulate trading strategy with commissions for given MA parameters.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Price data
    fast_ma : int
        Fast moving average period
    slow_ma : int
        Slow moving average period
    initial_capital : float
        Starting capital
    commission : float
        Commission rate per trade (e.g., 0.001 for 0.1%)
        
    Returns:
    --------
    Dict
        Dictionary with backtest results
    """
    # Calculate signals with given parameters
    df = calculate_signals(df, fast_ma, slow_ma)
    
    # Skip if not enough data for slow MA
    if df['SlowMA'].isna().sum() == len(df):
        return {
            'total_return': -100.0,
            'win_rate': 0.0,
            'num_trades': 0,
            'final_equity': 0.0
        }
    
    # Get position changes (trades)
    position_changes = df['Position'].diff().abs()
    num_trades = int(position_changes.sum())
    
    # Calculate cumulative strategy returns (excluding commissions)
    df['Cumulative_Strategy'] = (1 + df['Strategy_Returns']).cumprod()
    
    # Apply commissions
    # Each trade costs commission on both entry and exit
    commission_cost = num_trades * commission * 2  # Entry + Exit
    
    # Final equity
    final_equity = initial_capital * df['Cumulative_Strategy'].iloc[-1] * (1 - commission_cost)
    total_return = (final_equity / initial_capital - 1) * 100
    
    # Calculate win rate
    trade_returns = []
    in_position = False
    entry_price = None
    
    for i in range(1, len(df)):
        prev_pos = df['Position'].iloc[i-1]
        curr_pos = df['Position'].iloc[i]
        price = df['Close'].iloc[i]
        
        # Entry
        if prev_pos == 0 and curr_pos == 1:
            in_position = True
            entry_price = price
        
        # Exit
        elif prev_pos == 1 and curr_pos == 0 and in_position:
            if entry_price is not None:
                trade_return = (price / entry_price - 1) * 100
                trade_returns.append(trade_return)
            in_position = False
            entry_price = None
    
    # Calculate win rate
    if trade_returns:
        winning_trades = sum(1 for r in trade_returns if r > 0)
        win_rate = (winning_trades / len(trade_returns)) * 100
    else:
        win_rate = 0.0
    
    return {
        'total_return': total_return,
        'win_rate': win_rate,
        'num_trades': num_trades,
        'final_equity': final_equity
    }


def calculate_buyhold_return(df: pd.DataFrame) -> float:
    """
    Calculate buy and hold return.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Price data with 'Close' column
        
    Returns:
    --------
    float
        Total return percentage
    """
    if len(df) < 2:
        return 0.0
    
    first_price = df['Close'].iloc[0]
    last_price = df['Close'].iloc[-1]
    
    return ((last_price / first_price) - 1) * 100


# =============================================================================
# OPTIMIZATION ENGINE
# =============================================================================

def optimize_asset_training(
    ticker: str, 
    df: pd.DataFrame,
    fast_range: List[int],
    slow_range: List[int],
    initial_capital: float,
    commission: float
) -> Tuple[Dict, float]:
    """
    Optimize MA parameters for training period.
    
    Parameters:
    -----------
    ticker : str
        Asset ticker
    df : pd.DataFrame
        Price data (training period)
    fast_range : List[int]
        Range of Fast MA periods to test
    slow_range : List[int]
        Range of Slow MA periods to test
    initial_capital : float
        Starting capital
    commission : float
        Commission rate per trade
        
    Returns:
    --------
    Tuple[Dict, float]
        (best_result_dict, buyhold_return)
    """
    print(f"🔍 Optimizing {ticker} on training period...")
    
    # Calculate buy & hold return for comparison
    buyhold_return = calculate_buyhold_return(df)
    
    # Store all results
    all_results = []
    
    # Test all valid combinations (Fast < Slow)
    valid_combinations = 0
    for fast_ma, slow_ma in product(fast_range, slow_range):
        if fast_ma >= slow_ma:
            continue  # Skip invalid combinations
        
        valid_combinations += 1
        result = backtest_strategy(df, fast_ma, slow_ma, initial_capital, commission)
        
        all_results.append({
            'fast_ma': fast_ma,
            'slow_ma': slow_ma,
            'total_return': result['total_return'],
            'win_rate': result['win_rate'],
            'num_trades': result['num_trades'],
            'final_equity': result['final_equity']
        })
    
    print(f"   Tested {valid_combinations} valid combinations")
    
    # Find best result based on total return
    if not all_results:
        print(f"⚠️  No valid results for {ticker}")
        return {}, buyhold_return
    
    best_result = max(all_results, key=lambda x: x['total_return'])
    
    return best_result, buyhold_return


def test_validation_period(
    ticker: str,
    df: pd.DataFrame,
    fast_ma: int,
    slow_ma: int,
    initial_capital: float,
    commission: float
) -> Tuple[Dict, float]:
    """
    Test fixed parameters on validation period.
    
    Parameters:
    -----------
    ticker : str
        Asset ticker
    df : pd.DataFrame
        Price data (validation period)
    fast_ma : int
        Fast MA period (from training optimization)
    slow_ma : int
        Slow MA period (from training optimization)
    initial_capital : float
        Starting capital
    commission : float
        Commission rate per trade
        
    Returns:
    --------
    Tuple[Dict, float]
        (validation_result_dict, buyhold_return)
    """
    print(f"🧪 Testing {ticker} on validation period with SMA {fast_ma}/{slow_ma}...")
    
    # Calculate buy & hold return
    buyhold_return = calculate_buyhold_return(df)
    
    # Test with fixed parameters
    result = backtest_strategy(df, fast_ma, slow_ma, initial_capital, commission)
    
    return result, buyhold_return


# =============================================================================
# ROBUSTNESS ANALYSIS
# =============================================================================

def is_robust(training_return: float, validation_return: float) -> Tuple[bool, str]:
    """
    Determine if strategy is robust based on walk-forward results.
    
    Robustness Criteria:
    1. Validation return must be positive
    2. Validation return must be >= 50% of training return efficiency
    
    Parameters:
    -----------
    training_return : float
        Return percentage from training period
    validation_return : float
        Return percentage from validation period
        
    Returns:
    --------
    Tuple[bool, str]
        (is_robust, explanation)
    """
    if validation_return <= 0:
        return False, "Validation return is negative or zero"
    
    # Calculate efficiency ratio
    if training_return > 0:
        efficiency_ratio = validation_return / training_return
        if efficiency_ratio >= 0.5:
            return True, f"Validation maintains {efficiency_ratio*100:.1f}% of training efficiency"
        else:
            return False, f"Validation only maintains {efficiency_ratio*100:.1f}% of training efficiency (< 50%)"
    elif training_return <= 0 and validation_return > 0:
        # Training was negative but validation is positive - this is actually good
        return True, "Validation improved over negative training period"
    else:
        return False, "Both periods negative"


# =============================================================================
# REPORTING
# =============================================================================

def print_results(results: Dict[str, Dict]) -> None:
    """
    Print walk-forward validation results.
    
    Parameters:
    -----------
    results : Dict[str, Dict]
        Dictionary mapping ticker to walk-forward results
    """
    print("\n" + "="*90)
    print(" " * 25 + "WALK-FORWARD VALIDATION RESULTS")
    print("="*90)
    print(f"\nTraining Period: {TRAINING_START} to {TRAINING_END}")
    print(f"Validation Period: {VALIDATION_START} to {VALIDATION_END}")
    print(f"Initial Capital per Asset: ${INITIAL_CAPITAL:,.2f}")
    print(f"Commission Rate: {COMMISSION_RATE*100:.2f}% per trade\n")
    
    print("="*90)
    print(f"{'Ticker':<12} {'Best MA':<12} {'Train Return':<15} {'Valid Return':<15} {'Robust?':<10} {'Reason'}")
    print("-"*90)
    
    for ticker, result in results.items():
        if not result or 'best_params' not in result:
            print(f"{ticker:<12} {'N/A':<12} {'N/A':<15} {'N/A':<15} {'NO':<10} {'No valid results'}")
            continue
        
        best_params = result['best_params']
        training_return = result['training_return']
        validation_return = result['validation_return']
        is_robust_flag, reason = result['is_robust']
        
        ma_str = f"SMA {best_params['fast_ma']}/{best_params['slow_ma']}"
        train_str = f"{training_return:>7.2f}%"
        valid_str = f"{validation_return:>7.2f}%"
        robust_str = "✅ SÍ" if is_robust_flag else "❌ NO"
        
        print(f"{ticker:<12} {ma_str:<12} {train_str:<15} {valid_str:<15} {robust_str:<10} {reason}")
    
    print("-"*90)
    
    # Summary statistics
    robust_count = sum(1 for r in results.values() if r and r.get('is_robust', (False,))[0])
    total_count = len([r for r in results.values() if r and 'best_params' in r])
    
    print(f"\n📊 SUMMARY:")
    print(f"   Robust Strategies: {robust_count}/{total_count}")
    if total_count > 0:
        robust_pct = (robust_count / total_count) * 100
        print(f"   Robustness Rate: {robust_pct:.1f}%")
    print()
    print("="*90 + "\n")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main walk-forward validation execution."""
    print("\n" + "="*90)
    print(" " * 20 + "PYQUANT ALEXANDER - WALK-FORWARD VALIDATION")
    print("="*90 + "\n")
    
    print("Configuration:")
    print(f"  Assets: {list(ASSETS.keys())}")
    print(f"  Training: {TRAINING_START} to {TRAINING_END}")
    print(f"  Validation: {VALIDATION_START} to {VALIDATION_END}")
    print(f"  Fast MA Range: {FAST_MA_RANGE}")
    print(f"  Slow MA Range: {SLOW_MA_RANGE}\n")
    
    results = {}
    
    # Process each asset
    for ticker, name in ASSETS.items():
        print(f"\n{'='*90}")
        print(f"Processing: {ticker} ({name})")
        print(f"{'='*90}")
        
        # Fetch training data
        training_df = fetch_data(ticker, TRAINING_START, TRAINING_END)
        if training_df.empty:
            print(f"⚠️  Skipping {ticker} (no training data)")
            results[ticker] = {}
            continue
        
        # Fetch validation data
        validation_df = fetch_data(ticker, VALIDATION_START, VALIDATION_END)
        if validation_df.empty:
            print(f"⚠️  Skipping {ticker} (no validation data)")
            results[ticker] = {}
            continue
        
        # STEP 1: Optimize on training period
        print(f"\n📊 STEP 1: Optimizing on Training Period...")
        best_result, training_buyhold = optimize_asset_training(
            ticker=ticker,
            df=training_df,
            fast_range=FAST_MA_RANGE,
            slow_range=SLOW_MA_RANGE,
            initial_capital=INITIAL_CAPITAL,
            commission=COMMISSION_RATE
        )
        
        if not best_result:
            print(f"⚠️  No valid optimization results for {ticker}")
            results[ticker] = {}
            continue
        
        print(f"\n✅ Best parameters found:")
        print(f"   SMA {best_result['fast_ma']}/{best_result['slow_ma']}")
        print(f"   Training Return: {best_result['total_return']:.2f}%")
        print(f"   Training Buy & Hold: {training_buyhold:.2f}%")
        
        # STEP 2: Test on validation period with fixed parameters
        print(f"\n📊 STEP 2: Testing on Validation Period (Out-of-Sample)...")
        validation_result, validation_buyhold = test_validation_period(
            ticker=ticker,
            df=validation_df,
            fast_ma=best_result['fast_ma'],
            slow_ma=best_result['slow_ma'],
            initial_capital=INITIAL_CAPITAL,
            commission=COMMISSION_RATE
        )
        
        print(f"\n✅ Validation results:")
        print(f"   Validation Return: {validation_result['total_return']:.2f}%")
        print(f"   Validation Buy & Hold: {validation_buyhold:.2f}%")
        
        # STEP 3: Determine robustness
        is_robust_flag, reason = is_robust(
            best_result['total_return'],
            validation_result['total_return']
        )
        
        print(f"\n📊 STEP 3: Robustness Analysis...")
        print(f"   Is Robust? {'✅ SÍ' if is_robust_flag else '❌ NO'}")
        print(f"   Reason: {reason}")
        
        # Store results
        results[ticker] = {
            'best_params': {
                'fast_ma': best_result['fast_ma'],
                'slow_ma': best_result['slow_ma']
            },
            'training_return': best_result['total_return'],
            'validation_return': validation_result['total_return'],
            'training_buyhold': training_buyhold,
            'validation_buyhold': validation_buyhold,
            'is_robust': (is_robust_flag, reason)
        }
    
    # Print final report
    print_results(results)


if __name__ == "__main__":
    main()

