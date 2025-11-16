# main_v0_2b_atr.py
# v0.2b - BTC con OHLC + ATR20 + SMAs + RSI

import matplotlib.pyplot as plt
import pandas as pd

from data_fetcher import get_coingecko_ohlc
from indicators import add_sma, add_rsi, add_atr

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 12)
plt.style.use("ggplot")


def main():
    print("Descargando BTC OHLC desde CoinGecko (v0.2b)...")
    df = get_coingecko_ohlc("bitcoin", days=365)

    # Añadimos indicadores usando la columna 'close'
    df = add_sma(df, window=50, price_col="close")    # SMA_50
    df = add_sma(df, window=200, price_col="close")   # SMA_200
    df = add_rsi(df, window=14, price_col="close")    # RSI_14
    df = add_atr(df, window=20)                       # ATR_20

    print("\nÚltimas filas con indicadores (OHLC + ATR):")
    print(df.tail())

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    # 1) Precio + SMAs
    axes[0].plot(df.index, df["close"], label="BTC Close", linewidth=1.5)
    axes[0].plot(df.index, df["SMA_50"], label="SMA 50", linewidth=1.2)
    axes[0].plot(df.index, df["SMA_200"], label="SMA 200", linewidth=1.2)
    axes[0].set_title("BTCUSD – Price + SMA50/200 (v0.2b)")
    axes[0].set_ylabel("Precio (USD)")
    axes[0].legend(loc="upper left")
    axes[0].grid(True)

    # 2) RSI
    axes[1].plot(df.index, df["RSI_14"], label="RSI 14", linewidth=1.2)
    axes[1].axhline(70, linestyle="--")
    axes[1].axhline(30, linestyle="--")
    axes[1].set_ylabel("RSI")
    axes[1].legend(loc="upper left")
    axes[1].grid(True)

    # 3) ATR
    axes[2].plot(df.index, df["ATR_20"], label="ATR 20", linewidth=1.2)
    axes[2].set_ylabel("ATR (volatilidad)")
    axes[2].set_xlabel("Fecha")
    axes[2].legend(loc="upper left")
    axes[2].grid(True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
