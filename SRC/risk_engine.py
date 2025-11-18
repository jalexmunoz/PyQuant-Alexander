# risk_engine.py
# v1.0.0 - Envoltorio (wrapper) para el pipeline de indicadores y regímenes.

import pandas as pd
import logging
from strategy import StrategyProfile

# Importamos las funciones 'core' que ya funcionan
from indicators import add_sma, add_rsi, add_atr
from regimes import add_basic_regimes, add_risk_state
from signal_generator import add_risk_onoff_signal

class RiskEngine:
    """
    Envoltorio POO para la lógica de indicators.py y regimes.py.
    Toma datos puros y un StrategyProfile, y devuelve un DataFrame
    procesado con todos los indicadores, regímenes y el risk_state.
    """
    
    def __init__(self, profile: StrategyProfile):
        self.profile = profile
        self.params = profile.get_params_dict()
        logging.info(f"RiskEngine inicializado para {self.profile.name}")

    def compute(self, df_data: pd.DataFrame) -> pd.DataFrame:
        """
        Toma un DataFrame de datos OHLCV puros y aplica todo el
        pipeline de indicadores, regímenes y estado de riesgo.
        """
        df = df_data.copy()
        
        # --- 1. Generar Nombres de Columna ---
        sma_s_col = f"SMA_{self.params['sma_short']}"
        sma_l_col = f"SMA_{self.params['sma_long']}"
        rsi_col = f"RSI_{self.params['rsi_window']}"
        atr_col = f"ATR_{self.params['atr_window']}"

        # --- 2. Calcular Indicadores ---
        df = add_sma(df, window=self.params['sma_short'], col_name=sma_s_col)
        df = add_sma(df, window=self.params['sma_long'], col_name=sma_l_col)
        df = add_rsi(df, window=self.params['rsi_window'], col_name=rsi_col)
        df = add_atr(df, window=self.params['atr_window'], col_name=atr_col)

        # --- 3. Calcular Regímenes ---
        df = add_basic_regimes(df,
            sma_short_col=sma_s_col, sma_long_col=sma_l_col,
            atr_col=atr_col, rsi_col=rsi_col,
            # Pasa todos los demás parámetros de régimen
            **{k: v for k, v in self.params.items() if k in [
                'trend_slope_window', 'vol_window', 'vol_high_mult', 
                'vol_low_mult', 'mom_bull_thr', 'mom_bear_thr'
            ]}
        )
        
        # --- 4. Calcular Estado de Riesgo ---
        df = add_risk_state(df)
        
        # --- 5. Calcular Señal (para backtest) ---
        df = add_risk_onoff_signal(df)
        
        return df

    def get_latest_state(self, df_data: pd.DataFrame) -> pd.Series:
        """
        Método de conveniencia para el "dashboard diario".
        Calcula todo y devuelve solo la última fila (el estado de hoy).
        """
        df_processed = self.compute(df_data)
        if df_processed.empty:
            return pd.Series(dtype='object')
        
        return df_processed.iloc[-1]