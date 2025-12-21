# utils/validate_tv_data.py

import pandas as pd
import os
from pathlib import Path

def validate_export():
    """Validate TV exported data"""
    
    export_dir = Path("Data/tv_export")
    
    expected_files = {
    "BTCUSDT_1D.csv": {"min_year": 2017},
    "ETHUSDT_1D.csv": {"min_year": 2017},
    "SOLUSDT_1D.csv": {"min_year": 2020},
    "LINKUSDT_1D.csv": {"min_year": 2019},
}
    
    for filename, constraints in expected_files.items():
        filepath = export_dir / filename
        
        if not filepath.exists():
            print(f"❌ Missing: {filename}")
            continue
        
        df = pd.read_csv(filepath)
        
        # Check if 'datetime' column exists (TradingView export format)
        if 'datetime' in df.columns:
            time_col = 'datetime'
        elif 'time' in df.columns:
            time_col = 'time'
        else:
            print(f"❌ {filename}: No 'datetime' or 'time' column found. Columns: {df.columns.tolist()}")
            continue
        
        df[time_col] = pd.to_datetime(df[time_col])
        
        # Checks
        min_date = df[time_col].min()
        max_date = df[time_col].max()
        num_rows = len(df)
        duplicates = df.duplicated(subset=[time_col]).sum()
        gaps = (df[time_col].diff() > pd.Timedelta(days=2)).sum()
        
        print(f"\n✅ {filename}")
        print(f"  Range: {min_date.date()} to {max_date.date()}")
        print(f"  Rows: {num_rows}")
        print(f"  Duplicates: {duplicates}")
        print(f"  Gaps (>2d): {gaps}")
        
        if min_date.year > constraints['min_year']:
            print(f"  ⚠️  Expected data from {constraints['min_year']}, got {min_date.year}")

if __name__ == '__main__':
    validate_export()