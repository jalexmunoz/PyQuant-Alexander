# news_client.py
# v1.0.0 - Cliente de API para servicios de noticias.

import os
import logging
import requests
from dotenv import load_dotenv

# --- Carga de Claves ---
load_dotenv()
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY")

class NewsClient:
    """
    Envoltorio para APIs de noticias (CryptoPanic, NewsAPI, etc.)
    """

    def __init__(self, service: str = "cryptopanic"):
        self.service = service
        self.api_key = None

        if self.service == "cryptopanic":
            self.api_key = CRYPTOPANIC_API_KEY
            self.base_url = "https://cryptopanic.com/api/developer/v2"
            if not self.api_key:
                logging.warning("NewsClient: CRYPTOPANIC_API_KEY no encontrada. No se podrán obtener noticias.")
        else:
            logging.warning(f"NewsClient: Servicio '{self.service}' no reconocido.")
        
    def get_headlines_for_symbols(self, symbols: list[str], limit: int = 3) -> dict:
        """
        Obtiene titulares de CryptoPanic para una lista de símbolos (ej. "BTC", "ETH").
        Devuelve un dict: {"BTC": [lista de noticias], "ETH": [lista de noticias]}
        """
        if not self.api_key or self.service != "cryptopanic":
            return {}
            
        # Convierte ["BTC", "ETH"] en "BTC,ETH"
        currencies_str = ",".join(symbols)
        
        # ESTE ES EL CÓDIGO CORRECTO
        params = {
            "auth_token": self.api_key,
            "currencies": currencies_str,
            "filter": "important" # <<< ESTE ES EL CAMBIO
}
        
        try:
            response = requests.get(f"{self.base_url}/posts/", params=params, timeout=10)
            response.raise_for_status() # Lanza error si la API falla
            data = response.json()
            
            # Procesar y agrupar noticias por símbolo
            news_by_symbol = {symbol: [] for symbol in symbols}
            if not data.get("results"):
                return news_by_symbol
                
            for post in data["results"]:
                headline = {
                    "title": post.get("title"),
                    "url": post.get("url"),
                    "source": post.get("source", {}).get("title"),
                    "published_at": post.get("created_at")
                }
                
                # Asignar la noticia a cada símbolo que mencionó
                for currency in post.get("currencies", []):
                    symbol = currency.get("code")
                    if symbol in news_by_symbol and len(news_by_symbol[symbol]) < limit:
                        news_by_symbol[symbol].append(headline)
                        
            return news_by_symbol
            
        except Exception as e:
            logging.error(f"NewsClient: Error al llamar a la API de CryptoPanic: {e}")
            return {}