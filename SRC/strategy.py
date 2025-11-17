# strategy.py
# v1.0.0 - Clases para definir perfiles de estrategia.

class StrategyProfile:
    """
    Una clase simple (DataClass) para contener los parámetros
    de una estrategia de framework.
    """
    def __init__(
        self,
        # --- Parámetros de Identificación ---
        name: str,
        coin_id: str,
        symbol: str,
        
        # --- Parámetros de Indicadores ---
        sma_short: int,
        sma_long: int,
        rsi_window: int = 14,
        atr_window: int = 20,
        
        # --- Parámetros de Lógica de Régimen ---
        trend_slope_window: int = 5,
        vol_window: int = 100,
        vol_high_mult: float = 1.3,
        vol_low_mult: float = 0.7,
        mom_bull_thr: float = 55.0,
        mom_bear_thr: float = 45.0
    ):
        self.name = name
        self.coin_id = coin_id
        self.symbol = symbol # Símbolo de Binance (ej. BTCUSDT)
        
        self.sma_short = sma_short
        self.sma_long = sma_long
        self.rsi_window = rsi_window
        self.atr_window = atr_window
        
        self.trend_slope_window = trend_slope_window
        self.vol_window = vol_window
        self.vol_high_mult = vol_high_mult
        self.vol_low_mult = vol_low_mult
        self.mom_bull_thr = mom_bull_thr
        self.mom_bear_thr = mom_bear_thr

    def get_params_dict(self) -> dict:
        """
        Devuelve los parámetros como un diccionario, compatible
        con el pipeline antiguo.
        """
        return {
            "sma_short": self.sma_short,
            "sma_long": self.sma_long,
            "rsi_window": self.rsi_window,
            "atr_window": self.atr_window,
            "trend_slope_window": self.trend_slope_window,
            "vol_window": self.vol_window,
            "vol_high_mult": self.vol_high_mult,
            "vol_low_mult": self.vol_low_mult,
            "mom_bull_thr": self.mom_bull_thr,
            "mom_bear_thr": self.mom_bear_thr,
        }

    def __repr__(self) -> str:
        return (f"<StrategyProfile: {self.name} | "
                f"SMA({self.sma_short}, {self.sma_long})>")