"""
Visualization utilities for market microstructure analysis.

Generates publication-quality plots for spreads, VPIN, order flow,
price impact, and transaction cost analysis.
"""

import logging
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

logger = logging.getLogger(__name__)

# Configure matplotlib styling
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (14, 6)
plt.rcParams["font.size"] = 10


def plot_intraday_spread(
    spread_df: pd.DataFrame,
    figsize: tuple = (14, 7),
    title: str = "Intraday Spread Dynamics",
) -> plt.Figure:
    """
    Plot effective and realized spreads over time with volume overlay.

    Args:
        spread_df: DataFrame from compute_spreads() with index timestamp
        figsize: Figure size (width, height)
        title: Plot title

    Returns:
        matplotlib Figure object
    """
    if spread_df.empty:
        logger.warning("Empty spread dataframe provided")
        return None

    fig, axes = plt.subplots(2, 1, figsize=figsize, sharex=True)

    # Spreads
    ax1 = axes[0]
    ax1.plot(
        spread_df.index,
        spread_df["effective_spread"] * 100,
        label="Effective Spread",
        linewidth=2,
        alpha=0.8,
    )
    ax1.plot(
        spread_df.index,
        spread_df["realized_spread"] * 100,
        label="Realized Spread",
        linewidth=2,
        alpha=0.8,
        linestyle="--",
    )
    ax1.fill_between(
        spread_df.index,
        spread_df["effective_spread"] * 100,
        spread_df["realized_spread"] * 100,
        alpha=0.2,
        label="Price Impact",
    )
    ax1.set_ylabel("Spread (%)")
    ax1.legend(loc="best")
    ax1.grid(True, alpha=0.3)
    ax1.set_title(title)

    # Volume
    ax2 = axes[1]
    ax2.bar(spread_df.index, spread_df["volume"], alpha=0.6, color="steelblue")
    ax2.set_ylabel("Volume")
    ax2.set_xlabel("Time")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


def plot_vpin_timeseries(
    vpin_series: pd.Series,
    price_series: Optional[pd.Series] = None,
    threshold: float = 0.5,
    figsize: tuple = (14, 8),
) -> plt.Figure:
    """
    Plot VPIN time series with price overlay and high-VPIN indicators.

    Args:
        vpin_series: Series of VPIN values indexed by timestamp
        price_series: Optional series of prices for overlay
        threshold: VPIN threshold for highlighting elevated periods
        figsize: Figure size

    Returns:
        matplotlib Figure object
    """
    if vpin_series.empty:
        logger.warning("Empty VPIN series provided")
        return None

    if price_series is not None and not price_series.empty:
        fig, axes = plt.subplots(2, 1, figsize=figsize, sharex=True)

        # VPIN
        ax1 = axes[0]
        ax1.plot(vpin_series.index, vpin_series.values, label="VPIN", linewidth=1.5)
        ax1.axhline(y=threshold, color="red", linestyle="--", alpha=0.5, label=f"Threshold ({threshold})")
        ax1.fill_between(
            vpin_series.index,
            0,
            vpin_series.values,
            where=(vpin_series.values > threshold),
            alpha=0.3,
            color="red",
            label="High VPIN Period",
        )
        ax1.set_ylabel("VPIN")
        ax1.legend(loc="best")
        ax1.grid(True, alpha=0.3)
        ax1.set_title("VPIN and Price Dynamics")
        ax1.set_ylim([0, 1])

        # Price
        ax2 = axes[1]
        ax2.plot(price_series.index, price_series.values, label="Price", color="darkgreen", linewidth=2)
        ax2.set_ylabel("Price")
        ax2.set_xlabel("Time")
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc="best")

        plt.tight_layout()
    else:
        fig, ax = plt.subplots(figsize=figsize)
        ax.plot(vpin_series.index, vpin_series.values, label="VPIN", linewidth=1.5)
        ax.axhline(y=threshold, color="red", linestyle="--", alpha=0.5, label=f"Threshold ({threshold})")
        ax.fill_between(
            vpin_series.index,
            0,
            vpin_series.values,
            where=(vpin_series.values > threshold),
            alpha=0.3,
            color="red",
        )
        ax.set_ylabel("VPIN")
        ax.set_xlabel("Time")
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)
        ax.set_title("Volume-Synchronized Probability of Informed Trading (VPIN)")
        ax.set_ylim([0, 1])
        plt.tight_layout()

    return fig


def plot_order_flow_heatmap(
    ofi_df: pd.DataFrame,
    figsize: tuple = (14, 8),
    cmap: str = "RdBu_r",
) -> plt.Figure:
    """
    Create heatmap of order flow imbalance by hour and day of week.

    Args:
        ofi_df: DataFrame from order_flow_imbalance() with index timestamp
        figsize: Figure size
        cmap: Colormap name

    Returns:
        matplotlib Figure object
    """
    if ofi_df.empty:
        logger.warning("Empty OFI dataframe provided")
        return None

    # Extract hour and day of week
    ofi_df_copy = ofi_df.copy()
    ofi_df_copy["hour"] = ofi_df_copy.index.hour
    ofi_df_copy["day_of_week"] = ofi_df_copy.index.day_name()

    # Create pivot table
    heatmap_data = ofi_df_copy.pivot_table(
        values="ofi",
        index="day_of_week",
        columns="hour",
        aggfunc="mean",
    )

    # Reorder days
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    heatmap_data = heatmap_data.reindex([d for d in day_order if d in heatmap_data.index])

    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(
        heatmap_data,
        cmap=cmap,
        center=0,
        cbar_kws={"label": "Order Flow Imbalance"},
        ax=ax,
        vmin=-0.5,
        vmax=0.5,
    )
    ax.set_title("Intraday Order Flow Imbalance (Hour × Day of Week)")
    ax.set_xlabel("Hour of Day (UTC)")
    ax.set_ylabel("Day of Week")
    plt.tight_layout()

    return fig


def plot_price_impact(
    trades_df: pd.DataFrame,
    freq: str = "1h",
    figsize: tuple = (10, 6),
) -> plt.Figure:
    """
    Scatter plot of signed volume vs. price change to visualize price impact.

    Args:
        trades_df: DataFrame with columns [timestamp, price, qty, is_buyer_maker]
        freq: Aggregation frequency for price changes
        figsize: Figure size

    Returns:
        matplotlib Figure object
    """
    if trades_df.empty:
        logger.warning("Empty trades dataframe provided")
        return None

    df = trades_df.copy()
    df = df.set_index("timestamp")

    signed_vols = []
    price_changes = []

    for period_end, group in df.resample(freq):
        if len(group) < 2:
            continue

        buy_vol = group.loc[~group["is_buyer_maker"], "qty"].sum()
        sell_vol = group.loc[group["is_buyer_maker"], "qty"].sum()
        signed_vol = (buy_vol - sell_vol) / (buy_vol + sell_vol) if (buy_vol + sell_vol) > 0 else 0

        price_change = (group.iloc[-1]["price"] - group.iloc[0]["price"]) / group.iloc[0]["price"]

        signed_vols.append(signed_vol)
        price_changes.append(price_change)

    fig, ax = plt.subplots(figsize=figsize)
    scatter = ax.scatter(
        signed_vols,
        np.array(price_changes) * 100,
        alpha=0.6,
        c=np.abs(price_changes),
        cmap="viridis",
        s=50,
    )
    ax.axhline(y=0, color="k", linestyle="-", alpha=0.3, linewidth=0.5)
    ax.axvline(x=0, color="k", linestyle="-", alpha=0.3, linewidth=0.5)

    # Add trend line
    z = np.polyfit(signed_vols, price_changes, 1)
    p = np.poly1d(z)
    ax.plot(
        np.array(signed_vols),
        p(np.array(signed_vols)) * 100,
        "r--",
        alpha=0.8,
        linewidth=2,
        label=f"Trend: {z[0]*100:.2f}% per unit OF",
    )

    ax.set_xlabel("Order Flow Imbalance")
    ax.set_ylabel("Price Change (%)")
    ax.set_title("Price Impact vs. Order Flow")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label("Abs. Price Change")
    plt.tight_layout()

    return fig


def plot_tca_breakdown(
    tca_results: dict,
    figsize: tuple = (10, 6),
) -> plt.Figure:
    """
    Bar chart decomposing transaction costs into components.

    Args:
        tca_results: Dictionary from implementation_shortfall() with cost components
        figsize: Figure size

    Returns:
        matplotlib Figure object
    """
    components = {
        "Execution Cost": tca_results.get("execution_cost", 0),
        "Opportunity Cost": tca_results.get("opportunity_cost", 0),
        "Total Cost": tca_results.get("total_cost", 0),
    }

    fig, ax = plt.subplots(figsize=figsize)
    colors = ["steelblue", "coral", "darkred"]
    bars = ax.bar(components.keys(), components.values(), color=colors, alpha=0.7, edgecolor="black")

    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"${height:,.0f}",
            ha="center",
            va="bottom",
        )

    ax.set_ylabel("Cost ($)")
    ax.set_title("Transaction Cost Analysis Breakdown")
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()

    return fig


def plot_maker_taker_analysis(
    mt_df: pd.DataFrame,
    figsize: tuple = (14, 8),
) -> plt.Figure:
    """
    Plot maker vs. taker volume and cost analysis.

    Args:
        mt_df: DataFrame from maker_taker_analysis() with index timestamp
        figsize: Figure size

    Returns:
        matplotlib Figure object
    """
    if mt_df.empty:
        logger.warning("Empty maker/taker dataframe provided")
        return None

    fig, axes = plt.subplots(2, 1, figsize=figsize, sharex=True)

    # Volume comparison
    ax1 = axes[0]
    ax1.bar(
        mt_df.index,
        mt_df["maker_volume"],
        alpha=0.6,
        label="Maker Volume",
        color="green",
    )
    ax1.bar(
        mt_df.index,
        mt_df["taker_volume"],
        bottom=mt_df["maker_volume"],
        alpha=0.6,
        label="Taker Volume",
        color="red",
    )
    ax1.set_ylabel("Volume")
    ax1.legend(loc="best")
    ax1.grid(True, alpha=0.3)
    ax1.set_title("Maker vs. Taker Volume")

    # Cost differential
    ax2 = axes[1]
    ax2.bar(
        mt_df.index,
        mt_df["taker_cost_bps"],
        alpha=0.6,
        color="darkred",
        label="Taker Cost Premium (bps)",
    )
    ax2.axhline(y=0, color="k", linestyle="-", alpha=0.3, linewidth=1)
    ax2.set_ylabel("Cost Differential (bps)")
    ax2.set_xlabel("Time")
    ax2.legend(loc="best")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig
