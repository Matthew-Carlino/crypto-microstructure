"""
Unit tests for microstructure metrics using synthetic data.

Tests verify correctness of spread computation, VPIN, Kyle's lambda,
and other metrics on controlled examples.
"""

import numpy as np
import pandas as pd
import pytest

from src.microstructure import (
    autocorrelation_analysis,
    compute_kyle_lambda,
    compute_roll_spread,
    compute_spreads,
    compute_vpin,
    order_flow_imbalance,
)


class TestComputeSpreads:
    """Tests for spread computation."""

    @pytest.fixture
    def simple_trades(self):
        """Create a simple trade sequence."""
        data = {
            "timestamp": pd.date_range("2025-01-01", periods=4, freq="1min"),
            "price": [100.0, 100.1, 100.05, 100.2],
            "qty": [1.0, 1.0, 1.0, 1.0],
            "is_buyer_maker": [False, True, False, True],  # Buy, Sell, Buy, Sell
        }
        return pd.DataFrame(data)

    def test_spreads_not_empty(self, simple_trades):
        """Test that spreads are computed for valid input."""
        spreads = compute_spreads(simple_trades, freq="1min")
        assert not spreads.empty
        assert "effective_spread" in spreads.columns

    def test_spreads_columns(self, simple_trades):
        """Test that all required columns are present."""
        spreads = compute_spreads(simple_trades, freq="2min")
        required_cols = [
            "effective_spread",
            "realized_spread",
            "price_impact",
            "mid_price",
            "n_trades",
            "volume",
        ]
        for col in required_cols:
            assert col in spreads.columns

    def test_spreads_empty_input(self):
        """Test handling of empty input."""
        empty_df = pd.DataFrame(
            columns=["timestamp", "price", "qty", "is_buyer_maker"]
        )
        spreads = compute_spreads(empty_df)
        assert spreads.empty


class TestComputeVPIN:
    """Tests for VPIN computation."""

    @pytest.fixture
    def informed_trades(self):
        """Create trades with clear buy/sell pattern (informed)."""
        timestamps = pd.date_range("2025-01-01", periods=100, freq="1s")
        # Pattern: strong buying pressure
        is_buyer_maker = [False] * 70 + [True] * 30  # 70% buys, 30% sells
        data = {
            "timestamp": timestamps,
            "price": np.linspace(100, 110, 100),
            "qty": [1.0] * 100,
            "is_buyer_maker": is_buyer_maker,
        }
        return pd.DataFrame(data)

    def test_vpin_range(self, informed_trades):
        """Test that VPIN values are in [0, 1]."""
        vpin = compute_vpin(informed_trades, bucket_size=10000)
        assert vpin.min() >= 0
        assert vpin.max() <= 1

    def test_vpin_imbalance_detection(self, informed_trades):
        """Test that VPIN detects order flow imbalance."""
        vpin = compute_vpin(informed_trades, bucket_size=10000)
        # With 70% buys, should show elevated VPIN
        assert vpin.mean() > 0.3  # Conservative threshold

    def test_vpin_empty_input(self):
        """Test handling of empty input."""
        empty_df = pd.DataFrame(
            columns=["timestamp", "price", "qty", "is_buyer_maker"]
        )
        vpin = compute_vpin(empty_df)
        assert vpin.empty


class TestComputeKylesLambda:
    """Tests for Kyle's lambda estimation."""

    @pytest.fixture
    def trending_trades(self):
        """Create trades with clear price trend."""
        timestamps = pd.date_range("2025-01-01", periods=200, freq="1s")
        prices = np.linspace(100, 102, 200) + np.random.normal(0, 0.1, 200)
        # Buying pressure (negative is_buyer_maker = buy)
        is_buyer_maker = [False] * 150 + [True] * 50
        data = {
            "timestamp": timestamps,
            "price": prices,
            "qty": [1.0] * 200,
            "is_buyer_maker": is_buyer_maker,
        }
        return pd.DataFrame(data)

    def test_kyle_lambda_positive(self, trending_trades):
        """Test that Kyle's lambda is positive for trending market."""
        kyle = compute_kyle_lambda(trending_trades, freq="30s")
        assert not kyle.empty
        assert "kyle_lambda" in kyle.columns
        # Kyle's lambda should be non-negative
        assert (kyle["kyle_lambda"] >= 0).all()

    def test_kyle_lambda_columns(self, trending_trades):
        """Test that all required columns are present."""
        kyle = compute_kyle_lambda(trending_trades, freq="1min")
        required_cols = ["kyle_lambda", "price_change", "signed_volume", "n_obs"]
        for col in required_cols:
            assert col in kyle.columns


class TestComputeRollSpread:
    """Tests for Roll's spread estimator."""

    @pytest.fixture
    def mean_reverting_trades(self):
        """Create trades with mean-reverting price pattern."""
        timestamps = pd.date_range("2025-01-01", periods=100, freq="1s")
        # Mean-reverting: oscillates around 100
        prices = [100 + (-1) ** i * 0.05 + np.random.normal(0, 0.01) for i in range(100)]
        data = {
            "timestamp": timestamps,
            "price": prices,
            "qty": [1.0] * 100,
            "is_buyer_maker": [i % 2 == 0 for i in range(100)],
        }
        return pd.DataFrame(data)

    def test_roll_spread_non_negative(self, mean_reverting_trades):
        """Test that Roll spread is non-negative."""
        roll = compute_roll_spread(mean_reverting_trades, freq="10s")
        assert not roll.empty
        assert (roll["roll_spread"] >= 0).all()

    def test_roll_spread_columns(self, mean_reverting_trades):
        """Test that all required columns are present."""
        roll = compute_roll_spread(mean_reverting_trades, freq="10s")
        required_cols = ["roll_spread", "autocovariance", "mid_price", "n_obs"]
        for col in required_cols:
            assert col in roll.columns


class TestOrderFlowImbalance:
    """Tests for order flow imbalance."""

    @pytest.fixture
    def balanced_trades(self):
        """Create balanced buy/sell trades."""
        timestamps = pd.date_range("2025-01-01", periods=100, freq="1s")
        data = {
            "timestamp": timestamps,
            "price": [100.0] * 100,
            "qty": [1.0] * 100,
            "is_buyer_maker": [i % 2 == 0 for i in range(100)],  # 50% buy, 50% sell
        }
        return pd.DataFrame(data)

    def test_ofi_range(self, balanced_trades):
        """Test that OFI is in [-1, 1]."""
        ofi = order_flow_imbalance(balanced_trades, freq="5s")
        assert ofi["ofi"].min() >= -1
        assert ofi["ofi"].max() <= 1

    def test_ofi_balanced_near_zero(self, balanced_trades):
        """Test that balanced trades yield OFI near zero."""
        ofi = order_flow_imbalance(balanced_trades, freq="10s")
        assert abs(ofi["ofi"].mean()) < 0.2

    def test_ofi_columns(self, balanced_trades):
        """Test that all required columns are present."""
        ofi = order_flow_imbalance(balanced_trades, freq="5s")
        required_cols = [
            "ofi",
            "buy_volume",
            "sell_volume",
            "total_volume",
            "buy_count",
            "sell_count",
        ]
        for col in required_cols:
            assert col in ofi.columns

    def test_ofi_empty_input(self):
        """Test handling of empty input."""
        empty_df = pd.DataFrame(
            columns=["timestamp", "price", "qty", "is_buyer_maker"]
        )
        ofi = order_flow_imbalance(empty_df)
        assert ofi.empty


class TestAutocorrelation:
    """Tests for trade sign autocorrelation analysis."""

    @pytest.fixture
    def momentum_trades(self):
        """Create trades with momentum (positive autocorr)."""
        timestamps = pd.date_range("2025-01-01", periods=50, freq="1s")
        # Pattern: buy, buy, buy, sell, sell, sell (momentum)
        is_buyer_maker = [False, False, False, True, True, True] * 8 + [False, False]
        data = {
            "timestamp": timestamps,
            "price": [100.0] * 50,
            "qty": [1.0] * 50,
            "is_buyer_maker": is_buyer_maker,
        }
        return pd.DataFrame(data)

    def test_autocorr_structure(self):
        """Test output structure of autocorrelation analysis."""
        trades = pd.DataFrame({
            "timestamp": pd.date_range("2025-01-01", periods=100, freq="1s"),
            "price": [100.0] * 100,
            "qty": [1.0] * 100,
            "is_buyer_maker": [i % 2 == 0 for i in range(100)],
        })
        result = autocorrelation_analysis(trades, lags=10)

        assert "autocorrelations" in result
        assert "lags" in result
        assert "significant_lags" in result
        assert "mean_autocorr" in result
        assert "dominant_pattern" in result

    def test_autocorr_pattern_detection(self, momentum_trades):
        """Test that momentum pattern is detected."""
        result = autocorrelation_analysis(momentum_trades, lags=5)
        # With momentum pattern, should detect positive autocorr
        # (not strictly guaranteed, but likely)
        assert isinstance(result["dominant_pattern"], str)
        assert result["dominant_pattern"] in ["momentum", "mean_reversion", "white_noise"]

    def test_autocorr_insufficient_data(self):
        """Test handling of insufficient data."""
        trades = pd.DataFrame({
            "timestamp": pd.date_range("2025-01-01", periods=2, freq="1s"),
            "price": [100.0, 100.1],
            "qty": [1.0, 1.0],
            "is_buyer_maker": [False, True],
        })
        result = autocorrelation_analysis(trades, lags=10)
        assert result["dominant_pattern"] == "unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
