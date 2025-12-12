# execution/shadow_mode.py
# v1.3.0 - Shadow Mode with Strategy 1 Integration
#
# Purpose: Compare framework signals against real portfolio positions
# and generate suggested trades for manual review.
#
# Now uses Strategy 1 (Trend Filter) for dynamic target weights.
# NO AUTO-EXECUTION - This is for daily/weekly review only.

from dataclasses import dataclass, field
from typing import List, Literal, Optional, Dict, Tuple, Set
import pandas as pd
import sys
from pathlib import Path

# Add project root for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# =============================================================================
# CONFIGURATION
# =============================================================================

# Default target allocation for main assets (must sum to 1.0)
DEFAULT_TARGETS: Dict[str, float] = {
    "BTCUSDT": 0.40,   # 40% BTC
    "ETHUSDT": 0.40,   # 40% ETH
    "SOLUSDT": 0.15,   # 15% SOL
    "LINKUSDT": 0.05,  # 5% LINK
}

# Target bands for rebalancing (min, max) - for future use
TARGET_BANDS: Dict[str, Tuple[float, float]] = {
    "BTCUSDT": (0.38, 0.45),
    "ETHUSDT": (0.38, 0.45),
    "SOLUSDT": (0.10, 0.18),
    "LINKUSDT": (0.00, 0.07),  # 7% hard cap
}

# Legacy alts - parked positions, no BUY/SELL suggestions
# These still count toward total_equity but are excluded from target comparison
LEGACY_ALTS: Set[str] = {
    "HBARUSDT",
    "JUPUSDT",
    "PEPEUSDT",
    "BASUSDT",
    "SWTCHUSDT",
    "USDTUSDT",  # Include stablecoins
}

# Default threshold - 7% to avoid frequent small trades
DEFAULT_THRESHOLD: float = 0.07


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TargetSignal:
    """
    Represents a target portfolio weight from the framework's signals.
    
    Attributes:
        symbol: Trading pair (e.g., "BTCUSDT")
        timestamp: When the signal was generated
        target_weight: Target allocation (0.0-1.0, fraction of total equity)
        confidence: Signal confidence level (0.0-1.0)
        note: Optional explanation or context
    """
    symbol: str
    timestamp: pd.Timestamp
    target_weight: float  # 0.0 to 1.0
    confidence: float = 1.0
    note: str = ""
    
    def __post_init__(self):
        # Validate weight bounds
        if not 0.0 <= self.target_weight <= 1.0:
            raise ValueError(f"target_weight must be 0.0-1.0, got {self.target_weight}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")


@dataclass
class CurrentPosition:
    """
    Represents a current position in the real portfolio.
    
    Attributes:
        symbol: Trading pair (e.g., "BTCUSDT")
        quantity: Units currently held
        avg_price: Average entry price
        current_price: Latest market price
        current_value: Position value (quantity * current_price)
        current_weight: Position weight (current_value / total_equity)
    """
    symbol: str
    quantity: float
    avg_price: float
    current_price: float
    current_value: float = field(init=False)
    current_weight: float = 0.0  # Set externally based on total equity
    
    def __post_init__(self):
        self.current_value = self.quantity * self.current_price


@dataclass
class SuggestedTrade:
    """
    Represents a suggested trade action for manual review.
    
    Attributes:
        symbol: Trading pair (e.g., "BTCUSDT")
        side: Trade direction ("BUY", "SELL", or "HOLD")
        weight_delta: Difference (target_weight - current_weight)
        size_delta_units: Units to buy/sell
        size_delta_usd: USD value of the suggested trade
        confidence: Inherited from the signal
        note: Explanation or context
    """
    symbol: str
    side: Literal["BUY", "SELL", "HOLD"]
    weight_delta: float
    size_delta_units: float
    size_delta_usd: float
    confidence: float = 1.0
    note: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame creation."""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "weight_delta": self.weight_delta,
            "size_delta_units": self.size_delta_units,
            "size_delta_usd": self.size_delta_usd,
            "confidence": self.confidence,
            "note": self.note,
        }


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def generate_suggested_trades(
    signals: List[TargetSignal],
    positions: List[CurrentPosition],
    total_equity: float,
    min_trade_threshold: float = DEFAULT_THRESHOLD,
    legacy_alts: Set[str] = LEGACY_ALTS
) -> Tuple[List[SuggestedTrade], Dict[str, float]]:
    """
    Generate suggested trades by comparing target signals against current positions.
    
    Parameters
    ----------
    signals : List[TargetSignal]
        Target portfolio weights from the framework
    positions : List[CurrentPosition]
        Current positions in the real portfolio
    total_equity : float
        Total portfolio value in USD (includes all positions)
    min_trade_threshold : float
        Minimum weight delta to generate a trade suggestion (default 7%)
    legacy_alts : Set[str]
        Symbols to exclude from trade suggestions (but include in weight calc)
        
    Returns
    -------
    Tuple[List[SuggestedTrade], Dict[str, float]]
        (List of suggested trades, dict of legacy alt values)
    """
    suggested_trades: List[SuggestedTrade] = []
    legacy_values: Dict[str, float] = {}
    
    # Build lookup dictionaries for O(1) access
    signal_map = {s.symbol: s for s in signals}
    position_map = {p.symbol: p for p in positions}
    
    # Calculate current weights for ALL positions (including legacy)
    for pos in positions:
        pos.current_weight = pos.current_value / total_equity if total_equity > 0 else 0.0
        
        # Track legacy alt values
        if pos.symbol in legacy_alts:
            legacy_values[pos.symbol] = pos.current_value
    
    # Get symbols for target comparison (exclude legacy alts)
    target_symbols = set(signal_map.keys())
    position_symbols = set(p.symbol for p in positions if p.symbol not in legacy_alts)
    all_symbols = target_symbols | position_symbols
    
    for symbol in all_symbols:
        signal = signal_map.get(symbol)
        position = position_map.get(symbol)
        
        # Determine target and current weights
        target_weight = signal.target_weight if signal else 0.0
        current_weight = position.current_weight if position else 0.0
        current_price = position.current_price if position else 0.0
        
        # Calculate weight delta
        weight_delta = target_weight - current_weight
        
        # Skip if below threshold
        if abs(weight_delta) < min_trade_threshold:
            suggested_trades.append(SuggestedTrade(
                symbol=symbol,
                side="HOLD",
                weight_delta=weight_delta,
                size_delta_units=0.0,
                size_delta_usd=0.0,
                confidence=signal.confidence if signal else 1.0,
                note="Within band" if signal else "No target"
            ))
            continue
        
        # Calculate trade size
        size_delta_usd = weight_delta * total_equity
        size_delta_units = size_delta_usd / current_price if current_price > 0 else 0.0
        
        # Determine side
        if weight_delta > 0:
            side = "BUY"
        elif weight_delta < 0:
            side = "SELL"
        else:
            side = "HOLD"
        
        # Build note
        note = signal.note if signal else ""
        if not position and target_weight > 0:
            note = f"New position. {note}".strip()
        elif position and target_weight == 0:
            note = f"Close position. {note}".strip()
        
        suggested_trades.append(SuggestedTrade(
            symbol=symbol,
            side=side,
            weight_delta=weight_delta,
            size_delta_units=abs(size_delta_units),
            size_delta_usd=abs(size_delta_usd),
            confidence=signal.confidence if signal else 1.0,
            note=note
        ))
    
    # Sort by absolute weight delta (largest trades first)
    suggested_trades.sort(key=lambda t: abs(t.weight_delta), reverse=True)
    
    return suggested_trades, legacy_values


def trades_to_dataframe(trades: List[SuggestedTrade]) -> pd.DataFrame:
    """
    Convert list of suggested trades to a pandas DataFrame for easy review.
    """
    if not trades:
        return pd.DataFrame(columns=[
            "symbol", "side", "weight_delta", "size_delta_units", 
            "size_delta_usd", "confidence", "note"
        ])
    
    df = pd.DataFrame([t.to_dict() for t in trades])
    
    # Format for display
    df["weight_delta"] = df["weight_delta"].apply(lambda x: f"{x:+.2%}")
    df["size_delta_usd"] = df["size_delta_usd"].apply(lambda x: f"${x:,.2f}")
    df["confidence"] = df["confidence"].apply(lambda x: f"{x:.0%}")
    
    return df


# =============================================================================
# PORTFOLIO TRACKER INTEGRATION
# =============================================================================

def portfolio_to_positions(df_portfolio: pd.DataFrame) -> List[CurrentPosition]:
    """
    Convert portfolio_tracker DataFrame to list of CurrentPosition objects.
    Adds "USDT" suffix to symbols (e.g., "BTC" -> "BTCUSDT")
    """
    positions = []
    
    for _, row in df_portfolio.iterrows():
        # Skip if no valid price
        if pd.isna(row['current_price']) or row['current_price'] <= 0:
            continue
            
        # Add USDT suffix for trading pair format
        symbol = row['symbol']
        if not symbol.endswith('USDT'):
            symbol = f"{symbol}USDT"
        
        positions.append(CurrentPosition(
            symbol=symbol,
            quantity=row['quantity'],
            avg_price=row['avg_cost'],
            current_price=row['current_price']
        ))
    
    return positions


def run_shadow_analysis(
    target_weights: Dict[str, float] = None,
    csv_path: str = "Docs/portfolio_hot.csv",
    min_trade_threshold: float = DEFAULT_THRESHOLD,
    use_strategy1: bool = True
) -> Tuple[List[SuggestedTrade], pd.DataFrame, Dict[str, float], float, Dict[str, int], Dict[str, Dict]]:
    """
    End-to-end shadow mode analysis with Strategy 1 integration.
    
    Parameters
    ----------
    target_weights : Dict[str, float]
        Target portfolio weights by symbol (default: uses Strategy 1 dynamic targets)
    csv_path : str
        Path to portfolio CSV file
    min_trade_threshold : float
        Minimum weight delta to suggest a trade (default 7%)
    use_strategy1 : bool
        If True and target_weights is None, use Strategy 1 dynamic targets
        
    Returns
    -------
    Tuple containing:
        - trades: List[SuggestedTrade]
        - trades_df: pd.DataFrame
        - legacy_values: Dict[str, float]
        - total_equity: float
        - trend_states: Dict[str, int] (1=ON, 0=OFF per asset)
        - price_info: Dict[str, Dict] (price/SMA info per asset)
    """
    # Import here to avoid circular imports
    try:
        from .portfolio_tracker import get_portfolio_summary
    except ImportError:
        from portfolio_tracker import get_portfolio_summary
    
    # Get Strategy 1 dynamic targets if not provided
    trend_states = {}
    price_info = {}
    
    if target_weights is None and use_strategy1:
        from core.strategies.trend_filter_strategy import get_current_targets, BASE_TARGETS
        print("\n[INFO] Getting Strategy 1 (Trend Filter) current targets...")
        target_weights, trend_states, price_info = get_current_targets(BASE_TARGETS, verbose=True)
    elif target_weights is None:
        target_weights = DEFAULT_TARGETS
    
    # 1. Load portfolio from CSV
    print(f"\n[INFO] Loading portfolio from {csv_path}...")
    df_priced, df_missing, total_equity = get_portfolio_summary(csv_path)
    
    # 2. Convert to CurrentPosition list
    positions = portfolio_to_positions(df_priced)
    print(f"[INFO] Loaded {len(positions)} positions, total equity: ${total_equity:,.2f}")
    
    # 3. Convert target_weights dict to TargetSignal list
    signals = [
        TargetSignal(
            symbol=symbol,
            timestamp=pd.Timestamp.now(),
            target_weight=weight,
            confidence=1.0
        )
        for symbol, weight in target_weights.items()
    ]
    
    # 4. Run generate_suggested_trades()
    trades, legacy_values = generate_suggested_trades(
        signals=signals,
        positions=positions,
        total_equity=total_equity,
        min_trade_threshold=min_trade_threshold
    )
    
    # 5. Convert to DataFrame
    df_trades = trades_to_dataframe(trades)
    
    return trades, df_trades, legacy_values, total_equity, trend_states, price_info


def print_shadow_analysis(
    trades: List[SuggestedTrade],
    total_equity: float,
    legacy_values: Dict[str, float],
    target_weights: Dict[str, float] = None,
    min_trade_threshold: float = DEFAULT_THRESHOLD
) -> None:
    """
    Pretty print shadow analysis results with current vs target comparison.
    """
    if target_weights is None:
        target_weights = DEFAULT_TARGETS
    
    print("\n" + "="*90)
    print(" [SHADOW MODE] PORTFOLIO REBALANCING ANALYSIS")
    print("="*90)
    print(f" Total Equity: ${total_equity:,.2f}")
    print(f" Threshold: {min_trade_threshold:.0%} (${total_equity * min_trade_threshold:,.2f})")
    
    # Calculate legacy alts total
    legacy_total = sum(legacy_values.values())
    legacy_pct = (legacy_total / total_equity * 100) if total_equity > 0 else 0
    
    print(f" Active Portfolio: ${total_equity - legacy_total:,.2f} ({100 - legacy_pct:.1f}%)")
    print("-"*90)
    
    # Current vs Target comparison for main assets
    print("\n CURRENT vs TARGET ALLOCATION:")
    print("-"*90)
    print(f"{'Asset':<12} {'Current':>12} {'Target':>12} {'Delta':>12} {'Band':>16}")
    print("-"*90)
    
    # Build position lookup for current weights
    position_weights = {}
    for trade in trades:
        if trade.symbol in target_weights:
            # Calculate current from target - delta
            current = target_weights[trade.symbol] - trade.weight_delta
            position_weights[trade.symbol] = current
    
    for symbol, target in target_weights.items():
        current = position_weights.get(symbol, 0)
        delta = current - target
        band = TARGET_BANDS.get(symbol, (0, 1))
        
        # Status indicator
        if band[0] <= current <= band[1]:
            status = "OK"
        elif current < band[0]:
            status = "LOW"
        else:
            status = "HIGH"
        
        print(f"{symbol:<12} {current:>11.1%} {target:>11.1%} {delta:>+11.1%} {band[0]:.0%}-{band[1]:.0%} [{status}]")
    
    print("-"*90)
    
    # Suggested trades
    print("\n SUGGESTED TRADES:")
    print("-"*90)
    print(f"{'Symbol':<12} {'Side':<6} {'Delta':>10} {'Units':>14} {'USD Value':>14} {'Note':<20}")
    print("-"*90)
    
    # Filter actionable trades (exclude HOLD)
    actionable = [t for t in trades if t.side != "HOLD"]
    holds = [t for t in trades if t.side == "HOLD"]
    
    if actionable:
        for trade in actionable:
            delta_str = f"{trade.weight_delta:+.1%}"
            units_str = f"{trade.size_delta_units:,.6f}" if trade.size_delta_units < 100 else f"{trade.size_delta_units:,.2f}"
            usd_str = f"${trade.size_delta_usd:,.2f}"
            note = trade.note[:20] if trade.note else ""
            
            print(f"{trade.symbol:<12} {trade.side:<6} {delta_str:>10} {units_str:>14} {usd_str:>14} {note:<20}")
        
        print("-"*90)
        
        # Summary
        total_buy = sum(t.size_delta_usd for t in actionable if t.side == "BUY")
        total_sell = sum(t.size_delta_usd for t in actionable if t.side == "SELL")
        print(f" Total BUY:  ${total_buy:,.2f}")
        print(f" Total SELL: ${total_sell:,.2f}")
        print(f" Net Flow:   ${total_buy - total_sell:+,.2f}")
    else:
        print(" No trades needed - portfolio within target bands")
    
    if holds:
        hold_symbols = [t.symbol for t in holds]
        print(f"\n [HOLD] {len(holds)} positions within threshold: {', '.join(hold_symbols)}")
    
    # Legacy alts section
    if legacy_values:
        print("\n" + "-"*90)
        print(f" LEGACY ALTS (parked): {legacy_pct:.1f}% of portfolio (${legacy_total:,.2f})")
        print("-"*90)
        for symbol, value in sorted(legacy_values.items(), key=lambda x: -x[1]):
            pct = value / total_equity * 100 if total_equity > 0 else 0
            print(f"   {symbol:<12} ${value:>10,.2f} ({pct:.1f}%)")
    
    print("="*90)


# =============================================================================
# MAIN - FULL WORKFLOW WITH STRATEGY 1
# =============================================================================

if __name__ == "__main__":
    from core.strategies.trend_filter_strategy import (
        get_current_targets,
        BASE_TARGETS,
        SMA_SHORT,
        SMA_LONG,
        TREND_ON,
        TREND_OFF,
    )
    
    print("\n" + "="*90)
    print(" [SHADOW MODE] Running Full Analysis with Strategy 1")
    print("="*90)
    
    # 1. Get Strategy 1 dynamic targets
    print("\n STRATEGY 1 (Trend Filter) CURRENT STATE:")
    print(f" Parameters: SMA{SMA_SHORT} / SMA{SMA_LONG}")
    print("-"*90)
    
    target_weights, trend_states, price_info = get_current_targets(BASE_TARGETS, verbose=True)
    
    # Check if all assets are OFF
    all_off = all(state == TREND_OFF for state in trend_states.values())
    total_target = sum(target_weights.values())
    
    print("-"*90)
    print("\n STRATEGY 1 TARGETS:")
    print(f"{'Asset':<12} {'Trend':>8} {'Base':>10} {'Target':>10}")
    print("-"*50)
    
    for symbol in BASE_TARGETS.keys():
        state = trend_states.get(symbol, TREND_OFF)
        state_str = "ON" if state == TREND_ON else "OFF"
        base = BASE_TARGETS[symbol]
        target = target_weights.get(symbol, 0)
        print(f"{symbol:<12} {state_str:>8} {base:>9.0%} {target:>9.0%}")
    
    print("-"*50)
    print(f"{'TOTAL':<12} {'':<8} {'100%':>10} {total_target:>9.0%}")
    print(f"{'CASH':<12} {'':<8} {'0%':>10} {1-total_target:>9.0%}")
    
    if all_off:
        print("\n" + "!"*90)
        print(" >>> ALL ASSETS IN DOWNTREND - STRATEGY SAYS 100% CASH <<<")
        print("!"*90)
    
    print("-"*90)
    print(f" Threshold: {DEFAULT_THRESHOLD:.0%}")
    
    # 2. Run shadow analysis with Strategy 1 targets
    trades, df_trades, legacy_values, total_equity, _, _ = run_shadow_analysis(
        target_weights=target_weights,
        csv_path="Docs/portfolio_hot.csv",
        min_trade_threshold=DEFAULT_THRESHOLD,
        use_strategy1=False  # We already computed targets above
    )
    
    # 3. Print results
    print_shadow_analysis(
        trades=trades,
        total_equity=total_equity,
        legacy_values=legacy_values,
        target_weights=target_weights,
        min_trade_threshold=DEFAULT_THRESHOLD
    )
