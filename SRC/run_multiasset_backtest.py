# run_multiasset_backtest.py
# v0.7.0 - Backtest multi-activo parametrizado
#
# Historial:
# v0.7.0 - Define params dict y lo pasa al pipeline
# v0.6.0 - Refactor para usar print_backtest_metrics()

import pandas as pd
from pipeline import build_asset_regime_dataset
from signal_generator import add_risk_onoff_signal
from backtest import simple_long_only_backtest
from reporting import print_backtest_metrics

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 25)

# --- CONFIGURACIÓN CENTRAL DE PARÁMETROS ---
# Aquí definimos la estrategia "toy" que teníamos
STRATEGY_PARAMS_DEFAULT = {
    # Parámetros de Indicadores
    "sma_short": 20,
    "sma_long": 50,
    "rsi_window": 14,
    "atr_window": 20,
    
    # Parámetros de Regímenes (los valores fijos que teníamos)
    "trend_slope_window": 5,
    "vol_window": 100,
    "vol_high_mult": 1.3,
    "vol_low_mult": 0.7,
    "mom_bull_thr": 55.0,
    "mom_bear_thr": 45.0,
}


def run_backtest_for_asset(
    coin_id: str,
    label: str,
    params: dict,
    vs_currency: str = "usd"
):
    print("\n" + "#" * 80)
    print(f"# {label}  ({coin_id}) - Backtest (Historial completo)")
    print("#" * 80)

    # 1. Dataset (ahora pasa el dict 'params')
    df = build_asset_regime_dataset(
        coin_id=coin_id,
        params=params,
        vs_currency=vs_currency
    )
    
    if df.empty or len(df) < params['sma_long']: # Chequeo de datos
        print(f"No hay suficientes datos para {label} para el backtest.")
        return

    # 2. Señal Risk ON/OFF (sin cambios)
    df = add_risk_onoff_signal(df)

    # 3. Backtest long-only simple (sin cambios)
    df_bt, metrics = simple_long_only_backtest(df, train_frac=0.7)

    # 4. Imprimir métricas (sin cambios)
    print_backtest_metrics(metrics)

    # 5. Mostrar algunas filas finales
    sma_s_col = f"SMA_{params['sma_short']}"
    sma_l_col = f"SMA_{params['sma_long']}"
    cols_show = [
        "close",
        sma_s_col,
        sma_l_col,
        "trend_regime",
        "vol_regime",
        "momentum_regime",
        "risk_state",
        "position",
        "equity_curve",
    ]
    cols_show = [c for c in cols_show if c in df_bt.columns]

    print("\nÚltimas filas (precio, regímenes, posición):")
    print(df_bt[cols_show].tail(10))


def main():
    # --- Definición de Activos ---
    assets = [
        {"coin_id": "bitcoin",   "label": "BTC-USD"},
        {"coin_id": "ethereum",  "label": "ETH-USD"},
        {"coin_id": "solana",    "label": "SOL-USD"},
        {"coin_id": "ripple",    "label": "XRP-USD"},
        {"coin_id": "chainlink", "label": "LINK-USD"},
    ]

    vs_currency = "usd"

    # --- Definición de Parámetros ---
    
    # Estrategia 1: "Default" (la que ya teníamos)
    # Buena para activos core (BTC, ETH)
    params_default = STRATEGY_PARAMS_DEFAULT

    # Estrategia 2: "Altcoin Momentum" (Nuestra nueva hipótesis)
    # SMAs más rápidas (12/26) para altcoins
    params_altcoin = STRATEGY_PARAMS_DEFAULT.copy()
    params_altcoin.update({
        "sma_short": 12,
        "sma_long": 26,
    })

    # --- Bucle de Ejecución Dinámico ---
    
    for a in assets:
        # Decidimos qué parámetros usar para cada activo
        if a["coin_id"] in ["bitcoin", "ethereum"]:
            params_to_use = params_default
            print(f"\nUsando estrategia 'Default' (20/50) para {a['label']}...")
        else:
            params_to_use = params_altcoin
            print(f"\nUsando estrategia 'Altcoin Momentum' (12/26) para {a['label']}...")

        run_backtest_for_asset(
            coin_id=a["coin_id"],
            label=a["label"],
            params=params_to_use, # <-- Pasamos el dict dinámico
            vs_currency=vs_currency,
        )


if __name__ == "__main__":
    main()