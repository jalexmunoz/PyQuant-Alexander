from tvDatafeed import TvDatafeed, Interval
import pandas as pd

# Login anónimo (no requiere usuario)
tv = TvDatafeed()

assets = {
    "BTCUSDT": ("BINANCE", "BTCUSDT", "2017-08-01"),
    "ETHUSDT": ("BINANCE", "ETHUSDT", "2017-08-01"),
    "SOLUSDT": ("BINANCE", "SOLUSDT", "2020-08-01"),
    "LINKUSDT": ("BINANCE", "LINKUSDT", "2019-01-01"),
}

for name, (exchange, symbol, start_date) in assets.items():
    print(f"Descargando {name} desde {start_date}...")
    df = tv.get_hist(
        symbol=symbol,
        exchange=exchange,
        interval=Interval.in_daily,
        n_bars=5000  # suficiente para cubrir todo el rango
    )

    # Filtrar por fecha mínima
    df = df[df.index >= start_date]

    # Guardar CSV
    df.to_csv(f"Data/{name}_1D.csv")
    print(f"{name} listo ✅")