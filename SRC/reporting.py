# reporting.py
# Funciones de salida / resumen de regímenes

import pandas as pd


def print_regime_summary(df: pd.DataFrame):
    """
    Imprime un resumen de conteos por tipo de régimen.
    """
    print("\n=== Trend regime counts ===")
    print(df["trend_regime"].value_counts(dropna=False))

    if "vol_regime" in df.columns:
        print("\n=== Vol regime counts ===")
        print(df["vol_regime"].value_counts(dropna=False))

    print("\n=== Momentum regime counts ===")
    print(df["momentum_regime"].value_counts(dropna=False))


def print_current_snapshot(df: pd.DataFrame, label: str = "BTC-USD"):
    """
    Imprime el último punto de datos (estado actual del mercado).
    """
    last = df.iloc[-1]
    date = last.name

    close = last["close"]
    sma50 = last.get("SMA_50", float("nan"))
    sma200 = last.get("SMA_200", float("nan"))
    rsi = last.get("RSI_14", float("nan"))
    atr = last.get("ATR_20", float("nan"))

    trend = last.get("trend_regime", "n/a")
    vol = last.get("vol_regime", "n/a")
    mom = last.get("momentum_regime", "n/a")

    print("\n" + "=" * 60)
    print(f" Current snapshot for {label}  |  Date: {date.date()}")
    print("=" * 60)
    print(f" Close:   {close:10.2f}")
    print(f" SMA 50:  {sma50:10.2f}")
    print(f" SMA 200: {sma200:10.2f}")
    print(f" RSI 14:  {rsi:10.2f}")
    print(f" ATR 20:  {atr:10.2f}")
    print("-" * 60)
    print(f" Trend regime:    {trend}")
    print(f" Vol regime:      {vol}")
    print(f" Momentum regime: {mom}")
    print("=" * 60 + "\n")
