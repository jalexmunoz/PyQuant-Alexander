# run_multiasset_backtest.py
# v0.8.0 - Orquestador de Motores de Backtest (POO)
#
# Historial:
# v0.8.0 - Refactor final para usar DataEngine, RiskEngine y BacktestEngine.
# v0.7.0 - Define params dict y lo pasa al pipeline
# ...

import pandas as pd
import logging

# --- Los 3 Motores y Perfiles ---
from data_engine import DataEngine
from risk_engine import RiskEngine
from backtest_engine import BacktestEngine
from strategy_profiles import STRATEGY_PROFILES_V1
from strategy import StrategyProfile


def run_backtest_for_asset(
    data_engine: DataEngine,
    profile: StrategyProfile,
    label: str
):
    """
    Orquesta la ejecución completa de un backtest para un perfil.
    1. DataEngine obtiene datos.
    2. RiskEngine procesa regímenes.
    3. BacktestEngine ejecuta simulación y reporta.
    """
    print(f"\nUsando {profile.name} (SMA({profile.sma_short}, {profile.sma_long})) para {label}...")

    # --- PASO 1: DATA ENGINE ---
    df_data = data_engine.get_data_for_profile(profile)
    if df_data.empty:
        print(f"DataEngine no pudo obtener datos para {label}. Saltando.")
        return

    # --- PASO 2: RISK ENGINE ---
    risk_eng = RiskEngine(profile=profile)
    df_processed = risk_eng.compute(df_data)
    if df_processed.empty:
        print(f"RiskEngine no pudo procesar datos para {label}. Saltando.")
        return

    # --- PASO 3: BACKTEST ENGINE ---
    backtest_eng = BacktestEngine(profile=profile)
    backtest_eng.run(df_processed, train_frac=0.7)

    # --- PASO 4: REPORTE ---
    backtest_eng.print_report()
    
    # Mostrar filas finales (tomadas del df_bt guardado en el engine)
    df_bt_results, _ = backtest_eng.get_results()
    if df_bt_results.empty:
        logging.warning("BacktestEngine no generó un DataFrame de resultados.")
        return

    sma_s_col = f"SMA_{profile.sma_short}"
    sma_l_col = f"SMA_{profile.sma_long}"
    
    cols_show = [
        "close", sma_s_col, sma_l_col,
        "trend_regime", "vol_regime", "momentum_regime",
        "risk_state", "position", "equity_curve",
    ]
    # Filtramos solo las columnas que realmente existen
    cols_show_exist = [c for c in df_bt_results.columns if c in cols_show]
    
    print("\nÚltimas filas (precio, regímenes, posición):")
    print(df_bt_results[cols_show_exist].tail(10))


def main():
    
    # 1. Inicializar el DataEngine
    engine = DataEngine(default_source="binance")

    print("Ejecutando Backtests con Arquitectura de Motores POO (Paso 4)...")

    # 2. Bucle de Ejecución
    for label, profile in STRATEGY_PROFILES_V1.items():
        
        if profile is None:
            print(f"\nEstrategia para {label} está 'None'. Saltando.")
            continue
        
        run_backtest_for_asset(
            data_engine=engine,
            profile=profile,
            label=label,
        )


if __name__ == "__main__":
    # Configurar logging para ver los mensajes de los motores
    logging.basicConfig(level=logging.INFO, format='INFO:root:%(message)s')
    # Configurar pandas
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 10)
    
    main()