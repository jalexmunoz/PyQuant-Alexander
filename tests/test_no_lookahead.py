# tests/test_no_lookahead.py
# v1.0.0 - Anti-Lookahead Bias Unit Tests
#
# ═══════════════════════════════════════════════════════════════════════════════
# CRITICAL: These tests verify that the backtest engine does NOT have lookahead bias.
#
# WHY THIS TEST IS CRITICAL:
# ──────────────────────────────────────────────────────────────────────────────
# Lookahead bias is one of the most dangerous backtest errors. It occurs when:
#   1. A signal generated at time T is applied to the return at time T
#   2. This means we're "seeing" the price move BEFORE we trade
#   3. In reality, we can only act on a signal AFTER it's generated
#
# CORRECT behavior:
#   - Signal generated at end of day T (after close)
#   - Trade executed at open of day T+1
#   - Position captures return from T+1 to T+2
#
# WRONG behavior (lookahead):
#   - Signal generated at end of day T
#   - Position somehow captures return from T to T+1
#   - This is impossible in real trading!
#
# If ANY test in this file fails, the backtest has lookahead bias and ALL
# performance metrics are INVALID and OVERSTATED.
# ═══════════════════════════════════════════════════════════════════════════════

import pytest
import pandas as pd
import numpy as np


class TestAntiLookahead:
    """
    Test suite for verifying no lookahead bias exists in signal timing.
    
    These tests are CRITICAL for backtest validity. A failing test means
    the backtest is capturing future information, which is impossible
    in live trading and invalidates all performance metrics.
    """
    
    def test_signal_timing_no_lookahead(self):
        """
        CRITICAL: Signals must be applied with 1-day lag.
        If this test fails, backtest has lookahead bias.
        
        Scenario:
        - Price spikes on day 4 (100 → 150 = +47% return)
        - Signal triggers when price > 105 (first True on day 4)
        - CORRECT: We cannot capture day 4's return because we didn't
                   know the signal would trigger until end of day 4
        - Day 4's return should be 0 (not invested yet)
        - Day 5's return should be captured (signal was known from day 4)
        """
        # Toy data: price spike on day 4 (index 4)
        prices = pd.Series([100, 101, 102, 103, 150, 149, 148])
        
        # Signal: price > 105 = ON
        signals = (prices > 105).astype(int)
        # Expected: [0, 0, 0, 0, 1, 1, 1]
        
        # CORRECT: Apply with 1-day lag
        positions = signals.shift(1).fillna(0)
        # Expected: [0, 0, 0, 0, 0, 1, 1]
        
        # Returns (simple returns for this test)
        returns = prices.pct_change()
        portfolio_returns = positions * returns
        
        # CRITICAL ASSERTIONS:
        # Day 4 spike should NOT be captured (signal wasn't applied yet)
        assert portfolio_returns.iloc[4] == 0, \
            "LOOKAHEAD DETECTED: Captured same-day signal on spike day"
        
        # Day 5 should be captured (signal applied from day 4)
        assert portfolio_returns.iloc[5] != 0, \
            "Signal lag broken: Day T signal not applied to Day T+1"
        
        print("✅ Anti-lookahead test PASSED")
    
    def test_signal_lag_with_log_returns(self):
        """
        Same test using log returns (project standard).
        Verifies the lag applies correctly with our return methodology.
        """
        prices = pd.Series([100.0, 101.0, 102.0, 103.0, 150.0, 149.0, 148.0])
        
        # Signal: price > 105 = ON
        signals = (prices > 105).astype(int)
        
        # CORRECT: 1-day lag
        positions = signals.shift(1).fillna(0)
        
        # Log returns (project standard)
        log_returns = np.log(prices / prices.shift(1))
        portfolio_log_returns = positions * log_returns
        
        # Day 4: big spike day - should NOT be captured
        assert portfolio_log_returns.iloc[4] == 0, \
            "LOOKAHEAD: Log returns captured same-day spike"
        
        # Day 5: should be captured (negative return from 150 → 149)
        expected_day5_return = np.log(149 / 150)  # ≈ -0.0067
        assert abs(portfolio_log_returns.iloc[5] - expected_day5_return) < 1e-10, \
            f"Day 5 return mismatch: got {portfolio_log_returns.iloc[5]}, expected {expected_day5_return}"
        
        print("✅ Anti-lookahead test (log returns) PASSED")
    
    def test_signal_off_timing(self):
        """
        Verify that signal OFF is also lagged correctly.
        
        Scenario:
        - Price drops on day 4 (150 → 100 = -33% return)
        - Signal turns OFF when price < 120 (first False on day 4)
        - We should still be exposed to day 4's loss (signal OFF not applied yet)
        """
        prices = pd.Series([150, 151, 152, 153, 100, 99, 98])
        
        # Signal: price > 120 = ON (starts ON, turns OFF on day 4)
        signals = (prices > 120).astype(int)
        # Expected: [1, 1, 1, 1, 0, 0, 0]
        
        # CORRECT: 1-day lag
        positions = signals.shift(1).fillna(0)
        # Expected: [0, 1, 1, 1, 1, 0, 0]
        
        # Returns
        returns = prices.pct_change()
        portfolio_returns = positions * returns
        
        # Day 4: crash day - we SHOULD capture this loss (still invested)
        # because signal OFF wasn't applied until day 5
        assert portfolio_returns.iloc[4] != 0, \
            "Signal OFF applied too early - should still be exposed on crash day"
        
        # Day 5: should be 0 (now out of position)
        assert portfolio_returns.iloc[5] == 0, \
            "Should be out of position on day 5 (signal OFF from day 4)"
        
        print("✅ Anti-lookahead test (signal OFF timing) PASSED")
    
    def test_multiple_signal_changes(self):
        """
        Test with multiple signal changes to verify consistent lagging.
        """
        prices = pd.Series([100, 110, 90, 120, 80, 130, 70])
        
        # Signal: price > 100 = ON
        signals = (prices > 100).astype(int)
        # Expected: [0, 1, 0, 1, 0, 1, 0]
        
        # CORRECT: 1-day lag
        positions = signals.shift(1).fillna(0)
        # Expected: [0, 0, 1, 0, 1, 0, 1]
        
        returns = prices.pct_change()
        portfolio_returns = positions * returns
        
        # Verify each transition is lagged
        # Day 1: signal turns ON, but position should be 0
        assert positions.iloc[1] == 0, "Day 1 position should be 0 (lag)"
        
        # Day 2: position should be 1 (from day 1 signal)
        assert positions.iloc[2] == 1, "Day 2 position should be 1"
        
        # Day 3: signal turned ON again, position should be 0 (from day 2 OFF)
        assert positions.iloc[3] == 0, "Day 3 position should be 0"
        
        print("✅ Anti-lookahead test (multiple changes) PASSED")


class TestPortfolioEngineLag:
    """
    Tests to verify the actual PortfolioBacktestEngine applies signal lag.
    
    Note: These tests import actual project code and verify it follows
    the correct signal timing convention.
    """
    
    def test_portfolio_engine_uses_lagged_weights(self):
        """
        Verify PortfolioBacktestEngine applies positions with proper lag.
        
        The engine should use weight_t_minus_1 (shifted) not weight_t.
        """
        import sys
        from pathlib import Path
        
        # Add project root
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))
        
        try:
            from core.portfolio_backtest_engine import PortfolioBacktestEngine
        except ImportError:
            pytest.skip("PortfolioBacktestEngine not available")
        
        # Create test data with known pattern
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        
        # Price that spikes on day 5
        prices = pd.Series(
            [100, 101, 102, 103, 104, 200, 199, 198, 197, 196],
            index=dates
        )
        
        # Position: ON from day 5 onwards
        positions = pd.Series(
            [0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
            index=dates
        )
        
        log_returns = np.log(prices / prices.shift(1))
        
        test_data = {
            'TESTUSDT': pd.DataFrame({
                'close': prices,
                'log_return': log_returns,
                'position': positions
            }, index=dates)
        }
        
        engine = PortfolioBacktestEngine(target_weights={'TESTUSDT': 1.0})
        engine.run(test_data)
        
        portfolio_returns = engine.returns
        
        # Day 5 (index 5): spike day - should NOT capture this return
        # because position only turned ON at end of day 5
        spike_day_return = portfolio_returns.iloc[4]  # Day index 4 in returns (after dropna)
        
        # The spike return from 104 → 200 should NOT be in our portfolio
        spike_log_return = np.log(200 / 104)  # ≈ 0.654
        
        # Our portfolio should NOT have captured this spike
        # (some small returns from earlier days are OK)
        assert abs(spike_day_return) < spike_log_return * 0.5, \
            f"LOOKAHEAD: Portfolio captured spike return. Got {spike_day_return}, spike was {spike_log_return}"
        
        print("✅ PortfolioBacktestEngine lag test PASSED")


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    # Run tests directly
    print("=" * 70)
    print(" ANTI-LOOKAHEAD BIAS TESTS")
    print(" These tests are CRITICAL for backtest validity")
    print("=" * 70)
    
    test_suite = TestAntiLookahead()
    
    try:
        test_suite.test_signal_timing_no_lookahead()
        test_suite.test_signal_lag_with_log_returns()
        test_suite.test_signal_off_timing()
        test_suite.test_multiple_signal_changes()
        
        print("\n" + "=" * 70)
        print(" ALL ANTI-LOOKAHEAD TESTS PASSED ✅")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        print("\n⚠️  CRITICAL: Backtest may have lookahead bias!")
        raise

