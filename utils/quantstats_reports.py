# utils/quantstats_reports.py
# v1.2.0 - QuantStats Integration for OOS Performance Reports
#
# Purpose: Generate professional tear sheets for out-of-sample regime tests
#
# v1.2.0 Changes:
# - Added safe file writing with fallback filenames when locked
#
# v1.1.0 Changes:
# - Added scoreboard CSV/markdown generation
# - Added synthetic combined series (no calendar gaps)
# - Warning banner for combined_oos.html calendar gap issue

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import numpy as np
import pandas as pd

try:
    import quantstats as qs
    QUANTSTATS_AVAILABLE = True
except ImportError:
    QUANTSTATS_AVAILABLE = False
    logging.warning("QuantStats not installed. Run: pip install quantstats")

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def log_returns_to_simple(log_returns: pd.Series) -> pd.Series:
    """
    Convert log returns to simple returns for QuantStats.
    
    Parameters:
        log_returns: pd.Series of log (continuously compounded) returns
        
    Returns:
        pd.Series of simple (arithmetic) returns
    """
    return np.exp(log_returns) - 1


def _validate_returns(returns: pd.Series, name: str = "returns") -> bool:
    """
    Validate returns series before processing.
    
    Returns True if valid, False otherwise.
    """
    if returns is None:
        logging.warning(f"[SKIP] {name}: returns is None")
        return False
    
    if returns.empty:
        logging.warning(f"[SKIP] {name}: returns series is empty")
        return False
    
    if returns.isna().all():
        logging.warning(f"[SKIP] {name}: returns series is all NaN")
        return False
    
    return True


def _ensure_output_dir(output_path: str) -> Path:
    """
    Ensure output directory exists.
    
    Returns Path object for the output file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def calc_risk_metrics(returns: pd.Series, confidence: float = 0.05) -> Tuple[float, float]:
    """
    Calculate VaR and CVaR at given confidence level.
    
    Parameters:
        returns: Daily returns series (log or simple)
        confidence: Confidence level for VaR (default 0.05 = 95% VaR)
        
    Returns:
        Tuple of (VaR, CVaR) as decimals (e.g., -0.03 = -3%)
        
    Note:
        VaR = Value at Risk (worst expected loss at confidence level)
        CVaR = Conditional VaR (expected loss given VaR is breached)
    """
    if returns is None or len(returns.dropna()) == 0:
        return np.nan, np.nan
    
    clean_returns = returns.dropna()
    
    # VaR: quantile at confidence level (e.g., 5th percentile)
    var = float(clean_returns.quantile(confidence))
    
    # CVaR: mean of returns below VaR
    tail_returns = clean_returns[clean_returns <= var]
    if len(tail_returns) > 0:
        cvar = float(tail_returns.mean())
    else:
        cvar = var  # Fallback if no tail observations
    
    return var, cvar


def _safe_write_file(
    path: Path,
    write_func,
    file_type: str = "file"
) -> Tuple[Path, bool]:
    """
    Safely write a file with fallback to timestamped filename if locked.
    
    Parameters:
        path: Target file path
        write_func: Callable that takes a Path and writes to it
        file_type: Description for logging (e.g., "CSV", "markdown")
        
    Returns:
        Tuple of (actual_path_written, used_fallback)
    """
    try:
        write_func(path)
        return path, False
    except PermissionError:
        # File likely locked (e.g., open in Excel)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = path.stem
        suffix = path.suffix
        fallback_path = path.parent / f"{stem}_{timestamp}{suffix}"
        
        try:
            write_func(fallback_path)
            logging.warning(
                f"[WARN] {path.name} locked → saved as {fallback_path.name}"
            )
            return fallback_path, True
        except Exception as e:
            logging.error(f"[ERROR] Failed to write {file_type} even with fallback: {e}")
            raise
    except Exception as e:
        logging.error(f"[ERROR] Failed to write {file_type}: {e}")
        raise


# =============================================================================
# MAIN FUNCTIONS
# =============================================================================

def generate_tearsheet(
    returns: pd.Series,
    benchmark: Optional[pd.Series] = None,
    title: str = "Strategy Performance",
    output_path: Optional[str] = None
) -> None:
    """
    Generate QuantStats HTML tear sheet.
    
    Parameters:
        returns: pd.Series of daily returns (log or simple).
                 If log returns detected, converts to simple automatically.
        benchmark: optional benchmark returns (e.g., BTC buy-hold)
        title: report title
        output_path: if provided, save HTML to this path (e.g., "Output/tearsheet.html")
                    If None, displays in browser.
    
    Returns:
        None
    
    Raises:
        ImportError: if quantstats is not installed
    """
    if not QUANTSTATS_AVAILABLE:
        raise ImportError("QuantStats not installed. Run: pip install quantstats>=0.0.62")
    
    if not _validate_returns(returns, title):
        return
    
    # Clean returns - drop NaN and ensure proper index
    returns_clean = returns.dropna().copy()
    
    if not isinstance(returns_clean.index, pd.DatetimeIndex):
        returns_clean.index = pd.to_datetime(returns_clean.index)
    
    # QuantStats expects simple returns - convert if log returns detected
    # Heuristic: log returns typically have smaller absolute values and sum closer to 0
    # For safety, always convert assuming log returns (as per project standard)
    returns_simple = log_returns_to_simple(returns_clean)
    
    # Process benchmark if provided
    benchmark_simple = None
    if benchmark is not None and _validate_returns(benchmark, "benchmark"):
        benchmark_clean = benchmark.dropna().copy()
        if not isinstance(benchmark_clean.index, pd.DatetimeIndex):
            benchmark_clean.index = pd.to_datetime(benchmark_clean.index)
        benchmark_simple = log_returns_to_simple(benchmark_clean)
        
        # Align benchmark to returns index
        common_idx = returns_simple.index.intersection(benchmark_simple.index)
        if len(common_idx) > 0:
            returns_simple = returns_simple.loc[common_idx]
            benchmark_simple = benchmark_simple.loc[common_idx]
        else:
            logging.warning("[WARN] No overlapping dates between returns and benchmark")
            benchmark_simple = None
    
    # Generate report
    if output_path:
        output_file = _ensure_output_dir(output_path)
        qs.reports.html(
            returns_simple,
            benchmark=benchmark_simple,
            title=title,
            output=str(output_file)
        )
        logging.info(f"[OK] Tear sheet saved: {output_file}")
    else:
        # Display in browser
        qs.reports.html(
            returns_simple,
            benchmark=benchmark_simple,
            title=title
        )


def _scenario_to_filename(scenario_name: str) -> str:
    """Convert scenario name to safe filename."""
    safe_name = scenario_name.lower()
    safe_name = safe_name.replace(" ", "_")
    safe_name = safe_name.replace("/", "_")
    safe_name = safe_name.replace("(", "")
    safe_name = safe_name.replace(")", "")
    safe_name = safe_name.replace("'", "")
    return safe_name


def generate_scoreboard(
    regime_results: List[Dict],
    output_dir: str = "Output/quantstats"
) -> pd.DataFrame:
    """
    Generate a scoreboard CSV and markdown summary of all regime results.
    
    This is the preferred way to interpret combined OOS results since it
    avoids the calendar gap problem inherent in stitched time series.
    
    Parameters:
        regime_results: List of dicts from run_strategy1_regime_tests
        output_dir: Directory to save scoreboard files
        
    Returns:
        DataFrame with scoreboard data
        
    Creates:
        - Output/quantstats/combined_scoreboard.csv
        - Output/quantstats/combined_scoreboard.md
    """
    if not regime_results:
        logging.warning("[SKIP] No regime results for scoreboard")
        return pd.DataFrame()
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    rows = []
    
    for result in regime_results:
        if result is None:
            continue
        
        scenario = result.get('scenario', 'Unknown')
        
        # Calculate switches summary
        switch_analysis = result.get('switch_analysis', {})
        total_switches = sum(s.get('switches', 0) for s in switch_analysis.values())
        
        # Calculate VaR/CVaR directly from returns (fixes NaN issue)
        returns_series = result.get('returns')
        var_95, cvar_95 = calc_risk_metrics(returns_series, confidence=0.05)
        
        row = {
            'Scenario': scenario,
            'Period': f"{result.get('start_date', '')} to {result.get('end_date', '')}",
            'Assets': len(result.get('assets', [])),
            'Return (%)': result.get('total_return', np.nan) * 100,
            'Max DD (%)': result.get('max_drawdown', np.nan) * 100,
            'CAGR (%)': result.get('cagr', np.nan) * 100,
            'Sharpe': result.get('sharpe', np.nan),
            'Sortino': result.get('sortino', np.nan),
            'VaR 95 (%)': var_95 * 100 if not np.isnan(var_95) else np.nan,
            'CVaR 95 (%)': cvar_95 * 100 if not np.isnan(cvar_95) else np.nan,
            'Cash Days (%)': result.get('cash_pct', np.nan),
            'Total Switches': total_switches,
            'Status': 'PARTIAL' if result.get('is_partial', False) else 'FULL',
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    
    if df.empty:
        return df
    
    # Save CSV with safe write (fallback if locked)
    csv_path = output_path / "combined_scoreboard.csv"
    
    def write_csv(p: Path):
        df.to_csv(p, index=False, float_format='%.2f')
    
    try:
        actual_csv, used_fallback = _safe_write_file(csv_path, write_csv, "CSV")
        logging.info(f"[OK] Scoreboard CSV: {actual_csv}")
    except Exception:
        logging.error("[ERROR] Could not save scoreboard CSV")
    
    # Save Markdown with safe write
    md_path = output_path / "combined_scoreboard.md"
    
    def write_markdown(p: Path):
        with open(p, 'w', encoding='utf-8') as f:
            f.write("# Strategy 1 OOS Regime Tests - Scoreboard\n\n")
            f.write("**Interpretation Note**: This scoreboard shows metrics per stress regime.\n")
            f.write("Do NOT use combined_oos.html for CAGR/DD duration - it has calendar gaps.\n\n")
            f.write("## Results by Scenario\n\n")
            f.write(df.to_markdown(index=False, floatfmt='.2f'))
            f.write("\n\n## Key Metrics\n\n")
            
            # Summary stats
            valid_returns = df['Return (%)'].dropna()
            valid_sharpe = df['Sharpe'].dropna()
            valid_dd = df['Max DD (%)'].dropna()
            
            if len(valid_returns) > 0:
                f.write(f"- **Average Return**: {valid_returns.mean():.2f}%\n")
                f.write(f"- **Worst Return**: {valid_returns.min():.2f}%\n")
                f.write(f"- **Best Return**: {valid_returns.max():.2f}%\n")
            if len(valid_sharpe) > 0:
                f.write(f"- **Average Sharpe**: {valid_sharpe.mean():.2f}\n")
            if len(valid_dd) > 0:
                # Use .min() because DD is negative - most negative is worst
                f.write(f"- **Worst Max DD**: {valid_dd.min():.2f}%\n")
            
            f.write("\n---\n")
            f.write(f"*Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}*\n")
    
    try:
        actual_md, _ = _safe_write_file(md_path, write_markdown, "markdown")
        logging.info(f"[OK] Scoreboard MD: {actual_md}")
    except Exception:
        logging.error("[ERROR] Could not save scoreboard markdown")
    
    return df


def _inject_warning_banner(html_path: Path, warning_html: str) -> bool:
    """
    Inject a warning banner into an existing HTML file.
    
    Inserts the warning after the opening <body> tag.
    
    Returns True if successful.
    """
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find <body> tag and insert after it
        body_pos = content.lower().find('<body')
        if body_pos == -1:
            logging.warning(f"[WARN] No <body> tag found in {html_path}")
            return False
        
        # Find the end of the body tag
        body_end = content.find('>', body_pos)
        if body_end == -1:
            return False
        
        # Insert warning after body tag
        new_content = (
            content[:body_end + 1] + 
            '\n' + warning_html + '\n' +
            content[body_end + 1:]
        )
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return True
    except Exception as e:
        logging.warning(f"[WARN] Failed to inject warning banner: {e}")
        return False


def generate_synthetic_combined(
    regime_results: List[Dict],
    output_dir: str = "Output/quantstats"
) -> Optional[pd.Series]:
    """
    Generate a synthetic combined returns series with no calendar gaps.
    
    This concatenates all regime returns sequentially using a SYNTHETIC
    date index for visualization only. Real dates are NOT preserved.
    
    Parameters:
        regime_results: List of dicts with 'returns' key
        output_dir: Directory to save HTML report
        
    Returns:
        Synthetic combined returns series (or None if failed)
        
    Creates:
        - Output/quantstats/combined_oos_synthetic_VISUAL_ONLY.html
    """
    if not QUANTSTATS_AVAILABLE:
        logging.warning("[SKIP] QuantStats not available for synthetic combined")
        return None
    
    if not regime_results:
        logging.warning("[SKIP] No regime results for synthetic combined")
        return None
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Collect all returns (in order) and count days per scenario
    all_returns = []
    scenario_info = []
    
    for result in regime_results:
        if result is None:
            continue
        
        returns = result.get('returns')
        scenario_name = result.get('scenario', 'unknown')
        if not _validate_returns(returns, scenario_name):
            continue
        
        clean_returns = returns.dropna()
        all_returns.append(clean_returns)
        scenario_info.append({
            'name': scenario_name,
            'days': len(clean_returns)
        })
    
    if not all_returns:
        logging.warning("[SKIP] No valid returns for synthetic combined")
        return None
    
    # Concatenate returns sequentially (ignore original dates)
    combined_values = pd.concat(all_returns, axis=0, ignore_index=True)
    
    # Create synthetic daily date index (starting from 2000-01-01)
    synthetic_dates = pd.date_range(
        start='2000-01-01',
        periods=len(combined_values),
        freq='D'
    )
    
    synthetic_series = pd.Series(
        combined_values.values,
        index=synthetic_dates,
        name='synthetic_combined'
    )
    
    # Build scenario breakdown string
    scenario_breakdown = " + ".join(
        f"{s['name']}: {s['days']}d" for s in scenario_info
    )
    total_days = sum(s['days'] for s in scenario_info)
    
    # Generate HTML report with clear filename
    try:
        output_file = output_path / "combined_oos_synthetic_VISUAL_ONLY.html"
        generate_tearsheet(
            returns=synthetic_series,
            benchmark=None,
            title=f"⚠️ SYNTHETIC Combined OOS ({total_days} days stitched)",
            output_path=str(output_file)
        )
        
        # Inject warning banner into the HTML
        warning_html = f"""
<div style="background-color: #fff3cd; border: 2px solid #ffc107; 
            padding: 15px; margin: 20px; border-radius: 5px; font-family: Arial, sans-serif;">
    <strong style="font-size: 16px;">⚠️ SYNTHETIC TIME SERIES - VISUAL ONLY</strong><br><br>
    This report stitches {len(scenario_info)} stress scenarios into a continuous series:<br>
    <code style="background: #f8f9fa; padding: 3px 6px; border-radius: 3px;">{scenario_breakdown} = {total_days} days</code><br><br>
    <strong>Dates shown are artificial</strong> (starting 2000-01-01) for visualization only.<br>
    Do <strong>NOT</strong> use for duration-based metrics (CAGR annualization, DD duration, EOY returns).<br><br>
    For actual per-scenario metrics, see: <code>combined_scoreboard.csv</code>
</div>
"""
        _inject_warning_banner(output_file, warning_html)
        
        logging.info(f"[OK] Synthetic combined report: {output_file}")
        
        return synthetic_series
        
    except Exception as e:
        logging.error(f"[ERROR] Failed to generate synthetic combined: {e}")
        return None


def generate_regime_tearsheet(
    regime_results: List[Dict],
    output_dir: str = "Output/quantstats"
) -> None:
    """
    Generate tear sheets for each regime and combined OOS reports.
    
    Parameters:
        regime_results: List of dicts from run_strategy1_regime_tests.
                       Each dict must have:
                       - 'scenario': str (scenario name)
                       - 'returns': pd.Series (log returns)
        output_dir: Directory to save HTML reports
    
    Creates:
        - Output/quantstats/{scenario_name}.html (per scenario)
        - Output/quantstats/combined_oos.html (stitched calendar - with warning)
        - Output/quantstats/combined_oos_synthetic.html (no gaps)
        - Output/quantstats/combined_scoreboard.csv
        - Output/quantstats/combined_scoreboard.md
    """
    if not QUANTSTATS_AVAILABLE:
        raise ImportError("QuantStats not installed. Run: pip install quantstats>=0.0.62")
    
    if not regime_results:
        logging.warning("[SKIP] No regime results provided")
        return
    
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    all_returns = []
    
    # Generate individual scenario tearsheets
    for result in regime_results:
        if result is None:
            continue
        
        scenario_name = result.get('scenario', 'unknown')
        returns = result.get('returns')
        
        if not _validate_returns(returns, scenario_name):
            continue
        
        filename = f"{_scenario_to_filename(scenario_name)}.html"
        output_file = output_path / filename
        
        try:
            generate_tearsheet(
                returns=returns,
                benchmark=None,
                title=f"OOS: {scenario_name}",
                output_path=str(output_file)
            )
            all_returns.append(returns.dropna())
        except Exception as e:
            logging.error(f"[ERROR] Failed to generate tearsheet for {scenario_name}: {e}")
    
    # Generate scoreboard (PREFERRED for combined interpretation)
    generate_scoreboard(regime_results, output_dir)
    
    # Generate synthetic combined (no calendar gaps)
    generate_synthetic_combined(regime_results, output_dir)
    
    # Generate combined OOS report (with calendar gaps - add warning)
    if all_returns:
        try:
            # Concatenate all returns (sorted by date)
            combined = pd.concat(all_returns, axis=0)
            combined = combined.sort_index()
            
            # Remove any duplicate dates (keep first)
            combined = combined[~combined.index.duplicated(keep='first')]
            
            combined_file = output_path / "combined_oos.html"
            generate_tearsheet(
                returns=combined,
                benchmark=None,
                title="Combined OOS (⚠️ Calendar Gaps - Use Scoreboard for Interpretation)",
                output_path=str(combined_file)
            )
            logging.info(f"[OK] Combined OOS report: {combined_file}")
            
        except Exception as e:
            logging.error(f"[ERROR] Failed to generate combined OOS report: {e}")
    
    # Print warning about combined_oos.html
    print(f"\n{'='*70}")
    print(" ⚠️  COMBINED OOS WARNING")
    print(f"{'='*70}")
    print(" combined_oos.html stitches sparse stress windows with calendar gaps.")
    print(" This causes MISLEADING CAGR/DD duration and EOY table gaps.")
    print(" ")
    print(" For proper interpretation, use:")
    print(f"   - {output_dir}/combined_scoreboard.csv (metrics per scenario)")
    print(f"   - {output_dir}/combined_oos_synthetic_VISUAL_ONLY.html")
    print("     (stitched for visualization, synthetic dates)")
    print(f"{'='*70}")
    
    print(f"\nQuantStats reports generated in {output_dir}/")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def quick_stats(returns: pd.Series, title: str = "Quick Stats") -> None:
    """
    Print quick stats to console (no HTML generation).
    
    Useful for quick performance checks without generating full report.
    """
    if not QUANTSTATS_AVAILABLE:
        raise ImportError("QuantStats not installed. Run: pip install quantstats>=0.0.62")
    
    if not _validate_returns(returns, title):
        return
    
    returns_simple = log_returns_to_simple(returns.dropna())
    
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")
    
    # Use QuantStats metrics
    print(f" Total Return: {qs.stats.comp(returns_simple)*100:.2f}%")
    print(f" CAGR: {qs.stats.cagr(returns_simple)*100:.2f}%")
    print(f" Sharpe: {qs.stats.sharpe(returns_simple):.2f}")
    print(f" Sortino: {qs.stats.sortino(returns_simple):.2f}")
    print(f" Max Drawdown: {qs.stats.max_drawdown(returns_simple)*100:.2f}%")
    print(f" Volatility (ann): {qs.stats.volatility(returns_simple)*100:.2f}%")
    print(f" Calmar: {qs.stats.calmar(returns_simple):.2f}")
    print(f"{'='*60}\n")


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    # Quick test with synthetic data
    print("[TEST] QuantStats Reports Module")
    
    if not QUANTSTATS_AVAILABLE:
        print("[FAIL] QuantStats not installed")
        exit(1)
    
    # Generate synthetic log returns
    np.random.seed(42)
    dates = pd.date_range('2022-01-01', periods=252, freq='D')
    log_rets = pd.Series(
        np.random.normal(0.0005, 0.02, len(dates)),  # ~20% vol, small positive drift
        index=dates,
        name='strategy'
    )
    
    print(f"[OK] Generated {len(log_rets)} synthetic daily log returns")
    
    # Test quick stats
    quick_stats(log_rets, "Synthetic Strategy")
    
    # Test HTML generation
    output_file = "Output/quantstats/test_tearsheet.html"
    generate_tearsheet(
        returns=log_rets,
        title="Test Synthetic Strategy",
        output_path=output_file
    )
    
    print(f"[OK] Test complete. Check {output_file}")

