# utils/weekly_summary.py
# Generate weekly summary report from shadow mode decisions

import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

OUTPUT_DIR = Path("Output/shadow")

def generate_weekly_summary(days_back: int = 7):
    """Analyze last N days of shadow mode decisions."""
    
    print("=" * 80)
    print(f" PyQuant Alexander - Weekly Summary (Last {days_back} Days)")
    print("=" * 80)
    print()
    
    # Collect data
    days_with_data = []
    total_events = 0
    asset_actions = defaultdict(lambda: defaultdict(int))
    
    for i in range(days_back):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        filepath = OUTPUT_DIR / f"decisions_{date}.json"
        
        if filepath.exists():
            with open(filepath, 'r') as f:
                data = json.load(f)
                days_with_data.append(data)
                
                # Count events
                metadata = data.get("run_metadata", {})
                total_events += metadata.get("events_processed", 0)
                
                # Count actions per asset
                decisions = data.get("decisions", {})
                for ticker, decision in decisions.items():
                    action = decision.get("action", "UNKNOWN")
                    asset_actions[ticker][action] += 1
    
    # Calculate metrics
    uptime_pct = (len(days_with_data) / days_back) * 100
    
    print(f"📊 Uptime & Execution")
    print(f"  Days with data: {len(days_with_data)}/{days_back} ({uptime_pct:.1f}%)")
    print(f"  Total events processed: {total_events}")
    print()
    
    print(f"📈 Actions by Asset")
    for ticker in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "LINKUSDT"]:
        actions = asset_actions[ticker]
        print(f"  {ticker:10} - HOLD: {actions['HOLD']:2d}  BUY: {actions['BUY']:2d}  SELL: {actions['SELL']:2d}")
    print()
    
    # Market structure trends
    if days_with_data:
        print(f"📉 Market Structure (Latest)")
        latest = days_with_data[0]  # Most recent
        market = latest.get("market_structure", {})
        
        for ticker in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "LINKUSDT"]:
            data = market.get(ticker, {})
            gap = data.get("gap_pct")
            signal = data.get("signal", "UNKNOWN")
            
            if gap is not None:
                gap_str = f"{gap:+6.2f}%"
                status = "🔴" if gap < 0 else "🟢"
                print(f"  {ticker:10} {status} Gap: {gap_str}  Signal: {signal}")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    generate_weekly_summary()