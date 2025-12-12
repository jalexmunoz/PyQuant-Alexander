# regimes.py
# v0.2.0 - Reglas parametrizadas para regímenes de mercado
#
# Historial:
# v0.2.0 - Promovidos todos los umbrales/parámetros fijos a argumentos.
# v0.1.0 - (Versión inicial)

import pandas as pd


def add_trend_regime(
    df: pd.DataFrame,
    close_col: str = "close",
    sma_short_col: str = "SMA_50",
    sma_long_col: str = "SMA_200",
    slope_window: int = 5,
) -> pd.DataFrame:
    """
    Clasifica el régimen de tendencia.
    (La lógica interna no cambia)
    """
    df = df.copy()

    sma_short = df[sma_short_col]
    sma_long = df[sma_long_col]

    # "pendiente" simple de la SMA corta
    slope = sma_short.diff(slope_window) # <-- Usa el parámetro

    cond_up = (df[close_col] > sma_long) & (sma_short > sma_long) & (slope > 0)
    cond_down = (df[close_col] < sma_long) & (sma_short < sma_long) & (slope < 0)

    trend_regime = pd.Series("range", index=df.index)
    trend_regime = trend_regime.mask(cond_up, "uptrend")
    trend_regime = trend_regime.mask(cond_down, "downtrend")

    df["trend_regime"] = trend_regime
    return df


def add_vol_regime(
    df: pd.DataFrame,
    atr_col: str = "ATR_20",
    close_col: str = "close",
    window: int = 100,
    high_mult: float = 1.3,
    low_mult: float = 0.7,
) -> pd.DataFrame:
    """
    Clasifica la volatilidad usando ATR normalizado.
    (Ahora parametrizado)
    """
    df = df.copy()

    atr_norm = df[atr_col] / df[close_col]
    med = atr_norm.rolling(window=window, min_periods=20).median()

    high_thr = med * high_mult # <-- Usa el parámetro
    low_thr = med * low_mult # <-- Usa el parámetro

    cond_high = atr_norm > high_thr
    cond_low = atr_norm < low_thr

    vol_regime = pd.Series("normal", index=df.index)
    vol_regime = vol_regime.mask(cond_high, "high_vol")
    vol_regime = vol_regime.mask(cond_low, "low_vol")

    df["atr_norm"] = atr_norm
    df["vol_regime"] = vol_regime
    return df


def add_momentum_regime(
    df: pd.DataFrame,
    rsi_col: str = "RSI_14",
    bull_thr: float = 55.0,
    bear_thr: float = 45.0,
) -> pd.DataFrame:
    """
    Clasifica el momentum usando RSI.
    (Ahora parametrizado)
    """
    df = df.copy()

    rsi = df[rsi_col]

    cond_bull = rsi >= bull_thr # <-- Usa el parámetro
    cond_bear = rsi <= bear_thr # <-- Usa el parámetro

    mom_regime = pd.Series("neutral", index=df.index)
    mom_regime = mom_regime.mask(cond_bull, "bullish")
    mom_regime = mom_regime.mask(cond_bear, "bearish")

    df["momentum_regime"] = mom_regime
    return df


def add_basic_regimes(
    df: pd.DataFrame,
    # Nombres de columnas de indicadores
    sma_short_col: str,
    sma_long_col: str,
    atr_col: str,
    rsi_col: str,
    # Parámetros de lógica de régimen
    trend_slope_window: int = 5,
    vol_window: int = 100,
    vol_high_mult: float = 1.3,
    vol_low_mult: float = 0.7,
    mom_bull_thr: float = 55.0,
    mom_bear_thr: float = 45.0,
) -> pd.DataFrame:
    """
    Orquestador principal que llama a las sub-funciones de régimen
    con todos los parámetros dinámicos.
    """
    
    # Asegurarse de que las columnas de entrada existan antes de usarlas
    if sma_short_col in df.columns and sma_long_col in df.columns:
        df = add_trend_regime(
            df,
            sma_short_col=sma_short_col,
            sma_long_col=sma_long_col,
            slope_window=trend_slope_window,
        )
    else:
        df["trend_regime"] = "n/a"

    if atr_col in df.columns:
        df = add_vol_regime(
            df,
            atr_col=atr_col,
            window=vol_window,
            high_mult=vol_high_mult,
            low_mult=vol_low_mult,
        )
    else:
        df["vol_regime"] = "n/a"

    if rsi_col in df.columns:
        df = add_momentum_regime(
            df,
            rsi_col=rsi_col,
            bull_thr=mom_bull_thr,
            bear_thr=mom_bear_thr,
        )
    else:
        df["momentum_regime"] = "n/a"
        
    return df


def add_risk_state(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deriva un estado de riesgo (risk_on / risk_off / neutral) combinando
    tendencia, volatilidad y momentum.
    
    (La lógica interna no cambia, se basa en la *salida* de las otras funciones)
    """
    df = df.copy()

    trend = df.get("trend_regime")
    vol = df.get("vol_regime")
    mom = df.get("momentum_regime")

    # 1) risk_off primero
    cond_off_highvol = (vol == "high_vol") & (mom != "bullish")
    cond_off_bear_trend = (trend != "uptrend") & (mom == "bearish")
    cond_off = cond_off_highvol | cond_off_bear_trend

    # 2) risk_on
    cond_on = (trend == "uptrend") & (mom == "bullish") & (vol.isin(["normal", "low_vol"]))

    risk_state = pd.Series("neutral", index=df.index)
    risk_state = risk_state.mask(cond_on, "risk_on")
    risk_state = risk_state.mask(cond_off, "risk_off")

    df["risk_state"] = risk_state
    return df