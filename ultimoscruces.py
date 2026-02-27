import pandas as pd
from pathlib import Path

assets = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'LINKUSDT']

for asset in assets:
    csv_path = Path(f'Data/tv_export/{asset}_1D.csv')
    if not csv_path.exists():
        print(f"\n❌ Missing file for {asset}: {csv_path}")
        continue
    
    df = pd.read_csv(csv_path, parse_dates=['time'])
    df = df.sort_values('time')

    # Calcular SMAs
    df['sma50'] = df['close'].rolling(50).mean()
    df['sma200'] = df['close'].rolling(200).mean()

    # Detectar cruces
    df['cross_up'] = (df['sma50'] > df['sma200']) & (df['sma50'].shift(1) <= df['sma200'].shift(1))
    df['cross_down'] = (df['sma50'] < df['sma200']) & (df['sma50'].shift(1) >= df['sma200'].shift(1))

    # Últimos cruces
    last_cross_up = df[df['cross_up']].tail(1)
    last_cross_down = df[df['cross_down']].tail(1)

    print(f"\n{asset}:")

    if not last_cross_up.empty:
        t = last_cross_up.iloc[0]['time'].strftime('%Y-%m-%d')
        c = last_cross_up.iloc[0]['close']
        print(f"  Last CROSS UP:   {t} @ ${c:.2f}")

    if not last_cross_down.empty:
        t = last_cross_down.iloc[0]['time'].strftime('%Y-%m-%d')
        c = last_cross_down.iloc[0]['close']
        print(f"  Last CROSS DOWN: {t} @ ${c:.2f}")

    # Estado actual
    current = df.tail(1).iloc[0]
    status = 'ON' if current['sma50'] > current['sma200'] else 'OFF'
    print(f"  Current Status:  {status} (SMA50: ${current['sma50']:.2f}, SMA200: ${current['sma200']:.2f})")