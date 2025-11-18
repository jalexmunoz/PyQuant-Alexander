# run_ai_summary.py
# v1.1.0 - Actualizado para obtener noticias reales.
#
# Lee el snapshot JSON, pide noticias y resumen a la IA.

import json
import os
import logging
from ai_assistant import AIAssistant

# --- CONFIGURACIÓN ---
OUTPUT_DIR = "output"
JSON_INPUT_FILE = os.path.join(OUTPUT_DIR, "daily_snapshot.json")

def run_summary():
    print("=" * 60)
    print(" Iniciando Asistente de IA de PyQuant (v1.1 con Noticias)...")
    print("=" * 60)

    # 1. Cargar el snapshot JSON
    try:
        with open(JSON_INPUT_FILE, 'r', encoding='utf-8') as f:
            snapshot = json.load(f)
        print(f"Snapshot JSON cargado desde {JSON_INPUT_FILE}")
        print(f"Estado 'as_of': {snapshot.get('as_of_local')}")
    except FileNotFoundError:
        print(f"ERROR: No se encontró el archivo {JSON_INPUT_FILE}.")
        print("Por favor, ejecuta 'run_daily_dashboard.py' primero.")
        return
    except Exception as e:
        print(f"ERROR: No se pudo leer el archivo JSON: {e}")
        return

    # 2. Inicializar el Asistente de IA
    assistant = AIAssistant()
    if not assistant.llm_client:
        print("ERROR: El cliente LLM (OpenAI) no pudo inicializarse.")
        return

    # 3. Obtener Noticias Relevantes
    print("\nObteniendo noticias relevantes de CryptoPanic...")
    news_context = assistant.get_contextual_news(snapshot)
    
    if not news_context:
        print("No se pudieron obtener noticias o no se encontraron símbolos.")
    else:
        print("Noticias obtenidas exitosamente.")

    # 4. Generar Resumen
    print("\nGenerando resumen de IA (combinando snapshot + noticias)...")
    summary = assistant.summarize_dashboard(snapshot, news_context)
    
    print("\n" + "=" * 60)
    print(" Resumen Táctico del Asistente (IA)")
    print("=" * 60)
    print(summary)
    print("." * 60)

    # 5. Imprimir los titulares crudos
    print("\n" + "=" * 60)
    print(" Titulares de Noticias (Fuente: CryptoPanic)")
    print("=" * 60)
    if not news_context:
        print("No se encontraron noticias.")
    else:
        for symbol, news_list in news_context.items():
            if news_list:
                print(f" {symbol}:")
                for item in news_list:
                    print(f"   - {item['title']} ({item['source']})")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='INFO:root:%(message)s')
    run_summary()