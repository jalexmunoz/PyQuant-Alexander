# runners/run_strategy1_regime_tests.py
# v1.1.0 - Strategy 1 Regime Stress Tests with Strict Mode
#
# Purpose: Validate Trend Filter strategy through key historical stress periods
# before v0.1-shadow-beta freeze.
#
# Scenarios: 2018 Crypto Winter, COVID Crash, 2022 Bear/FTX
#
# v1.1.0 Changes:
# - Added STRICT mode: fail fast if any asset fetch fails
# - Track requested/fetched/missing assets explicitly
# - Always print final weights used by PortfolioEngine
# - Enable caching for TradingView fetches

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field

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
from utils.quantstats_reports import generate_regime_tearsheet

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# =============================================================================
# CONFIGURATION
# =============================================================================

# STRICT MODE: If True, fail fast when any expected asset fails to fetch
# Set to False to allow partial asset sets (with renormalized weights)
STRICT_MODE: bool = True

# Enable caching for TradingView fetches (reduces connection drops)
USE_CACHE: bool = True

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
# ASSET TRACKING
# =============================================================================

@dataclass
class AssetTracker:
    """
    Track asset availability and fetch status for a scenario.
    
    Terminology:
    - requested_assets: All assets in BASE_TARGETS
    - historically_unavailable: Assets that didn't exist at scenario start date
    - fetch_failed: Assets that existed but data fetch failed (network, etc.)
    - fetched_successfully: Assets with data retrieved OK
    
    Status semantics:
    - FULL: All historically-available assets were fetched successfully
    - PARTIAL: Some historically-available assets failed to fetch (fetch_failed > 0)
    """
    scenario_name: str
    requested_assets: Set[str] = field(default_factory=set)
    historically_unavailable: Set[str] = field(default_factory=set)  # Didn't exist yet
    fetch_failed: Set[str] = field(default_factory=set)  # Existed but fetch failed
    fetched_successfully: Set[str] = field(default_factory=set)
    original_weights: Dict[str, float] = field(default_factory=dict)
    final_weights: Dict[str, float] = field(default_factory=dict)
    
    @property
    def is_partial(self) -> bool:
        """
        True if any historically-available asset failed to fetch.
        
        Note: Assets excluded due to historical unavailability do NOT make this partial.
        """
        return len(self.fetch_failed) > 0
    
    @property
    def expected_assets(self) -> Set[str]:
        """Assets that were expected (historically available) for this scenario."""
        return self.requested_assets - self.historically_unavailable
    
    def print_summary(self) -> None:
        """Print asset tracking summary."""
        print(f"\n ASSET TRACKING:")
        print(f"   Requested (base):     {sorted(self.requested_assets)}")
        print(f"   Hist. Unavailable:    {sorted(self.historically_unavailable) or '(none)'}")
        print(f"   Expected (hist OK):   {sorted(self.expected_assets)}")
        print(f"   Fetch Failed:         {sorted(self.fetch_failed) or '(none)'}")
        print(f"   Fetched Successfully: {sorted(self.fetched_successfully)}")
        
        # Only show PARTIAL warning if fetch_failed > 0
        if self.is_partial:
            print(f"\n   ⚠️  PARTIAL: {len(self.fetch_failed)} asset(s) failed to fetch!")
        else:
            print(f"\n   ✓ FULL: All historically-available assets fetched")
        
        print(f"\n   Original Weights: {self.original_weights}")
        print(f"   Final Weights:    {self.final_weights}")
        
        # Verify sum = 1
        total = sum(self.final_weights.values())
        if abs(total - 1.0) > 0.001:
            print(f"   ⚠️  WARNING: Weights sum to {total:.4f}, not 1.0!")
        else:
            print(f"   ✓ Weights sum: {total:.4f}")
    
    def has_fetch_failures(self) -> bool:
        """Check if any assets failed to fetch (not due to historical unavailability)."""
        return self.is_partial


class DataFetchError(RuntimeError):
    """Raised when asset data fetch fails in STRICT mode."""
    pass


# =============================================================================
# DATA FUNCTIONS
# =============================================================================

def fetch_asset_data(
    symbol: str,
    start_date: str,
    end_date: str,
    tracker: AssetTracker,
    use_cache: bool = USE_CACHE
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data for a single asset with buffer for SMA calculation.
    
    NOTE: This function is only called for historically-available assets.
          Historical availability is determined by get_assets_for_scenario().
    
    Updates tracker with:
    - fetched_successfully: if fetch succeeds
    - fetch_failed: if fetch fails (network error, no data, etc.)
    
    Returns:
        DataFrame if successful, None if fetch failed
    """
    # Asset should exist historically - attempt fetch
    try:
        df = get_tradingview_ohlc(
            symbol=symbol,
            exchange="BINANCE",
            n_bars=5000,
            use_cache=use_cache
        )
        
        # get_tradingview_ohlc now returns None on failure (after retries)
        if df is None or df.empty:
            logging.error(f"  [FETCH FAIL] {symbol} - No data returned after retries")
            tracker.fetch_failed.add(symbol)
            return None
        
        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        # Make timezone-naive for consistent handling
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        
        # Check data coverage
        data_start = df.index.min()
        scenario_start_ts = pd.Timestamp(start_date)
        if data_start > scenario_start_ts:
            logging.warning(f"  [WARN] {symbol} data starts {data_start.strftime('%Y-%m-%d')}, "
                          f"scenario needs {start_date}. Will use available range.")
        
        tracker.fetched_successfully.add(symbol)
        return df
        
    except Exception as e:
        logging.error(f"  [FETCH ERROR] {symbol}: {e}")
        tracker.fetch_failed.add(symbol)
        return None


def get_assets_for_scenario(
    scenario_name: str, 
    start_date: str,
    tracker: AssetTracker
) -> Dict[str, float]:
    """
    Get expected assets and base weights for a scenario.
    
    Determines which assets should be available based on historical dates.
    Does NOT renormalize weights - that happens after fetch attempts.
    
    Updates tracker with:
    - requested_assets: all assets in BASE_TARGETS
    - original_weights: base weights for all requested assets
    - historically_unavailable: assets that didn't exist at scenario start
    
    Returns:
        Dict of expected assets (historically available) with base weights
    """
    expected_assets = {}
    scenario_start = pd.Timestamp(start_date)
    
    for symbol, base_weight in BASE_TARGETS.items():
        tracker.requested_assets.add(symbol)
        tracker.original_weights[symbol] = base_weight
        
        availability_date = pd.Timestamp(ASSET_AVAILABILITY.get(symbol, "2017-01-01"))
        
        if availability_date <= scenario_start:
            expected_assets[symbol] = base_weight
        else:
            # Mark as historically unavailable NOW (not during fetch)
            tracker.historically_unavailable.add(symbol)
            logging.info(f"  [HIST] {symbol} not available for {scenario_name} (launched {availability_date.strftime('%Y-%m-%d')})")
    
    return expected_assets


def renormalize_weights(weights: Dict[str, float], available_assets: Set[str]) -> Dict[str, float]:
    """
    Renormalize weights to sum to 1.0 for available assets only.
    
    Returns dict with only available assets and normalized weights.
    """
    filtered = {k: v for k, v in weights.items() if k in available_assets}
    total = sum(filtered.values())
    
    if total > 0:
        return {k: v / total for k, v in filtered.items()}
    return {}


def print_fetch_failure_table(tracker: AssetTracker) -> None:
    """Print diagnostic table of fetch failures."""
    print("\n" + "="*60)
    print(" ❌ DATA FETCH FAILURE DIAGNOSTIC")
    print("="*60)
    print(f" Scenario: {tracker.scenario_name}")
    print(f" Missing assets due to FETCH FAILURE (not historical):")
    print("-"*60)
    for symbol in sorted(tracker.fetch_failed):
        weight = tracker.original_weights.get(symbol, 0)
        print(f"   {symbol:<12} (base weight: {weight*100:.1f}%)")
    print("-"*60)
    print(" These assets existed historically but data fetch failed.")
    print(" Check network connection or TradingView availability.")
    print("="*60)


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
    end_date: str,
    strict_mode: bool = STRICT_MODE,
    allow_partial_assets: bool = False
) -> Optional[Dict]:
    """
    Run Strategy 1 backtest for a single stress scenario.
    
    Parameters:
        scenario_name: Name of the scenario
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        strict_mode: If True, fail fast on any fetch failure
        allow_partial_assets: If True (and not strict), continue with partial asset set
    
    Returns:
        dict with metrics or None if failed
        
    Raises:
        DataFetchError: In strict mode, if any expected asset fails to fetch
    """
    print(f"\n{'='*80}")
    print(f" SCENARIO: {scenario_name}")
    print(f" Period: {start_date} to {end_date}")
    print(f" Mode: {'STRICT' if strict_mode else 'PARTIAL ALLOWED' if allow_partial_assets else 'STANDARD'}")
    print(f"{'='*80}")
    
    # Initialize asset tracker
    tracker = AssetTracker(scenario_name=scenario_name)
    
    # 1. Get expected assets for this period (based on historical availability)
    expected_weights = get_assets_for_scenario(scenario_name, start_date, tracker)
    print(f"\n Expected Assets (historically available): {list(expected_weights.keys())}")
    print(f" Base Weights: {expected_weights}")
    
    if not expected_weights:
        logging.error(f" No assets available for scenario {scenario_name}")
        return None
    
    # 2. Fetch data for all expected assets
    print(f"\n Fetching data (cache={'ON' if USE_CACHE else 'OFF'})...")
    price_data = {}
    for symbol in expected_weights.keys():
        df = fetch_asset_data(symbol, start_date, end_date, tracker)
        if df is not None:
            price_data[symbol] = df
            print(f"   ✓ {symbol}: {len(df)} bars")
        else:
            print(f"   ✗ {symbol}: FAILED")
    
    # 3. Check for fetch failures (not historical unavailability)
    if tracker.has_fetch_failures():
        print_fetch_failure_table(tracker)
        
        if strict_mode:
            failed_list = ", ".join(sorted(tracker.fetch_failed))
            raise DataFetchError(
                f"Scenario '{scenario_name}' invalid: missing {failed_list} due to data fetch failure. "
                f"Set STRICT_MODE=False to allow partial asset sets."
            )
        elif not allow_partial_assets:
            logging.error(f" Scenario aborted due to fetch failures. Use allow_partial_assets=True to continue.")
            return None
        else:
            print(f"\n ⚠️  CONTINUING WITH PARTIAL ASSET SET (allow_partial_assets=True)")
            # is_partial is now a computed property based on fetch_failed
    
    if not price_data:
        logging.error(f" No price data available for scenario")
        return None
    
    # 4. Calculate final weights (renormalized for available assets)
    final_weights = renormalize_weights(expected_weights, tracker.fetched_successfully)
    tracker.final_weights = final_weights
    
    # Print asset tracking summary
    tracker.print_summary()
    
    # 5. Generate daily positions based on trend filter
    print(f"\n Computing trend signals...")
    processed_data, trend_states = generate_daily_positions(
        price_data=price_data,
        asset_weights=final_weights,
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
    
    # 6. Analyze trend switches
    switch_analysis = analyze_trend_switches(trend_states)
    cash_pct = calculate_portfolio_cash_days(trend_states, final_weights)
    
    print(f"\n Trend Analysis:")
    print(f"   Portfolio days in cash: {cash_pct:.1f}%")
    for symbol, stats in switch_analysis.items():
        print(f"   {symbol}: {stats['switches']} switches, {stats['pct_on']:.0f}% ON / {stats['pct_off']:.0f}% OFF")
    
    # 7. Run PortfolioBacktestEngine with FINAL weights
    print(f"\n Running backtest...")
    print(f"   Final assets: {list(final_weights.keys())}")
    print(f"   Final weights: {final_weights}")
    
    # Verify weights sum to 1
    weight_sum = sum(final_weights.values())
    if abs(weight_sum - 1.0) > 0.001:
        logging.error(f"   Weight sum error: {weight_sum:.4f} != 1.0")
        return None
    
    try:
        engine = PortfolioBacktestEngine(target_weights=final_weights)
        engine.run(processed_data)
        
        # Extract results
        results = engine.get_results()
        metrics = results['metrics']
        
        # Build result dict
        scenario_result = {
            'scenario': scenario_name,
            'start_date': start_date,
            'end_date': end_date,
            'assets': list(final_weights.keys()),
            'weights': final_weights,
            'is_partial': tracker.is_partial,
            'original_weights': tracker.original_weights,
            'fetch_failed': list(tracker.fetch_failed),
            'historically_unavailable': list(tracker.historically_unavailable),
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
        if tracker.is_partial:
            print(f"   ⚠️  PARTIAL ASSET SET USED")
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
    print("\n" + "="*100)
    print(" STRATEGY 1 (TREND FILTER) - STRESS TEST SUMMARY")
    print("="*100)
    print(f" SMA Short: {SMA_SHORT} | SMA Long: {SMA_LONG}")
    print(f" Base Targets: {BASE_TARGETS}")
    print("-"*100)
    
    # Header
    print(f"\n{'Scenario':<28} {'Assets':>12} {'Return':>10} {'Max DD':>10} {'CAGR':>10} {'Sharpe':>8} {'Cash %':>8} {'Status':>10}")
    print("-"*100)
    
    for r in results:
        if r is None:
            continue
        
        name = r['scenario'][:27]
        assets = f"{len(r['assets'])}/{len(BASE_TARGETS)}"
        ret = f"{r['total_return']*100:+.1f}%" if not np.isnan(r['total_return']) else "N/A"
        dd = f"{r['max_drawdown']*100:.1f}%" if not np.isnan(r['max_drawdown']) else "N/A"
        cagr = f"{r['cagr']*100:+.1f}%" if not np.isnan(r['cagr']) else "N/A"
        sharpe = f"{r['sharpe']:.2f}" if not np.isnan(r['sharpe']) else "N/A"
        cash = f"{r['cash_pct']:.0f}%"
        status = "PARTIAL" if r.get('is_partial', False) else "FULL"
        
        print(f"{name:<28} {assets:>12} {ret:>10} {dd:>10} {cagr:>10} {sharpe:>8} {cash:>8} {status:>10}")
    
    print("-"*100)
    
    # Show final weights used for each scenario
    print("\n FINAL WEIGHTS USED (after renormalization):")
    print("-"*100)
    
    for r in results:
        if r is None:
            continue
        weights_str = ", ".join([f"{k}: {v*100:.1f}%" for k, v in r['weights'].items()])
        partial_flag = " [PARTIAL]" if r.get('is_partial', False) else ""
        print(f" {r['scenario']}{partial_flag}:")
        print(f"   {weights_str}")
        if r.get('fetch_failed'):
            print(f"   ⚠️ Fetch failed: {r['fetch_failed']}")
        if r.get('historically_unavailable'):
            print(f"   (Historically unavailable: {r['historically_unavailable']})")
    
    # Detailed switch analysis
    print("\n TREND SWITCHES BY ASSET:")
    print("-"*100)
    
    for r in results:
        if r is None:
            continue
        print(f"\n {r['scenario']}:")
        for symbol, stats in r['switch_analysis'].items():
            print(f"   {symbol:<10} {stats['switches']:>3} switches | ON: {stats['pct_on']:>4.0f}% ({stats['days_on']:>4} days) | OFF: {stats['pct_off']:>4.0f}% ({stats['days_off']:>4} days)")
    
    print("\n" + "="*100)
    print(" INTERPRETATION:")
    print("-"*100)
    print(" - High Cash %: Strategy correctly identified downtrend and exited")
    print(" - Low Switches: Less whipsawing, smoother equity curve")
    print(" - Positive Return in bear: Alpha from trend following")
    print(" - Max DD < Buy-Hold: Risk management working")
    
    # Only show PARTIAL explanation if any scenario is actually PARTIAL
    has_partial = any(r.get('is_partial', False) for r in results if r is not None)
    if has_partial:
        print(" - PARTIAL status: Some assets missing due to fetch failure (results may not represent full basket)")
    
    print("="*100)


def run_all_scenarios(
    strict_mode: bool = STRICT_MODE,
    allow_partial_assets: bool = False
) -> List[Dict]:
    """
    Run all stress scenarios and return results.
    
    Parameters:
        strict_mode: If True, fail fast on any fetch failure
        allow_partial_assets: If True (and not strict), continue with partial asset sets
    
    Returns:
        List of result dicts (None for failed scenarios)
        
    Raises:
        DataFetchError: In strict mode, if any expected asset fails to fetch
    """
    print("\n" + "#"*90)
    print(" STRATEGY 1 REGIME TESTS")
    print(" Validating Trend Filter through historical stress periods")
    print(f" Mode: {'STRICT' if strict_mode else 'PARTIAL ALLOWED' if allow_partial_assets else 'STANDARD'}")
    print(f" Cache: {'ON' if USE_CACHE else 'OFF'}")
    print("#"*90)
    
    results = []
    
    for scenario_name, (start_date, end_date) in STRESS_SCENARIOS.items():
        result = run_scenario(
            scenario_name, 
            start_date, 
            end_date,
            strict_mode=strict_mode,
            allow_partial_assets=allow_partial_assets
        )
        results.append(result)
    
    return results


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Strategy 1 Regime Stress Tests")
    parser.add_argument(
        "--no-strict", 
        action="store_true", 
        help="Disable strict mode (allow partial asset sets on fetch failure)"
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Continue with partial asset sets when fetch fails (requires --no-strict)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable data caching"
    )
    args = parser.parse_args()
    
    # Override globals based on args
    if args.no_cache:
        USE_CACHE = False
    
    strict_mode = not args.no_strict
    allow_partial = args.allow_partial
    
    try:
        # Run all scenarios
        results = run_all_scenarios(
            strict_mode=strict_mode,
            allow_partial_assets=allow_partial
        )
        
        # Print summary
        valid_results = [r for r in results if r is not None]
        
        if valid_results:
            print_summary_table(valid_results)
            
            # Generate QuantStats HTML tear sheets
            try:
                generate_regime_tearsheet(
                    regime_results=valid_results,
                    output_dir="Output/quantstats"
                )
                print("QuantStats reports generated in Output/quantstats/")
            except ImportError as e:
                print(f"\n[WARN] {e}")
                print("       Skipping QuantStats report generation.")
            except Exception as e:
                print(f"\n[ERROR] QuantStats generation failed: {e}")
        else:
            print("\n[ERROR] No scenarios completed successfully.")
        
        print("\n[DONE] Strategy 1 regime tests complete.")
        
    except DataFetchError as e:
        print(f"\n{'='*80}")
        print(f" ❌ STRICT MODE FAILURE")
        print(f"{'='*80}")
        print(f" {e}")
        print(f"\n To continue with partial asset sets, run with:")
        print(f"   python {__file__} --no-strict --allow-partial")
        print(f"{'='*80}")
        sys.exit(1)

