"""
analysis/backtest_simple.py
PyQuant Alexander - Simple Historical Backtest

Purpose: Evaluate historical profitability of Golden Cross strategy (SMA50/SMA200)
before deploying live capital.

Strategy: Golden Cross / Death Cross
- BUY Signal: SMA_50 crosses ABOVE SMA_200
- SELL Signal: SMA_50 crosses BELOW SMA_200
- Always LONG or NEUTRAL (no shorting)
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from typing import Dict, List, Tuple
from pathlib import Path


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
        
        # Rename Date column if it exists
        if 'Date' in df.columns:
            df.rename(columns={'Date': 'Date'}, inplace=True)
        
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

def calculate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate SMA50, SMA200 and trading signals.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Price data with 'Close' column
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with added columns: SMA50, SMA200, Signal, Position
    """
    df = df.copy()
    
    # Calculate moving averages
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    
    # Detect crossovers
    # Signal: 1 = BUY (SMA50 > SMA200), 0 = SELL (SMA50 < SMA200)
    df['Signal'] = (df['SMA50'] > df['SMA200']).astype(int)
    
    # Position: 1 = LONG, 0 = NEUTRAL
    # Use shift(1) to avoid lookahead bias (signal from previous day)
    df['Position'] = df['Signal'].shift(1).fillna(0)
    
    # Calculate returns
    df['Returns'] = df['Close'].pct_change()
    df['Strategy_Returns'] = df['Position'] * df['Returns']
    
    return df


def detect_crosses(df: pd.DataFrame) -> Tuple[int, int]:
    """
    Count number of golden crosses (BUY) and death crosses (SELL).
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with Signal column
        
    Returns:
    --------
    Tuple[int, int]
        (golden_crosses, death_crosses)
    """
    # Detect crossovers: when Signal changes
    signal_changes = df['Signal'].diff()
    
    # Golden Cross: Signal goes from 0 to 1 (SMA50 crosses above SMA200)
    golden_crosses = (signal_changes == 1).sum()
    
    # Death Cross: Signal goes from 1 to 0 (SMA50 crosses below SMA200)
    death_crosses = (signal_changes == -1).sum()
    
    return int(golden_crosses), int(death_crosses)


# =============================================================================
# BACKTEST SIMULATION
# =============================================================================

def backtest_strategy(df: pd.DataFrame, initial_capital: float, commission: float) -> Dict:
    """
    Simulate trading strategy with commissions.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with Strategy_Returns column
    initial_capital : float
        Starting capital
    commission : float
        Commission rate per trade (e.g., 0.001 for 0.1%)
        
    Returns:
    --------
    Dict
        Dictionary with backtest results
    """
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
        'num_trades': num_trades,
        'total_return': total_return,
        'final_equity': final_equity,
        'win_rate': win_rate,
        'trade_returns': trade_returns
    }


def backtest_buy_hold(df: pd.DataFrame, initial_capital: float) -> float:
    """
    Calculate buy and hold return.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Price data with 'Close' column
    initial_capital : float
        Starting capital
        
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
# REPORTING
# =============================================================================

def print_results(results: Dict[str, Dict], portfolio_total: Dict) -> None:
    """
    Print beautiful results table.
    
    Parameters:
    -----------
    results : Dict[str, Dict]
        Dictionary with results per asset
    portfolio_total : Dict
        Total portfolio results
    """
    print("\n" + "="*80)
    print(" " * 25 + "BACKTEST RESULTS")
    print("="*80)
    print(f"\nPeriod: {START_DATE} to {END_DATE}")
    print(f"Strategy: Golden Cross (SMA50/SMA200)")
    print(f"Initial Capital per Asset: ${INITIAL_CAPITAL:,.2f}")
    print(f"Commission Rate: {COMMISSION_RATE*100:.2f}% per trade\n")
    
    # Table header
    print(f"{'Ticker':<12} {'Trades':<8} {'Win Rate %':<12} {'Strategy %':<15} {'Buy&Hold %':<15}")
    print("-" * 80)
    
    # Table rows
    for ticker, result in results.items():
        trades = result['num_trades']
        win_rate = result['win_rate']
        strategy_return = result['total_return']
        buyhold_return = result['buyhold_return']
        
        # Color coding (simple text indicators)
        strategy_str = f"{strategy_return:>7.2f}%"
        buyhold_str = f"{buyhold_return:>7.2f}%"
        
        print(f"{ticker:<12} {trades:<8} {win_rate:>7.2f}%    {strategy_str:>15} {buyhold_str:>15}")
    
    print("-" * 80)
    
    # Portfolio totals
    print(f"\n{'PORTFOLIO TOTAL':<12} {portfolio_total['total_trades']:<8} "
          f"{portfolio_total['avg_win_rate']:>7.2f}%    "
          f"{portfolio_total['total_return']:>7.2f}%    "
          f"{portfolio_total['buyhold_return']:>7.2f}%")
    
    print("\n" + "="*80)
    print(f"Initial Portfolio Value: ${portfolio_total['initial_capital']:,.2f}")
    print(f"Final Portfolio Value: ${portfolio_total['final_value']:,.2f}")
    print(f"Total Return: {portfolio_total['total_return']:.2f}%")
    print(f"Buy & Hold Return: {portfolio_total['buyhold_return']:.2f}%")
    print("="*80 + "\n")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main backtest execution."""
    print("\n" + "="*80)
    print(" " * 20 + "PYQUANT ALEXANDER - HISTORICAL BACKTEST")
    print("="*80 + "\n")
    
    results = {}
    portfolio_initial = 0
    portfolio_final = 0
    total_trades = 0
    total_win_rates = []
    
    # Process each asset
    for ticker, name in ASSETS.items():
        print(f"\n{'='*80}")
        print(f"Processing: {ticker} ({name})")
        print(f"{'='*80}")
        
        # Fetch data
        df = fetch_data(ticker, START_DATE, END_DATE)
        
        if df.empty:
            print(f"⚠️  Skipping {ticker} (no data)")
            continue
        
        # Calculate signals
        df = calculate_signals(df)
        
        # Detect crosses
        golden_crosses, death_crosses = detect_crosses(df)
        print(f"Golden Crosses (BUY): {golden_crosses}")
        print(f"Death Crosses (SELL): {death_crosses}")
        
        # Backtest strategy
        strategy_result = backtest_strategy(df, INITIAL_CAPITAL, COMMISSION_RATE)
        
        # Backtest buy & hold
        buyhold_return = backtest_buy_hold(df, INITIAL_CAPITAL)
        
        # Store results
        results[ticker] = {
            'num_trades': strategy_result['num_trades'],
            'win_rate': strategy_result['win_rate'],
            'total_return': strategy_result['total_return'],
            'final_equity': strategy_result['final_equity'],
            'buyhold_return': buyhold_return
        }
        
        # Accumulate portfolio metrics
        portfolio_initial += INITIAL_CAPITAL
        portfolio_final += strategy_result['final_equity']
        total_trades += strategy_result['num_trades']
        if strategy_result['win_rate'] > 0:
            total_win_rates.append(strategy_result['win_rate'])
        
        print(f"\n✅ {ticker} Backtest Complete:")
        print(f"   Trades: {strategy_result['num_trades']}")
        print(f"   Win Rate: {strategy_result['win_rate']:.2f}%")
        print(f"   Strategy Return: {strategy_result['total_return']:.2f}%")
        print(f"   Buy & Hold Return: {buyhold_return:.2f}%")
    
    # Calculate portfolio totals
    portfolio_return = ((portfolio_final / portfolio_initial) - 1) * 100
    avg_win_rate = np.mean(total_win_rates) if total_win_rates else 0.0
    
    # Calculate buy & hold for portfolio (equal weighted)
    portfolio_buyhold = sum(r['buyhold_return'] for r in results.values()) / len(results) if results else 0.0
    
    portfolio_total = {
        'initial_capital': portfolio_initial,
        'final_value': portfolio_final,
        'total_return': portfolio_return,
        'total_trades': total_trades,
        'avg_win_rate': avg_win_rate,
        'buyhold_return': portfolio_buyhold
    }
    
    # Print final report
    print_results(results, portfolio_total)


if __name__ == "__main__":
    main()

