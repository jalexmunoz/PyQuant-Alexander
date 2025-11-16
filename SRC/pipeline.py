# pipeline.py
# v0.2.0 - Orquestador para construir datasets
#
# Historial:
# v0.2.0 - Modificado para usar get_binance_ohlc() como fuente principal
# v0.1.0 - (Versión inicial con CoinGecko)

from data_fetcher import get_binance_ohlc, get_coingecko_ohlc
from indicators import add_sma, add_rsi, add_atr
from regimes import add_basic_regimes, add_risk_state
import logging

# MAPA DE 'coin_id' (gecko) a 'symbol' (binance)
# Esto es crucial para traducir las solicitudes
COIN_TO_SYMBOL_MAP = {
    "bitcoin": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "solana": "SOLUSDT",
    "ripple": "XRPUSDT",
    "chainlink": "LINKUSDT",
}


def build_asset_regime_dataset(
    coin_id: str = "bitcoin",
    days: int = 365,
    vs_currency: str = "usd",
):
    """
    Construye un DataFrame con OHLCV, indicadores y regímenes.
    Usa Binance como fuente principal si el coin_id está en el MAPA.
    Si no, intenta usar CoinGecko (limitado a 365 días y sin volumen).

    Parameters
    ----------
    coin_id : str
        Id de CoinGecko (ej: 'bitcoin', 'ethereum').
    days : int
        Días hacia atrás (SOLO se usa para el fallback de CoinGecko).
    vs_currency : str
        Moneda de cotización (SOLO se usa para el fallback de CoinGecko).

    Returns
    -------
    df : pd.DataFrame
        DataFrame indexado por fecha con columnas OHLCV, indicadores y regímenes.
    """
    symbol = COIN_TO_SYMBOL_MAP.get(coin_id.lower())

    if symbol:
        # --- Ruta Principal: Usar Binance (Datos completos) ---
        # Los parámetros 'days' y 'vs_currency' se ignoran, usamos el historial completo
        df = get_binance_ohlc(symbol=symbol, start_date="1 Jan, 2017")
    else:
        # --- Ruta de Fallback: Usar CoinGecko ---
        logging.warning(f"No se encontró {coin_id} en COIN_TO_SYMBOL_MAP. "
                        f"Usando CoinGecko (limitado a {days} días y sin 'volume').")
        df = get_coingecko_ohlc(coin_id=coin_id, days=days, vs_currency=vs_currency)

    # Si la descarga falló (ej. API caída), retornamos un DF vacío
    if df.empty:
        logging.error(f"No se pudieron obtener datos para {coin_id}. Retornando DF vacío.")
        return df

    # --- Pipeline de Indicadores (sin cambios) ---
    # Nota: add_atr ahora usará la columna 'volume' si existe, pero
    # nuestros indicadores actuales (SMA, RSI, ATR) no la necesitan.
    # Si ATR da error, es porque necesita 'high', 'low', 'close'.

    # Indicadores (OHLC)
    df = add_sma(df, window=20, price_col="close")     # SMA_20
    df = add_sma(df, window=50, price_col="close")     # SMA_50
    df = add_rsi(df, window=14, price_col="close")     # RSI_14
    
    # ATR necesita H-L-C, lo cual tenemos
    df = add_atr(df, window=20)                        # ATR_20

    # Regímenes + estado de riesgo
    df = add_basic_regimes(df, sma_short_col="SMA_20", sma_long_col="SMA_50")
    df = add_risk_state(df)

    return df