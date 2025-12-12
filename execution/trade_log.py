# execution/trade_log.py
# v1.0.0 - Simple Trade Logger
#
# Purpose: Log manual trades after execution for tracking and future analysis.
# No sync, no portfolio updates, just logging.

import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

# Default log file path
DEFAULT_LOG_PATH = "Docs/trade_log.csv"

# CSV columns
COLUMNS = ["timestamp", "symbol", "side", "quantity", "price", "total_value", "exchange", "notes"]


def log_trade(
    symbol: str,
    side: Literal["BUY", "SELL"],
    quantity: float,
    price: float,
    exchange: str,
    timestamp: Optional[str] = None,
    notes: str = "",
    log_path: str = DEFAULT_LOG_PATH
) -> None:
    """
    Log a manual trade to CSV.
    
    Parameters
    ----------
    symbol : str
        Asset symbol (e.g., "BTC", "ETH")
    side : Literal["BUY", "SELL"]
        Trade direction
    quantity : float
        Amount traded
    price : float
        Execution price
    exchange : str
        Exchange name (e.g., "Phemex", "Bingx")
    timestamp : Optional[str]
        Trade timestamp (default: now)
    notes : str
        Optional context or notes
    log_path : str
        Path to CSV file
    """
    # Default timestamp to now
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Calculate total value
    total_value = quantity * price
    
    # Create trade record
    trade = {
        "timestamp": timestamp,
        "symbol": symbol.upper(),
        "side": side.upper(),
        "quantity": quantity,
        "price": price,
        "total_value": total_value,
        "exchange": exchange,
        "notes": notes
    }
    
    # Check if file exists
    log_file = Path(log_path)
    file_exists = log_file.exists()
    
    # Create directory if needed
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Append to CSV
    df = pd.DataFrame([trade])
    df.to_csv(log_path, mode='a', header=not file_exists, index=False)
    
    # Print confirmation
    print(f"[OK] Logged: {side} {quantity:,.6f} {symbol} @ ${price:,.2f} on {exchange}")
    if notes:
        print(f"     Note: {notes}")


def get_trade_history(log_path: str = DEFAULT_LOG_PATH) -> pd.DataFrame:
    """
    Get all logged trades.
    
    Parameters
    ----------
    log_path : str
        Path to CSV file
        
    Returns
    -------
    pd.DataFrame
        All logged trades
    """
    log_file = Path(log_path)
    
    if not log_file.exists():
        print(f"[WARN] No trade log found at {log_path}")
        return pd.DataFrame(columns=COLUMNS)
    
    df = pd.read_csv(log_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def print_trade_history(log_path: str = DEFAULT_LOG_PATH) -> None:
    """
    Print formatted trade history.
    
    Parameters
    ----------
    log_path : str
        Path to CSV file
    """
    df = get_trade_history(log_path)
    
    if df.empty:
        print("No trades logged yet.")
        return
    
    print("\n" + "="*80)
    print(" [TRADE LOG] History")
    print("="*80)
    print(f"{'Date':<20} {'Side':<6} {'Symbol':<8} {'Qty':>12} {'Price':>12} {'Value':>12} {'Exchange':<10}")
    print("-"*80)
    
    for _, row in df.iterrows():
        ts = row['timestamp'].strftime("%Y-%m-%d %H:%M") if pd.notna(row['timestamp']) else "N/A"
        print(f"{ts:<20} {row['side']:<6} {row['symbol']:<8} {row['quantity']:>12,.6f} ${row['price']:>10,.2f} ${row['total_value']:>10,.2f} {row['exchange']:<10}")
    
    print("-"*80)
    
    # Summary
    buys = df[df['side'] == 'BUY']['total_value'].sum()
    sells = df[df['side'] == 'SELL']['total_value'].sum()
    print(f"Total Buys: ${buys:,.2f} | Total Sells: ${sells:,.2f} | Net: ${buys - sells:,.2f}")
    print("="*80)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys
    
    # Usage: python trade_log.py BUY BTC 0.01 97000 Phemex "DCA weekly"
    #        python trade_log.py --history
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Log trade:  python trade_log.py BUY BTC 0.01 97000 Phemex \"optional notes\"")
        print("  History:    python trade_log.py --history")
        sys.exit(1)
    
    if sys.argv[1] == "--history":
        print_trade_history()
    else:
        if len(sys.argv) < 6:
            print("[ERROR] Not enough arguments.")
            print("Usage: python trade_log.py SIDE SYMBOL QTY PRICE EXCHANGE [NOTES]")
            sys.exit(1)
        
        side = sys.argv[1].upper()
        symbol = sys.argv[2].upper()
        quantity = float(sys.argv[3])
        price = float(sys.argv[4])
        exchange = sys.argv[5]
        notes = sys.argv[6] if len(sys.argv) > 6 else ""
        
        if side not in ["BUY", "SELL"]:
            print(f"[ERROR] Invalid side: {side}. Use BUY or SELL.")
            sys.exit(1)
        
        log_trade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            exchange=exchange,
            notes=notes
        )




