import warnings

import numpy as np
import pandas as pd
from zipline import run_algorithm
from zipline.api import (
    attach_pipeline,
    cancel_order,
    date_rules,
    get_datetime,
    get_open_orders,
    order_target_percent,
    pipeline_output,
    schedule_function,
    set_commission,
    set_slippage,
    time_rules,
)
from zipline.finance import commission, slippage
from zipline.pipeline import Pipeline
from zipline.pipeline.data import USEquityPricing
from zipline.pipeline.factors import AverageDollarVolume, CustomFactor

warnings.filterwarnings("ignore")


LOOKBACK_WEEKS = 151
LOOKBACK_DAYS = LOOKBACK_WEEKS * 5
UNIVERSE_SIZE = 3000
QUANTILE = 4
class WeeklyVolatility(CustomFactor):
    """
    Computes standard deviation of weekly returns over a 3-year window.
    Weekly return is defined over 5 consecutive trading days:
        r_week = (close[t] / close[t-4]) - 1
    We take non-overlapping 5-day chunks across the window for stability.
    """

    inputs = [USEquityPricing.close]
    window_length = LOOKBACK_DAYS

    def compute(self, today, assets, out, closes):
        n_weeks = closes.shape[0] // 5
        if n_weeks < 2:  # not enough weeks to compute a standard deviation
            out[:] = np.nan
            return

        trimmed = closes[-n_weeks * 5 :, :]  # (n_weeks*5, n_assets)
        weekly_open = trimmed[::5, :]  # first close in each 5-day block
        weekly_close = trimmed[4::5, :]  # last close in each 5-day block
        weekly_rets = (weekly_close / weekly_open) - 1  # shape (n_weeks, n_assets)

        out[:] = np.nanstd(weekly_rets, axis=0, ddof=1)

def make_pipeline():
    adv20 = AverageDollarVolume(window_length=20)
    base_universe = adv20.top(UNIVERSE_SIZE)

    vol = WeeklyVolatility(mask=base_universe)
    # Select lowest-volatility quartile by taking the bottom N within the ADV-filtered universe.
    target_count = max(1, UNIVERSE_SIZE // QUANTILE)
    lows = vol.bottom(target_count, mask=base_universe)

    pipe = Pipeline(
        columns={
            "adv20": adv20,
            "vol": vol,
            "low_vol_long": lows,
        },
        screen=base_universe,
    )
    return pipe
	
	
	import os
from zipline.data import bundles


os.environ["QUANDL_API_KEY"] = "YOUR_API_KEY"
bundles.ingest("quandl")