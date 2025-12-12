import pandas as pd
import numpy as np


def add_risk_onoff_signal(
    df: pd.DataFrame,
    price_col: str = "close",
    risk_col: str = "risk_state",
) -> pd.DataFrame:
    """
    Estrategia Risk ON/OFF simple:

    - position = 1 cuando risk_state == 'risk_on'
    - position = 0 en cualquier otro caso (neutral o risk_off)

    'signal_raw' marca solo los días donde cambia la posición.
    """
    df = df.copy()

    # Posición directa en función del estado de riesgo
    position = (df[risk_col] == "risk_on").astype(float)

    # Señal solo donde hay cambio de posición
    signal_raw = position.where(position.ne(position.shift(1)))

    df["signal_raw"] = signal_raw
    df["position"] = position

    return df
