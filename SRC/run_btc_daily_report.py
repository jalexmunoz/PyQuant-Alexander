# run_btc_daily_report.py
# v0.3.1 - Daily regime report para BTC

import pandas as pd

from pipeline import build_asset_regime_dataset
from reporting import print_regime_summary, print_current_snapshot

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)


def main():
    print("Construyendo dataset BTC con indicadores + regímenes (v0.3.1)...")
    df = build_asset_regime_dataset(coin_id="bitcoin", days=365, vs_currency="usd")

    # Resumen histórico simple
    print_regime_summary(df)

    # Estado actual
    print_current_snapshot(df, label="BTC-USD")


if __name__ == "__main__":
    main()
