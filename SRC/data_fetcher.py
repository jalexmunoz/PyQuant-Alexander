# data_fetcher.py
# Utilidades para descargar datos de CoinGecko

import pandas as pd
import requests


def get_coingecko_price(coin_id: str, days: int = 180, vs_currency: str = "usd") -> pd.DataFrame:
    """
    Descarga precios históricos (diarios) desde la API pública de CoinGecko.

    Parameters
    ----------
    coin_id : str
        Id del activo (por ejemplo 'bitcoin', 'ethereum').
    days : int, default 180
        Días hacia atrás desde hoy.
    vs_currency : str, default "usd"
        Moneda contra la que se cotiza.

    Returns
    -------
    pd.DataFrame
        DataFrame indexado por fecha con una columna llamada como el id capitalizado (e.g. 'Bitcoin').
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
import pandas as pd
import requests


# ... aquí está ya tu get_coingecko_price ...


def get_coingecko_ohlc(coin_id: str, days: int = 365, vs_currency: str = "usd") -> pd.DataFrame:
    """
    Descarga datos OHLC desde CoinGecko para calcular volatilidad (ATR, etc.).

    Parameters
    ----------
    coin_id : str
        Id del activo (ej: 'bitcoin').
    days : int, default 365
        Días hacia atrás. CoinGecko soporta: 1, 7, 14, 30, 90, 180, 365.
    vs_currency : str, default "usd"
        Moneda de cotización.

    Returns
    -------
    pd.DataFrame
        DataFrame indexado por fecha con columnas: ['open', 'high', 'low', 'close'].
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": vs_currency, "days": days}
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    # data es una lista de listas: [timestamp, open, high, low, close]
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("date")[["open", "high", "low", "close"]]

    return df
