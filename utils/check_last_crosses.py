import pandas as pd
from pathlib import Path

assets = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'LINKUSDT']

for asset in assets:
    csv_path = Path(f'Data/tv_export/{asset}_1D.csv')
    if not csv_path.exists():
        print(f"\n{asset}: CSV not found")
        continue
    
    # Leer sin parse_dates primero para ver columnas
    df = pd.read_csv(csv_path)
    
    # Detectar columna de fecha (puede ser 'time', 'Time', 'Date', etc.)
    date_col = None
    for col in df.columns:
        if col.lower() in ['time', 'date', 'datetime', 'timestamp']:
            date_col = col
            break
    
    if not date_col:
        print(f"\n{asset}: No date column found. Columns: {df.columns.tolist()}")
        continue
    
    # Parsear fecha correctamente
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col)
    
    # Calcular SMAs
    df['sma50'] = df['close'].rolling(50).mean()
    df['sma200'] = df['close'].rolling(200).mean()
    
    # Detectar cruces
    df['cross_up'] = (df['sma50'] > df['sma200']) & (df['sma50'].shift(1) <= df['sma200'].shift(1))
    df['cross_down'] = (df['sma50'] < df['sma200']) & (df['sma50'].shift(1) >= df['sma200'].shift(1))
    
    # Último cruce
    last_cross_up = df[df['cross_up']].tail(1)
    last_cross_down = df[df['cross_down']].tail(1)
    
    print(f'\n{asset}:')
    if not last_cross_up.empty:
        date_str = last_cross_up.iloc[0][date_col].strftime("%Y-%m-%d")
        price = last_cross_up.iloc[0]["close"]
        print(f'  Last CROSS UP:   {date_str} @ ${price:.2f}')
    
    if not last_cross_down.empty:
        date_str = last_cross_down.iloc[0][date_col].strftime("%Y-%m-%d")
        price = last_cross_down.iloc[0]["close"]
        print(f'  Last CROSS DOWN: {date_str} @ ${price:.2f}')
    
    # Estado actual
    current = df.tail(1).iloc[0]
    status = 'ON' if current['sma50'] > current['sma200'] else 'OFF'
    print(f'  Current Status:  {status}')
    print(f'  SMA50:  ${current["sma50"]:.2f}')
    print(f'  SMA200: ${current["sma200"]:.2f}')
    
    # Distancia al cruce
    distance_pct = abs((current['sma50'] / current['sma200']) - 1) * 100
    print(f'  Distance: {distance_pct:.2f}% {"(close!)" if distance_pct < 1 else ""}')