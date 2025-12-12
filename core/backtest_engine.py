# backtest_engine.py
# v1.1.0 - Añadido análisis Walk-Forward (Bloque 1)
#
# Historial:
# v1.1.0 - Añadidos run_walkforward() y print_wf_report()
# v1.0.0 - Versión inicial

import pandas as pd
import numpy as np
import logging

# Importamos las funciones 'core'
from .backtest import simple_long_only_backtest
from utils.reporting import print_backtest_metrics
from .strategy import StrategyProfile
# Importamos RiskEngine para recalcular indicadores en cada ventana WF (anti-leak)
from .risk_engine import RiskEngine

class BacktestEngine:
    """
    Envoltorio POO para la lógica de backtest.
    v1.1: Añade capacidad de Walk-Forward.
    """
    
    def __init__(self, profile: StrategyProfile):
        self.profile = profile
        self.metrics = {}
        self.df_bt = pd.DataFrame()
        # Almacén para resultados de WF
        self.wf_results = []
        logging.info(f"BacktestEngine inicializado para {self.profile.name}")

    def run(self, df_processed: pd.DataFrame, train_frac: float = 0.7):
        """
        Ejecuta un ÚNICO backtest (el método 'antiguo').
        """
        if df_processed.empty or len(df_processed) < self.profile.sma_long:
            logging.warning(f"No hay suficientes datos para {self.profile.name}. Backtest saltado.")
            return

        try:
            self.df_bt, self.metrics = simple_long_only_backtest(
                df_processed, 
                train_frac=train_frac
            )
            logging.info(f"Backtest simple completado para {self.profile.name}.")
        
        except Exception as e:
            logging.error(f"Error durante la ejecución de simple_long_only_backtest: {e}")
            self.metrics = {}
            self.df_bt = pd.DataFrame()
    
    def print_report(self):
        """
        Imprime el reporte del backtest simple.
        """
        if not self.metrics:
            logging.warning("No hay métricas para reportar (run).")
            return
        
        print_backtest_metrics(self.metrics)

    def get_results(self) -> tuple[pd.DataFrame, dict]:
        """
        Devuelve los resultados crudos del backtest simple.
        """
        return self.df_bt, self.metrics

    # --- INICIO BLOQUE 1: WALK-FORWARD (NUEVO) ---

    def run_walkforward(
        self,
        df_raw_data: pd.DataFrame,
        wf_config: dict
    ):
        """
        Ejecuta un análisis Walk-Forward (WF) rodante.
        
        Para evitar data leakage, esta función recalcula los
        indicadores (usando RiskEngine) para CADA ventana.
        
        wf_config = {
            "train_years": 3,
            "test_years": 1,
            "start_date": "2018-01-01",
            "end_date": "2024-01-01"
        }
        """
        logging.info("Iniciando análisis Walk-Forward (WF)...")
        self.wf_results = []
        
        # 1. Generar las ventanas de fechas
        start = pd.to_datetime(wf_config["start_date"])
        end = pd.to_datetime(wf_config["end_date"])
        train_len = pd.DateOffset(years=wf_config["train_years"])
        test_len = pd.DateOffset(years=wf_config["test_years"])
        
        window_start = start
        
        while window_start + train_len + test_len <= end:
            # Definir fechas de la ventana
            train_start = window_start
            train_end = window_start + train_len - pd.DateOffset(days=1)
            test_start = window_start + train_len
            test_end = window_start + train_len + test_len - pd.DateOffset(days=1)
            
            window_label = f"{train_start.year}-{train_end.year} (Train) | {test_start.year} (Test)"
            logging.info(f"  Procesando Ventana WF: {window_label}")

            try:
                # 2. Slice de datos RAW (Anti-Leakage)
                df_window_raw = df_raw_data.loc[train_start:test_end].copy()
                
                if df_window_raw.empty:
                    logging.warning("    Ventana vacía, saltando.")
                    window_start += test_len
                    continue

                # 3. Recalcular indicadores SÓLO en esta ventana
                risk_eng = RiskEngine(self.profile)
                df_window_processed = risk_eng.compute(df_window_raw)
                
                # 4. Calcular train_frac para esta ventana
                # (simple_long_only_backtest se encarga del split)
                try:
                    # Encontrar el índice exacto del split
                    train_split_date = test_start - pd.DateOffset(days=1)
                    # Asegurarse de que el split_date está en el índice
                    while train_split_date not in df_window_processed.index and train_split_date > df_window_processed.index[0]:
                        train_split_date -= pd.DateOffset(days=1)
                        
                    if train_split_date <= df_window_processed.index[0]:
                         raise ValueError("No se encontró fecha de split válida")

                    train_rows = len(df_window_processed.loc[:train_split_date])
                    total_rows = len(df_window_processed)
                    train_frac = train_rows / total_rows
                except Exception as e:
                    logging.error(f"    Error calculando train_frac para ventana {window_label}: {e}")
                    logging.error(f"    Fechas: {train_split_date}, Inicio DF: {df_window_processed.index[0]}")
                    window_start += test_len
                    continue

                # 5. Ejecutar backtest SÓLO en esta ventana
                _, metrics = simple_long_only_backtest(
                    df_window_processed, 
                    train_frac=train_frac
                )
                
                # 6. Guardar métricas OOS (Out-of-Sample)
                self.wf_results.append({
                    "window": window_label,
                    "oos_cagr_strat": metrics.get("test_cagr_strategy"),
                    "oos_cagr_bh": metrics.get("test_cagr_buy_hold"),
                    "oos_sharpe": metrics.get("test_sharpe_ratio"),
                    "oos_profit_factor": metrics.get("test_trades_profit_factor"),
                    "oos_max_drawdown": metrics.get("test_max_drawdown_strategy"),
                    "oos_num_trades": metrics.get("test_trades_total_num"),
                    "strat_beats_bh": metrics.get("test_cagr_strategy", 0) > metrics.get("test_cagr_buy_hold", 0)
                })

            except Exception as e:
                logging.error(f"    FALLO Ventana WF {window_label}: {e}")
            
            # Mover la ventana
            window_start += test_len
            
        logging.info("Análisis Walk-Forward completado.")

    def print_wf_report(self):
        """
        Imprime el reporte agregado del análisis Walk-Forward.
        """
        if not self.wf_results:
            logging.warning("No hay resultados Walk-Forward para reportar.")
            return

        df_report = pd.DataFrame(self.wf_results).set_index("window")
        
        print("\n" + "="*80)
        print(f" Reporte Walk-Forward (OOS) para: {self.profile.name} ")
        print("="*80)
        
        print("\n--- Métricas por Ventana (Out-of-Sample) ---")
        print(df_report.to_string(float_format="%.3f"))
        
        print("\n--- Resumen Agregado (Out-of-Sample) ---")
        
        # Reemplazar infinitos (de profit factor) con NaN para cálculos
        df_report.replace([np.inf, -np.inf], np.nan, inplace=True)
        
        total_windows = len(df_report)
        win_windows = df_report["strat_beats_bh"].sum()
        win_pct = (win_windows / total_windows) * 100
        
        avg_sharpe = df_report["oos_sharpe"].mean()
        std_sharpe = df_report["oos_sharpe"].std()
        
        avg_profit_factor = df_report["oos_profit_factor"].mean()
        avg_max_drawdown = df_report["oos_max_drawdown"].mean()
        avg_num_trades = df_report["oos_num_trades"].mean()

        print(f"  Ventanas Totales:           {total_windows}")
        print(f"  Estrategia > B&H (OOS):     {win_windows} / {total_windows}  ({win_pct:.1f}%)")
        print(f"  Sharpe OOS (Media):         {avg_sharpe:.3f}")
        print(f"  Sharpe OOS (Std Dev):       {std_sharpe:.3f}")
        print(f"  Profit Factor OOS (Media):  {avg_profit_factor:.3f}")
        print(f"  Max Drawdown OOS (Media):   {avg_max_drawdown:.3f}")
        print(f"  Trades OOS (Media/Ventana): {avg_num_trades:.1f}")
        print("="*80)

    # --- FIN BLOQUE 1 ---
    # core/backtest_engine.py (Añadir a la clase BacktestEngine)

    def run_optimization(self, df_data: pd.DataFrame) -> StrategyProfile | None:
        """
        [NUEVO] Ejecuta una optimización simple de parámetros (ej. SMA/RSI) 
        sobre una ventana de datos y devuelve el StrategyProfile óptimo.
        
        Nota: Esta es una versión TOY. En producción, usaríamos un algoritmo genético.
        """
        
        logging.info(f"  > Optimizando parámetros para {self.profile.symbol}...")
        
        best_sharpe = -np.inf
        best_profile = None
        
        # 1. Definir el espacio de búsqueda (Ejemplo: ventanas SMA)
        # Optimizaremos solo las ventanas SMA. Los demás parámetros se mantienen fijos.
        sma_short_range = [7, 10, 14]
        sma_long_range = [20, 30, 40]

        # 2. Bucle de Optimización
        for s_short in sma_short_range:
            for s_long in sma_long_range:
                if s_short >= s_long:
                    continue # Debe ser short < long

                # 3. Crear un perfil temporal con los nuevos parámetros
                current_params = self.profile.get_params_dict().copy()
                current_params['sma_short'] = s_short
                current_params['sma_long'] = s_long
                
                # Crear un StrategyProfile temporal (necesitamos los métodos del profile)
                temp_profile = StrategyProfile(
                    name=self.profile.name,
                    coin_id=self.profile.coin_id,
                    symbol=self.profile.symbol,
                    sma_short=s_short,
                    sma_long=s_long,
                    timeframe=self.profile.timeframe,
                    source=self.profile.source,
                    rsi_window=current_params['rsi_window'],
                    atr_window=current_params['atr_window'],
                    trend_slope_window=current_params['trend_slope_window'],
                    vol_window=current_params['vol_window'],
                    vol_high_mult=current_params['vol_high_mult'],
                    vol_low_mult=current_params['vol_low_mult'],
                    mom_bull_thr=current_params['mom_bull_thr'],
                    mom_bear_thr=current_params['mom_bear_thr']
                )
                
                # 4. Procesar y Backtestear (In-Sample)
                try:
                    # Usamos RiskEngine para generar indicadores y señal para el perfil temporal
                    risk_eng = RiskEngine(temp_profile)
                    df_processed = risk_eng.compute(df_data.copy())
                    
                    # Ejecutar backtest SIN split (train_frac=None, todo es In-Sample)
                    _, metrics = simple_long_only_backtest(
                        df_processed, 
                        train_frac=None 
                    )
                    
                    # 5. Evaluar (Usamos Sharpe Ratio como criterio)
                    current_sharpe = metrics.get('sharpe_ratio', -np.inf)
                    
                    if not np.isnan(current_sharpe) and current_sharpe > best_sharpe:
                        best_sharpe = current_sharpe
                        best_profile = temp_profile

                except Exception as e:
                    # Fallo silencioso en optimización por data incompleta o error
                    pass 
        
        if best_profile:
            logging.info(f"  > Óptimo encontrado: Sharpe={best_sharpe:.3f}, SMA Short/Long: {best_profile.sma_short}/{best_profile.sma_long}")
        else:
            logging.warning(f"  > No se encontró perfil óptimo para {self.profile.symbol} en esta ventana.")

        return best_profile