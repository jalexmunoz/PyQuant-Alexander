# core/strategies/__init__.py
# Strategy modules for the quant framework

from .trend_filter_strategy import (
    BASE_TARGETS,
    SMA_SHORT,
    SMA_LONG,
    TREND_ON,
    TREND_OFF,
    compute_trend_state,
    apply_trend_filter,
    get_filtered_targets,
    get_current_targets,
    get_trend_signals,
)

__all__ = [
    "BASE_TARGETS",
    "SMA_SHORT",
    "SMA_LONG",
    "TREND_ON",
    "TREND_OFF",
    "compute_trend_state",
    "apply_trend_filter",
    "get_filtered_targets",
    "get_current_targets",
    "get_trend_signals",
]

