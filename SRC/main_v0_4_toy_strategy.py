# main_v0_4_toy_strategy.py
# v0.4 - Toy strategy basada en risk_state (BTC)

import matplotlib.pyplot as plt
import pandas as pd

from pipeline import build_asset_regime_dataset
from signal_generator import add_risk_onoff_signal
from backtest import simple_long_only_backtest

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)
plt.style.use("ggplot")


def main():
    print("Construyendo dataset BTC con indicadores + regímenes...")
    df = build_asset_regime_dataset(coin_id="bitcoin", days=365, vs_currency="usd")

    # Generar señal y posición
    df = add_risk_onoff_signal(df)

    # Backtest
    df_bt, metrics = simple_long_only_backtest(df)

    print("\n=== Métricas estrategia Risk ON/OFF (toy) ===")
    for k, v in metrics.items():
        print(f"{k:25s}: {v: .4f}")

    # Mostrar algunas filas finales
    print("\nÚltimas filas (precio, regímenes, posición):")
    cols_show = [
        "close", "SMA_20", "SMA_50",
        "trend_regime", "vol_regime", "momentum_regime", "risk_state",
        "position", "strategy_ret", "equity_curve",
    ]
    cols_show = [c for c in cols_show if c in df_bt.columns]
    print(df_bt[cols_show].tail(15))

    # Plot precio + curva de capital
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # Precio + puntos donde cambia la posición
    axes[0].plot(df_bt.index, df_bt["close"], label="BTC Close", linewidth=1.2)
    # Marcar días donde hay cambio de signal_raw
    if "signal_raw" in df_bt.columns:
        buy_days = df_bt["signal_raw"] == 1
        flat_days = df_bt["signal_raw"] == 0
        axes[0].scatter(df_bt.index[buy_days], df_bt["close"][buy_days], marker="^", s=40, label="Signal: LONG")
        axes[0].scatter(df_bt.index[flat_days], df_bt["close"][flat_days], marker="v", s=40, label="Signal: FLAT")

    axes[0].set_title("BTCUSD + señales Risk ON/OFF (toy v0.4)")
    axes[0].set_ylabel("Precio (USD)")
    axes[0].legend(loc="upper left")
    axes[0].grid(True)

    # Equity curve vs buy&hold
    axes[1].plot(df_bt.index, df_bt["equity_curve"], label="Strategy equity", linewidth=1.5)
    axes[1].plot(df_bt.index, df_bt["buy_hold_curve"], label="Buy & Hold BTC", linewidth=1.0)
    axes[1].set_ylabel("Crecimiento (x)")
    axes[1].set_xlabel("Fecha")
    axes[1].legend(loc="upper left")
    axes[1].grid(True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
