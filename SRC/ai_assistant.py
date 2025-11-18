# ai_assistant.py
# v1.1.0 - Actualizado para usar NewsClient y contexto de noticias.
#
# Lee el snapshot JSON y genera resúmenes.

import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv
from news_client import NewsClient # <<< NUEVA IMPORTACIÓN

# --- Carga de Claves ---
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class AIAssistant:
    """
    Asistente de IA que envuelve un cliente LLM (OpenAI)
    y un NewsClient para interactuar con el snapshot.
    """
    
    def __init__(self):
        # Cliente LLM
        if not OPENAI_API_KEY:
            logging.warning("OPENAI_API_KEY no encontrada en .env. AIAssistant no funcionará.")
            self.llm_client = None
        else:
            self.llm_client = OpenAI(api_key=OPENAI_API_KEY)
            logging.info("AIAssistant inicializado con cliente OpenAI.")
        
        # <<< INICIO BLOQUE NUEVO (News) >>>
        # Cliente de Noticias
        try:
            self.news_client = NewsClient(service="cryptopanic")
            logging.info("AIAssistant inicializado con NewsClient (CryptoPanic).")
        except Exception as e:
            logging.error(f"No se pudo inicializar NewsClient: {e}")
            self.news_client = None
        # <<< FIN BLOQUE NUEVO (News) >>>

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Función wrapper privada para llamar al LLM."""
        if not self.llm_client:
            return "Error: El cliente OpenAI no está inicializado."
        
        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Error al llamar a la API de OpenAI: {e}")
            return f"Error de API: {e}"

    def summarize_dashboard(self, snapshot: dict, news_context: dict | None = None) -> str:
        """
        Toma el snapshot JSON y (opcional) noticias,
        y devuelve un resumen en lenguaje natural.
        """
        
        snapshot_str = json.dumps(snapshot, indent=2)
        news_str = json.dumps(news_context, indent=2) if news_context else "No se proporcionaron noticias."
        
        system_prompt = (
            "Eres 'PyQuant', un analista cuantitativo de criptomonedas, profesional y directo. "
            "Tu trabajo es resumir un reporte de estado táctico (JSON) y titulares de noticias (JSON) para un gerente. "
            "El reporte indica el 'risk_state' (risk_on, risk_off, neutral) basado en un modelo cuantitativo. "
            "Tu resumen debe ser conciso (2-3 párrafos). "
            "1. Empieza con la conclusión del modelo (el estado general). "
            "2. Explica *por qué* el modelo ve eso (tendencia, momentum, vol). "
            "3. **Usa los titulares de noticias** para dar 'color' y contexto a *por qué* el mercado se está moviendo así."
        )
        
        user_prompt = f"""
        Aquí está el snapshot táctico de hoy y los titulares de noticias relevantes.
        Por favor, genera el resumen ejecutivo que combine ambas fuentes.

        --- SNAPSHOT CUANTITATIVO ---
        {snapshot_str}
        
        --- TITULARES DE NOTICIAS ---
        {news_str}
        """
        
        return self._call_llm(system_prompt, user_prompt)

    def get_contextual_news(self, snapshot: dict) -> dict:
        """
        Analiza el snapshot, extrae los símbolos de los activos
        y llama al NewsClient para obtener titulares reales.
        """
        if not self.news_client:
            logging.warning("NewsClient no está disponible. No se pueden obtener noticias.")
            return {}
            
        # Extraer símbolos (ej. "BTC" de "BTC-USD")
        symbols_to_query = []
        for asset in snapshot.get("assets", []):
            label = asset.get("symbol", "") # "BTC-USD"
            symbol = label.split('-')[0]     # "BTC"
            if symbol and symbol not in symbols_to_query:
                symbols_to_query.append(symbol)
        
        if not symbols_to_query:
            return {}
            
        # Llamar al worker (NewsClient)
        return self.news_client.get_headlines_for_symbols(symbols_to_query, limit=3)