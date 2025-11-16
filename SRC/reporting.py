# reporting.py
# Funciones de salida / resumen de regímenes

import pandas as pd

def print_current_snapshot(df: pd.DataFrame, label: str = "BTC-USD"):
    """
    Imprime el último punto de datos (estado actual del mercado).
    Soporta tanto SMA_20/50 como SMA_50/200.
    """
    last = df.iloc[-1]
    date = last.name

    close = last["close"]

    # Detectar automáticamente qué SMAs hay
    sma_short = last.get("SMA_20", last.get("SMA_50", float("nan")))
    # "larga": si hay SMA_50 y SMA_20, larga es 50; si no, intenta 200
    if "SMA_20" in df.columns and "SMA_50" in df.columns:
        sma_long = last.get("SMA_50", float("nan"))
    else:
        sma_long = last.get("SMA_200", float("nan"))

    rsi = last.get("RSI_14", float("nan"))
    atr = last.get("ATR_20", float("nan"))

    trend = last.get("trend_regime", "n/a")
    vol = last.get("vol_regime", "n/a")
    mom = last.get("momentum_regime", "n/a")
    risk = last.get("risk_state", "n/a")  # lo rellenamos en el siguiente paso

    print("\n" + "=" * 60)
    print(f" Current snapshot for {label}  |  Date: {date.date()}")
    print("=" * 60)
    print(f" Close:       {close:10.2f}")
    print(f" SMA short:   {sma_short:10.2f}")
    print(f" SMA long:    {sma_long:10.2f}")
    print(f" RSI 14:      {rsi:10.2f}")
    print(f" ATR 20:      {atr:10.2f}")
    print("-" * 60)
    print(f" Trend regime:    {trend}")
    print(f" Vol regime:      {vol}")
    print(f" Momentum regime: {mom}")
    print(f" Risk state:      {risk}")
    print("=" * 60 + "\n")

def print_regime_summary(df: pd.DataFrame):
    print("\n=== Trend regime counts ===")
    print(df["trend_regime"].value_counts(dropna=False))

    if "vol_regime" in df.columns:
        print("\n=== Vol regime counts ===")
        print(df["vol_regime"].value_counts(dropna=False))

    print("\n=== Momentum regime counts ===")
    print(df["momentum_regime"].value_counts(dropna=False))

    if "risk_state" in df.columns:
        print("\n=== Risk state counts ===")
        print(df["risk_state"].value_counts(dropna=False))

