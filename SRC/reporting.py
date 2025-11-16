# reporting.py
# v0.1.0 - Funciones de salida / resumen
#
# Historial:
# v0.1.0 - Añadida print_backtest_metrics()
# v0.0.x - (Versión inicial)

import pandas as pd
import numpy as np

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

def print_backtest_metrics(metrics: dict):
    """
    Imprime un resumen formateado del diccionario de métricas del backtest.
    """
    
    # --- Sección 1: Métricas de Rendimiento (Full Sample) ---
    print("\n=== Métricas de Rendimiento (Full Sample) ===")
    
    # Definir las métricas clave y su formato
    perf_keys = [
        ("total_return_strategy", "{: .2%}"),
        ("total_return_buy_hold", "{: .2%}"),
        ("cagr_strategy", "{: .2%}"),
        ("cagr_buy_hold", "{: .2%}"),
        ("max_drawdown_strategy", "{: .2%}"),
        ("max_drawdown_buy_hold", "{: .2%}"),
        ("annual_volatility_strategy", "{: .2%}"),
        ("sharpe_ratio", "{: .3f}"),
        ("sortino_ratio", "{: .3f}"),
        ("calmar_ratio", "{: .3f}"),
    ]

    for key, fmt in perf_keys:
        if key in metrics:
            print(f"{key:28s}: {fmt.format(metrics[key])}")

    # --- Sección 2: Análisis de Trades (Full Sample) ---
    print("\n=== Análisis de Trades (Full Sample) ===")
    trade_keys = [
        ("trades_total_num", "{: .0f}"),
        ("trades_pct_profitable", "{: .2%}"),
        ("trades_avg_return", "{: .2%}"),
        ("trades_avg_win", "{: .2%}"),
        ("trades_avg_loss", "{: .2%}"),
        ("trades_profit_factor", "{: .2f}"),
        ("trades_max_win", "{: .2%}"),
        ("trades_max_loss", "{: .2%}"),
    ]

    for key, fmt in trade_keys:
        if key in metrics:
            val = metrics[key]
            # Manejar 'nan' e 'inf' que no se formatean bien como .2%
            if pd.isna(val) or (isinstance(val, float) and np.isinf(val)):
                print(f"{key:28s}: {val}")
            else:
                print(f"{key:28s}: {fmt.format(val)}")

    # --- Sección 3: Métricas Train/Test ---
    # Filtra todas las métricas que comienzan con "train_" o "test_"
    train_metrics = {k: v for k, v in metrics.items() if k.startswith("train_")}
    test_metrics = {k: v for k, v in metrics.items() if k.startswith("test_")}

    if train_metrics:
        print("\n=== Métricas (Train) ===")
        for k, v in train_metrics.items():
            # Mantenemos el formato simple aquí, ya que hay muchas
            print(f"{k:28s}: {v: .4f}")
    
    if test_metrics:
        print("\n=== Métricas (Test) ===")
        for k, v in test_metrics.items():
            print(f"{k:28s}: {v: .4f}")
