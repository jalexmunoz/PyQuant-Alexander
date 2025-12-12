# conditions.py
# v0.7 - Flags de "condiciones especiales" de mercado
#
# Se apoya en el dataset que devuelve pipeline.build_asset_regime_dataset:
# columnas esperadas: close, SMA_20, SMA_50, ATR_20, RSI_14, trend_regime, vol_regime, momentum_regime, risk_state

import pandas as pd


def add_condition_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Añade columnas booleanas que marcan condiciones especiales de mercado.

    Flags incluidos (por ahora):
    - cond_rsi_overbought: RSI >= 70
    - cond_rsi_oversold:   RSI <= 30
    - cond_break_above_sma50: cierre cruza al alza la SMA_50
    - cond_break_below_sma50: cierre cruza a la baja la SMA_50
    - atr_norm: ATR_20 / mediana móvil (ventana 100, min 20)
    - cond_vol_spike: atr_norm >= 1.5
    - cond_vol_crush: atr_norm <= 0.7
    """
    df = df.copy()

    # RSI flags
    if "RSI_14" in df.columns:
        df["cond_rsi_overbought"] = df["RSI_14"] >= 70
        df["cond_rsi_oversold"] = df["RSI_14"] <= 30
    else:
        df["cond_rsi_overbought"] = False
        df["cond_rsi_oversold"] = False

    # Cruces de SMA_50
    if "close" in df.columns and "SMA_50" in df.columns:
        close = df["close"]
        sma50 = df["SMA_50"]

        prev_close = close.shift(1)
        prev_sma50 = sma50.shift(1)

        df["cond_break_above_sma50"] = (close > sma50) & (prev_close <= prev_sma50)
        df["cond_break_below_sma50"] = (close < sma50) & (prev_close >= prev_sma50)
    else:
        df["cond_break_above_sma50"] = False
        df["cond_break_below_sma50"] = False

    # Volatilidad normalizada a partir de ATR_20
    if "ATR_20" in df.columns:
        atr = df["ATR_20"]
        atr_med = atr.rolling(window=100, min_periods=20).median()
        df["atr_norm"] = atr / atr_med
        df["cond_vol_spike"] = df["atr_norm"] >= 1.5
        df["cond_vol_crush"] = df["atr_norm"] <= 0.7
    else:
        df["atr_norm"] = float("nan")
        df["cond_vol_spike"] = False
        df["cond_vol_crush"] = False

    return df
