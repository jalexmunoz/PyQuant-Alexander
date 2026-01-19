"""
analysis/optimize_strategy.py
PyQuant Alexander - Strategy Parameter Optimization

Purpose: Find optimal Fast/Slow moving average combination for Golden Cross strategy
that maximizes returns for crypto assets.

Optimization: Grid search over Fast MA [10, 20, 30, 50] and Slow MA [50, 100, 150, 200]
where Fast < Slow.

Strategy: Golden Cross / Death Cross
- BUY Signal: Fast MA crosses ABOVE Slow MA
- SELL Signal: Fast MA crosses BELOW Slow MA
- Always LONG or NEUTRAL (no shorting)
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from typing import Dict, List, Tuple
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

START_DATE = "2020-01-01"
END_DATE = datetime.now().strftime("%Y-%m-%d")
INITIAL_CAPITAL = 10000  # USD per asset
COMMISSION_RATE = 0.001  # 0.1% per trade

# Parameter ranges for optimization
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
        DataFrame with columns: Date, Open, High, Low, Close, Volume
    """
    print(f"📥 Fetching data for {ticker}...")
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
# STRATEGY LOGIC (Parameterized)
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
    # Use shift(1) to avoid lookahead bias (signal from previous day)
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
    # Identify winning and losing trades
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

def optimize_asset(
    ticker: str, 
    df: pd.DataFrame,
    fast_range: List[int],
    slow_range: List[int],
    initial_capital: float,
    commission: float
) -> Tuple[Dict, float]:
    """
    Optimize MA parameters for a single asset.
    
    Parameters:
    -----------
    ticker : str
        Asset ticker
    df : pd.DataFrame
        Price data
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
    print(f"\n🔍 Optimizing {ticker}...")
    print(f"   Testing {len(fast_range)} x {len(slow_range)} = {len(fast_range) * len(slow_range)} combinations")
    
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


# =============================================================================
# REPORTING
# =============================================================================

def print_results(results: Dict[str, Tuple[Dict, float]]) -> None:
    """
    Print optimization results in beautiful format.
    
    Parameters:
    -----------
    results : Dict[str, Tuple[Dict, float]]
        Dictionary mapping ticker to (best_result, buyhold_return)
    """
    print("\n" + "="*80)
    print(" " * 20 + "OPTIMIZATION RESULTS")
    print("="*80)
    print(f"\nPeriod: {START_DATE} to {END_DATE}")
    print(f"Strategy: Golden Cross (Fast MA / Slow MA)")
    print(f"Parameter Ranges:")
    print(f"  Fast MA: {FAST_MA_RANGE}")
    print(f"  Slow MA: {SLOW_MA_RANGE}")
    print(f"Initial Capital per Asset: ${INITIAL_CAPITAL:,.2f}")
    print(f"Commission Rate: {COMMISSION_RATE*100:.2f}% per trade\n")
    
    print("="*80)
    print("🏆 BEST COMBINATIONS PER ASSET")
    print("="*80 + "\n")
    
    # Print best combination for each asset
    for ticker, (best_result, buyhold_return) in results.items():
        if not best_result:
            print(f"⚠️  {ticker}: No valid results")
            continue
        
        fast_ma = best_result['fast_ma']
        slow_ma = best_result['slow_ma']
        strategy_return = best_result['total_return']
        win_rate = best_result['win_rate']
        num_trades = best_result['num_trades']
        
        # Calculate improvement over buy & hold
        improvement = strategy_return - buyhold_return
        improvement_pct = ((strategy_return + 100) / (buyhold_return + 100) - 1) * 100 if buyhold_return != -100 else 0
        
        print(f"🏆 Mejor para {ticker}:")
        print(f"   SMA {fast_ma} / SMA {slow_ma}")
        print(f"   Retorno Estrategia: {strategy_return:>8.2f}%")
        print(f"   Retorno Buy & Hold: {buyhold_return:>8.2f}%")
        print(f"   Mejora vs B&H:      {improvement:>8.2f}% ({improvement_pct:+.2f}% relativo)")
        print(f"   Win Rate:           {win_rate:>8.2f}%")
        print(f"   Trades Totales:     {num_trades:>8}")
        print()
    
    print("="*80)
    
    # Summary statistics
    strategy_returns = [r[0]['total_return'] for r in results.values() if r[0]]
    buyhold_returns = [r[1] for r in results.values()]
    
    if strategy_returns:
        avg_strategy = np.mean(strategy_returns)
        avg_buyhold = np.mean(buyhold_returns)
        
        print(f"\n📊 SUMMARY:")
        print(f"   Average Strategy Return: {avg_strategy:>8.2f}%")
        print(f"   Average Buy & Hold:      {avg_buyhold:>8.2f}%")
        print(f"   Average Improvement:     {avg_strategy - avg_buyhold:>8.2f}%")
        print()
    
    print("="*80 + "\n")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main optimization execution."""
    print("\n" + "="*80)
    print(" " * 15 + "PYQUANT ALEXANDER - STRATEGY OPTIMIZATION")
    print("="*80 + "\n")
    
    print("Configuration:")
    print(f"  Assets: {list(ASSETS.keys())}")
    print(f"  Fast MA Range: {FAST_MA_RANGE}")
    print(f"  Slow MA Range: {SLOW_MA_RANGE}")
    print(f"  Period: {START_DATE} to {END_DATE}\n")
    
    results = {}
    
    # Process each asset
    for ticker, name in ASSETS.items():
        print(f"\n{'='*80}")
        print(f"Processing: {ticker} ({name})")
        print(f"{'='*80}")
        
        # Fetch data
        df = fetch_data(ticker, START_DATE, END_DATE)
        
        if df.empty:
            print(f"⚠️  Skipping {ticker} (no data)")
            results[ticker] = ({}, 0.0)
            continue
        
        # Optimize parameters
        best_result, buyhold_return = optimize_asset(
            ticker=ticker,
            df=df,
            fast_range=FAST_MA_RANGE,
            slow_range=SLOW_MA_RANGE,
            initial_capital=INITIAL_CAPITAL,
            commission=COMMISSION_RATE
        )
        
        results[ticker] = (best_result, buyhold_return)
        
        if best_result:
            print(f"\n✅ {ticker} Optimization Complete:")
            print(f"   Best: SMA {best_result['fast_ma']} / SMA {best_result['slow_ma']}")
            print(f"   Return: {best_result['total_return']:.2f}% (vs {buyhold_return:.2f}% Buy & Hold)")
    
    # Print final report
    print_results(results)


if __name__ == "__main__":
    main()

