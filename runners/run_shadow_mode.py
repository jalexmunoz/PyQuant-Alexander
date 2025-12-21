# runners/run_shadow_mode.py
# v2.0.0 - Shadow Mode Validation Runner
#
# Purpose: Process webhook signals and generate shadow mode decisions.
# Phase 1 of 90-day out-of-sample validation before live capital deployment.
#
# Usage:
#   python runners/run_shadow_mode.py              # Use today
#   python runners/run_shadow_mode.py --date 2025-12-19  # Backtest specific day

import json
import logging
import sys
import argparse
from pathlib import Path
from datetime import datetime, date, timezone
from typing import Dict, List, Optional, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.strategies.trend_filter_strategy import BASE_TARGETS
from utils.heartbeat import write_heartbeat

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

# =============================================================================
# CONFIGURATION
# =============================================================================

PORTFOLIO_CONFIG = Path("config/portfolio.json")
WEBHOOK_DIR = Path("Output/webhooks")
SHADOW_OUTPUT_DIR = Path("Output/shadow")

ASSETS = list(BASE_TARGETS.keys())


# =============================================================================
# VALIDATION
# =============================================================================

def validate_event_data(event: dict) -> bool:
    """Validate event data quality. Returns True if valid, False if invalid."""
    ticker = event.get("ticker")
    event_type = event.get("event_type")
    
    if not ticker or not event_type:
        logging.warning(f"Missing required fields: ticker={ticker}, event_type={event_type}")
        return False
    
    if event_type == "daily_snapshot":
        price = event.get("price")
        sma50 = event.get("sma50")
        sma200 = event.get("sma200")
        
        for field_name, field_value in [("price", price), ("sma50", sma50), ("sma200", sma200)]:
            if field_value is None:
                logging.warning(f"{ticker}: Missing {field_name}")
                return False
            if not isinstance(field_value, (int, float)):
                logging.warning(f"{ticker}: Invalid {field_name} type")
                return False
            if field_value <= 0:
                logging.warning(f"{ticker}: {field_name} must be positive")
                return False
    
    return True


# =============================================================================
# DATA STRUCTURES
# =============================================================================

def get_default_portfolio() -> Dict[str, Any]:
    """Get default portfolio structure."""
    return {
        "equity_curve": 1.0,
        "positions": {
            asset: {
                "status": "OFF",
                "entry_price": None,
                "entry_date": None,
                "weight": 0.0
            }
            for asset in ASSETS
        },
        "last_updated": None,
        "notes": "Shadow mode - Day 0"
    }


# =============================================================================
# FILE I/O
# =============================================================================

def load_portfolio() -> Dict[str, Any]:
    """
    Load portfolio state from config/portfolio.json.
    
    Returns:
        Portfolio dictionary
        
    Raises:
        SystemExit: If file is corrupted or invalid
    """
    if not PORTFOLIO_CONFIG.exists():
        logging.warning(f"Portfolio config not found, creating default: {PORTFOLIO_CONFIG}")
        portfolio = get_default_portfolio()
        save_portfolio(portfolio)
        return portfolio
    
    try:
        with open(PORTFOLIO_CONFIG, 'r') as f:
            portfolio = json.load(f)
        
        # Validate structure
        if 'positions' not in portfolio or 'equity_curve' not in portfolio:
            raise ValueError("Invalid portfolio structure")
        
        return portfolio
        
    except json.JSONDecodeError as e:
        logging.error(f"Corrupted portfolio.json: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to load portfolio: {e}")
        sys.exit(1)


def save_portfolio(portfolio: Dict[str, Any]) -> None:
    """Save portfolio state to config/portfolio.json."""
    PORTFOLIO_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    
    with open(PORTFOLIO_CONFIG, 'w') as f:
        json.dump(portfolio, f, indent=2)


def load_webhook_events(target_date: date) -> List[Dict[str, Any]]:
    """
    Load webhook events from file for given date.
    
    Automatically detects and handles both formats:
    - JSON array format: [{...}, {...}] (manual/test files)
    - NDJSON format: one JSON per line (from webhook_receiver.py)
    
    Parameters:
        target_date: Date to load events for
        
    Returns:
        List of event dictionaries, empty list if file not found or invalid
    """
    webhook_file = WEBHOOK_DIR / f"events_{target_date.strftime('%Y-%m-%d')}.json"
    
    if not webhook_file.exists():
        logging.warning(f"Webhook file not found: {webhook_file}")
        return []
    
    try:
        with open(webhook_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            logging.warning(f"Webhook file is empty: {webhook_file}")
            return []
        
        # Try JSON array format first
        if content.startswith('['):
            try:
                events = json.loads(content)
                if isinstance(events, list):
                    events = [e for e in events if validate_event_data(e)]
                    logging.info(f"Loaded {len(events)} events (JSON array format) from {webhook_file}")
                    return events
            except json.JSONDecodeError:
                pass
        
        # Fall back to NDJSON format (one JSON per line)
        events = []
        for line in content.split('\n'):
            line = line.strip()
            if line:
                try:
                    event = json.loads(line)
                    if validate_event_data(event):
                        events.append(event)
                except json.JSONDecodeError as e:
                    logging.warning(f"Skipping invalid JSON line: {e}")
                    continue
        
        logging.info(f"Loaded {len(events)} events (NDJSON format) from {webhook_file}")
        return events
        
    except Exception as e:
        logging.error(f"Error reading webhook file: {e}")
        return []


def save_decisions(decisions: Dict[str, Any], target_date: date) -> Path:
    """
    Save decisions to Output/shadow/decisions_YYYY-MM-DD.json.
    
    Returns:
        Path to saved file
    """
    SHADOW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    output_file = SHADOW_OUTPUT_DIR / f"decisions_{target_date.strftime('%Y-%m-%d')}.json"
    
    with open(output_file, 'w') as f:
        json.dump(decisions, f, indent=2)
    
    return output_file


# =============================================================================
# EVENT PROCESSING
# =============================================================================

def filter_events_by_asset(events: List[Dict[str, Any]], ticker: str) -> List[Dict[str, Any]]:
    """Filter events for a specific asset ticker."""
    return [e for e in events if e.get('ticker') == ticker]


def get_cross_event(events: List[Dict[str, Any]], direction: str) -> Optional[Dict[str, Any]]:
    """
    Get latest cross event of specified direction.
    
    Parameters:
        events: List of events for an asset
        direction: 'ON' or 'OFF'
        
    Returns:
        Latest cross event, or None if not found
    """
    cross_events = [
        e for e in events
        if e.get('event_type') == 'cross' and e.get('signal') == direction
    ]
    
    if not cross_events:
        return None
    
    # Sort by time, return latest
    cross_events.sort(key=lambda x: x.get('time', ''), reverse=True)
    return cross_events[0]


def get_snapshot_event(events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Get latest snapshot event."""
    snapshots = [e for e in events if e.get('event_type') == 'snapshot']
    
    if not snapshots:
        return None
    
    snapshots.sort(key=lambda x: x.get('time', ''), reverse=True)
    return snapshots[0]


# =============================================================================
# DECISION LOGIC
# =============================================================================

def process_asset_decision(
    ticker: str,
    asset_events: List[Dict[str, Any]],
    current_position: Dict[str, Any],
    weights: Dict[str, float]
) -> Dict[str, Any]:
    """
    Process decision logic for a single asset.
    
    Parameters:
        ticker: Asset ticker (e.g., 'BTCUSDT')
        asset_events: All events for this asset
        current_position: Current position state
        weights: Asset weights dictionary
        
    Returns:
        Decision dictionary
    """
    decision = {
        "action": "HOLD",
        "reason": "No cross event today",
        "position": current_position["status"],
        "weight": weights.get(ticker, 0.0),
        "snapshot": None
    }
    
    # Get snapshot data if available
    snapshot = get_snapshot_event(asset_events)
    if snapshot:
        decision["snapshot"] = {
            "price": snapshot.get('price'),
            "sma50": snapshot.get('sma50'),
            "sma200": snapshot.get('sma200')
        }
    
    # Check for cross ON event
    cross_on = get_cross_event(asset_events, 'ON')
    if cross_on:
        if current_position["status"] == "OFF":
            decision["action"] = "BUY"
            decision["reason"] = "SMA50 crossed above SMA200"
            decision["position"] = "ON"
            # Use price from cross event or snapshot for entry
            entry_price = cross_on.get('price') or (snapshot.get('price') if snapshot else None)
            if entry_price:
                decision["entry_price"] = entry_price
            return decision
        else:
            decision["action"] = "HOLD"
            decision["reason"] = "Already in position"
            return decision
    
    # Check for cross OFF event
    cross_off = get_cross_event(asset_events, 'OFF')
    if cross_off:
        if current_position["status"] == "ON":
            decision["action"] = "SELL"
            decision["reason"] = "SMA50 crossed below SMA200"
            decision["position"] = "OFF"
            
            # Store exit price from cross event or snapshot
            exit_price = cross_off.get('price') or (snapshot.get('price') if snapshot else None)
            if exit_price and current_position.get("entry_price"):
                decision["exit_price"] = exit_price
                decision["entry_price"] = current_position["entry_price"]
            return decision
        else:
            decision["action"] = "HOLD"
            decision["reason"] = "Already out of position"
            return decision
    
    return decision


def print_summary(decisions: Dict[str, Any], old_equity: float, new_equity: float) -> None:
    """Print formatted summary table."""
    print("\nAsset      Action  Reason                Position  Price")
    print("─────────  ──────  ────────────────────  ────────  ────────")
    
    for ticker, decision in decisions.items():
        # Handle None decision (no webhook data)
        if decision is None:
            print(f"{ticker:10} {'HOLD':6}  {'No webhook data':20}  {'--':8}  {'--':8}")
            continue
            
        action = decision.get("action", "HOLD")
        reason = decision.get("reason", "Unknown")[:20]
        position = decision.get("position", "--")
        
        # Safely get price from snapshot
        snapshot = decision.get("snapshot", {})
        price = snapshot.get("price") if snapshot else None
        price_str = f"{price:,.2f}" if price else "--"
        
        print(f"{ticker:10} {action:6}  {reason:20}  {position:8}  {price_str:>8}")
    
    equity_change = ((new_equity / old_equity) - 1) * 100 if old_equity > 0 else 0
    print(f"\nPortfolio Equity: {old_equity:.4f} → {new_equity:.4f} ({equity_change:+.2f}%)")


def calculate_equity_update(
    portfolio: Dict[str, Any],
    decisions: Dict[str, Dict[str, Any]],
    weights: Dict[str, float]
) -> float:
    """
    Calculate equity curve update from SELL decisions.
    
    Parameters:
        portfolio: Current portfolio state
        decisions: All asset decisions
        weights: Asset weights
        
    Returns:
        New equity curve value
    """
    equity = portfolio["equity_curve"]
    
    for ticker, decision in decisions.items():
        if decision is None:
            continue
        if decision.get("action") == "SELL":
            entry_price = decision.get("entry_price")
            exit_price = decision.get("exit_price")
            weight = weights.get(ticker, 0.0)
            
            if entry_price and exit_price and weight > 0:
                return_value = (exit_price / entry_price) - 1.0
                equity_update = 1 + (return_value * weight)
                equity *= equity_update
                logging.info(
                    f"{ticker} SELL: entry={entry_price:.2f}, exit={exit_price:.2f}, "
                    f"return={return_value*100:.2f}%, weight={weight*100:.0f}%"
                )
    
    return equity


def update_portfolio_positions(
    portfolio: Dict[str, Any],
    decisions: Dict[str, Dict[str, Any]],
    target_date: str,
    weights: Dict[str, float]
) -> None:
    """Update portfolio positions based on decisions."""
    for ticker, decision in decisions.items():
        if decision is None:
            continue
            
        position = portfolio["positions"][ticker]
        
        if decision.get("action") == "BUY":
            position["status"] = "ON"
            # Use entry_price from decision (from cross event or snapshot)
            entry_price = decision.get("entry_price")
            if entry_price:
                position["entry_price"] = entry_price
            position["entry_date"] = target_date
            position["weight"] = weights.get(ticker, 0.0)
            
        elif decision.get("action") == "SELL":
            position["status"] = "OFF"
            position["entry_price"] = None
            position["entry_date"] = None
            position["weight"] = 0.0


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_shadow_mode(target_date: Optional[date] = None) -> None:
    """
    Main shadow mode processing function.
    
    Parameters:
        target_date: Date to process (default: today)
    """
    if target_date is None:
        target_date = date.today()
    
    date_str = target_date.strftime('%Y-%m-%d')
    
    # Print header
    print("╔════════════════════════════════════════╗")
    print("║   PyQuant Alexander - Shadow Mode      ║")
    print(f"║   Date: {date_str:<30} ║")
    print("╚════════════════════════════════════════╝")
    print()
    
    # Load portfolio
    portfolio = load_portfolio()
    equity_start = portfolio["equity_curve"]
    
    # Load webhook events
    events = load_webhook_events(target_date)
    
    # Use BASE_TARGETS for asset weights
    weights = BASE_TARGETS.copy()
    
    # Process each asset
    decisions = {}
    
    for ticker in ASSETS:
        asset_events = filter_events_by_asset(events, ticker)
        current_position = portfolio["positions"][ticker]
        
        decision = process_asset_decision(
            ticker=ticker,
            asset_events=asset_events,
            current_position=current_position,
            weights=weights
        )
        
        decisions[ticker] = decision
    
    # Calculate equity update
    equity_end = calculate_equity_update(portfolio, decisions, weights)
    
    # Print summary table
    print_summary(decisions, equity_start, equity_end)
    print()
    
    # Prepare output
    output = {
        "date": date_str,
        "run_metadata": {
            "run_time_utc": datetime.now(timezone.utc).isoformat(),
            "run_time_local": datetime.now().isoformat(),
            "timezone": "America/New_York"
        },
        "decisions": decisions,
        "portfolio_equity": equity_end,
        "notes": f"Shadow mode - Day {target_date.strftime('%j')}"
    }
    
    # Save decisions
    output_path = save_decisions(output, target_date)
    logging.info(f"Decisions saved: {output_path}")
    
    # Update portfolio
    portfolio["equity_curve"] = equity_end
    update_portfolio_positions(portfolio, decisions, date_str, weights)
    portfolio["last_updated"] = datetime.now().isoformat()
    portfolio["notes"] = output["notes"]
    
    save_portfolio(portfolio)
    logging.info(f"Portfolio updated: {PORTFOLIO_CONFIG}")
    
    # === HEARTBEAT TRACKING ===
    assets_data = {}
    for ticker in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "LINKUSDT"]:
        decision = decisions.get(ticker)
        
        if decision and isinstance(decision, dict):
            snapshot = decision.get("snapshot")
            if snapshot and isinstance(snapshot, dict):
                assets_data[ticker] = {
                    "snapshot_received": True,
                    "price": snapshot.get("price"),
                    "action": decision.get("action", "UNKNOWN")
                }
            else:
                assets_data[ticker] = {
                    "snapshot_received": False,
                    "price": None,
                    "action": decision.get("action", "UNKNOWN")
                }
        else:
            assets_data[ticker] = {
                "snapshot_received": False,
                "price": None,
                "action": "UNKNOWN"
            }
    
    write_heartbeat(
        status="SUCCESS",
        events_processed=len(events),
        assets_data=assets_data
    )
    # === END HEARTBEAT ===


# =============================================================================
# CLI
# =============================================================================

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PyQuant Alexander Shadow Mode Validation Runner"
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Date to process (YYYY-MM-DD), default: today'
    )
    
    args = parser.parse_args()
    
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            logging.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
            sys.exit(1)
    
    run_shadow_mode(target_date)


if __name__ == '__main__':
    main()
