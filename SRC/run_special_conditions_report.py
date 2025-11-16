# run_special_conditions_report.py
# v0.7 - Reporte de condiciones especiales (RSI, rupturas, spikes de vol) para BTC/ETH/SOL

import pandas as pd

from pipeline import build_asset_regime_dataset
from conditions import add_condition_flags

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 30)


def run_for_asset(coin_id: str, label: str, days: int = 365, vs_currency: str = "usd"):
    print("\n" + "#" * 80)
    print(f"# {label}  ({coin_id}) - Special conditions report ({days} days)")
    print("#" * 80)

    df = build_asset_regime_dataset(coin_id=coin_id, days=days, vs_currency=vs_currency)
    df = add_condition_flags(df)

    last = df.iloc[-1]
    date = last.name.date()

    print(f"\nSnapshot actual - {label}  |  Fecha: {date}")
    print("-" * 80)
    print(f"Close:        {float(last['close']):10.2f}")
    print(f"RSI 14:       {float(last.get('RSI_14', float('nan'))):5.1f}")
    print(f"SMA_20:       {float(last.get('SMA_20', float('nan'))):10.2f}")
    print(f"SMA_50:       {float(last.get('SMA_50', float('nan'))):10.2f}")
    print(f"ATR_20:       {float(last.get('ATR_20', float('nan'))):10.2f}")
    print(f"atr_norm:     {float(last.get('atr_norm', float('nan'))):5.2f}")
    print(f"trend_regime: {str(last.get('trend_regime', 'n/a'))}")
    print(f"vol_regime:   {str(last.get('vol_regime', 'n/a'))}")
    print(f"momentum:     {str(last.get('momentum_regime', 'n/a'))}")
    print(f"risk_state:   {str(last.get('risk_state', 'n/a'))}")
    print("-" * 80)

    # Flags activos hoy
    active_flags = []
    for col in [
        "cond_rsi_overbought",
        "cond_rsi_oversold",
        "cond_break_above_sma50",
        "cond_break_below_sma50",
        "cond_vol_spike",
        "cond_vol_crush",
    ]:
        if col in df.columns and bool(last[col]):
            active_flags.append(col)

    if not active_flags:
        print("Flags activos hoy: ninguno (condiciones normales dentro de lo definido).")
    else:
        print("Flags activos hoy:")
        for f in active_flags:
            print(f"  - {f}")

    # Mostrar últimas N filas con flags para ver contexto
    N = 8
    cols_show = [
        "close",
        "RSI_14",
        "SMA_20",
        "SMA_50",
        "ATR_20",
        "atr_norm",
        "cond_rsi_overbought",
        "cond_rsi_oversold",
        "cond_break_above_sma50",
        "cond_break_below_sma50",
        "cond_vol_spike",
        "cond_vol_crush",
    ]
    cols_show = [c for c in cols_show if c in df.columns]

    print(f"\nÚltimas {N} filas con flags:")
    print(df[cols_show].tail(N))


def main():
    assets = [
        {"coin_id": "bitcoin",  "label": "BTC-USD"},
        {"coin_id": "ethereum", "label": "ETH-USD"},
        {"coin_id": "solana",   "label": "SOL-USD"},
    ]

    days = 365
    vs_currency = "usd"

    for a in assets:
        run_for_asset(a["coin_id"], a["label"], days=days, vs_currency=vs_currency)


if __name__ == "__main__":
    main()
