# news_client.py
# v1.3.0 - Añadido filtro de spam y captura de 'domain'
#
# Historial:
# v1.3.0 - Añadida blacklist para spam y guardado de 'domain'
# v1.2.0 - Normaliza "BTC-USD" -> "BTC" y reintenta
# v1.1.0 - Corregido para bucle de API v2
# v1.0.0 - Versión inicial

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
            self.base_url = "https://cryptopanic.com/api/developer/v2" # v2 es correcto
            if not self.api_key:
                logging.warning("NewsClient: CRYPTOPANIC_API_KEY no encontrada.")
        else:
            logging.warning(f"NewsClient: Servicio '{service}' no soportado.")

    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normaliza un símbolo de "BTC-USD" a "BTC".
        """
        if "-" in symbol:
            return symbol.split("-")[0].upper()
        return symbol.upper()

    def get_headlines_for_symbols(self, symbols: list[str], limit: int = 3) -> dict:
        """
        Obtiene titulares de CryptoPanic para una lista de símbolos.
        """
        if not self.api_key or self.service != "cryptopanic":
            return {}
            
        news_by_symbol = {}
        
        # <<< INICIO BLOQUE NUEVO (Sugerencia b) >>>
        # Filtro de ruido "shitcoinero"
        blacklist_snippets = [
            "Best Meme Coins", "Presales to Buy", "New Coins That Will Explode",
            "Best Crypto Presales", "Top X Coins to Buy", "Official Trump",
            "Useless Coin", "Bitcoin Hyper"
        ]
        # <<< FIN BLOQUE NUEVO >>>

        for symbol in symbols:
            code = self._normalize_symbol(symbol)
            params = {
                "auth_token": self.api_key,
                "currencies": code,
                "filter": "important"
            }
            logging.info(f"NewsClient: Buscando noticias 'important' para {symbol} (code={code})...")
            
            try:
                response = requests.get(f"{self.base_url}/posts/", params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if not data.get("results"):
                    logging.info(f"NewsClient: Sin resultados 'important' para {code}, reintentando sin filtro...")
                    params.pop("filter", None)
                    response = requests.get(f"{self.base_url}/posts/", params=params, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                        
                headlines = []
                if not data.get("results"):
                    news_by_symbol[symbol] = []
                    continue
                
                for post in data.get("results", []):
                    if len(headlines) >= limit:
                        break
                    
                    title = post.get("title", "") or ""
                    
                    # <<< INICIO BLOQUE NUEVO (Sugerencia b) >>>
                    # Aplicar el filtro de spam
                    if any(bad.lower() in title.lower() for bad in blacklist_snippets):
                        continue # Saltar esta noticia spam
                    # <<< FIN BLOQUE NUEVO >>>
                    
                    headlines.append({
                        "title": title,
                        "url": post.get("url"),
                        "source": post.get("source", {}).get("title"),
                        "domain": post.get("source", {}).get("domain"), # <-- Captura de fallback
                        "published_at": post.get("created_at")
                    })
                
                news_by_symbol[symbol] = headlines
            
            except Exception as e:
                logging.error(f"NewsClient: Error al llamar a API para {code}: {e}")
                news_by_symbol[symbol] = []
        
        return news_by_symbol