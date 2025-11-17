# run_sma_param_sweep.py
# v0.1.0 - Optimización de parámetros (Parameter Sweep)
#
# Historial:
# v0.1.0 - Versión inicial para optimizar sma_short y sma_long

import pandas as pd
import numpy as np
import itertools
import logging
from pipeline import build_asset_regime_dataset
from signal_generator import add_risk_onoff_signal
from backtest import simple_long_only_backtest

# --- CONFIGURACIÓN DE LA OPTIMIZACIÓN ---

# Activo a optimizar

COIN_ID_TO_TEST = "PEPE"
LABEL = "PEPEUSDT"

# Parámetros base (los que no cambiamos)
# Usaremos los "altcoin" (12/26) como punto de partida
PARAMS_BASE = {
    "sma_short": 12,
    "sma_long": 26,
    "rsi_window": 14,
    "atr_window": 20,
    "trend_slope_window": 5,
    "vol_window": 100,
    "vol_high_mult": 1.3,
    "vol_low_mult": 0.7,
    "mom_bull_thr": 55.0,
    "mom_bear_thr": 45.0,
}

# --- GRID DE PARÁMETROS A PROBAR ---
# Creamos rangos para las SMAs
# np.arange(inicio, fin + 1, paso)
sma_short_range = np.arange(10, 26, 2)  # [10, 12, 14, ..., 24]
sma_long_range = np.arange(30, 61, 5)   # [30, 35, 40, ..., 60]


def run_sweep():
    print("Iniciando barrido de parámetros (Parameter Sweep)...")
    print(f"Activo: {LABEL} ({COIN_ID_TO_TEST})")
    
    # 1. Crear todas las combinaciones
    # (itertools.product crea el producto cartesiano de los rangos)
    param_grid = list(itertools.product(sma_short_range, sma_long_range))
    
    # Filtrar combinaciones inválidas (corta > larga)
    valid_params = [
        (s, l) for s, l in param_grid if s < l
    ]
    
    print(f"Probando {len(valid_params)} combinaciones de SMA_Short vs SMA_Long...")

    # 2. Obtener los datos UNA SOLA VEZ
    # Modificamos el pipeline para que solo obtenga datos y los devuelva
    # (Así no descargamos 100 veces lo mismo)
    
    # Obtenemos los datos *sin* indicadores
    from data_fetcher import get_binance_ohlc
    symbol = "PEPEUSDT" # <<< CAMBIADO de "SOLUSDT"
    df_base = get_binance_ohlc(symbol=symbol, start_date="1 Jan, 2017")
    
    if df_base.empty:
        print("Error: No se pudieron cargar los datos base. Abortando.")
        return
    
    print(f"Datos base de {symbol} cargados. ({len(df_base)} filas)")

    results = [] # Lista para guardar los diccionarios de métricas

    # 3. Bucle de Backtest
    for i, (sma_s, sma_l) in enumerate(valid_params):
        
        print(f"  Probando combo {i+1}/{len(valid_params)}: ({sma_s}, {sma_l})...", end="")
        
        # Copiamos los params base y actualizamos con el combo
        params = PARAMS_BASE.copy()
        params["sma_short"] = sma_s
        params["sma_long"] = sma_l
        
        # --- Ejecutamos el pipeline (solo indicadores y regímenes) ---
        # (Necesitamos una versión 'ligera' de build_asset_regime_dataset)
        # Por simplicidad, llamaremos a la función completa
        # (La descarga de datos se cacheará, pero es ineficiente)
        
        # --- CORRECCIÓN: Llamaremos a la lógica del pipeline manualmente ---
        # (Esto es mucho más rápido que llamar a build_asset_regime_dataset 100 veces)
        
        from indicators import add_sma, add_rsi, add_atr
        from regimes import add_basic_regimes, add_risk_state

        df = df_base.copy() # Usamos los datos base
        
        # Nombres de columna
        sma_s_col = f"SMA_{params['sma_short']}"
        sma_l_col = f"SMA_{params['sma_long']}"
        rsi_col = f"RSI_{params['rsi_window']}"
        atr_col = f"ATR_{params['atr_window']}"

        # Indicadores
        df = add_sma(df, window=params['sma_short'], col_name=sma_s_col)
        df = add_sma(df, window=params['sma_long'], col_name=sma_l_col)
        df = add_rsi(df, window=params['rsi_window'], col_name=rsi_col)
        df = add_atr(df, window=params['atr_window'], col_name=atr_col)

        # Regímenes
        df = add_basic_regimes(df,
            sma_short_col=sma_s_col, sma_long_col=sma_l_col,
            atr_col=atr_col, rsi_col=rsi_col,
            # (usamos los demás params del dict base)
            **{k: v for k, v in params.items() if k in [
                'trend_slope_window', 'vol_window', 'vol_high_mult', 
                'vol_low_mult', 'mom_bull_thr', 'mom_bear_thr'
            ]}
        )
        df = add_risk_state(df)
        
        # Señal
        df = add_risk_onoff_signal(df)
        
        # Backtest
        df_bt, metrics = simple_long_only_backtest(df, train_frac=0.7)
        
        # Guardar resultados
        result_row = {
            "sma_short": sma_s,
            "sma_long": sma_l,
            # Enfocarnos en métricas del TEST SET
            "test_cagr": metrics.get("test_cagr_strategy", np.nan),
            "test_sharpe": metrics.get("test_sharpe_ratio", np.nan),
            "test_profit_factor": metrics.get("test_trades_profit_factor", np.nan),
            "test_max_drawdown": metrics.get("test_max_drawdown_strategy", np.nan),
            "test_num_trades": metrics.get("test_trades_total_num", 0),
            # Y algunas del Full set
            "full_cagr": metrics.get("cagr_strategy", np.nan),
            "full_profit_factor": metrics.get("trades_profit_factor", np.nan),
        }
        results.append(result_row)
        print(" Hecho.")

    # 4. Analizar y mostrar resultados
    if not results:
        print("No se generaron resultados.")
        return

    results_df = pd.DataFrame(results)
    
    print("\n\n" + "=" * 80)
    print(f"Resultados de Optimización para {LABEL} (Ordenado por Profit Factor en Test Set)")
    print("=" * 80)
    
    # Ordenar por el Test Profit Factor
    results_df_sorted = results_df.sort_values(by="test_profit_factor", ascending=False)
    
    # Mostrar el Top 10
    print(results_df_sorted.head(10).to_string())

    # Guardar en CSV
    output_file = f"sweep_results_{COIN_ID_TO_TEST}.csv" # <<< Esta línea ya es dinámica
    results_df_sorted.to_csv(output_file, index=False)
    print(f"\nResultados completos guardados en: {output_file}")


if __name__ == "__main__":
    # Configurar pandas para mostrar bien
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 10)
    pd.set_option("display.float_format", '{:,.3f}'.format)
    
    run_sweep()