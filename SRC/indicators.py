# indicators.py
# Indicadores técnicos base para el framework

import pandas as pd


def add_sma(df: pd.DataFrame, window: int, price_col: str = "close", col_name: str | None = None) -> pd.DataFrame:
    """
    Añade una media móvil simple (SMA) al DataFrame.
    """
    if col_name is None:
        col_name = f"SMA_{window}"

    df = df.copy()
    df[col_name] = df[price_col].rolling(window=window, min_periods=window).mean()
    return df


def add_rsi(
    df: pd.DataFrame,
    window: int = 14,
    price_col: str = "close",
    col_name: str | None = None
) -> pd.DataFrame:
    """
    Añade RSI (Relative Strength Index) al DataFrame, estilo Wilder.
    """
    if col_name is None:
        col_name = f"RSI_{window}"

    df = df.copy()

    delta = df[price_col].diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    avg_gain = gains.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1/window, min_periods=window, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    df[col_name] = rsi

    return df
