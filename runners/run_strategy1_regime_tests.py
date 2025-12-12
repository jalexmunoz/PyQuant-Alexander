# runners/run_strategy1_regime_tests.py
# v1.0.0 - Strategy 1 Regime Stress Tests
#
# Purpose: Validate Trend Filter strategy through key historical stress periods
# before v0.1-shadow-beta freeze.
#
# Scenarios: 2018 Crypto Winter, COVID Crash, 2022 Bear/FTX

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime

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
    apply_trend_filter,
)
from core.portfolio_backtest_engine import PortfolioBacktestEngine
from utils.data_fetcher import get_tradingview_ohlc

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# =============================================================================
# CONFIGURATION
# =============================================================================

STRESS_SCENARIOS: Dict[str, Tuple[str, str]] = {
    "2018 Crypto Winter": ("2017-12-01", "2018-12-31"),
    "COVID Crash (Mar'20)": ("2020-02-01", "2020-05-31"),
    "2022 Bear Market / FTX": ("2022-01-01", "2023-01-31"),
}

ASSETS: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "LINKUSDT"]

# Asset availability dates (approximate)
ASSET_AVAILABILITY: Dict[str, str] = {
    "BTCUSDT": "2017-01-01",
    "ETHUSDT": "2017-01-01",
    "SOLUSDT": "2020-08-11",  # SOL launched Aug 2020
    "LINKUSDT": "2019-01-01",  # LINK available from early 2019 on Binance
}


# =============================================================================
# DATA FUNCTIONS
# =============================================================================

def fetch_asset_data(
    symbol: str,
    start_date: str,
    end_date: str,
    buffer_days: int = 250  # Need 200+ days before start for SMA200
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data for a single asset with buffer for SMA calculation.
    
    Returns None if asset wasn't available during the period.
    """
    # Check if asset was available
    availability_date = pd.Timestamp(ASSET_AVAILABILITY.get(symbol, "2017-01-01"))
    scenario_start = pd.Timestamp(start_date)
    
    if availability_date > scenario_start:
        logging.warning(f"  [SKIP] {symbol} not available until {availability_date.strftime('%Y-%m-%d')}")
        return None
    
    try:
        # Fetch max available history (TradingView free has limits)
        # 5000 daily bars ≈ 13+ years
        df = get_tradingview_ohlc(
            symbol=symbol,
            exchange="BINANCE",
            n_bars=5000
        )
        
        if df.empty:
            logging.warning(f"  [WARN] No data returned for {symbol}")
            return None
        
        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        # Make timezone-naive for consistent handling
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        
        # Check data coverage
        data_start = df.index.min()
        data_end = df.index.max()
        
        if data_start > scenario_start:
            logging.warning(f"  [WARN] {symbol} data starts {data_start.strftime('%Y-%m-%d')}, "
                          f"scenario needs {start_date}. Will use available range.")
        
        return df
        
    except Exception as e:
        logging.error(f"  [ERROR] Failed to fetch {symbol}: {e}")
        return None


def get_assets_for_scenario(scenario_name: str, start_date: str) -> Dict[str, float]:
    """
    Get available assets and adjusted weights for a scenario.
    
    Redistributes weights if some assets aren't available.
    """
    available_assets = {}
    unavailable_weight = 0.0
    
    scenario_start = pd.Timestamp(start_date)
    
    for symbol, base_weight in BASE_TARGETS.items():
        availability_date = pd.Timestamp(ASSET_AVAILABILITY.get(symbol, "2017-01-01"))
        
        if availability_date <= scenario_start:
            available_assets[symbol] = base_weight
        else:
            unavailable_weight += base_weight
            logging.info(f"  {symbol} unavailable for {scenario_name} (starts {availability_date.strftime('%Y-%m-%d')})")
    
    # Redistribute unavailable weight proportionally
    if unavailable_weight > 0 and available_assets:
        total_available = sum(available_assets.values())
        for symbol in available_assets:
            available_assets[symbol] = available_assets[symbol] / total_available
    
    return available_assets


# =============================================================================
# STRATEGY FUNCTIONS
# =============================================================================

def generate_daily_positions(
    price_data: Dict[str, pd.DataFrame],
    asset_weights: Dict[str, float],
    start_date: str,
    end_date: str
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, pd.Series]]:
    """
    Generate daily position signals for all assets based on trend filter.
    
    Returns:
        - processed_data: Dict of DataFrames with 'position', 'log_return' columns
        - trend_states: Dict of trend state Series for analysis
    """
    processed_data = {}
    trend_states = {}
    
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    
    for symbol, df in price_data.items():
        if df is None or df.empty:
            continue
        
        # Make index timezone-naive for consistent slicing
        df = df.copy()
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        
        # Check if data covers the scenario period
        data_start = df.index.min()
        data_end = df.index.max()
        
        if data_start > start_ts:
            logging.warning(f"  [WARN] {symbol} data starts {data_start.strftime('%Y-%m-%d')}, after scenario start {start_date}")
            # Use available data from data_start
            effective_start = data_start
        else:
            effective_start = start_ts
        
        if data_end < end_ts:
            logging.warning(f"  [WARN] {symbol} data ends {data_end.strftime('%Y-%m-%d')}, before scenario end {end_date}")
            effective_end = data_end
        else:
            effective_end = end_ts
        
        # Compute trend state for full history (need SMA200)
        trend_series = compute_trend_state(df, price_col='close')
        
        # Compute log returns
        df['log_return'] = np.log(df['close'] / df['close'].shift(1))
        
        # Position = trend state (1 or 0)
        df['position'] = trend_series
        
        # Slice to scenario period (using effective dates)
        df_scenario = df.loc[effective_start:effective_end].copy()
        
        if df_scenario.empty:
            logging.warning(f"  [WARN] No data for {symbol} in period {start_date} to {end_date}")
            continue
        
        processed_data[symbol] = df_scenario[['close', 'log_return', 'position']].copy()
        trend_states[symbol] = trend_series.loc[effective_start:effective_end]
    
    return processed_data, trend_states


def analyze_trend_switches(trend_states: Dict[str, pd.Series]) -> Dict[str, Dict]:
    """
    Analyze trend state switches for each asset.
    
    Returns dict with:
        - switches: number of ON/OFF transitions
        - days_on: percentage of days in ON state
        - days_off: percentage of days in OFF state
    """
    analysis = {}
    
    for symbol, trend_series in trend_states.items():
        if trend_series.empty:
            continue
        
        # Count switches (state changes)
        switches = (trend_series != trend_series.shift(1)).sum() - 1  # -1 for first NaN
        switches = max(0, switches)
        
        # Days in each state
        total_days = len(trend_series)
        days_on = (trend_series == TREND_ON).sum()
        days_off = (trend_series == TREND_OFF).sum()
        
        analysis[symbol] = {
            'switches': int(switches),
            'days_on': days_on,
            'days_off': days_off,
            'pct_on': days_on / total_days * 100 if total_days > 0 else 0,
            'pct_off': days_off / total_days * 100 if total_days > 0 else 0,
        }
    
    return analysis


def calculate_portfolio_cash_days(
    trend_states: Dict[str, pd.Series],
    asset_weights: Dict[str, float]
) -> float:
    """
    Calculate percentage of days portfolio was effectively in cash.
    
    A day is "in cash" when all assets have trend_state = OFF.
    """
    if not trend_states:
        return 100.0
    
    # Align all trend series
    df_trends = pd.DataFrame(trend_states)
    
    # Portfolio is in cash when all assets are OFF (sum of positions = 0)
    df_trends_weighted = df_trends.copy()
    for col in df_trends_weighted.columns:
        if col in asset_weights:
            df_trends_weighted[col] = df_trends[col] * asset_weights[col]
    
    portfolio_exposure = df_trends_weighted.sum(axis=1)
    days_in_cash = (portfolio_exposure == 0).sum()
    total_days = len(portfolio_exposure)
    
    return days_in_cash / total_days * 100 if total_days > 0 else 0


# =============================================================================
# MAIN TEST RUNNER
# =============================================================================

def run_scenario(
    scenario_name: str,
    start_date: str,
    end_date: str
) -> Optional[Dict]:
    """
    Run Strategy 1 backtest for a single stress scenario.
    
    Returns dict with metrics or None if failed.
    """
    print(f"\n{'='*80}")
    print(f" SCENARIO: {scenario_name}")
    print(f" Period: {start_date} to {end_date}")
    print(f"{'='*80}")
    
    # 1. Get available assets for this period
    asset_weights = get_assets_for_scenario(scenario_name, start_date)
    print(f" Assets: {list(asset_weights.keys())}")
    print(f" Weights: {asset_weights}")
    
    if not asset_weights:
        logging.error(f" No assets available for scenario {scenario_name}")
        return None
    
    # 2. Fetch data for all available assets
    print(f"\n Fetching data...")
    price_data = {}
    for symbol in asset_weights.keys():
        df = fetch_asset_data(symbol, start_date, end_date)
        if df is not None and not df.empty:
            price_data[symbol] = df
            print(f"   {symbol}: {len(df)} bars")
    
    if not price_data:
        logging.error(f" No price data available for scenario")
        return None
    
    # 3. Generate daily positions based on trend filter
    print(f"\n Computing trend signals...")
    processed_data, trend_states = generate_daily_positions(
        price_data=price_data,
        asset_weights=asset_weights,
        start_date=start_date,
        end_date=end_date
    )
    
    if not processed_data:
        logging.error(f" Failed to generate positions - no data in scenario period")
        print(f" [SKIP] Scenario {scenario_name}: Data does not cover this period")
        return None
    
    # Check actual date range in processed data
    for symbol, df in processed_data.items():
        actual_start = df.index.min().strftime('%Y-%m-%d')
        actual_end = df.index.max().strftime('%Y-%m-%d')
        print(f"   {symbol}: {actual_start} to {actual_end} ({len(df)} days)")
    
    # 4. Analyze trend switches
    switch_analysis = analyze_trend_switches(trend_states)
    cash_pct = calculate_portfolio_cash_days(trend_states, asset_weights)
    
    print(f"\n Trend Analysis:")
    print(f"   Portfolio days in cash: {cash_pct:.1f}%")
    for symbol, stats in switch_analysis.items():
        print(f"   {symbol}: {stats['switches']} switches, {stats['pct_on']:.0f}% ON / {stats['pct_off']:.0f}% OFF")
    
    # 5. Run PortfolioBacktestEngine
    print(f"\n Running backtest...")
    
    # Adjust weights for actually available processed data
    available_in_period = set(processed_data.keys())
    adjusted_weights = {k: v for k, v in asset_weights.items() if k in available_in_period}
    
    # Normalize weights
    total_w = sum(adjusted_weights.values())
    if total_w > 0:
        adjusted_weights = {k: v / total_w for k, v in adjusted_weights.items()}
    
    try:
        engine = PortfolioBacktestEngine(target_weights=adjusted_weights)
        engine.run(processed_data)
        
        # Extract results using new risk fields
        results = engine.get_results()
        metrics = results['metrics']
        
        # Build result dict
        scenario_result = {
            'scenario': scenario_name,
            'start_date': start_date,
            'end_date': end_date,
            'assets': list(adjusted_weights.keys()),
            'weights': adjusted_weights,
            # Performance metrics
            'total_return': metrics.get('total_return_strategy', np.nan),
            'cagr': metrics.get('cagr_strategy', np.nan),
            'max_drawdown': results['max_drawdown'],
            'sharpe': metrics.get('sharpe_ratio', np.nan),
            'sortino': metrics.get('sortino_ratio', np.nan),
            # Risk metrics
            'var_95': metrics.get('VaR_95_daily', np.nan),
            'cvar_95': metrics.get('CVaR_95_daily', np.nan),
            # Trend analysis
            'cash_pct': cash_pct,
            'switch_analysis': switch_analysis,
            # Series for further analysis
            'equity_curve': results['equity_curve'],
            'returns': results['returns'],
            'drawdown_series': results['drawdown_series'],
        }
        
        print(f"\n Results:")
        print(f"   Total Return: {scenario_result['total_return']*100:+.1f}%")
        print(f"   Max Drawdown: {scenario_result['max_drawdown']*100:.1f}%")
        print(f"   CAGR: {scenario_result['cagr']*100:+.1f}%")
        print(f"   Sharpe: {scenario_result['sharpe']:.2f}")
        
        return scenario_result
        
    except Exception as e:
        logging.error(f" Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def print_summary_table(results: List[Dict]) -> None:
    """
    Print summary table of all scenario results.
    """
    print("\n" + "="*90)
    print(" STRATEGY 1 (TREND FILTER) - STRESS TEST SUMMARY")
    print("="*90)
    print(f" SMA Short: {SMA_SHORT} | SMA Long: {SMA_LONG}")
    print(f" Base Targets: {BASE_TARGETS}")
    print("-"*90)
    
    # Header
    print(f"\n{'Scenario':<28} {'Return':>10} {'Max DD':>10} {'CAGR':>10} {'Sharpe':>10} {'Cash %':>10}")
    print("-"*90)
    
    for r in results:
        if r is None:
            continue
        
        name = r['scenario'][:27]
        ret = f"{r['total_return']*100:+.1f}%" if not np.isnan(r['total_return']) else "N/A"
        dd = f"{r['max_drawdown']*100:.1f}%" if not np.isnan(r['max_drawdown']) else "N/A"
        cagr = f"{r['cagr']*100:+.1f}%" if not np.isnan(r['cagr']) else "N/A"
        sharpe = f"{r['sharpe']:.2f}" if not np.isnan(r['sharpe']) else "N/A"
        cash = f"{r['cash_pct']:.0f}%"
        
        print(f"{name:<28} {ret:>10} {dd:>10} {cagr:>10} {sharpe:>10} {cash:>10}")
    
    print("-"*90)
    
    # Detailed switch analysis
    print("\n TREND SWITCHES BY ASSET:")
    print("-"*90)
    
    for r in results:
        if r is None:
            continue
        print(f"\n {r['scenario']}:")
        for symbol, stats in r['switch_analysis'].items():
            print(f"   {symbol:<10} {stats['switches']:>3} switches | ON: {stats['pct_on']:>4.0f}% ({stats['days_on']:>4} days) | OFF: {stats['pct_off']:>4.0f}% ({stats['days_off']:>4} days)")
    
    print("\n" + "="*90)
    print(" INTERPRETATION:")
    print("-"*90)
    print(" - High Cash %: Strategy correctly identified downtrend and exited")
    print(" - Low Switches: Less whipsawing, smoother equity curve")
    print(" - Positive Return in bear: Alpha from trend following")
    print(" - Max DD < Buy-Hold: Risk management working")
    print("="*90)


def run_all_scenarios() -> List[Dict]:
    """
    Run all stress scenarios and return results.
    """
    print("\n" + "#"*90)
    print(" STRATEGY 1 REGIME TESTS")
    print(" Validating Trend Filter through historical stress periods")
    print("#"*90)
    
    results = []
    
    for scenario_name, (start_date, end_date) in STRESS_SCENARIOS.items():
        result = run_scenario(scenario_name, start_date, end_date)
        results.append(result)
    
    return results


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Run all scenarios
    results = run_all_scenarios()
    
    # Print summary
    valid_results = [r for r in results if r is not None]
    
    if valid_results:
        print_summary_table(valid_results)
    else:
        print("\n[ERROR] No scenarios completed successfully.")
    
    print("\n[DONE] Strategy 1 regime tests complete.")

