# backtest.py
# Backtest long-only muy simple para estrategias de posición diaria

import math
import pandas as pd


def simple_long_only_backtest(
    df: pd.DataFrame,
    price_col: str = "close",
    position_col: str = "position",
    freq_per_year: int = 252,
):
    """
    Backtest simple:

    - Usa retornos de cierre a cierre: ret_t = close_t / close_{t-1} - 1
    - La posición que aplica en el retorno t es position_{t-1}
      (es decir, se asume que se decide al cierre y se ejecuta al siguiente bar).

    Devuelve:
    - df_res : DataFrame con columnas ['ret', 'strategy_ret', 'equity_curve', 'buy_hold_curve', 'drawdown']
    - metrics : dict con métricas básicas.
    """
    df = df.copy()

    # Retorno simple del activo
    df["ret"] = df[price_col].pct_change()

    # Retorno de la estrategia: usar posición del día anterior
    df["position_shifted"] = df[position_col].shift(1).fillna(0.0)
    df["strategy_ret"] = df["ret"] * df["position_shifted"]

    # Curva de capital de la estrategia y de buy&hold
    df["equity_curve"] = (1 + df["strategy_ret"]).cumprod()
    df["buy_hold_curve"] = df[price_col] / df[price_col].iloc[0]

    # Drawdown
    running_max = df["equity_curve"].cummax()
    df["drawdown"] = df["equity_curve"] / running_max - 1

    total_ret = df["equity_curve"].iloc[-1] - 1
    bh_ret = df["buy_hold_curve"].iloc[-1] - 1

    # Volatilidad y Sharpe (aprox anualizado)
    strat_ret = df["strategy_ret"].dropna()
    if len(strat_ret) > 1:
        vol_annual = strat_ret.std() * math.sqrt(freq_per_year)
        mean_annual = strat_ret.mean() * freq_per_year
        sharpe = mean_annual / vol_annual if vol_annual != 0 else float("nan")
    else:
        vol_annual = float("nan")
        mean_annual = float("nan")
        sharpe = float("nan")

    max_dd = df["drawdown"].min()

    metrics = {
        "total_return_strategy": float(total_ret),
        "total_return_buy_hold": float(bh_ret),
        "annual_return_estimate": float(mean_annual),
        "annual_volatility": float(vol_annual),
        "sharpe_ratio": float(sharpe),
        "max_drawdown": float(max_dd),
    }

    return df, metrics
