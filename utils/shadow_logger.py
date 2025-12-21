# utils/shadow_logger.py
# v1.0.0 - Shadow Mode Daily Logging
#
# Purpose: Log daily strategy signals for shadow mode validation.
# NO actual trading - observation only.
#
# Schema version: 1.0 (do not change without versioning)

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

import pandas as pd

# =============================================================================
# CONFIGURATION
# =============================================================================

SHADOW_LOG_DIR = Path("Output/shadow")
STRATEGY_VERSION = "v0.1-shadow-beta"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SuggestedTrade:
    """A suggested trade action (observation only - not executed)."""
    asset: str
    action: str  # "BUY" or "SELL"
    amount: float  # Weight change (e.g., 0.15 = 15% of portfolio)
    reason: str = ""


@dataclass
class ShadowLogEntry:
    """
    Schema for daily shadow mode log entry.
    
    Schema version: 1.0
    Do NOT change field names/order without version bump.
    """
    # Identifiers
    date: str  # YYYY-MM-DD
    timestamp: str  # ISO 8601 with timezone
    
    # Prices
    btc_close: float
    eth_close: float
    sol_close: float
    link_close: float
    
    # Signals (1=ON, 0=OFF)
    btc_signal: int
    eth_signal: int
    sol_signal: int
    link_signal: int
    
    # Target weights (based on signal * base_weight)
    btc_target: float
    eth_target: float
    sol_target: float
    link_target: float
    
    # SMA values for transparency
    btc_sma50: float
    btc_sma200: float
    eth_sma50: float
    eth_sma200: float
    sol_sma50: float
    sol_sma200: float
    link_sma50: float
    link_sma200: float
    
    # Portfolio state
    total_exposure: float  # Sum of target weights where signal=ON
    cash_weight: float  # 1 - total_exposure
    
    # Reasons for each signal
    btc_reason: str
    eth_reason: str
    sol_reason: str
    link_reason: str
    
    # Suggested trades (JSON string for complex data)
    suggested_trades_json: str
    
    # Metadata
    strategy_version: str
    data_source: str


# =============================================================================
# SHADOW LOGGER CLASS
# =============================================================================

class ShadowLogger:
    """
    Logger for shadow mode daily observations.
    
    Saves daily CSV logs to Output/shadow/daily_log_YYYY-MM-DD.csv
    
    Usage:
        logger = ShadowLogger()
        entry = logger.create_entry(
            prices={'BTCUSDT': 98500, ...},
            signals={'BTCUSDT': 1, ...},
            sma_values={'BTCUSDT': {'sma50': 96000, 'sma200': 88000}, ...},
            base_weights={'BTCUSDT': 0.40, ...}
        )
        logger.log(entry)
    """
    
    def __init__(
        self,
        log_dir: Path = SHADOW_LOG_DIR,
        strategy_version: str = STRATEGY_VERSION,
        data_source: str = "TradingView"
    ):
        self.log_dir = Path(log_dir)
        self.strategy_version = strategy_version
        self.data_source = data_source
        
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_log_path(self, date: str) -> Path:
        """Get path for daily log file."""
        return self.log_dir / f"daily_log_{date}.csv"
    
    def _signal_to_reason(self, signal: int, sma50: float, sma200: float) -> str:
        """Generate reason string for signal."""
        if signal == 1:
            return f"SMA50({sma50:.0f})>SMA200({sma200:.0f})"
        else:
            return f"SMA50({sma50:.0f})<SMA200({sma200:.0f})"
    
    def create_entry(
        self,
        prices: Dict[str, float],
        signals: Dict[str, int],
        sma_values: Dict[str, Dict[str, float]],
        base_weights: Dict[str, float],
        suggested_trades: Optional[List[SuggestedTrade]] = None,
        date: Optional[str] = None,
        timestamp: Optional[str] = None
    ) -> ShadowLogEntry:
        """
        Create a ShadowLogEntry from current market state.
        
        Parameters:
            prices: Dict of {symbol: close_price}
            signals: Dict of {symbol: signal} where signal is 1 (ON) or 0 (OFF)
            sma_values: Dict of {symbol: {'sma50': value, 'sma200': value}}
            base_weights: Dict of {symbol: base_weight}
            suggested_trades: List of SuggestedTrade objects
            date: Override date (default: today)
            timestamp: Override timestamp (default: now)
        
        Returns:
            ShadowLogEntry ready for logging
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        if timestamp is None:
            timestamp = datetime.now().isoformat() + 'Z'
        
        # Helper to safely get values
        def get_price(symbol: str) -> float:
            return prices.get(symbol, 0.0)
        
        def get_signal(symbol: str) -> int:
            return signals.get(symbol, 0)
        
        def get_sma(symbol: str, key: str) -> float:
            return sma_values.get(symbol, {}).get(key, 0.0)
        
        def get_weight(symbol: str) -> float:
            return base_weights.get(symbol, 0.0)
        
        # Calculate targets (base_weight if signal ON, 0 if OFF)
        def calc_target(symbol: str) -> float:
            return get_weight(symbol) if get_signal(symbol) == 1 else 0.0
        
        # Calculate total exposure
        total_exposure = sum(
            calc_target(s) for s in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'LINKUSDT']
        )
        
        # Generate reasons
        def gen_reason(symbol: str) -> str:
            return self._signal_to_reason(
                get_signal(symbol),
                get_sma(symbol, 'sma50'),
                get_sma(symbol, 'sma200')
            )
        
        # Serialize suggested trades to JSON
        trades_json = "[]"
        if suggested_trades:
            trades_list = [asdict(t) for t in suggested_trades]
            trades_json = json.dumps(trades_list)
        
        return ShadowLogEntry(
            date=date,
            timestamp=timestamp,
            btc_close=get_price('BTCUSDT'),
            eth_close=get_price('ETHUSDT'),
            sol_close=get_price('SOLUSDT'),
            link_close=get_price('LINKUSDT'),
            btc_signal=get_signal('BTCUSDT'),
            eth_signal=get_signal('ETHUSDT'),
            sol_signal=get_signal('SOLUSDT'),
            link_signal=get_signal('LINKUSDT'),
            btc_target=calc_target('BTCUSDT'),
            eth_target=calc_target('ETHUSDT'),
            sol_target=calc_target('SOLUSDT'),
            link_target=calc_target('LINKUSDT'),
            btc_sma50=get_sma('BTCUSDT', 'sma50'),
            btc_sma200=get_sma('BTCUSDT', 'sma200'),
            eth_sma50=get_sma('ETHUSDT', 'sma50'),
            eth_sma200=get_sma('ETHUSDT', 'sma200'),
            sol_sma50=get_sma('SOLUSDT', 'sma50'),
            sol_sma200=get_sma('SOLUSDT', 'sma200'),
            link_sma50=get_sma('LINKUSDT', 'sma50'),
            link_sma200=get_sma('LINKUSDT', 'sma200'),
            total_exposure=total_exposure,
            cash_weight=1.0 - total_exposure,
            btc_reason=gen_reason('BTCUSDT'),
            eth_reason=gen_reason('ETHUSDT'),
            sol_reason=gen_reason('SOLUSDT'),
            link_reason=gen_reason('LINKUSDT'),
            suggested_trades_json=trades_json,
            strategy_version=self.strategy_version,
            data_source=self.data_source
        )
    
    def log(self, entry: ShadowLogEntry) -> Path:
        """
        Append entry to daily log CSV.
        
        Parameters:
            entry: ShadowLogEntry to log
            
        Returns:
            Path to log file
        """
        log_path = self._get_log_path(entry.date)
        
        # Convert to DataFrame row
        entry_dict = asdict(entry)
        df_row = pd.DataFrame([entry_dict])
        
        # Check if file exists (for header)
        file_exists = log_path.exists()
        
        # Append to CSV
        df_row.to_csv(
            log_path,
            mode='a',
            header=not file_exists,
            index=False
        )
        
        logging.info(f"[SHADOW] Logged entry for {entry.date} to {log_path}")
        return log_path
    
    def log_from_data(
        self,
        prices: Dict[str, float],
        signals: Dict[str, int],
        sma_values: Dict[str, Dict[str, float]],
        base_weights: Dict[str, float],
        suggested_trades: Optional[List[SuggestedTrade]] = None
    ) -> Path:
        """
        Convenience method: create entry and log in one call.
        
        Returns:
            Path to log file
        """
        entry = self.create_entry(
            prices=prices,
            signals=signals,
            sma_values=sma_values,
            base_weights=base_weights,
            suggested_trades=suggested_trades
        )
        return self.log(entry)
    
    def read_log(self, date: str) -> Optional[pd.DataFrame]:
        """
        Read log file for a specific date.
        
        Parameters:
            date: Date in YYYY-MM-DD format
            
        Returns:
            DataFrame with log entries, or None if not found
        """
        log_path = self._get_log_path(date)
        
        if not log_path.exists():
            logging.warning(f"[SHADOW] No log found for {date}")
            return None
        
        return pd.read_csv(log_path)
    
    def read_all_logs(self) -> pd.DataFrame:
        """
        Read and concatenate all log files.
        
        Returns:
            DataFrame with all log entries
        """
        all_logs = []
        
        for log_file in sorted(self.log_dir.glob("daily_log_*.csv")):
            try:
                df = pd.read_csv(log_file)
                all_logs.append(df)
            except Exception as e:
                logging.warning(f"[SHADOW] Failed to read {log_file}: {e}")
        
        if not all_logs:
            return pd.DataFrame()
        
        return pd.concat(all_logs, ignore_index=True)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_csv_header() -> str:
    """
    Get CSV header string for shadow log schema.
    
    Useful for documentation or manual file creation.
    """
    fields = [
        'date', 'timestamp',
        'btc_close', 'eth_close', 'sol_close', 'link_close',
        'btc_signal', 'eth_signal', 'sol_signal', 'link_signal',
        'btc_target', 'eth_target', 'sol_target', 'link_target',
        'btc_sma50', 'btc_sma200', 'eth_sma50', 'eth_sma200',
        'sol_sma50', 'sol_sma200', 'link_sma50', 'link_sma200',
        'total_exposure', 'cash_weight',
        'btc_reason', 'eth_reason', 'sol_reason', 'link_reason',
        'suggested_trades_json', 'strategy_version', 'data_source'
    ]
    return ','.join(fields)


# =============================================================================
# TEST / EXAMPLE
# =============================================================================

if __name__ == "__main__":
    print("[TEST] Shadow Logger")
    
    # Create logger
    logger = ShadowLogger()
    
    # Example data (as specified in requirements)
    prices = {
        'BTCUSDT': 98500.0,
        'ETHUSDT': 3850.0,
        'SOLUSDT': 195.0,
        'LINKUSDT': 24.5
    }
    
    signals = {
        'BTCUSDT': 1,
        'ETHUSDT': 1,
        'SOLUSDT': 0,
        'LINKUSDT': 1
    }
    
    sma_values = {
        'BTCUSDT': {'sma50': 96000, 'sma200': 88000},
        'ETHUSDT': {'sma50': 3800, 'sma200': 3400},
        'SOLUSDT': {'sma50': 180, 'sma200': 210},
        'LINKUSDT': {'sma50': 22, 'sma200': 25}
    }
    
    base_weights = {
        'BTCUSDT': 0.40,
        'ETHUSDT': 0.40,
        'SOLUSDT': 0.15,
        'LINKUSDT': 0.05
    }
    
    # Example suggested trade
    suggested_trades = [
        SuggestedTrade(
            asset='SOL',
            action='SELL',
            amount=0.15,
            reason='SMA50 crossed below SMA200'
        )
    ]
    
    # Create entry
    entry = logger.create_entry(
        prices=prices,
        signals=signals,
        sma_values=sma_values,
        base_weights=base_weights,
        suggested_trades=suggested_trades
    )
    
    print(f"\nEntry created:")
    print(f"  Date: {entry.date}")
    print(f"  Total Exposure: {entry.total_exposure*100:.0f}%")
    print(f"  Cash Weight: {entry.cash_weight*100:.0f}%")
    print(f"  BTC Signal: {entry.btc_signal} ({entry.btc_reason})")
    print(f"  SOL Signal: {entry.sol_signal} ({entry.sol_reason})")
    print(f"  Suggested Trades: {entry.suggested_trades_json}")
    
    # Log entry
    log_path = logger.log(entry)
    print(f"\n[OK] Logged to: {log_path}")
    
    # Read back
    df = logger.read_log(entry.date)
    if df is not None:
        print(f"[OK] Read back {len(df)} entries")
    
    print("\n[DONE] Shadow logger test complete")


