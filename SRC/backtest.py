# backtest.py
# Backtest long-only muy simple para estrategias de posición diaria

import math
import numpy as np
import pandas as pd


def simple_long_only_backtest(
    df: pd.DataFrame,
    price_col: str = "close",
    position_col: str = "position",
    periods_per_year: int = 365,
    train_frac: float | None = 0.7,
) -> tuple[pd.DataFrame, dict]:
    """
    Backtest long-only simple usando log-returns como estándar.

    - df: DataFrame con columnas de precio y posición.
    - price_col: columna de precio (por defecto 'close').
    - position_col: columna con la señal de posición (0/1).
    - periods_per_year: 365 para cripto diario.
    - train_frac: fracción opcional para separar train/test por tiempo (ej. 0.7).

    Retorna:
      - df con columnas añadidas (log_return, strategy_log_ret, equity_curve, etc.)
      - metrics: dict con métricas full + (opcional) train_*/test_*
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
    }
