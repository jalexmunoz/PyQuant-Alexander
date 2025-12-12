# run_portfolio_stress_tests.py
# v1.0.0 - Script de Stress Testing por Regímenes de Mercado (Bloque 4)

import pandas as pd
import logging
import numpy as np

# --- Importamos los motores ---
# Debes tener estos archivos en tu carpeta SRC
from core.data_engine import DataEngine 
from core.risk_engine import RiskEngine
from core.portfolio_backtest_engine import PortfolioBacktestEngine
from core.strategy_profiles import STRATEGY_PROFILES_V1
from core.strategy import StrategyProfile

# --- CONFIGURACIÓN DEL PORTAFOLIO Y ESCENARIOS ---
PORTFOLIO_CONFIG = {
    "BTC-USD": 0.50,
    "ETH-USD": 0.30,
    "SOL-USD": 0.20,
}

# Definición de Sub-Períodos (Regímenes de Estrés de Mercado Cripto)
STRESS_SCENARIOS = {
    "2018 Crypto Winter": ("2017-12-01", "2018-12-31"),
    "COVID Crash (Mar'20)": ("2020-02-01", "2020-05-31"),
    "2022 Bear Market / FTX": ("2022-01-01", "2023-01-31"),
}


def main():
    # 1. Configuración de Logs y Display
    logging.basicConfig(level=logging.INFO, format='INFO:root:%(message)s')
    pd.set_option("display.width", 120)
    pd.set_option("display.max_columns", 10)
    pd.set_option("display.float_format", '{:,.4f}'.format)

    print("Iniciando Stress Testing de Portafolio por Regímenes...")
    
    # 2. Preparación de Datos Base (Requiere la historia completa)
    # Usando TradingView como fuente de datos
    data_engine = DataEngine(default_source="tradingview")
    processed_data_dict = {}

    for label in PORTFOLIO_CONFIG.keys():
        profile = STRATEGY_PROFILES_V1.get(label)
        df_raw_data = data_engine.get_data_for_profile(profile, start_date="2017-01-01")
        if df_raw_data.empty:
            logging.error(f"No hay data para {label}. Abortando.")
            return

        risk_eng = RiskEngine(profile=profile)
        df_processed = risk_eng.compute(df_raw_data)
        processed_data_dict[label] = df_processed

    if len(processed_data_dict) < len(PORTFOLIO_CONFIG):
        logging.error("Faltan datos procesados. Abortando Stress Test.")
        return
        
    # 3. Orquestar los Stress Tests
    base_engine = PortfolioBacktestEngine(target_weights=PORTFOLIO_CONFIG)
    all_stress_results = []
    
    for scenario_name, (start_date, end_date) in STRESS_SCENARIOS.items():
        print(f"\n--- Corriendo Escenario: {scenario_name} ({start_date} a {end_date}) ---")
        
        # --- NUEVA LÓGICA DE DETECCIÓN Y AJUSTE DE PORTAFOLIO ---
        
        sub_period_data_for_run = {}
        missing_assets = []

        # 1. Identificar activos con datos en el período
        for label, df_asset in processed_data_dict.items():
            # Recortar el DataFrame para verificar si contiene datos
            df_sub = df_asset.loc[start_date:end_date].copy()
            
            if df_sub.empty:
                missing_assets.append(label)
                logging.warning(f"Activo {label} vacío en el período. Será excluido.")
            else:
                sub_period_data_for_run[label] = df_sub

        if not sub_period_data_for_run:
            logging.error("No hay activos disponibles para este sub-período. Saltando.")
            continue
            
        # 2. Re-calcular Target Weights (Normalización)
        current_target_weights = base_engine.target_weights.copy()
        
        # Suma de los pesos de los activos que SÍ tienen data
        available_weight_sum = sum(
            w for label, w in current_target_weights.items() if label not in missing_assets
        )
        
        # Crear un nuevo diccionario de pesos normalizados
        normalized_weights = {}
        for label, w in current_target_weights.items():
            if label not in missing_assets:
                # Normalizar: peso_nuevo = peso_original / suma_pesos_disponibles
                normalized_weights[label] = w / available_weight_sum
                
# run_portfolio_stress_tests.py (Sección 3: Orquestación del Stress Test)

    # 3. Orquestar los Stress Tests
    all_stress_results = []
    
    # Recorremos cada escenario definido
    for scenario_name, (start_date, end_date) in STRESS_SCENARIOS.items():
        print(f"\n--- Corriendo Escenario: {scenario_name} ({start_date} a {end_date}) ---")
        
        current_weights = PORTFOLIO_CONFIG.copy()
        missing_assets = []
        
        # --- LÓGICA DE DETECCIÓN DE DATOS Y NORMALIZACIÓN DE PESOS ---

        # 1. Identificar activos faltantes en el período
        for label in PORTFOLIO_CONFIG.keys():
            df_asset = processed_data_dict[label]
            # Recortar el DataFrame para verificar si contiene datos
            df_sub = df_asset.loc[start_date:end_date]
            
            if df_sub.empty:
                missing_assets.append(label)

        if missing_assets:
            # 2. Re-calcular Target Weights (Normalización)
            
            # Suma de los pesos originales de los activos que SÍ tienen data
            available_weight_sum = sum(
                w for label, w in PORTFOLIO_CONFIG.items() if label not in missing_assets
            )
            
            # Crear el diccionario de pesos normalizados
            normalized_weights = {}
            for label, w in PORTFOLIO_CONFIG.items():
                if label not in missing_assets:
                    # Normalizar: peso_nuevo = peso_original / suma_pesos_disponibles
                    normalized_weights[label] = w / available_weight_sum
            
            logging.info(f"Portafolio Ajustado (Excluyendo {missing_assets}): {normalized_weights}")
            current_weights = normalized_weights
            
        else:
            logging.info("Portafolio Completo usado.")
            
        # 3. Ejecutar Stress Test con el Portafolio Ajustado
        
        # Creamos una NUEVA instancia de PortfolioBacktestEngine con los pesos correctos 
        # para este escenario (Esto evita que el engine intente usar SOL en 2018).
        adjusted_engine = PortfolioBacktestEngine(target_weights=current_weights)
        
        try:
            # run_sub_period usa los target_weights del engine que acabamos de crear (adjusted_engine)
            metrics = adjusted_engine.run_sub_period(
                processed_data_dict, 
                start_date, 
                end_date
            )
        except Exception as e:
            logging.error(f"Error al correr sub-período: {e}")
            continue
        
        if metrics:
            metrics['Scenario'] = scenario_name
            all_stress_results.append(metrics)
            
    # 4. Reporte Consolidado (el resto del código se mantiene)
    
    if not all_stress_results:
        print("\nNo se pudieron generar resultados de Stress Test.")
        return
        
    df_report = pd.DataFrame(all_stress_results)
    
    # Seleccionar y Formatear Columnas Clave
    report_cols = [
        'Scenario', 
        'total_return_strategy', 
        'max_drawdown_stress',
        'cagr_strategy',
        'VaR_95_daily',
        'CVaR_95_daily',
    ]
    
    df_final = df_report[report_cols].set_index('Scenario')
    
    # Formateo
    df_final['total_return_strategy'] = df_final['total_return_strategy'].apply(lambda x: f"{x:,.2%}")
    df_final['max_drawdown_stress'] = df_final['max_drawdown_stress'].apply(lambda x: f"{x:,.2%}")
    df_final['cagr_strategy'] = df_final['cagr_strategy'].apply(lambda x: f"{x:,.2%}")
    df_final['VaR_95_daily'] = df_final['VaR_95_daily'].apply(lambda x: f"{x:,.3%}")
    df_final['CVaR_95_daily'] = df_final['CVaR_95_daily'].apply(lambda x: f"{x:,.3%}")

    print("\n" + "="*80)
    print(" 📊 REPORTE INSTITUCIONAL: STRESS TESTING POR REGÍMENES DE MERCADO ")
    print("="*80)
    print(df_final.to_string())
    print("="*80)
    
    logging.info("Stress Testing completado. Esta matriz de riesgo es clave para la Tarea B.")

if __name__ == "__main__":
    main()