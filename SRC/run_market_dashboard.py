# run_market_dashboard.py
# v0.6 - Market Dashboard (BTC, ETH, SOL) con regímenes y estado de riesgo

import pandas as pd
from pipeline import build_asset_regime_dataset

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 25)

ASSETS = [
    {"coin_id": "bitcoin",  "symbol": "BTC", "label": "BTC-USD"},
    {"coin_id": "ethereum", "symbol": "ETH", "label": "ETH-USD"},
    {"coin_id": "solana",   "symbol": "SOL", "label": "SOL-USD"},
]


def compute_global_risk(asset_snapshots):
    """
    Dado el risk_state de cada activo, define un estado global sencillo:

    - Si al menos uno está en risk_off  -> global = risk_off
    - Si ninguno está en risk_off pero alguno en risk_on -> global = risk_on
    - Resto -> neutral
    """
    states = [snap["risk_state"] for snap in asset_snapshots]

    if "risk_off" in states:
        return "risk_off"
    if "risk_on" in states:
        return "risk_on"
    return "neutral"


def main():
    days = 365
    vs_currency = "usd"

    snapshots = []

    print("\n" + "=" * 80)
    print(f" PyQuant Alexander - Market Dashboard (BTC / ETH / SOL)  - {days} días")
    print("=" * 80)

    for a in ASSETS:
        coin_id = a["coin_id"]
        symbol = a["symbol"]
        label = a["label"]

        print(f"\nDescargando y procesando {label} ({coin_id})...")
        df = build_asset_regime_dataset(coin_id=coin_id, days=days, vs_currency=vs_currency)

        last = df.iloc[-1]
        date = last.name.date()

        snap = {
            "symbol": symbol,
            "label": label,
            "date": date,
            "close": float(last["close"]),
            "sma_short": float(last.get("SMA_20", last.get("SMA_50"))),
            "sma_long": float(last.get("SMA_50", last.get("SMA_200", float("nan")))),
            "rsi": float(last.get("RSI_14", float("nan"))),
            "atr": float(last.get("ATR_20", float("nan"))),
            "trend_regime": last.get("trend_regime", "n/a"),
            "vol_regime": last.get("vol_regime", "n/a"),
            "momentum_regime": last.get("momentum_regime", "n/a"),
            "risk_state": last.get("risk_state", "n/a"),
        }

        snapshots.append(snap)

    # ---------------- Tabla de estado por activo ----------------
    print("\n" + "-" * 80)
    print(" Estado actual por activo")
    print("-" * 80)

    header = (
        f"{'Sym':<4} {'Close':>10} {'SMA20':>10} {'SMA50':>10} "
        f"{'RSI14':>7} {'ATR20':>8}  {'Trend':<8} {'Vol':<8} "
        f"{'Mom':<8} {'Risk':<8}"
    )
    print(header)
    print("-" * len(header))

    for snap in snapshots:
        print(
            f"{snap['symbol']:<4} "
            f"{snap['close']:>10.2f} "
            f"{snap['sma_short']:>10.2f} "
            f"{snap['sma_long']:>10.2f} "
            f"{snap['rsi']:>7.2f} "
            f"{snap['atr']:>8.2f}  "
            f"{snap['trend_regime']:<8} "
            f"{snap['vol_regime']:<8} "
            f"{snap['momentum_regime']:<8} "
            f"{snap['risk_state']:<8}"
        )

    # ---------------- Resumen global ----------------
    global_risk = compute_global_risk(snapshots)

    print("\n" + "-" * 80)
    print(" Resumen de riesgo")
    print("-" * 80)

    print("Risk state por activo:")
    for snap in snapshots:
        print(f"  - {snap['symbol']}: {snap['risk_state']}")

    print(f"\nRisk state GLOBAL: {global_risk.upper()}")

    print("\nInterpretación rápida:")
    if global_risk == "risk_off":
        print("  → Entorno agresivo/feo: volatilidad elevada y/o momentum bajista en al menos un activo grande.")
        print("    Usar esto para moderar pólvora táctica, NO para vender HODL en pánico.")
    elif global_risk == "risk_on":
        print("  → Entorno constructivo: al menos un activo mayor en régimen alcista sano.")
        print("    Puede tener sentido ser más activo con trades tácticos.")
    else:
        print("  → Entorno neutral: ni especialmente peligroso ni especialmente atractivo.")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
