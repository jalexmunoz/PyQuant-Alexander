# run_portfolio_backtest.py
# v1.0.0 - (Season 2, Bloque 2)
# Orquestador del backtest a nivel de portafolio.

import pandas as pd
import logging

# --- Importamos los motores ---
from core.data_engine import DataEngine
from core.risk_engine import RiskEngine
from core.portfolio_backtest_engine import PortfolioBacktestEngine  # <<< NUEVO
from core.strategy_profiles import STRATEGY_PROFILES_V1
from core.strategy import StrategyProfile

# --- CONFIGURACIÓN DEL PORTAFOLIO ---
PORTFOLIO_CONFIG = {
    # Portafolio 1: Core/Satellite (BTC dominando)
    "BTC-USD": 0.50,
    "ETH-USD": 0.30,
    "SOL-USD": 0.20,
    # Total debe sumar 1.0 (o menos)
}


def main():
    logging.basicConfig(level=logging.INFO, format='INFO:root:%(message)s')
    pd.set_option("display.width", 120)
    pd.set_option("display.max_columns", 10)
    pd.set_option("display.float_format", '{:,.3f}'.format)

    print("Iniciando Análisis de Portafolio (Season 2, Bloque 2)...")

    # 1. Inicializar Motores Base
    data_engine = DataEngine(default_source="binance")
    processed_data_dict = {}

    # 2. Procesar CADA Activo Individualmente (Usando RiskEngine)
    for label, target_w in PORTFOLIO_CONFIG.items():
        profile = STRATEGY_PROFILES_V1.get(label)

        if profile is None:
            logging.error(f"Perfil de estrategia no encontrado para {label}. Saltando.")
            continue

        print(f"\n--- Procesando {label} (RiskEngine) ---")

        # Obtener datos raw (full history)
        df_raw_data = data_engine.get_data_for_profile(profile, start_date="2017-01-01")
        if df_raw_data.empty:
            logging.error(f"No se pudo obtener data raw para {label}. Saltando.")
            continue

        # Procesar (Crea la columna 'position' para el PortfolioEngine)
        risk_eng = RiskEngine(profile=profile)
        df_processed = risk_eng.compute(df_raw_data)

        processed_data_dict[label] = df_processed

    # 3. Validar que todos los activos fueron procesados
    if len(processed_data_dict) < len(PORTFOLIO_CONFIG):
       logging.error("No se pudieron procesar todos los activos. Abortando portafolio.")
       return

    print("\n" + "=" * 80)
    print(" PASO FINAL: Ejecutando PortfolioBacktestEngine ")
    print("=" * 80)

    # 4. Ejecutar el Portfolio Engine
    portfolio_eng = PortfolioBacktestEngine(target_weights=PORTFOLIO_CONFIG)
    portfolio_eng.run(processed_data_dict)

    # 5. Reporte
    portfolio_eng.print_report()

    # Opcional: Mostrar la curva de equity final del portafolio
    print("\nÚltimas filas de la curva de Equity del Portafolio:")
    print(portfolio_eng.df_portfolio['portfolio_equity'].tail(10).to_string())


if __name__ == "__main__":
    main()