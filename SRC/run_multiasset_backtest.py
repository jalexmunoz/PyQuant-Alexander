# run_multiasset_backtest.py
# v0.7.0 - Backtest multi-activo parametrizado
#
# Historial:
# v0.7.0 - Define params dict y lo pasa al pipeline
# v0.6.0 - Refactor para usar print_backtest_metrics()

import pandas as pd
from pipeline import build_asset_regime_dataset
from signal_generator import add_risk_onoff_signal
from backtest import simple_long_only_backtest
from reporting import print_backtest_metrics
from strategy_profiles import STRATEGY_PROFILES_V1
from data_engine import DataEngine
from strategy import StrategyProfile
from indicators import add_sma, add_rsi, add_atr
from regimes import add_basic_regimes, add_risk_state
from signal_generator import add_risk_onoff_signal

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 25)

# --- CONFIGURACIÓN CENTRAL DE PARÁMETROS ---
# Aquí definimos la estrategia "toy" que teníamos
STRATEGY_PARAMS_DEFAULT = {
    # Parámetros de Indicadores
    "sma_short": 20,
    "sma_long": 50,
    "rsi_window": 14,
    "atr_window": 20,
    
    # Parámetros de Regímenes (los valores fijos que teníamos)
    "trend_slope_window": 5,
    "vol_window": 100,
    "vol_high_mult": 1.3,
    "vol_low_mult": 0.7,
    "mom_bull_thr": 55.0,
    "mom_bear_thr": 45.0,
}


def run_backtest_for_asset(
    data_engine: DataEngine, # <<< AHORA RECIBE EL ENGINE
    profile: StrategyProfile,
    label: str,
    vs_currency: str = "usd" # (vs_currency ya casi no se usa)
):
    print(f"\nUsando {profile.name} (SMA({profile.sma_short}, {profile.sma_long})) para {label}...")

    # 1. Obtener Datos (NUEVA FORMA)
    # Ya no llamamos a pipeline, llamamos al DataEngine
    df_data = data_engine.get_data_for_profile(profile)
    
    if df_data.empty:
        print(f"No se pudieron obtener datos para {label}. Saltando backtest.")
        return

    # 2. Pipeline (AHORA SOLO PROCESA)
    # El pipeline sigue esperando un dict de params, se lo damos
    params = profile.get_params_dict()
    
    # --- Lógica Manual del Pipeline (para evitar doble llamada) ---
    # En lugar de llamar a build_asset_regime_dataset, que
    # volvería a descargar los datos, llamamos a las funciones
    # que necesitamos directamente.
    
    df = df_data.copy() # Empezamos con los datos puros
    
    # Nombres de columna
    sma_s_col = f"SMA_{params['sma_short']}"
    sma_l_col = f"SMA_{params['sma_long']}"
    rsi_col = f"RSI_{params['rsi_window']}"
    atr_col = f"ATR_{params['atr_window']}"

    # Indicadores
    df = add_sma(df, window=params['sma_short'], col_name=sma_s_col)
    df = add_sma(df, window=params['sma_long'], col_name=sma_l_col)
    df = add_rsi(df, window=params['rsi_window'], col_name=rsi_col)
    df = add_atr(df, window=params['atr_window'], col_name=atr_col)

    # Regímenes
    df = add_basic_regimes(df,
        sma_short_col=sma_s_col, sma_long_col=sma_l_col,
        atr_col=atr_col, rsi_col=rsi_col,
        **{k: v for k, v in params.items() if k in [
            'trend_slope_window', 'vol_window', 'vol_high_mult', 
            'vol_low_mult', 'mom_bull_thr', 'mom_bear_thr'
        ]}
    )
    df = add_risk_state(df)
    
    # 3. Señal
    df_signal = add_risk_onoff_signal(df)

    # 4. Backtest
    if df_signal.empty or len(df_signal) < params['sma_long']:
        print(f"No hay suficientes datos para {label} después de procesar. Saltando.")
        return
        
    df_bt, metrics = simple_long_only_backtest(df_signal, train_frac=0.7)

    # 5. Imprimir métricas
    print_backtest_metrics(metrics)
    
    # 6. Mostrar filas finales
    cols_show = [
        "close", sma_s_col, sma_l_col,
        "trend_regime", "vol_regime", "momentum_regime",
        "risk_state", "position", "equity_curve",
    ]
    cols_show = [c for c in cols_show if c in df_bt.columns]
    print("\nÚltimas filas (precio, regímenes, posición):")
    print(df_bt[cols_show].tail(10))


# --- REEMPLAZA ESTA FUNCIÓN ENTERA ---
def main():
    
    vs_currency = "usd"

    # 1. Inicializar los 'motores'
    engine = DataEngine(default_source="binance")

    print("Ejecutando Backtests con DataEngine (Paso 2)...")

    # 2. Bucle de Ejecución
    for label, profile in STRATEGY_PROFILES_V1.items():
        
        if profile is None:
            print(f"\nEstrategia para {label} está 'None'. Saltando.")
            continue
        
        run_backtest_for_asset(
            data_engine=engine, # <-- Le pasamos el motor
            profile=profile,
            label=label,
            vs_currency=vs_currency,
        )


if __name__ == "__main__":
    main()