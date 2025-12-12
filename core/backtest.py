# backtest.py
# v0.7.0 - CORREGIDO: Eliminación de código muerto en _compute_metrics_from_logrets (Deuda Técnica)

import math
import numpy as np
import pandas as pd
# from trades import compute_trade_analysis # Asumimos que esta importación existe si se usa

# Reemplaza tu función simple_long_only_backtest con la tuya existente.
# Por simplicidad, solo incluimos las helpers y nos enfocamos en la limpieza.

def simple_long_only_backtest(
    df: pd.DataFrame,
    price_col: str = "close",
    position_col: str = "position",
    periods_per_year: int = 365,
    train_frac: float | None = 0.7,
    # transaction_cost: float = 0.0, # Asumimos que la gestión de costes está en PortfolioEngine
) -> tuple[pd.DataFrame, dict]:
    """
    Backtest long-only simple.
    (El cuerpo de esta función se mantiene sin cambios, sólo usa las helpers)
    """
    df = df.copy()

    # 1) Retornos y Posición
    df["log_return"] = np.log(df[price_col] / df[price_col].shift(1))
    df = df.dropna(subset=["log_return"])

    # La posición de hoy se aplica al retorno de MAÑANA (shift(1))
    position = df[position_col].shift(1).fillna(0.0)

    # 2) Retornos de la Estrategia (La línea pura)
    df["strategy_log_ret"] = df["log_return"] * position
    df["buy_hold_log_ret"] = df["log_return"]

    # 3) Curvas de Equity
    df["equity_curve"] = np.exp(df["strategy_log_ret"].cumsum())
    df["buy_hold_curve"] = np.exp(df["buy_hold_log_ret"].cumsum())

    # 4) Métricas y Split (Llama a la helper limpia)

    # Nota: Si compute_trade_analysis existe, debe ser llamada aquí.
    # trade_metrics = compute_trade_analysis(df['strategy_log_ret'])

    metrics = _compute_metrics_from_logrets(
        strategy_log_ret=df["strategy_log_ret"].dropna(),
        equity_curve=df["equity_curve"].dropna(),
        buy_hold_curve=df["buy_hold_curve"].dropna(),
        periods_per_year=periods_per_year,
    )
    
    # Asignaciones de compatibilidad
    metrics["annual_return_estimate"] = metrics["cagr_strategy"]
    metrics["annual_volatility"] = metrics["annual_volatility_strategy"]
    metrics["max_drawdown"] = metrics["max_drawdown_strategy"]

    # Añade trade_metrics aquí si es necesario: metrics.update(trade_metrics)

    # Split Train/Test (Se mantiene la lógica existente)
    if train_frac is not None and 0 < train_frac < 1:
        split_idx = int(len(df) * train_frac)
        df_train = df.iloc[:split_idx]
        df_test = df.iloc[split_idx:]

        # Recalculamos el retorno acumulado total para cada split
        m_train = _compute_metrics_from_logrets(
            strategy_log_ret=df_train["strategy_log_ret"].dropna(),
            equity_curve=np.exp(df_train["strategy_log_ret"].cumsum()).dropna(),
            buy_hold_curve=np.exp(df_train["buy_hold_log_ret"].cumsum()).dropna(),
            periods_per_year=periods_per_year,
        )
        m_test = _compute_metrics_from_logrets(
            strategy_log_ret=df_test["strategy_log_ret"].dropna(),
            equity_curve=np.exp(df_test["strategy_log_ret"].cumsum()).dropna(),
            buy_hold_curve=np.exp(df_test["buy_hold_log_ret"].cumsum()).dropna(),
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
    Calcula métricas principales (CAGR, Sharpe, Sortino, Skew, Kurtosis) 
    a partir de log-returns y la curva de equity.
    """
    strategy_log_ret = strategy_log_ret.dropna()
    n = len(strategy_log_ret)

    if n == 0:
        # Retorna un diccionario con todas las keys requeridas en NaN
        return {
            "total_return_strategy": np.nan, "total_return_buy_hold": np.nan, 
            "cagr_strategy": np.nan, "cagr_buy_hold": np.nan, 
            "max_drawdown_strategy": np.nan, "max_drawdown_buy_hold": np.nan, 
            "annual_volatility_strategy": np.nan, "sharpe_ratio": np.nan, 
            "calmar_ratio": np.nan, "sortino_ratio": np.nan, 
            "annual_skew": np.nan, "annual_kurtosis": np.nan,
            "yearly_returns": {},
        }

    eq = equity_curve.dropna()
    final_eq = float(eq.iloc[-1]) if not eq.empty else np.nan

    final_bh = np.nan
    if buy_hold_curve is not None:
        bh = buy_hold_curve.dropna()
        final_bh = float(bh.iloc[-1]) if not bh.empty else np.nan

    years = n / periods_per_year if periods_per_year > 0 else np.nan
    
    # Calculate CAGRs
    cagr_strategy = final_eq ** (1.0 / years) - 1.0 if years and years > 0 and final_eq > 0 else np.nan
    cagr_buy_hold = final_bh ** (1.0 / years) - 1.0 if years and years > 0 and not np.isnan(final_bh) and final_bh > 0 else np.nan

    max_dd_strategy = _max_drawdown(equity_curve)
    max_dd_buy = _max_drawdown(buy_hold_curve) if buy_hold_curve is not None else np.nan

    # Volatilidad & Sharpe
    daily_std = float(strategy_log_ret.std(ddof=0))
    daily_mean = float(strategy_log_ret.mean())
    
    if daily_std > 0:
        annual_vol = daily_std * np.sqrt(periods_per_year)
        # Sharpe Ratio (asumiendo Rf=0)
        sharpe = np.sqrt(periods_per_year) * (daily_mean / daily_std) 
    else:
        annual_vol = np.nan
        sharpe = np.nan

    # Calmar Ratio
    calmar = cagr_strategy / abs(max_dd_strategy) if max_dd_strategy is not None and max_dd_strategy < 0 and not np.isnan(cagr_strategy) else np.nan

    # Sortino Ratio
    downside_returns = strategy_log_ret.where(strategy_log_ret < 0, 0.0)
    downside_std = float(downside_returns.std(ddof=0))
    sortino = np.sqrt(periods_per_year) * (daily_mean / downside_std) if downside_std > 0 else (np.inf if daily_mean > 0 else np.nan)

    # Distribución (Skew y Kurtosis)
    # Se usa el n de la muestra, no la anualización directa, para estos factores
    annual_skew = strategy_log_ret.skew()
    annual_kurtosis = strategy_log_ret.kurtosis()

    # Retornos Anuales (Yearly Returns)
    strategy_simple_returns = np.exp(strategy_log_ret) - 1.0
    yearly_returns = strategy_simple_returns.groupby(strategy_log_ret.index.year).apply(
        lambda x: (1 + x).prod() - 1
    ).to_dict()

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
        "sortino_ratio": sortino,
        "annual_skew": annual_skew,
        "annual_kurtosis": annual_kurtosis,
        "yearly_returns": yearly_returns,
    }

# El código duplicado se ha eliminado.