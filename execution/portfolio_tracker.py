# execution/portfolio_tracker.py
# v1.2.0 - Multi-Wallet Portfolio Tracker
#
# Purpose: Consolidate portfolio across wallets, fetch live prices,
# calculate weighted average cost, and display clean summary.
# Supports manual prices for exotic tokens not on major exchanges.

import pandas as pd
import logging
import time
from typing import Tuple, Optional, Dict
from pathlib import Path

# Import TradingView fetcher
from utils.data_fetcher import get_tradingview_ohlc

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


# =============================================================================
# CONFIGURATION
# =============================================================================

# Symbol mapping: Local symbol -> TradingView/Binance symbol
# None = Manual price required (not on major exchanges)
SYMBOL_MAP: Dict[str, Optional[str]] = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "LINK": "LINKUSDT",
    "HBAR": "HBARUSDT",
    "JUP": "JUPUSDT",
    "PEPE": "1000PEPEUSDT",  # Binance lists it as 1000PEPE
    "BAS": None,      # Manual price required - not on major exchanges
    "SWTCH": None,    # Manual price required - not on major exchanges
    "USDT": None      # Stablecoin - use $1.00 or skip
}

# Default CSV path
DEFAULT_CSV_PATH = "Docs/portfolio_hot.csv"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


# =============================================================================
# DATA LOADING & AGGREGATION
# =============================================================================

def load_portfolio_raw(csv_path: str) -> pd.DataFrame:
    """
    Load raw portfolio data from CSV.
    
    Parameters
    ----------
    csv_path : str
        Path to the portfolio CSV file
        
    Returns
    -------
    pd.DataFrame
        Raw portfolio data with all rows
    """
    df = pd.read_csv(csv_path)
    
    # Clean column names
    df.columns = df.columns.str.strip()
    
    # Ensure numeric columns are properly typed
    numeric_cols = ['Quantity', 'Total Cost (USD)', 'Avg Cost (USD)', 'Price (USD)']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    return df


def aggregate_by_symbol(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate portfolio by symbol across all wallets.
    Calculates TRUE weighted average cost.
    Also aggregates manual prices (uses last non-zero value).
    
    Parameters
    ----------
    df_raw : pd.DataFrame
        Raw portfolio data
        
    Returns
    -------
    pd.DataFrame
        Aggregated portfolio with one row per symbol
    """
    # Group by symbol
    aggregated = df_raw.groupby('Symbol').agg({
        'Quantity': 'sum',
        'Total Cost (USD)': 'sum',
        'Price (USD)': 'max',  # Take the max (usually last entered) manual price
    }).reset_index()
    
    # Calculate TRUE weighted average cost
    # WAC = Total Cost / Total Quantity
    aggregated['avg_cost'] = aggregated.apply(
        lambda row: row['Total Cost (USD)'] / row['Quantity'] 
        if row['Quantity'] > 0 else 0,
        axis=1
    )
    
    # Rename columns for clarity
    aggregated.columns = ['symbol', 'quantity', 'total_cost', 'manual_price', 'avg_cost']
    
    return aggregated


def get_wallet_breakdown(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Get breakdown of positions by wallet (for detailed view).
    
    Parameters
    ----------
    df_raw : pd.DataFrame
        Raw portfolio data
        
    Returns
    -------
    pd.DataFrame
        Position details by wallet
    """
    return df_raw[['Symbol', 'Quantity', 'Total Cost (USD)', 'Avg Cost (USD)', 'Wallet']].copy()


# =============================================================================
# PRICE FETCHING
# =============================================================================

def fetch_current_prices(symbols: list) -> Tuple[Dict[str, float], list]:
    """
    Fetch current prices from TradingView for given symbols.
    Includes retry logic for WebSocket errors.
    
    Parameters
    ----------
    symbols : list
        List of local symbols (e.g., ["BTC", "ETH"])
        
    Returns
    -------
    Tuple[Dict[str, float], list]
        (Mapping of symbol -> current price, list of symbols needing manual price)
    """
    prices = {}
    needs_manual = []
    
    for symbol in symbols:
        tv_symbol = SYMBOL_MAP.get(symbol)
        
        # Check if symbol needs manual price
        if tv_symbol is None:
            logging.debug(f"[INFO] {symbol} - needs manual price (not on major exchanges)")
            needs_manual.append(symbol)
            continue
        
        # Retry logic for WebSocket errors
        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Fetch just the latest bar
                df = get_tradingview_ohlc(
                    symbol=tv_symbol,
                    exchange="BINANCE",
                    n_bars=1
                )
                
                if not df.empty:
                    current_price = df['close'].iloc[-1]
                    
                    # Handle PEPE special case (1000PEPE -> divide by 1000)
                    if symbol == "PEPE":
                        current_price = current_price / 1000
                        
                    prices[symbol] = current_price
                    logging.debug(f"[OK] {symbol}: ${current_price:,.6f}")
                    success = True
                    break  # Success, exit retry loop
                else:
                    # No data returned - might need retry
                    if attempt < MAX_RETRIES:
                        logging.warning(f"[WARN] {symbol} attempt {attempt}/{MAX_RETRIES}: No data. Retrying in {RETRY_DELAY}s...")
                        time.sleep(RETRY_DELAY)
                    else:
                        logging.warning(f"[WARN] {symbol}: No price data after {MAX_RETRIES} attempts. Will use manual price if available.")
                        needs_manual.append(symbol)
                    
            except Exception as e:
                if attempt < MAX_RETRIES:
                    logging.warning(f"[WARN] {symbol} attempt {attempt}/{MAX_RETRIES} failed: {e}. Retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                else:
                    logging.warning(f"[WARN] {symbol} failed after {MAX_RETRIES} attempts. Will use manual price if available.")
                    needs_manual.append(symbol)
    
    return prices, needs_manual


# =============================================================================
# PORTFOLIO CALCULATIONS
# =============================================================================

def calculate_portfolio_metrics(
    df_agg: pd.DataFrame, 
    prices: Dict[str, float],
    needs_manual: list
) -> Tuple[pd.DataFrame, pd.DataFrame, float]:
    """
    Calculate portfolio metrics: value, P&L, weight.
    Uses manual prices for assets without live data.
    
    Parameters
    ----------
    df_agg : pd.DataFrame
        Aggregated portfolio data
    prices : Dict[str, float]
        Current prices by symbol (from TradingView)
    needs_manual : list
        Symbols that need manual price
        
    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame, float]
        (Portfolio with live prices, Portfolio with manual/missing prices, total_equity)
    """
    df = df_agg.copy()
    
    # Determine price source for each asset
    df['price_source'] = 'live'
    df['current_price'] = df['symbol'].map(prices)
    
    # For assets without live price, try manual price
    mask_no_live = df['current_price'].isna()
    df.loc[mask_no_live, 'current_price'] = df.loc[mask_no_live, 'manual_price']
    df.loc[mask_no_live, 'price_source'] = 'manual'
    
    # Mark assets with no price at all
    mask_no_price = (df['current_price'].isna()) | (df['current_price'] == 0)
    df.loc[mask_no_price, 'price_source'] = 'missing'
    
    # Calculate metrics for assets with prices
    df['current_value'] = df['quantity'] * df['current_price'].fillna(0)
    df['pnl_usd'] = df['current_value'] - df['total_cost']
    df['pnl_pct'] = df.apply(
        lambda row: ((row['current_price'] / row['avg_cost']) - 1) * 100 
        if row['avg_cost'] > 0 and row['current_price'] > 0 else 0,
        axis=1
    )
    
    # Calculate total equity (only from assets with valid prices)
    total_equity = df[df['price_source'] != 'missing']['current_value'].sum()
    
    # Calculate weight
    df['weight'] = df.apply(
        lambda row: row['current_value'] / total_equity if total_equity > 0 and row['price_source'] != 'missing' else 0,
        axis=1
    )
    
    # Split into live/manual and missing
    df_priced = df[df['price_source'] != 'missing'].sort_values('weight', ascending=False).reset_index(drop=True)
    df_missing = df[df['price_source'] == 'missing'].reset_index(drop=True)
    
    return df_priced, df_missing, total_equity


# =============================================================================
# MAIN FUNCTIONS
# =============================================================================

def get_portfolio_summary(
    csv_path: str = DEFAULT_CSV_PATH
) -> Tuple[pd.DataFrame, pd.DataFrame, float]:
    """
    Get complete portfolio summary with live prices.
    
    Parameters
    ----------
    csv_path : str
        Path to portfolio CSV file
        
    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame, float]
        (Portfolio with prices, Portfolio missing prices, total_equity)
    """
    # Load and aggregate
    logging.info(f"Loading portfolio from {csv_path}...")
    df_raw = load_portfolio_raw(csv_path)
    df_agg = aggregate_by_symbol(df_raw)
    
    # Get all unique symbols
    all_symbols = df_agg['symbol'].unique().tolist()
    
    # Fetch prices (returns both prices and list of symbols needing manual)
    logging.info(f"Fetching live prices for {len(all_symbols)} assets...")
    prices, needs_manual = fetch_current_prices(all_symbols)
    
    # Calculate metrics
    df_priced, df_missing, total_equity = calculate_portfolio_metrics(df_agg, prices, needs_manual)
    
    return df_priced, df_missing, total_equity


def print_portfolio_summary(df_priced: pd.DataFrame, df_missing: pd.DataFrame, total_equity: float) -> None:
    """
    Pretty print the portfolio summary.
    
    Parameters
    ----------
    df_priced : pd.DataFrame
        Portfolio with live/manual prices
    df_missing : pd.DataFrame
        Portfolio with missing prices
    total_equity : float
        Total portfolio value
    """
    print("\n" + "="*90)
    print(" [PORTFOLIO] SUMMARY - LIVE")
    print("="*90)
    print(f" Total Equity (priced assets): ${total_equity:,.2f}")
    print("-"*90)
    
    # Header
    print(f"{'Asset':<8} {'Qty':>12} {'Avg Cost':>12} {'Price':>12} {'Value':>12} {'P&L %':>10} {'Weight':>8} {'Src':>6}")
    print("-"*90)
    
    # Portfolio total P&L (only from priced assets)
    total_cost = df_priced['total_cost'].sum()
    total_pnl = total_equity - total_cost
    total_pnl_pct = ((total_equity / total_cost) - 1) * 100 if total_cost > 0 else 0
    
    # Rows
    for _, row in df_priced.iterrows():
        symbol = row['symbol']
        qty = row['quantity']
        avg_cost = row['avg_cost']
        price = row['current_price']
        value = row['current_value']
        pnl_pct = row['pnl_pct']
        weight = row['weight'] * 100
        source = row['price_source'][:3].upper()  # LIV or MAN
        
        # Format quantity based on size
        if qty >= 1000:
            qty_str = f"{qty:,.0f}"
        elif qty >= 1:
            qty_str = f"{qty:,.4f}"
        else:
            qty_str = f"{qty:,.6f}"
        
        # Format prices based on size
        if avg_cost >= 100:
            avg_str = f"${avg_cost:,.0f}"
            price_str = f"${price:,.0f}"
        elif avg_cost >= 1:
            avg_str = f"${avg_cost:,.2f}"
            price_str = f"${price:,.2f}"
        else:
            avg_str = f"${avg_cost:,.6f}"
            price_str = f"${price:,.6f}"
        
        # P&L sign
        pnl_sign = "+" if pnl_pct >= 0 else ""
        
        print(f"{symbol:<8} {qty_str:>12} {avg_str:>12} {price_str:>12} ${value:>10,.2f} {pnl_sign}{pnl_pct:>8.1f}% {weight:>7.1f}% {source:>6}")
    
    print("-"*90)
    
    # Totals
    pnl_sign = "+" if total_pnl >= 0 else ""
    print(f"{'TOTAL':<8} {'':<12} {'':<12} {'':<12} ${total_equity:>10,.2f} {pnl_sign}{total_pnl_pct:>8.1f}% {'100.0%':>8}")
    print(f"{'':8} {'':12} {'Cost:':<12} ${total_cost:>10,.2f} {'P&L:':<12} {pnl_sign}${abs(total_pnl):>8,.2f}")
    print("="*90)
    
    # Show assets with missing prices
    if not df_missing.empty:
        print("\n" + "-"*90)
        print(" [WARN] ASSETS WITH MISSING PRICES (update 'Price (USD)' column in CSV)")
        print("-"*90)
        print(f"{'Asset':<8} {'Qty':>12} {'Avg Cost':>12} {'Total Cost':>14} {'Manual Price':>14}")
        print("-"*90)
        
        missing_cost = 0
        for _, row in df_missing.iterrows():
            symbol = row['symbol']
            qty = row['quantity']
            avg_cost = row['avg_cost']
            total_cost_row = row['total_cost']
            manual_price = row['manual_price']
            missing_cost += total_cost_row
            
            # Format quantity
            if qty >= 1000:
                qty_str = f"{qty:,.0f}"
            elif qty >= 1:
                qty_str = f"{qty:,.4f}"
            else:
                qty_str = f"{qty:,.6f}"
            
            # Format prices
            if avg_cost >= 1:
                avg_str = f"${avg_cost:,.2f}"
            else:
                avg_str = f"${avg_cost:,.6f}"
            
            # Manual price
            if manual_price > 0:
                if manual_price >= 1:
                    manual_str = f"${manual_price:,.2f}"
                else:
                    manual_str = f"${manual_price:,.6f}"
            else:
                manual_str = "N/A"
            
            print(f"{symbol:<8} {qty_str:>12} {avg_str:>12} ${total_cost_row:>12,.2f} {manual_str:>14}")
        
        print("-"*90)
        print(f"{'':8} {'':12} {'':12} {'Cost at risk:':<14} ${missing_cost:>12,.2f}")
        print("-"*90)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys
    
    # Allow custom CSV path via command line
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV_PATH
    
    # Get summary
    df_priced, df_missing, total_equity = get_portfolio_summary(csv_path)
    
    # Print summary
    print_portfolio_summary(df_priced, df_missing, total_equity)
