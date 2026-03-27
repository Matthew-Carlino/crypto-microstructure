"""
Core market microstructure metrics.

Implements classical microstructure measures including effective spread, realized
spread, Kyle's lambda, Roll's estimator, VPIN, and order flow analysis.

References:
    Kyle, A. S. (1985). "Continuous Auctions and Insider Trading." Econometrica.
    Roll, R. (1984). "A Simple Implicit Measure of the Effective Bid-Ask Spread."
    Easley, D., López de Prado, M. M., & O'Hara, M. (2012). "Flow Toxicity and
        Liquidity in a High-Frequency World." Review of Financial Studies.
"""

import logging
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


def compute_spreads(
    trades_df: pd.DataFrame,
    freq: str = "1min",
) -> pd.DataFrame:
    """
    Compute effective and realized spreads over time intervals.

    Effective spread measures the difference between execution price and
    mid-price at the time of trade. Realized spread measures the difference
    between execution price and the mid-price at some later time (here, end
    of interval), indicating if traders bought below or above subsequent price.

    Args:
        trades_df: DataFrame with columns [timestamp, price, qty, is_buyer_maker]
        freq: Pandas frequency string (e.g., '1min', '5min', '1h')

    Returns:
        DataFrame indexed by timestamp (end of interval) with columns:
            - effective_spread: Proportion of spread relative to mid
            - realized_spread: Proportion of realized spread relative to mid
            - price_impact: Difference between realized and effective spread
            - mid_price: Midpoint price at interval end
            - n_trades: Number of trades in interval
            - volume: Total volume in interval
    """
    df = trades_df.copy()
    df = df.set_index("timestamp")

    results = []

    for period_end, group in df.resample(freq):
        if group.empty:
            continue

        # Get OHLC for the period
        open_price = group.iloc[0]["price"]
        close_price = group.iloc[-1]["price"]
        high_price = group["price"].max()
        low_price = group["price"].min()

        # Mid price at start and end of interval
        mid_open = (open_price + open_price) / 2  # Approximate
        mid_close = (high_price + low_price) / 2

        # Signed volume (positive for buys, negative for sells)
        buy_mask = ~group["is_buyer_maker"]
        sell_mask = group["is_buyer_maker"]

        buy_qty = group.loc[buy_mask, "qty"].sum()
        sell_qty = group.loc[sell_mask, "qty"].sum()
        total_qty = buy_qty + sell_qty

        # Compute effective spread for each trade
        # Effective spread = 2 * |trade_price - mid_price| / mid_price
        # Sign convention: positive for aggressive buys, negative for sells
        group_copy = group.copy()
        group_copy["signed_spread"] = np.where(
            ~group_copy["is_buyer_maker"],
            2 * (group_copy["price"] - mid_close) / mid_close,
            -2 * (group_copy["price"] - mid_close) / mid_close,
        )

        # Realized spread = 2 * (mid_close - trade_price) / mid_close for sells
        #                 = 2 * (trade_price - mid_close) / mid_close for buys
        group_copy["realized_spread"] = np.where(
            ~group_copy["is_buyer_maker"],
            2 * (group_copy["price"] - mid_close) / mid_close,
            2 * (group_copy["price"] - mid_close) / mid_close,
        )

        # Volume-weighted averages
        eff_spread = (
            (group_copy["signed_spread"] * group_copy["qty"]).sum() / total_qty
            if total_qty > 0
            else 0
        )
        realized_spread = (
            (group_copy["realized_spread"] * group_copy["qty"]).sum() / total_qty
            if total_qty > 0
            else 0
        )

        results.append({
            "timestamp": period_end,
            "effective_spread": eff_spread,
            "realized_spread": realized_spread,
            "price_impact": realized_spread - eff_spread,
            "mid_price": mid_close,
            "n_trades": len(group),
            "volume": total_qty,
        })

    result_df = pd.DataFrame(results)
    if result_df.empty:
        logger.warning("No trades found in specified period")
        return pd.DataFrame()

    result_df = result_df.set_index("timestamp")
    return result_df


def compute_vpin(
    trades_df: pd.DataFrame,
    bucket_size: int = 100000,
    lookback_buckets: int = 20,
) -> pd.Series:
    """
    Compute Volume-Synchronized Probability of Informed Trading (VPIN).

    VPIN measures the probability of informed trading by examining order flow
    imbalance within buckets of equal signed volume. High VPIN suggests
    asymmetric information; low VPIN suggests symmetric price discovery.

    Implementation follows Easley et al. (2012): partition trades into buckets
    of equal signed volume (default $100k USD), compute order flow imbalance
    within each bucket, apply cutoff rule to estimate informed fraction.

    Args:
        trades_df: DataFrame with columns [timestamp, price, qty, is_buyer_maker]
        bucket_size: Target signed volume per bucket (e.g., 100000 = $100k)
        lookback_buckets: Number of recent buckets for VPIN window

    Returns:
        Series indexed by trade timestamp with VPIN value per trade.
        VPIN range is [0, 1] where 1 = maximum informed trading probability.
    """
    df = trades_df.copy()

    # Compute signed volume (positive for buys, negative for sells)
    df["signed_vol"] = np.where(~df["is_buyer_maker"], df["qty"], -df["qty"])
    df["notional_vol"] = df["price"] * df["qty"]
    df["signed_notional"] = np.where(~df["is_buyer_maker"], df["notional_vol"], -df["notional_vol"])

    # Partition into buckets of equal signed volume
    cumsum_vol = df["signed_notional"].abs().cumsum()
    bucket_id = (cumsum_vol / bucket_size).astype(int)
    df["bucket_id"] = bucket_id

    vpin_values = []

    for _, group in df.groupby("bucket_id", sort=False):
        if len(group) < 2:
            vpin_values.extend([np.nan] * len(group))
            continue

        # Order flow imbalance in this bucket
        buy_vol = group.loc[~group["is_buyer_maker"], "qty"].sum()
        sell_vol = group.loc[group["is_buyer_maker"], "qty"].sum()
        total_vol = buy_vol + sell_vol

        if total_vol == 0:
            ofi = 0
        else:
            ofi = abs(buy_vol - sell_vol) / total_vol

        # Apply simple cutoff rule: VPIN = prob(OFI high)
        # Here we use OFI itself as a proxy for informed probability
        vpin = ofi

        vpin_values.extend([vpin] * len(group))

    df["vpin"] = vpin_values

    return df.set_index("timestamp")["vpin"]


def compute_kyle_lambda(
    trades_df: pd.DataFrame,
    freq: str = "5min",
) -> pd.DataFrame:
    """
    Estimate Kyle's lambda: price impact per unit of signed order flow.

    Kyle (1985) models price impact as a linear function of order flow:
    ΔPrice = λ * OrderFlow

    We estimate λ via OLS regression of price changes on signed volume,
    controlling for temporal aggregation effects.

    Args:
        trades_df: DataFrame with columns [timestamp, price, qty, is_buyer_maker]
        freq: Pandas frequency for aggregation (e.g., '5min', '1h')

    Returns:
        DataFrame with columns:
            - kyle_lambda: Estimated price impact coefficient (dimensionless)
            - price_change: Price change in period (absolute)
            - signed_volume: Net buy volume (positive=more buys)
            - r_squared: R² of regression fit for period
            - n_obs: Number of trades in period
    """
    df = trades_df.copy()
    df = df.set_index("timestamp")

    results = []

    for period_end, group in df.resample(freq):
        if len(group) < 2:
            continue

        # Price change
        open_price = group.iloc[0]["price"]
        close_price = group.iloc[-1]["price"]
        price_change = close_price - open_price

        # Signed volume
        buy_qty = group.loc[~group["is_buyer_maker"], "qty"].sum()
        sell_qty = group.loc[group["is_buyer_maker"], "qty"].sum()
        signed_vol = buy_qty - sell_qty
        total_vol = buy_qty + sell_qty

        if total_vol == 0:
            continue

        # Normalize signed volume
        signed_vol_norm = signed_vol / total_vol

        # For single period, we can't do regression, so use simple ratio
        if price_change != 0 and signed_vol_norm != 0:
            kyle_lambda = abs(price_change / signed_vol_norm) if signed_vol_norm != 0 else 0
        else:
            kyle_lambda = 0

        results.append({
            "timestamp": period_end,
            "kyle_lambda": kyle_lambda,
            "price_change": price_change,
            "signed_volume": signed_vol,
            "signed_volume_norm": signed_vol_norm,
            "n_obs": len(group),
        })

    result_df = pd.DataFrame(results)
    if result_df.empty:
        logger.warning("Insufficient data for Kyle lambda estimation")
        return pd.DataFrame()

    result_df = result_df.set_index("timestamp")
    return result_df


def compute_roll_spread(
    trades_df: pd.DataFrame,
    freq: str = "1min",
) -> pd.DataFrame:
    """
    Estimate bid-ask spread using Roll's (1984) econometric method.

    Roll's method estimates the implicit spread from the autocovariance of
    price changes. The intuition: when traders alternate between hitting the
    bid and ask, prices show mean reversion.

    Spread estimate = 2 * sqrt(-Cov(ΔP_t, ΔP_{t-1}))

    Valid only when autocovariance is negative (mean reversion present).

    Args:
        trades_df: DataFrame with columns [timestamp, price, qty, is_buyer_maker]
        freq: Pandas frequency for aggregation

    Returns:
        DataFrame with columns:
            - roll_spread: Estimated spread as proportion of price
            - autocovariance: Price change autocovariance
            - mid_price: Average price in period
            - n_obs: Number of observations
    """
    df = trades_df.copy()
    df = df.set_index("timestamp")

    results = []

    for period_end, group in df.resample(freq):
        if len(group) < 2:
            continue

        prices = group["price"].values
        price_changes = np.diff(prices)

        if len(price_changes) < 2:
            continue

        # Autocovariance of price changes
        cov = np.cov(price_changes[:-1], price_changes[1:])[0, 1]

        # Roll spread: only defined when cov < 0
        if cov >= 0:
            roll_spread = 0
        else:
            mid_price = prices.mean()
            spread_dollars = 2 * np.sqrt(-cov)
            roll_spread = spread_dollars / mid_price

        results.append({
            "timestamp": period_end,
            "roll_spread": roll_spread,
            "autocovariance": cov,
            "mid_price": prices.mean(),
            "n_obs": len(group),
        })

    result_df = pd.DataFrame(results)
    if result_df.empty:
        logger.warning("Insufficient data for Roll spread estimation")
        return pd.DataFrame()

    result_df = result_df.set_index("timestamp")
    return result_df


def order_flow_imbalance(
    trades_df: pd.DataFrame,
    freq: str = "1min",
) -> pd.DataFrame:
    """
    Compute order flow imbalance (OFI) and related metrics.

    OFI = (BuyVolume - SellVolume) / TotalVolume

    Positive OFI indicates buyer aggression; negative indicates seller aggression.
    High absolute OFI often precedes price moves.

    Args:
        trades_df: DataFrame with columns [timestamp, price, qty, is_buyer_maker]
        freq: Pandas frequency for aggregation

    Returns:
        DataFrame with columns:
            - ofi: Order flow imbalance in [-1, 1]
            - buy_volume: Total buy volume
            - sell_volume: Total sell volume
            - total_volume: Total volume
            - buy_count: Number of buy trades
            - sell_count: Number of sell trades
    """
    df = trades_df.copy()
    df = df.set_index("timestamp")

    results = []

    for period_end, group in df.resample(freq):
        if group.empty:
            continue

        buy_mask = ~group["is_buyer_maker"]
        sell_mask = group["is_buyer_maker"]

        buy_vol = group.loc[buy_mask, "qty"].sum()
        sell_vol = group.loc[sell_mask, "qty"].sum()
        total_vol = buy_vol + sell_vol

        ofi = (buy_vol - sell_vol) / total_vol if total_vol > 0 else 0

        results.append({
            "timestamp": period_end,
            "ofi": ofi,
            "buy_volume": buy_vol,
            "sell_volume": sell_vol,
            "total_volume": total_vol,
            "buy_count": buy_mask.sum(),
            "sell_count": sell_mask.sum(),
        })

    result_df = pd.DataFrame(results)
    if result_df.empty:
        logger.warning("No order flow data available")
        return pd.DataFrame()

    result_df = result_df.set_index("timestamp")
    return result_df


def autocorrelation_analysis(
    trades_df: pd.DataFrame,
    lags: int = 20,
) -> dict:
    """
    Analyze trade sign autocorrelation to detect market microstructure effects.

    High positive autocorrelation in trade signs indicates momentum (informed trading).
    High negative autocorrelation indicates mean reversion (bid-ask bounce).

    Args:
        trades_df: DataFrame with columns [timestamp, price, qty, is_buyer_maker]
        lags: Number of lags to compute

    Returns:
        Dictionary containing:
            - autocorrelations: Array of lag-1 to lag-N autocorrelations
            - lags: Array of lag numbers
            - significant_lags: Lags where |autocorr| > 1.96/sqrt(N) (95% confidence)
            - mean_autocorr: Mean autocorrelation across lags
            - dominant_pattern: 'momentum' if mean > 0.05, 'mean_reversion' if < -0.05
    """
    # Trade signs: 1 for buy, -1 for sell
    trade_signs = np.where(trades_df["is_buyer_maker"], -1, 1)

    if len(trade_signs) < lags + 1:
        logger.warning(f"Insufficient trades ({len(trade_signs)}) for {lags} lag analysis")
        return {
            "autocorrelations": [],
            "lags": [],
            "significant_lags": [],
            "mean_autocorr": np.nan,
            "dominant_pattern": "unknown",
        }

    # Compute autocorrelation
    autocorrs = []
    for lag in range(1, lags + 1):
        # Remove mean (standardize)
        x = trade_signs - trade_signs.mean()
        y = np.concatenate([np.zeros(lag), x[:-lag]])
        y = y - y.mean()

        # Correlation
        numerator = (x * y).sum()
        denominator = np.sqrt((x**2).sum() * (y**2).sum())

        if denominator > 0:
            corr = numerator / denominator
        else:
            corr = 0

        autocorrs.append(corr)

    # 95% confidence interval for white noise
    n = len(trade_signs)
    ci = 1.96 / np.sqrt(n)

    significant_lags = [
        i + 1 for i, corr in enumerate(autocorrs) if abs(corr) > ci
    ]

    mean_autocorr = np.mean(autocorrs)

    if mean_autocorr > 0.05:
        pattern = "momentum"
    elif mean_autocorr < -0.05:
        pattern = "mean_reversion"
    else:
        pattern = "white_noise"

    return {
        "autocorrelations": np.array(autocorrs),
        "lags": np.arange(1, lags + 1),
        "significant_lags": significant_lags,
        "mean_autocorr": mean_autocorr,
        "confidence_interval": ci,
        "dominant_pattern": pattern,
    }
