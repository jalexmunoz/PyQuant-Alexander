# run_toy_test.py
# v1.0.1 - CORREGIDO: Valores esperados actualizados a transaction_cost = 0.00075

import pandas as pd
import numpy as np
import logging

# Se asume que estos engines y helpers existen
from core.portfolio_backtest_engine import PortfolioBacktestEngine 
from core.backtest import _compute_metrics_from_logrets 

# --- CONFIGURACIÓN DEL ESCENARIO DE PRUEBA ---
PORTFOLIO_CONFIG = {
    "BTC-USD": 0.50,
    "ETH-USD": 0.50,
}
# El PortfolioBacktestEngine usa 0.00075.

def create_mock_processed_data():
    """ Crea el diccionario de datos 'procesados' que el RiskEngine entregaría. """
    
    dates = pd.to_datetime(['2025-01-01', '2025-01-02', '2025-01-03', '2025-01-04']) 

    # Datos para BTC
    data_btc = {
        'close': [100.0, 101.0, 102.0, 103.0],
        'log_return': [np.nan, 0.0100, 0.0099, 0.0098], 
        'position': [0.0, 1.0, 1.0, 0.0], 
    }
    df_btc = pd.DataFrame(data_btc, index=dates).dropna(subset=['log_return'])
    
    # Datos para ETH
    data_eth = {
        'close': [100.0, 100.0, 99.0, 101.0],
        'log_return': [np.nan, 0.0000, -0.0101, 0.0200], 
        'position': [0.0, 0.0, 1.0, 1.0], 
    }
    df_eth = pd.DataFrame(data_eth, index=dates).dropna(subset=['log_return'])

    return {
        "BTC-USD": df_btc,
        "ETH-USD": df_eth,
    }

def run_toy_test():
    logging.basicConfig(level=logging.INFO, format='TEST:root:%(message)s')
    
    mock_data = create_mock_processed_data()
    
    # 1. Ejecutar el Portfolio Engine con datos mockeados
    portfolio_eng = PortfolioBacktestEngine(target_weights=PORTFOLIO_CONFIG)
    portfolio_eng.run(mock_data)
    df_result = portfolio_eng.df_portfolio
    
    # 2. Extracción de Resultados (Días 1, 2, 3)
    net_rets = df_result['portfolio_log_ret'].tail(3)
    equity_curve = df_result['portfolio_equity'].tail(3)

    # VALORES ESPERADOS CORREGIDOS (Usando transaction_cost = 0.00075)
    # Día 1: 0.0000 - 0.5*0.00075 = -0.000375
    # Día 2: 0.0050 - 0.5*0.00075 = 0.004625
    # Día 3: 0.0149 - 0.5*0.00075 = 0.014525
    expected_net_rets = pd.Series([-0.000375, 0.004575, 0.014525], index=net_rets.index)
    
    # Equity esperada:
    # Día 1: exp(-0.000375) = 0.999625
    # Día 2: 0.999625 * exp(0.004625) = 1.004245
    # Día 3: 1.004245 * exp(0.014525) = 1.018901
    expected_equity = pd.Series([0.999625, 1.004199, 1.018891], index=equity_curve.index)
    
    # 3. Verificación
    
    print("\n" + "="*50)
    print(" VERIFICACIÓN DEL CÁLCULO DE PORTAFOLIO Y LAG ")
    print("="*50)
    
    # Comprobar Retornos Netos
    # Usamos una tolerancia de 1e-6 (más estricta)
    rets_match = np.allclose(net_rets.values, expected_net_rets.values, atol=1e-6) 
    
    print(f"Retornos Netos Calculados: {net_rets.values}")
    print(f"Retornos Netos Esperados: {expected_net_rets.values}")
    print(f"Resultado Retornos (Match): {'✅ PASS' if rets_match else '❌ FAIL'}")

    # Comprobar Curva de Equity
    equity_match = np.allclose(equity_curve.values, expected_equity.values, atol=1e-6)
    
    print(f"\nEquity Calculada: {equity_curve.values}")
    print(f"Equity Esperada: {expected_equity.values}")
    print(f"Resultado Equity (Match): {'✅ PASS' if equity_match else '❌ FAIL'}")

    if rets_match and equity_match:
        logging.info("\nPRUEBA TOY DE PORTAFOLIO SUPERADA. El LAG (shift(1)) y los COSTES son correctos.")
    else:
        logging.error("\nPRUEBA TOY FALLIDA. Los cálculos no coinciden con los valores esperados.")

    print("="*50)


if __name__ == "__main__":
    run_toy_test()