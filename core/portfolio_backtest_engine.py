# portfolio_backtest_engine.py
# v1.3.0 - Added risk fields: equity_curve, returns, drawdown_series, max_drawdown
# v1.2.0 - Añadido run_sub_period para Stress Testing (Bloque 4: Tarea B)

import pandas as pd
import numpy as np
import logging
import statsmodels.api as sm

# Importamos la función de cálculo de métricas del backtest original
from .backtest import _compute_metrics_from_logrets
# Importamos la función de reporte
from utils.reporting import print_backtest_metrics


# --- HELPER DE REGRESIÓN OLS (MODIFICADA PARA MULTI-FACTOR) ---
def _compute_ols_metrics(
    portfolio_returns: pd.Series, 
    factor_returns_dict: dict[str, pd.Series]
) -> dict:
    """
    Calcula Alpha y Betas usando regresión OLS multi-factorial.
    """
    
    # 1. Alineación de Datos
    factor_df = pd.DataFrame(factor_returns_dict)
    df = pd.concat([portfolio_returns.rename('PORTFOLIO_RET'), factor_df], axis=1).dropna()
    
    if df.empty or len(df) < 5: 
        return {"annual_alpha": np.nan, "beta": np.nan, "factor_betas": {}, "r_squared_adj": np.nan}

    # Definir variables
    y = df['PORTFOLIO_RET']
    X = df.drop(columns=['PORTFOLIO_RET'])
    
    # 2. Correr OLS
    X = sm.add_constant(X)

    try:
        model = sm.OLS(y, X).fit()
    except ValueError as e:
        logging.error(f"Error al calcular OLS: {e}")
        return {"annual_alpha": np.nan, "beta": np.nan, "factor_betas": {}, "r_squared_adj": np.nan}

    # 3. Extracción de Resultados
    annual_alpha = model.params['const'] * 365 
    factor_betas = model.params.drop('const').to_dict()
    beta = factor_betas.get('MKT_BTC', np.nan)
    
    result = {
        "annual_alpha": annual_alpha,
        "beta": beta, 
        "factor_betas": factor_betas, 
        "r_squared_adj": model.rsquared_adj,
    }
    
    return result


class PortfolioBacktestEngine:
    """
    Motor para ejecutar backtests a nivel de portafolio multi-activo.
    
    ... [Documentación de Lag y Costes] ...
    """
    
    def __init__(self, target_weights: dict):
        self.target_weights = target_weights
        self.asset_labels = list(target_weights.keys())
        self.df_portfolio = pd.DataFrame()
        self.metrics = {}
        
        # Risk fields (populated after run())
        self.equity_curve: pd.Series = pd.Series(dtype=float)
        self.returns: pd.Series = pd.Series(dtype=float)
        self.drawdown_series: pd.Series = pd.Series(dtype=float)
        self.max_drawdown: float = 0.0
        
        if sum(target_weights.values()) > 1.00001:
            logging.error("La suma de target_weights excede 1.0. Corrija los pesos.")
            raise ValueError("Target weights must sum to 1.0.")
            
        logging.info(f"PortfolioEngine inicializado para {self.asset_labels}")

    def run(self, processed_data_dict: dict):
        """
        Ejecuta el backtest de portafolio con costes de transacción (Full Run).
        """
        
        # Coste de transacción fijo (0.075% por lado). Confirmado en Test Toy.
        transaction_cost = 0.00075 

        # 1. Alineación y Preparación de Datos
        multi_asset_data = {}
        
        for label, df_asset in processed_data_dict.items():
            multi_asset_data[f'{label}_pos'] = df_asset['position']
            multi_asset_data[f'{label}_ret'] = df_asset['log_return'] 
        
        df_master = pd.DataFrame(multi_asset_data).sort_index().dropna(how='all')
        # Advertencia: df_master = df_master.fillna(method='ffill') ya no debería dar warning
        df_master = df_master.ffill() 
        df_master = df_master.fillna(0.0)

        # 2. Aplicación de la Lógica de Rebalanceo (Omitido por brevedad, es tu lógica existente)
        adjusted_weights = pd.DataFrame(index=df_master.index)
        for label, target_w in self.target_weights.items():
            pos_col = f'{label}_pos'
            adj_w = df_master[pos_col] * target_w
            adjusted_weights[f'{label}_adj_w'] = adj_w
        df_master['cash_adj_w'] = 1.0 - adjusted_weights.fillna(0.0).sum(axis=1)

        # 3. Cálculo de Retornos del Portafolio y Costes (Omitido por brevedad, es tu lógica existente)
        portfolio_log_ret = pd.Series(0.0, index=df_master.index)
        portfolio_costs = pd.Series(0.0, index=df_master.index)

        for label in self.asset_labels:
            ret_col = f'{label}_ret'
            adj_w_col = f'{label}_adj_w'
            weight_t_minus_1 = adjusted_weights[adj_w_col].shift(1).fillna(0.0)
            contribution = df_master[ret_col] * weight_t_minus_1
            portfolio_log_ret += contribution

            weight_change = (adjusted_weights[adj_w_col] - weight_t_minus_1).abs()
            daily_cost = weight_change * transaction_cost
            portfolio_costs += daily_cost.fillna(0.0)

        portfolio_log_ret_with_costs = portfolio_log_ret - portfolio_costs
        portfolio_log_ret_with_costs = portfolio_log_ret_with_costs.dropna()
        
        df_master['portfolio_log_ret'] = portfolio_log_ret_with_costs
        df_master['portfolio_equity'] = np.exp(portfolio_log_ret_with_costs.cumsum())
        
        self.df_portfolio = df_master
        
        # Store risk fields
        self.equity_curve = df_master['portfolio_equity'].dropna()
        self.returns = df_master['portfolio_log_ret'].dropna()
        self.drawdown_series = (self.equity_curve / self.equity_curve.cummax()) - 1
        self.max_drawdown = float(self.drawdown_series.min())
        
        # 4. Cálculo de Métricas OLS Multi-Factorial (Omitido por brevedad, es tu lógica existente)
        factor_returns = {}
        main_asset_label = self.asset_labels[0]
        factor_returns['MKT_BTC'] = processed_data_dict[main_asset_label]['log_return'].dropna() 
        
        aligned_factor_returns = {}
        for factor_name, returns_series in factor_returns.items():
            aligned_factor_returns[factor_name] = returns_series.reindex(
                portfolio_log_ret_with_costs.index
            ).fillna(0.0)
            
        ols_metrics = _compute_ols_metrics(
            portfolio_log_ret_with_costs, 
            aligned_factor_returns
        )
        
        # 5. Cálculo de Métricas Finales y Reporte (Omitido por brevedad)
        self.metrics = _compute_metrics_from_logrets(
            strategy_log_ret=df_master['portfolio_log_ret'].dropna(),
            equity_curve=df_master['portfolio_equity'].dropna(),
        )
        
        self.metrics.update(ols_metrics)
        self.metrics.pop('total_return_buy_hold', None)
        self.metrics.pop('cagr_buy_hold', None)
        self.metrics.pop('max_drawdown_buy_hold', None)
        
        # Add risk fields to metrics for convenience
        self.metrics["equity_curve"] = self.equity_curve
        self.metrics["returns"] = self.returns
        self.metrics["drawdown_series"] = self.drawdown_series
        self.metrics["max_drawdown"] = self.max_drawdown

    # --- MÉTODO MODIFICADO PARA STRESS TESTING ---
    def run_sub_period(self, processed_data_dict: dict, start_date: str, end_date: str) -> dict:
        """
        Recorta el diccionario de datos procesados al subperíodo y ejecuta el backtest.
        NOTA: Asume que los target_weights del engine ya han sido ajustados para este período.
        """
        logging.info(f"Corriendo sub-período: {start_date} a {end_date}")

        sub_period_data = {}
        
        # 1. Recortar los datos de CADA ACTIVO definido en self.asset_labels
        for label in self.asset_labels: # <--- Usamos self.asset_labels, que ya fue filtrado por el orquestador
            df_asset = processed_data_dict[label]
            df_sub = df_asset.loc[start_date:end_date].copy()
            
            # NOTA: Ya no hacemos la validación df_sub.empty, 
            # ya que el orquestador garantiza que solo se usa data válida para el engine.
            
            sub_period_data[label] = df_sub

        # El resto de la función run_sub_period se mantiene igual:
        # 2. Ejecutar el motor (sub_eng.run(sub_period_data))
        # 3. Extracción y Cálculo de Métricas de Estrés
        
        # El código subsiguiente debe continuar con la lógica de ejecución del backtest (sub_eng.run(...))
        # ... [El código se mantiene igual a partir de aquí] ...
        
        # Ejecutar el motor con los datos recortados
        sub_eng = PortfolioBacktestEngine(target_weights=self.target_weights)
        
        try:
            sub_eng.run(sub_period_data)
        except Exception as e:
            logging.error(f"Error al correr sub-período: {e}")
            return {}
                      
        # 3. Extracción y Calculo de Métricas de Estrés
        metrics = sub_eng.metrics
        metrics['stress_period'] = f"{start_date[:4]}-{end_date[:4]}" 
        
        # Max Drawdown específico del período de Stress
        max_dd = sub_eng.metrics.get('max_drawdown_strategy', np.nan)
        metrics['max_drawdown_stress'] = max_dd
        
        # Cálculo de VaR (Percentil 5%) y CVaR
        returns = sub_eng.df_portfolio['portfolio_log_ret'].dropna()
        if not returns.empty:
            simple_returns = np.exp(returns) - 1
            # VaR 95% (el 5% peor)
            var_95 = simple_returns.quantile(0.05) 
            metrics['VaR_95_daily'] = var_95
            
            # CVaR (Expected Shortfall)
            cvar_95 = simple_returns[simple_returns <= var_95].mean()
            metrics['CVaR_95_daily'] = cvar_95
        
        # Add risk fields from sub_eng
        metrics["equity_curve"] = sub_eng.equity_curve
        metrics["returns"] = sub_eng.returns
        metrics["drawdown_series"] = sub_eng.drawdown_series
        metrics["max_drawdown"] = sub_eng.max_drawdown
        
        return metrics
    # --- FIN run_sub_period ---


    def print_report(self):
        """ Imprime el reporte de portafolio usando la lógica de reporting.py. """
        if not self.metrics:
            logging.warning("No hay métricas para reportar (Portafolio).")
            return
        
        print("\n" + "="*80)
        print(" Reporte Portfolio Backtest (Multi-Activo con Risk Overlay) ")
        print("="*80)
        print(f" Portafolio: {self.asset_labels}")
        print_backtest_metrics(self.metrics)
        print("="*80)

    def get_results(self) -> dict:
        """
        Returns all backtest results including risk fields.
        
        Returns
        -------
        dict with keys:
            - df_portfolio: Full DataFrame with all columns
            - metrics: Performance metrics dict
            - equity_curve: pd.Series of portfolio equity over time
            - returns: pd.Series of log returns
            - drawdown_series: pd.Series of drawdown values
            - max_drawdown: float, maximum drawdown value
        """
        return {
            "df_portfolio": self.df_portfolio,
            "metrics": self.metrics,
            "equity_curve": self.equity_curve,
            "returns": self.returns,
            "drawdown_series": self.drawdown_series,
            "max_drawdown": self.max_drawdown,
        }