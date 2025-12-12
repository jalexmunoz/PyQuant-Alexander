# test_binance_fetch.py
# Script para probar la descarga de datos históricos de Binance

import os
from binance.client import Client
from dotenv import load_dotenv
import pandas as pd

# Cargar variables de entorno (claves API) desde el archivo .env
load_dotenv()

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

if not api_key or not api_secret:
    print("Error: No se encontraron las claves API de Binance en el archivo .env")
    exit()

print("Claves API cargadas. Conectando a Binance...")
client = Client(api_key, api_secret)

# 1. Definir el par y el intervalo
symbol = "BTCUSDT"
interval = Client.KLINE_INTERVAL_1DAY
start_date = "1 Jan, 2017" # Intentemos desde muy atrás

print(f"Intentando descargar datos para {symbol} a {interval} desde {start_date}...")

try:
    # 2. Obtener los datos (klines)
    klines = client.get_historical_klines(symbol, interval, start_date)
    print(f"¡Éxito! Se descargaron {len(klines)} velas (días) de datos.")

    # 3. Convertir a un DataFrame de Pandas para entenderlo
    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ]
    df = pd.DataFrame(klines, columns=cols)
    
    # Convertir la hora a formato legible
    df["date"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("date")

    # 4. Mostrar el rango de fechas que obtuvimos
    print("\n=== Rango de Datos Obtenido ===")
    print(f"Fecha de inicio (primer registro): {df.index.min()}")
    print(f"Fecha de fin (último registro):   {df.index.max()}")

except Exception as e:
    print(f"Error al descargar datos de Binance: {e}")