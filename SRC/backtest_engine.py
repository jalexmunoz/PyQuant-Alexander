# backtest_engine.py
# v1.0.0 - Envoltorio (wrapper) para la lógica de backtesting.

import pandas as pd
import logging
import numpy as np

# Importamos las funciones 'core' que ya funcionan
from backtest import simple_long_only_backtest
from reporting import print_backtest_metrics
from strategy import StrategyProfile

class BacktestEngine:
    """
    Envoltorio POO para la lógica de backtest.py y trades.py.
    Toma un StrategyProfile y un DataFrame procesado (del RiskEngine)
    y ejecuta el backtest, guardando los resultados.
    """
    
    def __init__(self, profile: StrategyProfile):
        self.profile = profile
        self.metrics = {}
        self.df_bt = pd.DataFrame()
        logging.info(f"BacktestEngine inicializado para {self.profile.name}")

    def run(self, df_processed: pd.DataFrame, train_frac: float = 0.7):
        """
        Ejecuta el backtest usando la lógica 'core' de backtest.py.
        """
        if df_processed.empty or len(df_processed) < self.profile.sma_long:
            logging.warning(f"No hay suficientes datos para {self.profile.name}. Backtest saltado.")
            return

        try:
            # Llama a la función 'core' que ya probamos
            self.df_bt, self.metrics = simple_long_only_backtest(
                df_processed, 
                train_frac=train_frac
            )
            logging.info(f"Backtest completado para {self.profile.name}.")
        
        except Exception as e:
            logging.error(f"Error durante la ejecución de simple_long_only_backtest: {e}")
            self.metrics = {}
            self.df_bt = pd.DataFrame()
    
    def print_report(self):
        """
        Imprime el reporte de métricas usando la lógica 'core' de reporting.py.
        """
        if not self.metrics:
            logging.warning("No hay métricas para reportar.")
            return
        
        print_backtest_metrics(self.metrics)

    def get_results(self) -> tuple[pd.DataFrame, dict]:
        """
        Devuelve los resultados crudos (DataFrame del backtest y dict de métricas).
        """
        return self.df_bt, self.metrics