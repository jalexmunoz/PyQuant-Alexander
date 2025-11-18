# run_daily_dashboard.py
# v1.1.0 - Añadida salida JSON
#
# Historial:
# v1.1.0 - Guarda un 'daily_snapshot.json' en la carpeta /output
# v1.0.0 - Versión inicial de producción

import pandas as pd
from datetime import datetime, timedelta
import json
import os
import logging

# Los motores que construimos
from data_engine import DataEngine
from risk_engine import RiskEngine

# Los perfiles de estrategia que optimizamos
from strategy_profiles import STRATEGY_PROFILES_V1

# --- CONFIGURACIÓN ---
LOOKBACK_DAYS = 400 # (300 funcionó bien)
OUTPUT_DIR = "output"
JSON_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "daily_snapshot.json")


def run_dashboard():
    print("=" * 60)
    print(f" PyQuant Dashboard Táctico | Estado al {datetime.now().strftime('%Y-%m-%d %H:%M')} ")
    print("=" * 60)

    # Asegurarse de que el directorio de salida exista
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Calcular fecha de inicio
    start_date_str = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    # 2. Inicializar el DataEngine
    data_engine = DataEngine(default_source="binance")

    report_lines = []
    json_assets_output = [] # <<< NUEVO: Lista para el JSON

    # 3. Iterar sobre cada perfil
    for label, profile in STRATEGY_PROFILES_V1.items():
        if profile is None:
            continue
        
        print(f"\nProcesando {label} ({profile.name})...")
        
        # 4. Obtener datos RECIENTES
        df_data = data_engine.get_data_for_profile(
            profile,
            start_date=start_date_str
        )
        
        if df_data.empty:
            print(f"  ERROR: No se pudieron obtener datos para {label}.")
            report_lines.append(f" {label:<10} | ¡ERROR DE DATOS!")
            continue

        # 5. Inicializar el RiskEngine y obtener el estado
        try:
            risk_engine = RiskEngine(profile=profile)
            latest_state = risk_engine.get_latest_state(df_data)
            
            if latest_state.empty:
                print(f"  ERROR: No se pudo calcular el estado para {label}.")
                report_lines.append(f" {label:<10} | ¡ERROR DE CÁLCULO!")
                continue

            # 6. Formatear el resultado (para ambos, texto y JSON)
            current_risk = latest_state.get("risk_state", "n/a")
            current_trend = latest_state.get("trend_regime", "n/a")
            current_mom = latest_state.get("momentum_regime", "n/a")
            current_vol = latest_state.get("vol_regime", "n/a")
            
            # Línea para el reporte de texto
            line = (
                f" {label:<10} | RIESGO: {current_risk.upper():<8} "
                f"| (Tendencia: {current_trend}, Mom: {current_mom}, Vol: {current_vol})"
            )
            report_lines.append(line)
            
            # <<< INICIO BLOQUE NUEVO (JSON) >>>
            # Diccionario para el reporte JSON
            json_asset = {
                "symbol": label,
                "profile": profile.name,
                "risk_state": current_risk,
                "trend_regime": current_trend,
                "momentum_regime": current_mom,
                "vol_regime": current_vol,
                "sma_short": profile.sma_short,
                "sma_long": profile.sma_long,
            }
            json_assets_output.append(json_asset)
            # <<< FIN BLOQUE NUEVO (JSON) >>>
            
        except Exception as e:
            print(f"  ERROR: Fallo en RiskEngine para {label}: {e}")
            report_lines.append(f" {label:<10} | ¡ERROR DE CÁLCULO!")

    # 7. Imprimir el reporte final de texto
    print("\n\n" + "=" * 60)
    print(" Resumen de Estado Táctico")
    print("=" * 60)
    for line in report_lines:
        print(line)
    print("=" * 60)

    # <<< INICIO BLOQUE NUEVO (JSON) >>>
    # 8. Crear y guardar el snapshot JSON
    final_snapshot = {
        "as_of_utc": datetime.utcnow().isoformat(),
        "as_of_local": datetime.now().isoformat(),
        "assets": json_assets_output
    }
    
    try:
        with open(JSON_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_snapshot, f, indent=2, ensure_ascii=False)
        print(f"\nSnapshot JSON guardado exitosamente en: {JSON_OUTPUT_FILE}")
    except Exception as e:
        print(f"\nERROR: No se pudo guardar el snapshot JSON: {e}")
    # <<< FIN BLOQUE NUEVO (JSON) >>>


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='INFO:root:%(message)s')
    pd.set_option("display.width", 200)
    run_dashboard()