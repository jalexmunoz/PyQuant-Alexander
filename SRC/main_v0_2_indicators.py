# main_v0_2_indicators.py
# v0.2 - Indicadores base (SMA50, SMA200, RSI14) sobre BTC

import pandas as pd
import matplotlib.pyplot as plt

from data_fetcher import get_coingecko_price
from indicators import add_sma, add_rsi

# Opciones de display (puedes ajustar si quieres)
pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 10)
plt.style.use("ggplot")


def main():
    print("Descargando BTC desde CoinGecko (v0.2)...")
    df = get_coingecko_price("bitcoin", days=365)

    # Renombrar columna a 'close' para trabajar con indicadores
    df = df.rename(columns={"Bitcoin": "close"})

    # Añadir SMA50, SMA200 y RSI14
    df = add_sma(df, window=50, price_col="close")    # -> SMA_50
    df = add_sma(df, window=200, price_col="close")   # -> SMA_200
    df = add_rsi(df, window=14, price_col="close")    # -> RSI_14

    print("\nÚltimas filas con indicadores:")
    print(df.tail())

    # ----- Gráfico precio + SMAs -----
    fig, (ax_price, ax_rsi) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # Precio + SMAs
    ax_price.plot(df.index, df["close"], label="BTC Close", linewidth=1.5)
    ax_price.plot(df.index, df["SMA_50"], label="SMA 50", linewidth=1.2)
    ax_price.plot(df.index, df["SMA_200"], label="SMA 200", linewidth=1.2)
    ax_price.set_title("BTCUSD con SMA50 y SMA200 (v0.2)")
    ax_price.set_ylabel("Precio (USD)")
    ax_price.legend(loc="upper left")
    ax_price.grid(True)

    # RSI
    ax_rsi.plot(df.index, df["RSI_14"], label="RSI 14", linewidth=1.2)
    ax_rsi.axhline(70, linestyle="--")
    ax_rsi.axhline(30, linestyle="--")
    ax_rsi.set_ylabel("RSI")
    ax_rsi.set_xlabel("Fecha")
    ax_rsi.legend(loc="upper left")
    ax_rsi.grid(True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
