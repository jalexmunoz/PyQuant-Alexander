from data_fetcher import get_coingecko_ohlc
from indicators import add_sma, add_rsi, add_atr
from regimes import add_basic_regimes, add_risk_state

def build_asset_regime_dataset(
    coin_id: str = "bitcoin",
    days: int = 365,
    vs_currency: str = "usd",
):
    """
    Construye un DataFrame con:
    - OHLC desde CoinGecko
    - SMA_50, SMA_200
    - RSI_14
    - ATR_20
    - Regímenes de tendencia, volatilidad y momentum

    Parameters
    ----------
    coin_id : str
        Id de CoinGecko (ej: 'bitcoin', 'ethereum').
    days : int
        Días hacia atrás desde hoy.
    vs_currency : str
        Moneda de cotización, por defecto 'usd'.

    Returns
    -------
    df : pd.DataFrame
        DataFrame indexado por fecha con columnas OHLC, indicadores y regímenes.
    """
    df = get_coingecko_ohlc(coin_id=coin_id, days=days, vs_currency=vs_currency)

       # Indicadores (OHLC)
    df = add_sma(df, window=20, price_col="close")     # SMA_20
    df = add_sma(df, window=50, price_col="close")     # SMA_50
    df = add_rsi(df, window=14, price_col="close")     # RSI_14
    df = add_atr(df, window=20)                        # ATR_20

    # Regímenes + estado de riesgo
    df = add_basic_regimes(df, sma_short_col="SMA_20", sma_long_col="SMA_50")
    df = add_risk_state(df)

    return df
