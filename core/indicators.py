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
import pandas as pd


# ... add_sma y add_rsi ya existen arriba ...


def add_atr(
    df: pd.DataFrame,
    window: int = 20,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    col_name: str | None = None,
) -> pd.DataFrame:
    """
    Añade ATR (Average True Range) al DataFrame usando OHLC.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame con columnas high, low y close.
    window : int, default 20
        Ventana del ATR.
    high_col, low_col, close_col : str
        Nombres de las columnas OHLC.
    col_name : str | None
        Nombre de la columna resultante. Si None, usa "ATR_{window}".

    Returns
    -------
    pd.DataFrame
        DataFrame con una nueva columna de ATR.
    """
    if col_name is None:
        col_name = f"ATR_{window}"

    df = df.copy()

    high = df[high_col]
    low = df[low_col]
    close = df[close_col]

    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=window, min_periods=window).mean()

    df[col_name] = atr
    return df
