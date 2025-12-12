# runners/run_portfolio_walkforward.py
# v1.2.0 - Walk-Forward Analysis SIN Data Leakage (Bloque 4: Tarea C)
# 
# CRÍTICO: Los indicadores se calculan DENTRO del bucle walk-forward,
# usando SOLO datos históricos disponibles hasta cada punto de corte.
# Esto elimina look-ahead bias y simula condiciones de trading real.

import sys
from pathlib import Path

# Agregar directorio raíz al path para importar módulos core/
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
import logging
import datetime as dt

# --- Importaciones de la NUEVA ESTRUCTURA ---
from core.data_engine import DataEngine
from core.backtest_engine import BacktestEngine # Necesario para el WF individual
from core.portfolio_backtest_engine import PortfolioBacktestEngine
from core.strategy_profiles import STRATEGY_PROFILES_V1
from core.strategy import StrategyProfile
from utils.reporting import print_backtest_metrics # Usamos el reporter para el OOS

# --- CONFIGURACIÓN DEL PORTAFOLIO y WF ---
PORTFOLIO_CONFIG = {
    "BTC-USD": 0.50,
    "ETH-USD": 0.30,
    "SOL-USD": 0.20,
}

WF_CONFIG = {
    "train_years": 3,
    "test_years": 1,
    "start_date": "2018-01-01",
    "end_date": "2024-01-01" 
}

# runners/run_walkforward_analysis.py (Nueva Definición)

def _get_window_dates(start_date, end_date, train_years, test_years):
    """ Genera las ventanas deslizantes de Walk-Forward. """
    
    start_dt = pd.to_datetime(start_date) # Usa start_date
    end_dt = pd.to_datetime(end_date)     # Usa end_date
    
    current_start = start_dt
    train_y = train_years # Renombrar para usar en DateOffset
    test_y = test_years   # Renombrar para usar en DateOffset
    
    # Simple lógica de deslizamiento anual
    while current_start + pd.DateOffset(years=train_y + test_y) <= end_dt:
        train_end = current_start + pd.DateOffset(years=train_y) - pd.DateOffset(days=1)
        test_start = train_end + pd.DateOffset(days=1)
        test_end = test_start + pd.DateOffset(years=test_y) - pd.DateOffset(days=1)
        
        yield (
            current_start.strftime("%Y-%m-%d"), 
            train_end.strftime("%Y-%m-%d"), 
            test_start.strftime("%Y-%m-%d"), 
            test_end.strftime("%Y-%m-%d")
        )
        
        # Deslizar la ventana un período de prueba
        current_start = current_start + pd.DateOffset(years=test_y)


def main():
    
    # 1. Inicializar Motores y Configuración
    data_engine = DataEngine(default_source="binance")
    all_oos_metrics = [] # Para almacenar los resultados Out-of-Sample del portafolio

    print("\n" + "="*80)
    print(" INICIANDO WALK-FORWARD A NIVEL PORTAFOLIO (Season 3) ")
    print("="*80)
    print(f"Portafolio: {PORTFOLIO_CONFIG.keys()}")
    print(f"Configuración: {WF_CONFIG['train_years']}y Train / {WF_CONFIG['test_years']}y Test")
    
    # --- PASO A: OBTENER TODOS LOS DATOS RAW ---
    # Obtenemos los datos raw una sola vez para todos los activos
    raw_data_dict = {}
    for label in PORTFOLIO_CONFIG.keys():
        profile = STRATEGY_PROFILES_V1.get(label)
        df_raw = data_engine.get_data_for_profile(profile, start_date=WF_CONFIG['start_date'])
        if df_raw.empty:
            logging.error(f"No hay datos para {label}. Abortando.")
            return
        raw_data_dict[label] = df_raw


    # --- PASO B: BUCLE WALK-FORWARD (Por Ventana) ---
    for wf_start, train_end, test_start, test_end in _get_window_dates(**WF_CONFIG):
        
        print("\n" + "-"*80)
        print(f"VENTANA WF: [Train: {wf_start} a {train_end}] [Test: {test_start} a {test_end}]")
        print("-"*80)
        
        # 1. OPTIMIZACIÓN EN MUESTRA (IN-SAMPLE)
        # Diccionario para guardar el perfil con los mejores parámetros por activo
        best_profiles_insample = {}
        
        for label, df_raw in raw_data_dict.items():
            profile = STRATEGY_PROFILES_V1.get(label)
            
            # Recortar datos para la ventana de entrenamiento
            df_train_raw = df_raw.loc[wf_start:train_end].copy()
            
            if df_train_raw.empty:
                logging.warning(f"No hay datos en Train para {label}. Saltando activo.")
                continue

            # Ejecutar el BacktestEngine para optimizar (Encuentra el mejor perfil por Sharpe/Calmar)
            # ASUMIMOS que BacktestEngine tiene un método run_optimization(df_data)
            backtest_eng = BacktestEngine(profile=profile)
            best_profile = backtest_eng.run_optimization(df_train_raw)
            
            if best_profile:
                best_profiles_insample[label] = best_profile
                print(f"  > {label}: Optimizacion Completa. Mejor perfil: {best_profile.get_params_dict()}")
        
        if len(best_profiles_insample) != len(PORTFOLIO_CONFIG):
            logging.error("No se pudo optimizar al menos un activo. Saltando ventana.")
            continue
            

        # 2. EVALUACIÓN FUERA DE MUESTRA (OUT-OF-SAMPLE)
        
        # a. Procesar SOLO data histórica hasta el final del periodo de prueba (Sin Look-Ahead Bias)
        # Para cada activo, calculamos indicadores sobre datos disponibles hasta test_end
        processed_oos_data = {}
        
        for label, best_profile in best_profiles_insample.items():
            
            # CRÍTICO: Solo usamos datos históricos hasta el final de la ventana OOS (test_end)
            # Esto simula condiciones de trading real: solo conocemos el pasado
            df_raw_historical = raw_data_dict[label].loc[:test_end].copy()
            
            if df_raw_historical.empty:
                logging.error(f"Data histórica vacía para {label}. Fallo crítico.")
                continue
            
            # Calculamos indicadores SOLO sobre datos históricos (sin look-ahead)
            risk_eng = RiskEngine(profile=best_profile)
            df_processed_historical = risk_eng.compute(df_raw_historical)
            
            # Ahora recortamos al periodo OOS (test_start:test_end)
            # Los indicadores fueron calculados sin ver el futuro más allá de test_end
            df_oos = df_processed_historical.loc[test_start:test_end].copy()
            
            if df_oos.empty:
                logging.error(f"Data OOS vacía para {label}. Fallo crítico.")
                continue
                
            processed_oos_data[label] = df_oos
            
        
        # c. Ejecutar PortfolioBacktestEngine en la ventana OOS
        portfolio_eng = PortfolioBacktestEngine(target_weights=PORTFOLIO_CONFIG)
        
        # El run() espera el diccionario de data procesada. 
        # NOTA: En este punto, solo le pasamos la data recortada a OOS,
        # pero run() internamente re-alineará y calculará retornos.
        portfolio_eng.run(processed_oos_data)

        # d. Guardar Métricas OOS del Portafolio
        oos_metrics = portfolio_eng.metrics
        oos_metrics['wf_window'] = f"{test_start} a {test_end}"
        oos_metrics['oos_cagr'] = oos_metrics.get('cagr_strategy', np.nan)
        oos_metrics['oos_sharpe'] = oos_metrics.get('sharpe_ratio', np.nan)
        
        all_oos_metrics.append(oos_metrics)
        
        print(f"  > PORTAFOLIO OOS CÁLCULO FINALIZADO. CAGR: {oos_metrics['oos_cagr']:,.4f}")


    # --- PASO C: REPORTE FINAL WALK-FORWARD (OOS Consolidado) ---
    if all_oos_metrics:
        df_oos = pd.DataFrame(all_oos_metrics)
        
        # Métricas de Consistencia: Promedio y Mediana del CAGR y Sharpe OOS
        mean_cagr = df_oos['oos_cagr'].mean()
        median_cagr = df_oos['oos_cagr'].median()
        mean_sharpe = df_oos['oos_sharpe'].mean()
        
        print("\n" + "="*80)
        print(" ✅ REPORTE FINAL WALK-FORWARD PORTAFOLIO (OOS CONSOLIDADO) ")
        print("="*80)
        print(f"CAGR Promedio OOS: {mean_cagr:,.2%}")
        print(f"CAGR Mediana OOS: {median_cagr:,.2%}")
        print(f"Sharpe Promedio OOS: {mean_sharpe:,.3f}")
        print("\nResultados Por Ventana:")
        print(df_oos[['wf_window', 'oos_cagr', 'oos_sharpe', 'annual_alpha', 'beta']].to_string())
        print("="*80)
        
    else:
        print("\n[FALLO] No se generaron métricas OOS de Portafolio.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='INFO:root:%(message)s')
    pd.set_option("display.width", 120)
    pd.set_option("display.max_columns", 10)
    pd.set_option("display.float_format", '{:,.3f}'.format)
    
    # Asume que los engines están en core/
    try:
        from core.risk_engine import RiskEngine
    except ImportError:
        print("Error: Asegúrate de que RiskEngine esté en el directorio 'core/'.")

    # Renombrar y mover:
    # 1. Renombrar run_walkforward_analysis.py a run_portfolio_walkforward.py
    # 2. Moverlo al directorio runners/
    
    main()