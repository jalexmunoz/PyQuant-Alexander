# data_engine.py
# v1.0.0 - Envoltorio (wrapper) para la adquisición de datos.

import pandas as pd
import logging
from strategy import StrategyProfile

# Importamos las funciones 'core' que ya funcionan
from data_fetcher import get_binance_ohlc, get_coingecko_ohlc

class DataEngine:
    """
    Envoltorio POO para la lógica de data_fetcher.
    Abstrae la fuente de datos (Binance, Gecko) del resto del framework.
    """
    
    def __init__(self, default_source: str = "binance"):
        self.default_source = default_source
        logging.info(f"DataEngine inicializado (fuente por defecto: {default_source})")

    def get_data_for_profile(
        self,
        profile: StrategyProfile,
        start_date: str = "1 Jan, 2017"
    ) -> pd.DataFrame:
        """
        Obtiene datos históricos para un StrategyProfile específico.
        
        Utiliza el 'symbol' del perfil para Binance o el 'coin_id'
        para el fallback de CoinGecko.
        """
        
        if self.default_source == "binance" and profile.symbol:
            try:
                # Llama a la función 'core' que ya probamos
                df = get_binance_ohlc(
                    symbol=profile.symbol,
                    start_date=start_date
                )
                if not df.empty:
                    return df
                else:
                    logging.warning(f"Binance no devolvió datos para {profile.symbol}. "
                                    "Intentando fallback a CoinGecko.")
            except Exception as e:
                logging.error(f"Error al obtener datos de Binance para {profile.symbol}: {e}. "
                              "Intentando fallback a CoinGecko.")
        
        # --- Fallback a CoinGecko ---
        logging.info(f"Usando fallback de CoinGecko (365d) para {profile.coin_id}")
        try:
            # Llama a la función 'core' de CoinGecko
            df = get_coingecko_ohlc(coin_id=profile.coin_id, days=365)
            return df
        except Exception as e:
            logging.error(f"Fallback a CoinGecko también falló para {profile.coin_id}: {e}")
            return pd.DataFrame() # Retornar DF vacío en caso de fallo total

    def get_ohlc(self, symbol: str, start_date: str = "1 Jan, 2017") -> pd.DataFrame:
        """
        Método genérico para llamar a la fuente por defecto.
        """
        if self.default_source == "binance":
            return get_binance_ohlc(symbol=symbol, start_date=start_date)
        else:
            # Asumimos que 'symbol' es un 'coin_id' para CoinGecko
            return get_coingecko_ohlc(coin_id=symbol, days=365)