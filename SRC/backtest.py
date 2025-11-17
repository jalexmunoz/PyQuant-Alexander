# backtest.py
# v0.6.0 - Motor de backtesting simple
#
# Historial:
# v0.6.0 - Añade Sortino Ratio y llamada a análisis de trades
# v0.5.x - (Versión inicial)

import math
import numpy as np
import pandas as pd
from trades import compute_trade_analysis

# Reemplaza tu función simple_long_only_backtest con esta:

def simple_long_only_backtest(
    df: pd.DataFrame,
    price_col: str = "close",
    position_col: str = "position",
    periods_per_year: int = 365,
    train_frac: float | None = 0.7,  # <<< ESTA LÍNEA ES LA CLAVE
) -> tuple[pd.DataFrame, dict]:
    """
    Backtest long-only simple usando log-returns como estándar.
    ... (el resto de tu docstring) ...
    """
    df = df.copy()

    # 1) log-returns estándar
    df["log_return"] = np.log(df[price_col] / df[price_col].shift(1))

    # quitamos el primer NaN de log_return
    df = df.dropna(subset=["log_return"])

    # 2) estrategia: posición del día anterior * log_return del día actual
    position = df[position_col].shift(1).fillna(0.0)

    df["strategy_log_ret"] = df["log_return"] * position
    df["buy_hold_log_ret"] = df["log_return"]

    # 3) curvas de equity (exp de la suma acumulada de log-returns)
    df["equity_curve"] = np.exp(df["strategy_log_ret"].cumsum())
    df["buy_hold_curve"] = np.exp(df["buy_hold_log_ret"].cumsum())

    # 4) métricas full sample
    metrics = _compute_metrics_from_logrets(
        strategy_log_ret=df["strategy_log_ret"],
        equity_curve=df["equity_curve"],
        buy_hold_curve=df["buy_hold_curve"],
        periods_per_year=periods_per_year,
    )

    # Compatibilidad con scripts antiguos (nombres previos)
    metrics["annual_return_estimate"] = metrics["cagr_strategy"]
    metrics["annual_volatility"] = metrics["annual_volatility_strategy"]
    metrics["max_drawdown"] = metrics["max_drawdown_strategy"]

    # 5) Split train/test opcional
    if train_frac is not None and 0 < train_frac < 1:
        split_idx = int(len(df) * train_frac)
        df_train = df.iloc[:split_idx]
        df_test = df.iloc[split_idx:]

        m_train = _compute_metrics_from_logrets(
            strategy_log_ret=df_train["strategy_log_ret"],
            equity_curve=df_train["equity_curve"],
            buy_hold_curve=df_train["buy_hold_curve"],
            periods_per_year=periods_per_year,
        )
        m_test = _compute_metrics_from_logrets(
            strategy_log_ret=df_test["strategy_log_ret"],
            equity_curve=df_test["equity_curve"],
            buy_hold_curve=df_test["buy_hold_curve"],
            periods_per_year=periods_per_year,
        )

        metrics.update({f"train_{k}": v for k, v in m_train.items()})
        metrics.update({f"test_{k}": v for k, v in m_test.items()})

    # 6) Análisis de trades (Full sample)
    trade_metrics = compute_trade_analysis(
        df=df,
        position_col=position_col,
        log_ret_col="strategy_log_ret"
    )
    metrics.update(trade_metrics)

    # Análisis de trades (Train/Test)
    if train_frac is not None and 0 < train_frac < 1:
        trade_metrics_train = compute_trade_analysis(
            df=df_train,
            position_col=position_col,
            log_ret_col="strategy_log_ret"
        )
        metrics.update({f"train_{k}": v for k, v in trade_metrics_train.items()})
        
        trade_metrics_test = compute_trade_analysis(
            df=df_test,
            position_col=position_col,
            log_ret_col="strategy_log_ret"
        )
        metrics.update({f"test_{k}": v for k, v in trade_metrics_test.items()})

    return df, metrics

def _max_drawdown(equity_curve: pd.Series) -> float:
    """
    Calcula el máximo drawdown de una curva de equity.
    Retorna un número negativo (ej. -0.25 = -25%) o NaN si no hay datos.
    """
    eq = equity_curve.dropna()
    if eq.empty:
        return np.nan

    roll_max = eq.cummax()
    drawdown = eq / roll_max - 1.0
    return float(drawdown.min())


def _compute_metrics_from_logrets(
    strategy_log_ret: pd.Series,
    equity_curve: pd.Series,
    buy_hold_curve: pd.Series | None = None,
    periods_per_year: int = 365,
) -> dict:
    """
    Calcula métricas principales a partir de log-returns y la curva de equity.

    Retorna un dict con:
      - total_return_strategy / buy_hold
      - cagr_strategy / buy_hold
      - max_drawdown_strategy / buy_hold
      - annual_volatility_strategy
      - sharpe_ratio
      - calmar_ratio
      - sortino_ratio  <-- AÑADIDO
    """
    strategy_log_ret = strategy_log_ret.dropna()
    n = len(strategy_log_ret)

    if n == 0:
        return {
            "total_return_strategy": np.nan,
            "total_return_buy_hold": np.nan,
            "cagr_strategy": np.nan,
            "cagr_buy_hold": np.nan,
            "max_drawdown_strategy": np.nan,
            "max_drawdown_buy_hold": np.nan,
            "annual_volatility_strategy": np.nan,
            "sharpe_ratio": np.nan,
            "calmar_ratio": np.nan,
            "sortino_ratio": np.nan, # <<< NUEVO
        }

    eq = equity_curve.dropna()
    if eq.empty:
        final_eq = np.nan
    else:
        final_eq = float(eq.iloc[-1])

    final_bh = np.nan
    if buy_hold_curve is not None:
        bh = buy_hold_curve.dropna()
        if not bh.empty:
            final_bh = float(bh.iloc[-1])

    years = n / periods_per_year if periods_per_year > 0 else np.nan

    if years and years > 0 and final_eq > 0:
        cagr_strategy = final_eq ** (1.0 / years) - 1.0
    else:
        cagr_strategy = np.nan

    if years and years > 0 and not np.isnan(final_bh) and final_bh > 0:
        cagr_buy_hold = final_bh ** (1.0 / years) - 1.0
    else:
        cagr_buy_hold = np.nan

    max_dd_strategy = _max_drawdown(equity_curve)
    max_dd_buy = _max_drawdown(buy_hold_curve) if buy_hold_curve is not None else np.nan

    # Volatilidad & Sharpe (sobre log-returns)
    daily_std = float(strategy_log_ret.std(ddof=0))
    daily_mean = float(strategy_log_ret.mean())
    if daily_std > 0:
        annual_vol = daily_std * np.sqrt(periods_per_year)
        sharpe = np.sqrt(periods_per_year) * (daily_mean / daily_std)
    else:
        annual_vol = np.nan
        sharpe = np.nan

    # Calmar
    if max_dd_strategy is not None and max_dd_strategy < 0 and not np.isnan(cagr_strategy):
        calmar = cagr_strategy / abs(max_dd_strategy)
    else:
        calmar = np.nan

    # <<< INICIO BLOQUE NUEVO (Sortino) >>>
    # Calcular Downside Deviation (volatilidad de retornos negativos)
    downside_returns = strategy_log_ret.where(strategy_log_ret < 0, 0.0)
    downside_std = float(downside_returns.std(ddof=0))

    if downside_std > 0:
        sortino = np.sqrt(periods_per_year) * (daily_mean / downside_std)
    else:
        # Si no hay retornos negativos, Sortino es infinito (o NaN)
        sortino = np.inf if daily_mean > 0 else np.nan
    # <<< FIN BLOQUE NUEVO (Sortino) >>>


    return {
        "total_return_strategy": final_eq - 1.0 if not np.isnan(final_eq) else np.nan,
        "total_return_buy_hold": final_bh - 1.0 if not np.isnan(final_bh) else np.nan,
        "cagr_strategy": cagr_strategy,
        "cagr_buy_hold": cagr_buy_hold,
        "max_drawdown_strategy": max_dd_strategy,
        "max_drawdown_buy_hold": max_dd_buy,
        "annual_volatility_strategy": annual_vol,
        "sharpe_ratio": sharpe,
        "calmar_ratio": calmar,
        "sortino_ratio": sortino, # <<< NUEVO
    }