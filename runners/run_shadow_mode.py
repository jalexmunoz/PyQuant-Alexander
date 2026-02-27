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
from datetime import datetime, date, timezone, timedelta
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.strategies.trend_filter_strategy import BASE_TARGETS
from utils.heartbeat import write_heartbeat
from utils.db_provider import get_events_by_date

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Define root and directories
ROOT = Path(__file__).resolve().parents[1]   # .../pyquant_alexander
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "Output"

PORTFOLIO_CONFIG = CONFIG_DIR / "portfolio.json"
WEBHOOK_DIR = OUTPUT_DIR / "webhooks"
SHADOW_OUTPUT_DIR = OUTPUT_DIR / "shadow"

ASSETS = list(BASE_TARGETS.keys())


# =============================================================================
# VALIDATION
# =============================================================================

def validate_event_data(event: dict, fast_ma: int = 50, slow_ma: int = 200) -> bool:
    """
    Validate event data quality. Returns True if valid, False if invalid.
    
    Parameters:
        event: Event dictionary
        fast_ma: Fast MA period (for field name, defaults to 50 for backward compatibility)
        slow_ma: Slow MA period (for field name, defaults to 200 for backward compatibility)
    """
    ticker = event.get("ticker")
    event_type = event.get("event_type")
    
    if not ticker or not event_type:
        logging.warning(f"Missing required fields: ticker={ticker}, event_type={event_type}")
        return False
    
    if event_type == "daily_snapshot":
        price = event.get("price")
        # Try to get MA values - support both dynamic names and legacy sma50/sma200
        fast_ma_key = f"sma{fast_ma}" if fast_ma != 50 else "sma50"
        slow_ma_key = f"sma{slow_ma}" if slow_ma != 200 else "sma200"
        
        fast_sma = event.get(fast_ma_key) or event.get("sma50")
        slow_sma = event.get(slow_ma_key) or event.get("sma200")
        
        for field_name, field_value in [("price", price), (fast_ma_key, fast_sma), (slow_ma_key, slow_sma)]:
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
    """Get default portfolio structure with optimized MA parameters."""
    return {
        "equity_curve": 1.0,
        "assets": {
            "BTCUSDT": {
                "fast_ma": 10, "slow_ma": 100, "status": "active", "weight": 0.4,
                "entry_price": 0.0, "highest_close": 0.0,
                "hard_stop_pct": 0.12, "trailing_stop_pct": 0.10
            },
            "ETHUSDT": {
                "fast_ma": 30, "slow_ma": 150, "status": "active", "weight": 0.4,
                "entry_price": 0.0, "highest_close": 0.0,
                "hard_stop_pct": 0.12, "trailing_stop_pct": 0.10
            },
            "SOLUSDT": {
                "fast_ma": 10, "slow_ma": 50, "status": "active", "weight": 0.15,
                "entry_price": 0.0, "highest_close": 0.0,
                "hard_stop_pct": 0.12, "trailing_stop_pct": 0.10
            },
            "LINKUSDT": {
                "fast_ma": 20, "slow_ma": 100, "status": "active", "weight": 0.05,
                "entry_price": 0.0, "highest_close": 0.0,
                "hard_stop_pct": 0.12, "trailing_stop_pct": 0.10
            }
        },
        "positions": {
            asset: {
                "status": "OFF",
                "entry_price": None,
                "entry_date": None,
                "weight": 0.0
            }
            for asset in ASSETS
        },
        "global_settings": {
            "commission_rate": 0.001,
            "risk_on_threshold": 0.7,
            "risk_off_threshold": 0.3
        },
        "last_updated": None,
        "notes": "Shadow mode - Day 0 - Optimized MA parameters per asset"
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
    weights: Dict[str, float],
    asset_config: Dict[str, Any],
    fast_ma: int = 50,
    slow_ma: int = 200,
    previous_slow_ma: Optional[float] = None
) -> Dict[str, Any]:
    """
    Process decision logic for a single asset with Circuit Breaker protection.
    
    Parameters:
        ticker: Asset ticker (e.g., 'BTCUSDT')
        asset_events: All events for this asset
        current_position: Current position state
        weights: Asset weights dictionary
        asset_config: Asset configuration (from portfolio.assets)
        fast_ma: Fast moving average period
        slow_ma: Slow moving average period
        
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
    # Support both dynamic MA names and legacy sma50/sma200
    snapshot = get_snapshot_event(asset_events)
    current_price = None
    
    if snapshot:
        fast_ma_key = f"sma{fast_ma}" if fast_ma != 50 else "sma50"
        slow_ma_key = f"sma{slow_ma}" if slow_ma != 200 else "sma200"
        
        fast_sma_value = snapshot.get(fast_ma_key) or snapshot.get("sma50")
        slow_sma_value = snapshot.get(slow_ma_key) or snapshot.get("sma200")
        current_price = snapshot.get('price')
        
        decision["snapshot"] = {
            "price": current_price,
            "fast_ma": fast_sma_value,
            "slow_ma": slow_sma_value,
            "fast_ma_period": fast_ma,
            "slow_ma_period": slow_ma
        }
    
    # Get circuit breaker parameters from asset config
    hard_stop_pct = asset_config.get("hard_stop_pct", 0.12)
    trailing_stop_pct = asset_config.get("trailing_stop_pct", 0.10)
    entry_price_config = asset_config.get("entry_price", 0.0)
    highest_close_config = asset_config.get("highest_close", 0.0)
    
    # Get entry price from position or asset config
    entry_price = current_position.get("entry_price") or entry_price_config or None
    
    # =========================================================================
    # CIRCUIT BREAKER LOGIC (Priority Check)
    # =========================================================================
    if current_position["status"] == "ON" and current_price and entry_price:
        # Update highest_close if current price is higher
        if current_price > highest_close_config:
            highest_close_config = current_price
            decision["update_highest_close"] = current_price
        
        # Calculate drawdown from peak
        if highest_close_config > 0:
            drawdown = (current_price - highest_close_config) / highest_close_config
        else:
            drawdown = 0.0
        
        # Calculate loss from entry
        loss_from_entry = (current_price - entry_price) / entry_price
        
        # Circuit Breaker Trigger Check
        if loss_from_entry < -hard_stop_pct or drawdown < -trailing_stop_pct:
            decision["action"] = "SELL"
            decision["reason"] = "🛑 CIRCUIT BREAKER TRIGGERED"
            decision["position"] = "OFF"
            
            # Reset circuit breaker fields
            decision["reset_circuit_breaker"] = True
            
            # Store exit info
            if current_price:
                decision["exit_price"] = current_price
                decision["entry_price"] = entry_price
            
            return decision
    
    # =========================================================================
    # REGULAR SIGNAL LOGIC
    # =========================================================================
    
    # Check for cross ON event (BUY) with Slope Filter
    cross_on = get_cross_event(asset_events, 'ON')
    if cross_on:
        if current_position["status"] == "OFF":
            # Calculate Slow MA slope for trend filter
            slow_sma_value = None
            if snapshot:
                slow_ma_key = f"sma{slow_ma}" if slow_ma != 200 else "sma200"
                slow_sma_value = snapshot.get(slow_ma_key) or snapshot.get("sma200")
            
            # Apply Slope Filter: Only BUY if Slow MA is rising (slope > 0)
            slope = None
            if slow_sma_value and previous_slow_ma and previous_slow_ma > 0:
                slope = (slow_sma_value - previous_slow_ma) / previous_slow_ma
                decision["slope"] = slope
            
            # Check slope condition
            if slope is not None and slope <= 0:
                # Fast > Slow but Slow MA is not rising (lateral/falling market)
                decision["action"] = "HOLD"
                decision["reason"] = "⏳ WAITING FOR POSITIVE SLOPE"
                decision["position"] = "OFF"
                return decision
            
            # Slope is positive (or not available) - proceed with BUY
            decision["action"] = "BUY"
            decision["reason"] = f"SMA{fast_ma} crossed above SMA{slow_ma}"
            if slope is not None:
                decision["reason"] += f" (slope: {slope*100:.2f}%)"
            decision["position"] = "ON"
            # Use price from cross event or snapshot for entry
            entry_price = cross_on.get('price') or (snapshot.get('price') if snapshot else None)
            if entry_price:
                decision["entry_price"] = entry_price
                # Initialize highest_close with entry price
                decision["update_highest_close"] = entry_price
                decision["update_entry_price"] = entry_price
            return decision
        else:
            decision["action"] = "HOLD"
            decision["reason"] = "Already in position"
            return decision
    
    # Check for cross OFF event (SELL)
    cross_off = get_cross_event(asset_events, 'OFF')
    if cross_off:
        if current_position["status"] == "ON":
            decision["action"] = "SELL"
            decision["reason"] = f"SMA{fast_ma} crossed below SMA{slow_ma}"
            decision["position"] = "OFF"
            
            # Store exit price from cross event or snapshot
            exit_price = cross_off.get('price') or (snapshot.get('price') if snapshot else None)
            if exit_price and entry_price:
                decision["exit_price"] = exit_price
                decision["entry_price"] = entry_price
            
            # Reset circuit breaker fields
            decision["reset_circuit_breaker"] = True
            return decision
        else:
            decision["action"] = "HOLD"
            decision["reason"] = "Already out of position"
            return decision
    
    # If in position and price available, update highest_close if needed
    if current_position["status"] == "ON" and current_price:
        if current_price > highest_close_config:
            decision["update_highest_close"] = current_price
    
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
    """Update portfolio positions based on decisions, including Circuit Breaker fields."""
    assets_config = portfolio.get("assets", {})
    
    for ticker, decision in decisions.items():
        if decision is None:
            continue
            
        position = portfolio["positions"][ticker]
        
        # Ensure asset_config exists
        if ticker not in assets_config:
            assets_config[ticker] = {}
        asset_config = assets_config[ticker]
        
        if decision.get("action") == "BUY":
            position["status"] = "ON"
            # Use entry_price from decision (from cross event or snapshot)
            entry_price = decision.get("entry_price")
            if entry_price:
                position["entry_price"] = entry_price
                # Update asset config with entry price and highest close
                if decision.get("update_entry_price"):
                    asset_config["entry_price"] = entry_price
                if decision.get("update_highest_close"):
                    asset_config["highest_close"] = decision.get("update_highest_close")
            position["entry_date"] = target_date
            position["weight"] = weights.get(ticker, 0.0)
            
        elif decision.get("action") == "SELL":
            position["status"] = "OFF"
            position["entry_price"] = None
            position["entry_date"] = None
            position["weight"] = 0.0
            
            # Reset circuit breaker fields in asset config
            if decision.get("reset_circuit_breaker"):
                asset_config["entry_price"] = 0.0
                asset_config["highest_close"] = 0.0
        else:
            # HOLD: Update highest_close if price increased
            if decision.get("update_highest_close"):
                asset_config["highest_close"] = decision.get("update_highest_close")
        
        # Save asset_config back to portfolio
        portfolio["assets"][ticker] = asset_config


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
    
    # Get asset configuration (MA parameters) and weights from portfolio
    assets_config = portfolio.get("assets", {})
    
    # Load webhook events from Iron Vault (Supabase)
    date_str = target_date.strftime("%Y-%m-%d")
    events = get_events_by_date(date_str)
    
    # Load previous day events for slope calculation
    previous_date = target_date - timedelta(days=1)
    previous_date_str = previous_date.strftime("%Y-%m-%d")
    previous_events = get_events_by_date(previous_date_str)
    
    if not events:
        logging.warning(f"No events found in Iron Vault for date: {date_str}")
        logging.info("💡 Tip: Events are stored in Supabase when webhooks are received")
    else:
        logging.info(f"📥 Cargados {len(events)} eventos desde Iron Vault (Supabase) para fecha: {date_str}")
    
    if previous_events:
        logging.debug(f"📥 Cargados {len(previous_events)} eventos del día anterior ({previous_date_str}) para cálculo de pendiente")
    
    # Extract snapshots from events (current day)
    snapshot_data = {}
    for event in events:
        if event.get("event_type") == "daily_snapshot":
            ticker = event.get("ticker")
            snapshot_data[ticker] = {
                "price": event.get("price"),
                "sma50": event.get("sma50"),
                "sma200": event.get("sma200")
            }
    
    # Extract snapshots from previous day events for slope calculation
    previous_snapshot_data = {}
    for event in previous_events:
        if event.get("event_type") == "daily_snapshot":
            ticker = event.get("ticker")
            previous_snapshot_data[ticker] = {
                "price": event.get("price"),
                "sma50": event.get("sma50"),
                "sma200": event.get("sma200")
            }
    
    # Build weights dictionary from asset config or use BASE_TARGETS as fallback
    weights = {}
    for ticker in ASSETS:
        asset_config = assets_config.get(ticker, {})
        if asset_config:
            weights[ticker] = asset_config.get("weight", BASE_TARGETS.get(ticker, 0.0))
        else:
            weights[ticker] = BASE_TARGETS.get(ticker, 0.0)
    
    # Process each asset
    decisions = {}
    
    for ticker in ASSETS:
        # Get MA configuration for this asset
        asset_config = assets_config.get(ticker, {})
        fast_ma = asset_config.get("fast_ma", 50)  # Default to 50 for backward compatibility
        slow_ma = asset_config.get("slow_ma", 200)  # Default to 200 for backward compatibility
        
        # Log which MA configuration is being used
        logging.info(f"📊 Analizando {ticker} (SMA {fast_ma}/{slow_ma})...")
        
        asset_events = filter_events_by_asset(events, ticker)
        current_position = portfolio["positions"][ticker]
        
        # Get previous day Slow MA value for slope calculation
        previous_slow_ma = None
        previous_snapshot = previous_snapshot_data.get(ticker, {})
        if previous_snapshot:
            slow_ma_key = f"sma{slow_ma}" if slow_ma != 200 else "sma200"
            previous_slow_ma = previous_snapshot.get(slow_ma_key) or previous_snapshot.get("sma200")
        
        decision = process_asset_decision(
            ticker=ticker,
            asset_events=asset_events,
            current_position=current_position,
            weights=weights,
            asset_config=asset_config,
            fast_ma=fast_ma,
            slow_ma=slow_ma,
            previous_slow_ma=previous_slow_ma
        )
        
        decisions[ticker] = decision
    
    # Calculate equity update
    equity_end = calculate_equity_update(portfolio, decisions, weights)
    
    # Print summary table
    print_summary(decisions, equity_start, equity_end)
    print()
    
    # Build market_structure section
    market_structure = {}
    for ticker in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "LINKUSDT"]:
        snapshot = snapshot_data.get(ticker, {})
        asset_config = assets_config.get(ticker, {})
        fast_ma = asset_config.get("fast_ma", 50)
        slow_ma = asset_config.get("slow_ma", 200)
        
        price = snapshot.get("price")
        # Get MA values - support both dynamic and legacy fields
        fast_ma_key = f"sma{fast_ma}" if fast_ma != 50 else "sma50"
        slow_ma_key = f"sma{slow_ma}" if slow_ma != 200 else "sma200"
        
        fast_sma_value = snapshot.get(fast_ma_key) or snapshot.get("sma50")
        slow_sma_value = snapshot.get(slow_ma_key) or snapshot.get("sma200")
        
        # Calculate metrics
        if fast_sma_value and slow_sma_value and slow_sma_value != 0:
            gap_pct = ((fast_sma_value / slow_sma_value) - 1) * 100
            signal = "ON" if fast_sma_value > slow_sma_value else "OFF"
        else:
            gap_pct = None
            signal = "UNKNOWN"
        
        market_structure[ticker] = {
            "price": price,
            "fast_ma": fast_sma_value,
            "slow_ma": slow_sma_value,
            "fast_ma_period": fast_ma,
            "slow_ma_period": slow_ma,
            "gap_pct": round(gap_pct, 2) if gap_pct else None,
            "signal": signal,
            "days_since_last_cross": None
        }
    
    # Prepare output
    output = {
        "date": date_str,
        "run_metadata": {
            "run_time_utc": datetime.now(timezone.utc).isoformat(),
            "run_time_local": datetime.now().isoformat(),
            "timezone": "America/New_York"
        },
        "market_structure": market_structure,
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
        # Get price from market_structure (populated from events)
        price = market_structure.get(ticker, {}).get("price")
        snapshot_received = (price is not None)
        
        # Get action from decisions
        action = decisions.get(ticker, {}).get("action", "UNKNOWN")
        
        assets_data[ticker] = {
            "snapshot_received": snapshot_received,
            "price": price,
            "action": action
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
