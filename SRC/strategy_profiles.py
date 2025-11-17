# strategy_profiles.py
# v1.1.0 - Actualizado para usar la clase StrategyProfile
#
# Este archivo centraliza los perfiles de estrategia
# que fueron validados en la Fase 4 de optimización.

from strategy import StrategyProfile

# --- Perfiles Optimizados por Activo ---

PROFILE_BTC = StrategyProfile(
    name="BTC-Default",
    coin_id="bitcoin",
    symbol="BTCUSDT",
    sma_short=20,
    sma_long=50
    # (los demás parámetros usan los valores por defecto)
)

PROFILE_ETH = StrategyProfile(
    name="ETH-Default",
    coin_id="ethereum",
    symbol="ETHUSDT",
    sma_short=20,
    sma_long=50
)

PROFILE_SOL = StrategyProfile(
    name="SOL-Optimized",
    coin_id="solana",
    symbol="SOLUSDT",
    sma_short=14,
    sma_long=30
)

PROFILE_LINK = StrategyProfile(
    name="LINK-Optimized",
    coin_id="chainlink",
    symbol="LINKUSDT",
    sma_short=20,
    sma_long=55
)


# --- Mapa Maestro V1 ---
# Este es el mapa que consumirán los scripts
STRATEGY_PROFILES_V1 = {
    "BTC-USD": PROFILE_BTC,
    "ETH-USD": PROFILE_ETH,
    "SOL-USD": PROFILE_SOL,
    "LINK-USD": PROFILE_LINK,
    # "PEPE-USD": None, # Ejemplo de cómo apagarla
}