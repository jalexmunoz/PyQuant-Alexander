# regimes.py
# Reglas simples para clasificar regímenes de mercado:
# - Tendencia (uptrend / downtrend / range)
# - Volatilidad (high / low / normal)
# - Momentum (bullish / bearish / neutral)

import pandas as pd


def add_trend_regime(
    df: pd.DataFrame,
    close_col: str = "close",
    sma_short_col: str = "SMA_50",
    sma_long_col: str = "SMA_200",
    slope_window: int = 5,
) -> pd.DataFrame:
    """
    Clasifica el régimen de tendencia usando precio vs SMA200 y SMA50 vs SMA200.

    Reglas (simples, se pueden refinar luego):
    - uptrend:  close > SMA200, SMA50 > SMA200 y SMA50 subiendo.
    - downtrend: close < SMA200, SMA50 < SMA200 y SMA50 bajando.
    - range: todo lo demás.
    """
    df = df.copy()

    sma_short = df[sma_short_col]
    sma_long = df[sma_long_col]

    # "pendiente" simple de la SMA corta
    slope = sma_short.diff(slope_window)

    cond_up = (df[close_col] > sma_long) & (sma_short > sma_long) & (slope > 0)
    cond_down = (df[close_col] < sma_long) & (sma_short < sma_long) & (slope < 0)

    trend_regime = pd.Series("range", index=df.index)
    trend_regime = trend_regime.mask(cond_up, "uptrend")
    trend_regime = trend_regime.mask(cond_down, "downtrend")

    df["trend_regime"] = trend_regime
    df["is_trend_up"] = cond_up
    df["is_trend_down"] = cond_down
    df["is_trend_range"] = ~(cond_up | cond_down)

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
    Clasifica la volatilidad en high / low / normal usando ATR normalizado (ATR/close)
    contra una mediana rodante.

    - high_vol: ATR_norm > mediana * high_mult
    - low_vol: ATR_norm < mediana * low_mult
    - normal: resto
    """
    df = df.copy()

    atr_norm = df[atr_col] / df[close_col]
    med = atr_norm.rolling(window=window, min_periods=20).median()

    high_thr = med * high_mult
    low_thr = med * low_mult

    cond_high = atr_norm > high_thr
    cond_low = atr_norm < low_thr

    vol_regime = pd.Series("normal", index=df.index)
    vol_regime = vol_regime.mask(cond_high, "high_vol")
    vol_regime = vol_regime.mask(cond_low, "low_vol")

    df["atr_norm"] = atr_norm
    df["vol_regime"] = vol_regime
    df["is_vol_high"] = cond_high
    df["is_vol_low"] = cond_low
    df["is_vol_normal"] = ~(cond_high | cond_low)

    return df


def add_momentum_regime(
    df: pd.DataFrame,
    rsi_col: str = "RSI_14",
    bull_thr: float = 60.0,
    bear_thr: float = 40.0,
) -> pd.DataFrame:
    """
    Clasifica el momentum usando RSI:

    - bullish: RSI >= bull_thr
    - bearish: RSI <= bear_thr
    - neutral: entre ambos
    """
    df = df.copy()

    rsi = df[rsi_col]

    cond_bull = rsi >= bull_thr
    cond_bear = rsi <= bear_thr

    mom_regime = pd.Series("neutral", index=df.index)
    mom_regime = mom_regime.mask(cond_bull, "bullish")
    mom_regime = mom_regime.mask(cond_bear, "bearish")

    df["momentum_regime"] = mom_regime
    df["is_mom_bullish"] = cond_bull
    df["is_mom_bearish"] = cond_bear
    df["is_mom_neutral"] = ~(cond_bull | cond_bear)

    return df


def add_basic_regimes(
    df: pd.DataFrame,
    sma_short_col: str = "SMA_50",
    sma_long_col: str = "SMA_200",
) -> pd.DataFrame:
    df = add_trend_regime(
        df,
        sma_short_col=sma_short_col,
        sma_long_col=sma_long_col,
    )

    if "ATR_20" in df.columns:
        df = add_vol_regime(df)

    df = add_momentum_regime(df)
    return df

def add_risk_state(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deriva un estado de riesgo (risk_on / risk_off / neutral) combinando
    tendencia, volatilidad y momentum.

    - risk_on:   uptrend + bullish + vol normal/low
    - risk_off:  bearish + high_vol
    - neutral:   resto
    """
    df = df.copy()

    trend = df.get("trend_regime")
    vol = df.get("vol_regime")
    mom = df.get("momentum_regime")

    cond_on = (trend == "uptrend") & (mom == "bullish") & (vol.isin(["normal", "low_vol"]))
    cond_off = (mom == "bearish") & (vol == "high_vol")

    risk_state = pd.Series("neutral", index=df.index)
    risk_state = risk_state.mask(cond_on, "risk_on")
    risk_state = risk_state.mask(cond_off, "risk_off")

    df["risk_state"] = risk_state
    df["is_risk_on"] = cond_on
    df["is_risk_off"] = cond_off
    df["is_risk_neutral"] = ~(cond_on | cond_off)

    return df
