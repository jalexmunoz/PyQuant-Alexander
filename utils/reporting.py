# reporting.py
# v1.2.0 - Añadido soporte para Betas Multi-Factoriales y R^2 Ajustado

import pandas as pd
import numpy as np


def _max_drawdown(equity_curve: pd.Series | None) -> float | None:
    """Calcula el máximo drawdown."""
    if equity_curve is None or equity_curve.empty:
        return np.nan
    cumulative_max = equity_curve.cummax()
    drawdown = (equity_curve / cumulative_max) - 1.0
    return drawdown.min()


def print_backtest_metrics(metrics: dict):
    """
    Imprime un resumen formateado del diccionario de métricas del backtest,
    incluyendo distribución y retornos anuales. (Estilo 'Tear Sheet Lite')
    """
    
    # 1. Resumen General de Rendimiento y Riesgo
    print("\n\n" + "="*80)
    print(" === RESUMEN TACTICO (Full Sample) ===")
    print("="*80)
    
    # Definir las métricas clave y su formato
    perf_keys = [
        ("total_return_strategy", "Retorno Total", "{:,.2%}"),
        # ("total_return_buy_hold", "Retorno B&H", "{:,.2%}"), # Eliminado, se asume portafolio es la estrategia
        ("cagr_strategy", "CAGR Estrategia", "{:,.2%}"),
        # ("cagr_buy_hold", "CAGR B&H", "{:,.2%}"), # Eliminado
        
        ("sharpe_ratio", "Sharpe Ratio", "{:,.3f}"),
        ("sortino_ratio", "Sortino Ratio", "{:,.3f}"),
        ("calmar_ratio", "Calmar Ratio", "{:,.3f}"),
        
        ("annual_alpha", "Alpha Anual (vs MKT_BTC)", "{:,.2%}"),
        ("beta", "Beta (vs MKT_BTC)", "{:,.3f}"),
        
        ("annual_volatility_strategy", "Volatilidad Anual", "{:,.2%}"),
        ("max_drawdown_strategy", "Max Drawdown Estrategia", "{:,.2%}"),
        # ("max_drawdown_buy_hold", "Max Drawdown B&H", "{:,.2%}"), # Eliminado
    ]

    for key, label, fmt in perf_keys:
        if key in metrics and not pd.isna(metrics[key]):
            val = metrics[key]
            # Formato especial para retornos extremadamente grandes
            if "%" in fmt and isinstance(val, (float, int)) and val > 1000:
                 print(f"{label:30s}: {val:,.2f}x") 
            else:
                 print(f"{label:30s}: {fmt.format(val)}")

    # <<< INICIO: OLS Multi-Factorial Avanzado >>>
    # 1.5. Reporte OLS Avanzado
    if "factor_betas" in metrics and metrics["factor_betas"]:
        print("\n--- OLS Multi-Factorial ---")
        
        # Mostrar R-cuadrado ajustado
        if "r_squared_adj" in metrics and not pd.isna(metrics["r_squared_adj"]):
            print(f"R-cuadrado Ajustado: {metrics['r_squared_adj']:,.3f}")

        print("Betas por Factor:")
        for factor, beta_val in metrics["factor_betas"].items():
            print(f"  > Beta ({factor}): {beta_val:,.3f}")
    # <<< FIN: OLS Multi-Factorial Avanzado >>>

    # 2. Análisis de Trades
    print("\n--- Análisis de Trades (Full Sample) ---")
    trade_keys = [
        ("trades_total_num", "Total Trades", "{:,.0f}"),
        ("trades_pct_profitable", "% Ganadoras", "{:,.2%}"),
        ("trades_avg_return", "Retorno Promedio", "{:,.2%}"),
        ("trades_profit_factor", "Profit Factor", "{:,.2f}"),
        ("trades_max_win", "Ganancia Máx.", "{:,.2%}"),
        ("trades_max_loss", "Pérdida Máx.", "{:,.2%}"),
    ]
    
    for key, label, fmt in trade_keys:
        if key in metrics and not pd.isna(metrics[key]):
            val = metrics[key]
            if isinstance(val, (float, int)) and np.isinf(val):
                 print(f"{label:30s}: {'INF' if val > 0 else '-INF'}")
            else:
                 print(f"{label:30s}: {fmt.format(val)}")

    # 3. Distribución de Retornos
    print("\n--- Distribución de Retornos ---")
    dist_keys = [
        ("annual_skew", "Skew Anualizado", "{:,.3f}"),
        ("annual_kurtosis", "Kurtosis Anualizada", "{:,.3f}"),
    ]
    
    for key, label, fmt in dist_keys:
        if key in metrics and not pd.isna(metrics[key]):
            print(f"{label:30s}: {fmt.format(metrics[key])}")
    
    # 4. Retornos Anuales
    if "yearly_returns" in metrics and metrics["yearly_returns"]:
        print("\n--- Retornos Por Año ---")
        yearly_df = pd.Series(metrics["yearly_returns"], name='Return').to_frame()
        yearly_df['Return'] = yearly_df['Return'].apply(lambda x: f"{x:,.2%}")
        print(yearly_df.to_string())

    # 5. Métricas Train/Test
    train_metrics = {k: v for k, v in metrics.items() if k.startswith("train_")}
    test_metrics = {k: v for k, v in metrics.items() if k.startswith("test_")}

    if train_metrics or test_metrics:
        print("\n" + "="*80)
        print(" === ANÁLISIS OUT-OF-SAMPLE (OOS) y TRAIN ===")
        print("="*80)

    def print_split(split_metrics, label):
        if split_metrics:
            print(f"\n-- {label} --")
            for k, v in split_metrics.items():
                if isinstance(v, (float, int)) and not pd.isna(v):
                    # Usar .pop() para las métricas que no son de OLS y están en el reporte simple
                    clean_k = k.replace("train_", "").replace("test_", "")
                    if clean_k not in [pk[0] for pk in perf_keys]: # Evita imprimir las OLS simples
                         print(f"{k:30s}: {v:,.4f}")
    
    print_split(train_metrics, "Métricas TRAIN (In-Sample)")
    print_split(test_metrics, "Métricas TEST (Out-of-Sample)")
