# execution/__init__.py
# Execution module for shadow mode, trade suggestions, portfolio tracking, and trade logging

from .shadow_mode import (
    TargetSignal,
    CurrentPosition,
    SuggestedTrade,
    generate_suggested_trades,
)

from .portfolio_tracker import (
    get_portfolio_summary,
    print_portfolio_summary,
    SYMBOL_MAP,
)

from .trade_log import (
    log_trade,
    get_trade_history,
    print_trade_history,
)

__all__ = [
    # Shadow mode
    "TargetSignal",
    "CurrentPosition",
    "SuggestedTrade",
    "generate_suggested_trades",
    # Portfolio tracker
    "get_portfolio_summary",
    "print_portfolio_summary",
    "SYMBOL_MAP",
    # Trade log
    "log_trade",
    "get_trade_history",
    "print_trade_history",
]

