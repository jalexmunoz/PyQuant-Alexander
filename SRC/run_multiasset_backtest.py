# run_multiasset_backtest.py
# v0.6.0 - Backtest multi-activo (refactorizado)
#
# Historial:
# v0.6.0 - Refactor para usar print_backtest_metrics()
# v0.5.1 - (Versión inicial)

import pandas as pd

from pipeline import build_asset_regime_dataset
from signal_generator import add_risk_onoff_signal
from backtest import simple_long_only_backtest
from reporting import print_backtest_metrics  # <<< AÑADE ESTA LÍNEA

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 25)

def run_backtest_for_asset(coin_id: str, label: str, days: int = 365, vs_currency: str = "usd"):
    print("\n" + "#" * 80)
    print(f"# {label}  ({coin_id}) - Risk ON/OFF backtest ({days} days)")
    print("#" * 80)

    # 1. Dataset con indicadores + regímenes + risk_state
    df = build_asset_regime_dataset(coin_id=coin_id, days=days, vs_currency=vs_currency)

    # 2. Señal Risk ON/OFF
    df = add_risk_onoff_signal(df)

    # 3. Backtest long-only simple
    df_bt, metrics = simple_long_only_backtest(df)

    # 4. Imprimir métricas
    # <<< REEMPLAZA ESTAS 3 LÍNEAS >>>
    # print("\n=== Métricas estrategia Risk ON/OFF (toy) ===")
    # for k, v in metrics.items():
    #     print(f"{k:25s}: {v: .4f}")
    
    # <<< CON ESTA ÚNICA LÍNEA >>>
    print_backtest_metrics(metrics)

    # 5. Mostrar algunas filas finales (debug / sanity check)
    cols_show = [
        "close",
        "SMA_20",
        "SMA_50",
        "trend_regime",
        "vol_regime",
        "momentum_regime",
        "risk_state",
        "position",
        # "strategy_ret", # Esta columna no existe, se llama 'strategy_log_ret'
        "strategy_log_ret", # <-- Corregí esto
        "equity_curve",
    ]
    cols_show = [c for c in cols_show if c in df_bt.columns]

    print("\nÚltimas filas (precio, regímenes, posición):")
    print(df_bt[cols_show].tail(10))


def main():
    # ... (el resto del archivo no cambia) ...
    assets = [
        {"coin_id": "bitcoin",  "label": "BTC-USD"},
        {"coin_id": "ethereum", "label": "ETH-USD"},
        {"coin_id": "solana",   "label": "SOL-USD"},
    ]
    days = 365
    vs_currency = "usd"

    for a in assets:
        run_backtest_for_asset(
            coin_id=a["coin_id"],
            label=a["label"],
            days=days,
            vs_currency=vs_currency,
        )


if __name__ == "__main__":
    main()
