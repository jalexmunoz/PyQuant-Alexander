# trades.py
# Funciones para analizar trades individuales de un backtest

import pandas as pd
import numpy as np


def compute_trade_analysis(
    df: pd.DataFrame,
    position_col: str = "position",
    log_ret_col: str = "strategy_log_ret",
) -> dict:
    """
    Calcula un desglose estadístico de trades individuales.

    Un "trade" se define como un bloque contiguo donde la posición es 1.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame del backtest, debe tener position_col y log_ret_col.
    position_col : str
        Nombre de la columna de posición (0 o 1).
    log_ret_col : str
        Nombre de la columna de retornos logarítmicos de la estrategia.

    Returns
    -------
    dict
        Un diccionario con estadísticas de trades.
    """
    df = df.copy()

    # Identificar inicios y fines de trades
    # .diff() != 0 detecta cualquier cambio (0->1 o 1->0)
    # trade_id es un contador que incrementa solo en 0->1
    is_in_trade = df[position_col].astype(float) > 0
    start_trade = is_in_trade & (is_in_trade.diff() == 1)
    end_trade = ~is_in_trade & (is_in_trade.diff() == -1)

    # Asignar un ID a cada trade (bloque de posiciones en 1)
    df["trade_id"] = start_trade.cumsum()
    
    # Solo nos interesan los retornos mientras estábamos en un trade (ID > 0)
    # y antes de que el trade se cierre
    trades_df = df[df["trade_id"] > 0].copy()
    
    # Agrupar por ID de trade y sumar los log-returns
    trade_log_rets = trades_df.groupby("trade_id")[log_ret_col].sum()

    # Convertir log-returns a retornos simples (ej. 0.05 = 5%)
    trade_simple_rets = np.exp(trade_log_rets) - 1.0

    # Si no hubo trades, retornar vacío
    if trade_simple_rets.empty:
        return {
            "trades_total_num": 0,
            "trades_pct_profitable": np.nan,
            "trades_avg_return": np.nan,
            "trades_avg_win": np.nan,
            "trades_avg_loss": np.nan,
            "trades_profit_factor": np.nan,
            "trades_max_win": np.nan,
            "trades_max_loss": np.nan,
        }

    # Estadísticas
    total_trades = len(trade_simple_rets)
    winners = trade_simple_rets[trade_simple_rets > 0]
    losers = trade_simple_rets[trade_simple_rets <= 0]

    pct_profitable = (len(winners) / total_trades) if total_trades > 0 else 0.0
    
    avg_win = winners.mean() if not winners.empty else 0.0
    avg_loss = losers.mean() if not losers.empty else 0.0
    
    gross_profit = winners.sum()
    gross_loss = abs(losers.sum())
    
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        # Si no hay pérdidas, el profit factor es infinito
        profit_factor = np.inf if gross_profit > 0 else np.nan

    return {
        "trades_total_num": total_trades,
        "trades_pct_profitable": pct_profitable,
        "trades_avg_return": trade_simple_rets.mean(),
        "trades_avg_win": avg_win,
        "trades_avg_loss": avg_loss,
        "trades_profit_factor": profit_factor,
        "trades_max_win": winners.max() if not winners.empty else 0.0,
        "trades_max_loss": losers.min() if not losers.empty else 0.0,
    }