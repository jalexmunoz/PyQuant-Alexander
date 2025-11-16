# pipeline.py
# v0.3.0 - Orquestador parametrizado
#
# Historial:
# v0.3.0 - Acepta un dict 'params' para construir indicadores y regímenes
# v0.2.0 - Modificado para usar get_binance_ohlc()

from data_fetcher import get_binance_ohlc, get_coingecko_ohlc
from indicators import add_sma, add_rsi, add_atr
from regimes import add_basic_regimes, add_risk_state
import logging

# MAPA DE 'coin_id' (gecko) a 'symbol' (binance)
COIN_TO_SYMBOL_MAP = {
    "bitcoin": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "solana": "SOLUSDT",
    "ripple": "XRPUSDT",
    "chainlink": "LINKUSDT",
}


def build_asset_regime_dataset(
    coin_id: str,
    params: dict,
    days: int = 365,
    vs_currency: str = "usd",
):
    """
    Construye un DataFrame con OHLCV, indicadores y regímenes,
    basado en un diccionario de parámetros.

    Parameters
    ----------
    coin_id : str
        Id de CoinGecko (ej: 'bitcoin', 'ethereum').
    params : dict
        Diccionario con todos los parámetros de la estrategia.
    days : int
        Días hacia atrás (SOLO se usa para el fallback de CoinGecko).
    vs_currency : str
        Moneda de cotización (SOLO se usa para el fallback de CoinGecko).

    Returns
    -------
    df : pd.DataFrame
    """
    symbol = COIN_TO_SYMBOL_MAP.get(coin_id.lower())

    if symbol:
        # --- Ruta Principal: Usar Binance (Datos completos) ---
        df = get_binance_ohlc(symbol=symbol, start_date="1 Jan, 2017")
    else:
        # --- Ruta de Fallback: Usar CoinGecko ---
        logging.warning(f"No se encontró {coin_id} en COIN_TO_SYMBOL_MAP. "
                        f"Usando CoinGecko (limitado a {days} días y sin 'volume').")
        df = get_coingecko_ohlc(coin_id=coin_id, days=days, vs_currency=vs_currency)

    if df.empty:
        logging.error(f"No se pudieron obtener datos para {coin_id}. Retornando DF vacío.")
        return df

    # --- Pipeline de Indicadores (Ahora dinámico) ---
    
    # Nombres de columna que se generarán
    sma_s_col = f"SMA_{params['sma_short']}"
    sma_l_col = f"SMA_{params['sma_long']}"
    rsi_col = f"RSI_{params['rsi_window']}"
    atr_col = f"ATR_{params['atr_window']}"

    df = add_sma(df, window=params['sma_short'], price_col="close", col_name=sma_s_col)
    df = add_sma(df, window=params['sma_long'], price_col="close", col_name=sma_l_col)
    df = add_rsi(df, window=params['rsi_window'], price_col="close", col_name=rsi_col)
    df = add_atr(df, window=params['atr_window'], col_name=atr_col)

    # --- Pipeline de Regímenes (Ahora dinámico) ---
    df = add_basic_regimes(
        df,
        # Nombres de columnas de indicadores
        sma_short_col=sma_s_col,
        sma_long_col=sma_l_col,
        atr_col=atr_col,
        rsi_col=rsi_col,
        # Parámetros de lógica de régimen
        trend_slope_window=params['trend_slope_window'],
        vol_window=params['vol_window'],
        vol_high_mult=params['vol_high_mult'],
        vol_low_mult=params['vol_low_mult'],
        mom_bull_thr=params['mom_bull_thr'],
        mom_bear_thr=params['mom_bear_thr'],
    )
    
    # Estado de riesgo (sin cambios)
    df = add_risk_state(df)

    return df