# data_fetcher.py
# v0.2.0 - Utilidades para descargar datos (CoinGecko y Binance)
#
# Historial:
# v0.2.0 - Añadida get_binance_ohlc() y carga de .env
# v0.1.0 - (Versión inicial con CoinGecko)

import pandas as pd
import requests
import os
import logging
from binance.client import Client
from dotenv import load_dotenv

# --- Configuración de Logging y Carga de Claves de Binance ---

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Cargar variables de entorno (claves API) desde el archivo .env
load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

# Inicializar el cliente de Binance
binance_client = None
if BINANCE_API_KEY and BINANCE_API_SECRET:
    try:
        binance_client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
        logging.info("Cliente de Binance inicializado exitosamente.")
    except Exception as e:
        logging.warning(f"Error al inicializar el cliente de Binance: {e}. Las funciones de Binance fallarán.")
else:
    logging.warning("No se encontraron claves API de Binance en .env. Las funciones de Binance no estarán disponibles.")


# --- Funciones de CoinGecko (Se mantienen como fallback) ---

def get_coingecko_price(coin_id: str, days: int = 180, vs_currency: str = "usd") -> pd.DataFrame:
    """
    Descarga precios históricos (diarios) desde la API pública de CoinGecko.
    ... (docstring sin cambios) ...
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": vs_currency, "days": days}
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    prices = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
    prices["date"] = pd.to_datetime(prices["timestamp"], unit="ms")
    prices = prices[["date", "price"]].set_index("date")
    prices.rename(columns={"price": coin_id.capitalize()}, inplace=True)
    return prices


def get_coingecko_ohlc(coin_id: str, days: int = 365, vs_currency: str = "usd") -> pd.DataFrame:
    """
    Descarga datos OHLC desde CoinGecko.
    ... (docstring sin cambios) ...
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": vs_currency, "days": days}
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    # data es una lista de listas: [timestamp, open, high, low, close]
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
    # Aseguramos que solo devuelve O-H-L-C para ser compatible con la versión anterior
    df = df.set_index("date")[["open", "high", "low", "close"]] 
    return df


# --- NUEVA FUNCIÓN DE BINANCE ---

def get_binance_ohlc(
    symbol: str,
    interval: str = Client.KLINE_INTERVAL_1DAY,
    start_date: str = "1 Jan, 2017"
) -> pd.DataFrame:
    """
    Descarga datos OHLCV históricos completos desde Binance.
    Requiere claves API en .env (BINANCE_API_KEY, BINANCE_API_SECRET).

    Parameters
    ----------
    symbol : str
        El símbolo del par en formato Binance (ej: "BTCUSDT", "ETHUSDT").
    interval : str, default Client.KLINE_INTERVAL_1DAY
        Intervalo de Binance (ej: '1d', '4h', '1m').
    start_date : str, default "1 Jan, 2017"
        Fecha de inicio para la descarga de datos.

    Returns
    -------
    pd.DataFrame
        DataFrame indexado por fecha con columnas: ['open', 'high', 'low', 'close', 'volume'].
    """
    if not binance_client:
        logging.error("El cliente de Binance no está inicializado. Revisa las claves API en .env.")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    
    logging.info(f"Iniciando descarga de Binance para {symbol} desde {start_date}...")
    
    try:
        # 1. Descargar datos
        klines = binance_client.get_historical_klines(symbol, interval, start_date)
        
        if not klines:
            logging.warning(f"No se devolvieron datos de Binance para {symbol}.")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        # 2. Definir columnas
        cols = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
        ]
        df = pd.DataFrame(klines, columns=cols)
        
        # 3. Limpiar y formatear
        # Convertir a numérico (Binance devuelve todo como strings)
        numeric_cols = ["open", "high", "low", "close", "volume"]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        # Convertir timestamp a fecha y poner como índice
        df["date"] = pd.to_datetime(df["open_time"], unit="ms")
        df = df.set_index("date")[numeric_cols] # Seleccionar solo las columnas que necesitamos

        logging.info(f"Descarga de Binance para {symbol} completada. {len(df)} registros. "
                     f"Rango: {df.index.min()} a {df.index.max()}")
        
        return df

    except Exception as e:
        # Esto a menudo ocurre si el símbolo no existe (ej. "LINKUSD" en lugar de "LINKUSDT")
        logging.error(f"Error al descargar datos de Binance para {symbol}: {e}")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])