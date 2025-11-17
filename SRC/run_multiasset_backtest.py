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
    # --- Definición de Parámetros Base ---
    params_default = STRATEGY_PARAMS_DEFAULT

    params_sol_optimized = STRATEGY_PARAMS_DEFAULT.copy()
    params_sol_optimized.update({
        "sma_short": 14,
        "sma_long": 30,
    })
    
    params_link_optimized = STRATEGY_PARAMS_DEFAULT.copy()
    params_link_optimized.update({
        "sma_short": 20,
        "sma_long": 55,
    })

    # --- Definición de Activos y sus Parámetros Específicos ---
    assets_to_run = [
        {
            "coin_id": "bitcoin",
            "label": "BTC-USD",
            "params": params_default
        },
        {
            "coin_id": "ethereum",
            "label": "ETH-USD",
            "params": params_default
        },
        {
            "coin_id": "solana",
            "label": "SOL-USD",
            "params": params_sol_optimized
        },
        {
            "coin_id": "chainlink",
            "label": "LINK-USD",
            "params": params_link_optimized
        },
    ]

    vs_currency = "usd"

    print("Ejecutando Backtests con Parámetros Optimizados por Activo...")

    # --- Bucle de Ejecución ---
    for asset in assets_to_run:
        
        print(f"\nUsando SMA({asset['params']['sma_short']}, {asset['params']['sma_long']}) para {asset['label']}...")
        
        run_backtest_for_asset(
            coin_id=asset["coin_id"],
            label=asset["label"],
            params=asset["params"],
            vs_currency=vs_currency,
        )


if __name__ == "__main__":
    main()