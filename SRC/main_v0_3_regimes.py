# main_v0_3_regimes.py
# v0.3 - Regímenes de mercado básicos para BTC usando SMAs, RSI y ATR

import matplotlib.pyplot as plt
import pandas as pd

from data_fetcher import get_coingecko_ohlc
from indicators import add_sma, add_rsi, add_atr
from regimes import add_basic_regimes

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)
plt.style.use("ggplot")


def main():
    print("Descargando BTC OHLC desde CoinGecko (v0.3)...")
    df = get_coingecko_ohlc("bitcoin", days=365)

    # Indicadores base
    df = add_sma(df, window=50, price_col="close")     # SMA_50
    df = add_sma(df, window=200, price_col="close")    # SMA_200
    df = add_rsi(df, window=14, price_col="close")     # RSI_14
    df = add_atr(df, window=20)                        # ATR_20

    # Regímenes
    df = add_basic_regimes(df)

    print("\nÚltimas filas con regímenes:")
    print(df[["close", "SMA_50", "SMA_200", "RSI_14", "ATR_20",
              "trend_regime", "vol_regime", "momentum_regime"]].tail(15))

    print("\nResumen de regímenes de tendencia:")
    print(df["trend_regime"].value_counts(dropna=False))

    print("\nResumen de regímenes de volatilidad:")
    print(df["vol_regime"].value_counts(dropna=False))

    print("\nResumen de regímenes de momentum:")
    print(df["momentum_regime"].value_counts(dropna=False))

    # Visual simple: precio + colores por tendencia (solo para sentirlo)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df.index, df["close"], label="BTC Close", linewidth=1.2)

    # Marcar uptrend / downtrend con puntos
    up = df["is_trend_up"]
    down = df["is_trend_down"]

    ax.scatter(df.index[up], df["close"][up], marker="^", s=30, label="Uptrend", alpha=0.8)
    ax.scatter(df.index[down], df["close"][down], marker="v", s=30, label="Downtrend", alpha=0.8)

    ax.set_title("BTCUSD – Precio con puntos de Uptrend / Downtrend (v0.3)")
    ax.set_ylabel("Precio (USD)")
    ax.set_xlabel("Fecha")
    ax.legend(loc="upper left")
    ax.grid(True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
