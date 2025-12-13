# analysis/maxdd_attribution.py
# v1.0.0 - Maximum Drawdown Attribution Analysis
#
# Purpose: Diagnose MaxDD causes for each regime scenario
# Shows strategy state (signals, exposure) at MaxDD date
#
# Run: python analysis/maxdd_attribution.py

import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

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
    compute_trend_state,
)
from core.portfolio_backtest_engine import PortfolioBacktestEngine
from utils.data_fetcher import get_tradingview_ohlc

# =============================================================================
# CONFIGURATION (reuse from regime tests)
# =============================================================================

USE_CACHE: bool = True

STRESS_SCENARIOS: Dict[str, Tuple[str, str]] = {
    "2018 Crypto Winter": ("2017-12-01", "2018-12-31"),
    "COVID Crash (Mar'20)": ("2020-02-01", "2020-05-31"),
    "2022 Bear Market / FTX": ("2022-01-01", "2023-01-31"),
}

ASSET_AVAILABILITY: Dict[str, str] = {
    "BTCUSDT": "2017-01-01",
    "ETHUSDT": "2017-01-01",
    "SOLUSDT": "2020-08-11",
    "LINKUSDT": "2019-01-01",
}

SWITCH_WINDOW_DAYS: int = 20  # ±20 days around MaxDD

OUTPUT_DIR = Path("Output/analysis")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class AssetState:
    """State of a single asset at MaxDD date."""
    symbol: str
    signal: str  # "ON" or "OFF"
    target_weight: float  # Weight if signal is ON
    effective_weight: float  # Actual contribution (weight * signal)


@dataclass
class SignalSwitch:
    """A signal switch event."""
    symbol: str
    date: str
    direction: str  # "ON→OFF" or "OFF→ON"


@dataclass
class MaxDDAttribution:
    """Complete MaxDD attribution for a scenario."""
    scenario: str
    max_drawdown_pct: float
    max_drawdown_date: str
    asset_states: List[AssetState]
    total_exposure_pct: float
    switches_in_window: int
    switch_details: List[SignalSwitch]
    interpretation: str


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_available_assets(start_date: str) -> Dict[str, float]:
    """Get assets available for a scenario and their normalized weights."""
    scenario_start = pd.Timestamp(start_date)
    available = {}
    
    for symbol, weight in BASE_TARGETS.items():
        avail_date = pd.Timestamp(ASSET_AVAILABILITY.get(symbol, "2017-01-01"))
        if avail_date <= scenario_start:
            available[symbol] = weight
    
    # Normalize weights
    total = sum(available.values())
    if total > 0:
        available = {k: v / total for k, v in available.items()}
    
    return available


def fetch_asset_data(symbol: str) -> Optional[pd.DataFrame]:
    """Fetch OHLCV data for an asset with caching."""
    try:
        df = get_tradingview_ohlc(
            symbol=symbol,
            exchange="BINANCE",
            n_bars=5000,
            use_cache=USE_CACHE
        )
        
        if df is None or df.empty:
            print(f"  [WARN] No data for {symbol}")
            return None
        
        # Ensure datetime index, timezone-naive
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        
        return df
    except Exception as e:
        print(f"  [ERROR] Fetch failed for {symbol}: {e}")
        return None


def find_signal_switches(
    trend_series: pd.Series,
    center_date: pd.Timestamp,
    window_days: int = SWITCH_WINDOW_DAYS
) -> List[Tuple[pd.Timestamp, str]]:
    """
    Find signal switches within ±window_days of center_date.
    
    Returns list of (date, direction) tuples.
    """
    start = center_date - timedelta(days=window_days)
    end = center_date + timedelta(days=window_days)
    
    # Slice to window
    window_data = trend_series.loc[start:end]
    
    if len(window_data) < 2:
        return []
    
    switches = []
    prev_state = None
    
    for date, state in window_data.items():
        if prev_state is not None and state != prev_state:
            if prev_state == TREND_OFF and state == TREND_ON:
                direction = "OFF→ON"
            else:
                direction = "ON→OFF"
            switches.append((date, direction))
        prev_state = state
    
    return switches


def generate_interpretation(
    total_exposure: float,
    switch_count: int
) -> str:
    """Generate automatic interpretation based on exposure and switches."""
    if total_exposure >= 0.70:
        if switch_count > 5:
            return "High exposure + whipsaw - strategy was fully invested during volatile period with frequent signal changes"
        elif switch_count <= 2:
            return "SMA lag (normal) - strategy remained invested due to SMA smoothing; DD is expected behavior"
        else:
            return "High exposure with moderate switching - partial whipsaw effect"
    elif total_exposure < 0.20:
        return "Strategy correctly defensive - low exposure during drawdown indicates risk management working"
    else:
        return "Moderate exposure - review individual asset signals for optimization opportunities"


# =============================================================================
# MAIN ANALYSIS FUNCTIONS
# =============================================================================

def analyze_scenario(
    scenario_name: str,
    start_date: str,
    end_date: str
) -> Optional[MaxDDAttribution]:
    """
    Run backtest for a scenario and analyze MaxDD attribution.
    
    Returns MaxDDAttribution dataclass or None if failed.
    """
    print(f"\n{'='*60}")
    print(f" Analyzing: {scenario_name}")
    print(f" Period: {start_date} to {end_date}")
    print(f"{'='*60}")
    
    # 1. Get available assets
    asset_weights = get_available_assets(start_date)
    print(f" Assets: {list(asset_weights.keys())}")
    
    if not asset_weights:
        print(" [ERROR] No assets available")
        return None
    
    # 2. Fetch data
    print(" Fetching data...")
    price_data = {}
    for symbol in asset_weights.keys():
        df = fetch_asset_data(symbol)
        if df is not None:
            price_data[symbol] = df
    
    if not price_data:
        print(" [ERROR] No price data available")
        return None
    
    # 3. Compute trend states and positions
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    
    processed_data = {}
    trend_states = {}
    
    for symbol, df in price_data.items():
        df = df.copy()
        
        # Compute trend state
        trend_series = compute_trend_state(df, price_col='close')
        
        # Compute log returns
        df['log_return'] = np.log(df['close'] / df['close'].shift(1))
        df['position'] = trend_series
        
        # Slice to scenario period
        df_scenario = df.loc[start_ts:end_ts].copy()
        
        if df_scenario.empty:
            continue
        
        processed_data[symbol] = df_scenario[['close', 'log_return', 'position']].copy()
        trend_states[symbol] = trend_series  # Keep full history for switch analysis
    
    if not processed_data:
        print(" [ERROR] No data in scenario period")
        return None
    
    # 4. Run backtest to get equity curve and drawdown
    print(" Running backtest...")
    
    # Normalize weights for available assets
    available_symbols = set(processed_data.keys())
    final_weights = {k: v for k, v in asset_weights.items() if k in available_symbols}
    total_w = sum(final_weights.values())
    if total_w > 0:
        final_weights = {k: v / total_w for k, v in final_weights.items()}
    
    try:
        engine = PortfolioBacktestEngine(target_weights=final_weights)
        engine.run(processed_data)
        
        equity_curve = engine.equity_curve
        drawdown_series = engine.drawdown_series
        max_drawdown = engine.max_drawdown
        
    except Exception as e:
        print(f" [ERROR] Backtest failed: {e}")
        return None
    
    # 5. Find MaxDD date
    maxdd_idx = drawdown_series.idxmin()
    maxdd_date = pd.Timestamp(maxdd_idx)
    
    print(f" MaxDD: {max_drawdown*100:.2f}% on {maxdd_date.strftime('%Y-%m-%d')}")
    
    # 6. Get asset states at MaxDD date
    asset_states = []
    total_exposure = 0.0
    
    for symbol in final_weights.keys():
        if symbol not in processed_data:
            continue
        
        df = processed_data[symbol]
        
        # Find closest date to maxdd_date in data
        if maxdd_date in df.index:
            position = df.loc[maxdd_date, 'position']
        else:
            # Find nearest date
            idx = df.index.get_indexer([maxdd_date], method='nearest')[0]
            if idx >= 0 and idx < len(df):
                position = df.iloc[idx]['position']
            else:
                position = 0
        
        signal = "ON" if position == TREND_ON else "OFF"
        target_weight = final_weights.get(symbol, 0)
        effective_weight = target_weight if signal == "ON" else 0
        
        asset_states.append(AssetState(
            symbol=symbol,
            signal=signal,
            target_weight=target_weight,
            effective_weight=effective_weight
        ))
        
        total_exposure += effective_weight
    
    # 7. Find signal switches in window
    all_switches = []
    
    for symbol, trend_series in trend_states.items():
        if symbol not in final_weights:
            continue
        
        switches = find_signal_switches(trend_series, maxdd_date, SWITCH_WINDOW_DAYS)
        for switch_date, direction in switches:
            all_switches.append(SignalSwitch(
                symbol=symbol,
                date=switch_date.strftime('%Y-%m-%d'),
                direction=direction
            ))
    
    # Sort switches by date
    all_switches.sort(key=lambda x: x.date)
    
    # 8. Generate interpretation
    interpretation = generate_interpretation(total_exposure, len(all_switches))
    
    return MaxDDAttribution(
        scenario=scenario_name,
        max_drawdown_pct=max_drawdown * 100,
        max_drawdown_date=maxdd_date.strftime('%Y-%m-%d'),
        asset_states=asset_states,
        total_exposure_pct=total_exposure * 100,
        switches_in_window=len(all_switches),
        switch_details=all_switches,
        interpretation=interpretation
    )


def format_report(attributions: List[MaxDDAttribution]) -> str:
    """Format attributions as text report."""
    lines = []
    lines.append("MAXDD ATTRIBUTION REPORT")
    lines.append("=" * 60)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"SMA Parameters: Short={SMA_SHORT}, Long={SMA_LONG}")
    lines.append("")
    
    for attr in attributions:
        lines.append("=" * 60)
        lines.append(f"SCENARIO: {attr.scenario}")
        lines.append(f"Max Drawdown: {attr.max_drawdown_pct:.2f}% on {attr.max_drawdown_date}")
        lines.append("")
        
        lines.append("STRATEGY STATE:")
        for state in attr.asset_states:
            target_pct = f"target={state.target_weight*100:.0f}%" if state.signal == "ON" else "target=0%"
            lines.append(f"  {state.symbol}: {state.signal} ({target_pct})")
        lines.append(f"Total Exposure: {attr.total_exposure_pct:.1f}%")
        lines.append("")
        
        lines.append(f"SWITCHES ±{SWITCH_WINDOW_DAYS} days: {attr.switches_in_window}")
        if attr.switch_details:
            for switch in attr.switch_details:
                lines.append(f"  {switch.symbol}: {switch.direction} on {switch.date}")
        else:
            lines.append("  (none)")
        lines.append("")
        
        lines.append("INTERPRETATION:")
        lines.append(f"  {attr.interpretation}")
        lines.append("")
    
    lines.append("=" * 60)
    lines.append("END OF REPORT")
    
    return "\n".join(lines)


def save_results(
    attributions: List[MaxDDAttribution],
    output_dir: Path = OUTPUT_DIR
) -> None:
    """Save results to text and JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save text report
    txt_path = output_dir / "maxdd_attribution.txt"
    report = format_report(attributions)
    
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n[OK] Text report: {txt_path}")
    
    # Save JSON
    json_path = output_dir / "maxdd_attribution.json"
    
    # Convert dataclasses to dicts
    data = []
    for attr in attributions:
        d = asdict(attr)
        data.append(d)
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"[OK] JSON report: {json_path}")
    
    # Print report to console
    print("\n" + report)


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run MaxDD attribution analysis for all scenarios."""
    print("\n" + "#" * 60)
    print(" MAXDD ATTRIBUTION ANALYSIS")
    print(" Diagnosing Maximum Drawdown causes per regime")
    print("#" * 60)
    
    attributions = []
    
    for scenario_name, (start_date, end_date) in STRESS_SCENARIOS.items():
        result = analyze_scenario(scenario_name, start_date, end_date)
        if result:
            attributions.append(result)
    
    if attributions:
        save_results(attributions)
        print("\n[DONE] MaxDD attribution analysis complete.")
    else:
        print("\n[ERROR] No scenarios completed successfully.")


if __name__ == "__main__":
    main()


