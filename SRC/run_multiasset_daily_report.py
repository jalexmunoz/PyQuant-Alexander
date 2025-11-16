# run_multiasset_daily_report.py
# v0.5 - Daily regime report para múltiples criptoactivos (BTC, ETH, SOL)

import pandas as pd

from pipeline import build_asset_regime_dataset
from reporting import print_regime_summary, print_current_snapshot

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 25)


def main():
    assets = [
        {"coin_id": "bitcoin",  "label": "BTC-USD"},
        {"coin_id": "ethereum", "label": "ETH-USD"},
        {"coin_id": "solana",   "label": "SOL-USD"},
    ]

    days = 365
    vs_currency = "usd"

    for a in assets:
        coin_id = a["coin_id"]
        label = a["label"]

        print("\n" + "#" * 80)
        print(f"# {label}  ({coin_id}) - Regimes & Risk report ({days} days)")
        print("#" * 80)

        df = build_asset_regime_dataset(coin_id=coin_id, days=days, vs_currency=vs_currency)

        # Resumen histórico de regímenes
        print_regime_summary(df)

        # Snapshot actual
        print_current_snapshot(df, label=label)


if __name__ == "__main__":
    main()
