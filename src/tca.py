"""
Transaction Cost Analysis (TCA) for cryptocurrency trading.

Decomposes execution costs into components (arrival price impact, market impact,
implementation shortfall) and provides metrics for evaluating execution quality.

References:
    Almgren, R., & Chriss, N. (2001). "Optimal Execution of Portfolio
        Transactions." Journal of Risk.
    Perold, A. F. (1988). "The Implementation Shortfall: Paper versus Reality."
        Journal of Portfolio Management.
"""

import logging
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


def arrival_price_slippage(
    executed_prices: np.ndarray,
    executed_quantities: np.ndarray,
    arrival_price: float,
    qty_executed_so_far: float = 0.0,
) -> Dict[str, float]:
    """
    Analyze slippage relative to arrival (reference) price.

    Slippage is the difference between execution price and arrival price,
    quantifying market impact during execution.

    Args:
        executed_prices: Array of execution prices
        executed_quantities: Array of quantities executed at each price
        arrival_price: Reference price at decision time
        qty_executed_so_far: Cumulative quantity before this execution

    Returns:
        Dictionary with keys:
            - vwap: Volume-weighted average execution price
            - arrival_price: Reference price
            - slippage_abs: Absolute slippage in price units
            - slippage_pct: Slippage as percentage of arrival price
            - slippage_bps: Slippage in basis points
            - worst_price: Worst single execution price
            - best_price: Best single execution price
    """
    if len(executed_prices) == 0 or len(executed_quantities) == 0:
        return {
            "vwap": np.nan,
            "arrival_price": arrival_price,
            "slippage_abs": 0,
            "slippage_pct": 0,
            "slippage_bps": 0,
            "worst_price": np.nan,
            "best_price": np.nan,
        }

    executed_prices = np.asarray(executed_prices, dtype=float)
    executed_quantities = np.asarray(executed_quantities, dtype=float)

    # VWAP
    total_qty = executed_quantities.sum()
    if total_qty > 0:
        vwap = (executed_prices * executed_quantities).sum() / total_qty
    else:
        vwap = np.nan

    # Slippage
    slippage_abs = vwap - arrival_price
    slippage_pct = slippage_abs / arrival_price if arrival_price != 0 else 0
    slippage_bps = slippage_pct * 10000

    return {
        "vwap": vwap,
        "arrival_price": arrival_price,
        "slippage_abs": slippage_abs,
        "slippage_pct": slippage_pct,
        "slippage_bps": slippage_bps,
        "worst_price": executed_prices.max(),
        "best_price": executed_prices.min(),
    }


def implementation_shortfall(
    intended_price: float,
    intended_quantity: float,
    executed_prices: np.ndarray,
    executed_quantities: np.ndarray,
    benchmark_price_final: Optional[float] = None,
) -> Dict[str, float]:
    """
    Decompose total execution cost (implementation shortfall) into components.

    Implementation shortfall (Perold 1988) = Cost vs. pre-trade price
                                           = (Cost vs. decision price)
                                           + (Decision price drift)

    Components:
    1. Execution shortfall: (Execution price - Arrival price) * qty
    2. Opportunity cost: How much price moved while we were executing
    3. Market impact: Price moved because of our order

    Args:
        intended_price: Decision/intention price
        intended_quantity: Intended quantity to execute
        executed_prices: Array of execution prices
        executed_quantities: Array of quantities at each price
        benchmark_price_final: Final benchmark price (end of execution window).
                              If None, uses final executed price.

    Returns:
        Dictionary with cost components (all in price units):
            - cost_vs_intention: Total cost vs. intended price
            - execution_cost: Cost from actual execution price vs. intention
            - benchmark_cost: Cost from price drift during execution
            - opportunity_cost: Potential benefit/loss from delayed execution
            - total_cost: Total implementation shortfall
            - cost_pct: Cost as % of intended price
            - cost_bps: Cost in basis points
    """
    if len(executed_prices) == 0:
        return {
            "cost_vs_intention": 0,
            "execution_cost": 0,
            "benchmark_cost": 0,
            "opportunity_cost": 0,
            "total_cost": 0,
            "cost_pct": 0,
            "cost_bps": 0,
        }

    executed_prices = np.asarray(executed_prices, dtype=float)
    executed_quantities = np.asarray(executed_quantities, dtype=float)

    total_qty_executed = executed_quantities.sum()
    if total_qty_executed == 0:
        return {
            "cost_vs_intention": 0,
            "execution_cost": 0,
            "benchmark_cost": 0,
            "opportunity_cost": 0,
            "total_cost": 0,
            "cost_pct": 0,
            "cost_bps": 0,
        }

    # Execution cost: difference between what we paid vs. intention price
    vwap = (executed_prices * executed_quantities).sum() / total_qty_executed
    execution_cost = (vwap - intended_price) * total_qty_executed

    # Benchmark cost: price drift from intention price to final price
    if benchmark_price_final is None:
        benchmark_price_final = executed_prices[-1]

    benchmark_cost = (benchmark_price_final - intended_price) * (
        intended_quantity - total_qty_executed
    )

    # Opportunity cost: what we didn't execute
    opportunity_cost = (benchmark_price_final - intended_price) * (
        intended_quantity - total_qty_executed
    )

    # Total implementation shortfall
    total_cost = execution_cost + opportunity_cost

    # As percentage
    cost_pct = total_cost / (intended_price * intended_quantity) if intended_price != 0 else 0
    cost_bps = cost_pct * 10000

    return {
        "cost_vs_intention": execution_cost,
        "execution_cost": execution_cost,
        "benchmark_cost": benchmark_cost,
        "opportunity_cost": opportunity_cost,
        "total_cost": total_cost,
        "cost_pct": cost_pct,
        "cost_bps": cost_bps,
    }


def maker_taker_analysis(
    trades_df: pd.DataFrame,
    freq: str = "1h",
) -> pd.DataFrame:
    """
    Analyze maker vs. taker volume and costs over time.

    Takers are aggressive traders hitting existing orders (pay fee).
    Makers provide liquidity resting on books (often receive fee).

    Args:
        trades_df: DataFrame with columns [timestamp, price, qty, is_buyer_maker]
        freq: Pandas frequency for aggregation

    Returns:
        DataFrame with columns:
            - maker_volume: Volume from maker orders (liquidity providing)
            - taker_volume: Volume from taker orders (liquidity taking)
            - maker_count: Number of maker trades
            - taker_count: Number of taker trades
            - maker_price: Average price paid by makers
            - taker_price: Average price paid by takers
            - taker_cost: Extra cost for takers (vs. makers)
            - taker_cost_bps: Taker cost in basis points
    """
    df = trades_df.copy()
    df = df.set_index("timestamp")

    results = []

    for period_end, group in df.resample(freq):
        if group.empty:
            continue

        maker_mask = group["is_buyer_maker"]
        taker_mask = ~group["is_buyer_maker"]

        maker_vol = group.loc[maker_mask, "qty"].sum()
        taker_vol = group.loc[taker_mask, "qty"].sum()
        total_vol = maker_vol + taker_vol

        # Average price
        maker_price = (
            (group.loc[maker_mask, "price"] * group.loc[maker_mask, "qty"]).sum() / maker_vol
            if maker_vol > 0
            else np.nan
        )
        taker_price = (
            (group.loc[taker_mask, "price"] * group.loc[taker_mask, "qty"]).sum() / taker_vol
            if taker_vol > 0
            else np.nan
        )

        # Cost differential
        if not np.isnan(maker_price) and not np.isnan(taker_price):
            # Takers pay more (typically) because they hit the ask
            taker_cost_abs = taker_price - maker_price
            mid_price = (maker_price + taker_price) / 2
            taker_cost_bps = (taker_cost_abs / mid_price * 10000) if mid_price != 0 else 0
        else:
            taker_cost_abs = 0
            taker_cost_bps = 0

        results.append({
            "timestamp": period_end,
            "maker_volume": maker_vol,
            "taker_volume": taker_vol,
            "maker_count": maker_mask.sum(),
            "taker_count": taker_mask.sum(),
            "maker_price": maker_price,
            "taker_price": taker_price,
            "taker_cost_abs": taker_cost_abs,
            "taker_cost_bps": taker_cost_bps,
        })

    result_df = pd.DataFrame(results)
    if result_df.empty:
        logger.warning("No trades found for maker/taker analysis")
        return pd.DataFrame()

    result_df = result_df.set_index("timestamp")
    return result_df


def optimal_execution_schedule(
    total_quantity: float,
    urgency_hours: float = 1.0,
    volatility: float = 0.01,
    avg_hourly_volume: float = 1000000,
    starting_price: float = 1.0,
) -> Dict[str, any]:
    """
    Suggest optimal execution schedule using simplified Almgren-Chriss model.

    The Almgren-Chriss (2001) framework balances execution costs:
    - Market impact: cost increases with execution speed (nonlinear)
    - Timing risk: cost from price moves while executing (increases with delay)

    This implementation uses a simplified discrete version suitable for
    cryptocurrency markets.

    Args:
        total_quantity: Total quantity to execute
        urgency_hours: Time horizon for execution (hours)
        volatility: Daily volatility (e.g., 0.01 = 1% per day)
        avg_hourly_volume: Typical hourly traded volume
        starting_price: Starting price (for cost estimation)

    Returns:
        Dictionary with:
            - schedule: List of {hour: quantity_to_trade}
            - total_impact_bps: Estimated total impact in basis points
            - execution_recommendation: String description
    """
    # Simple model: compute participation rate vs. typical volume
    participation_rate = total_quantity / (avg_hourly_volume * urgency_hours)

    # Impact coefficients (simplified Almgren-Chriss)
    # Market impact grows with participation rate: impact ~ (qty/V)^2
    # Timing risk: grows with squared execution time
    lambda_param = 0.1  # Price impact parameter
    gamma_param = 0.01  # Timing risk parameter (volatility-dependent)

    # Optimal strategy depends on participation rate
    if participation_rate < 0.1:
        # Small order: execute quickly
        schedule_type = "aggressive_execute_fast"
        n_intervals = max(1, int(urgency_hours))
        qty_per_interval = total_quantity / n_intervals
    elif participation_rate < 0.3:
        # Medium order: linear VWAP
        schedule_type = "vwap_linear"
        n_intervals = max(2, int(urgency_hours * 2))
        qty_per_interval = total_quantity / n_intervals
    else:
        # Large order: start slow, ramp up (front-load to minimize timing risk)
        schedule_type = "vwap_front_loaded"
        n_intervals = max(3, int(urgency_hours * 4))
        # Allocate more to early intervals
        weights = np.linspace(1, 0.5, n_intervals)
        weights = weights / weights.sum()
        qty_per_interval = total_quantity * weights

    # Estimate costs
    # Market impact: linear in participation
    market_impact_bps = (
        lambda_param * participation_rate * 10000
    )

    # Timing risk: from price volatility
    # Increases with time horizon and volatility
    time_risk_bps = (
        gamma_param * (urgency_hours ** 0.5) * (volatility * 100) * 10000
    )

    total_impact_bps = market_impact_bps + time_risk_bps

    # Build schedule
    schedule = []
    if isinstance(qty_per_interval, np.ndarray):
        for i, qty in enumerate(qty_per_interval):
            schedule.append({
                "hour": i,
                "quantity": qty,
                "estimated_price": starting_price * (1 + 0.001 * i),  # Simple model
            })
    else:
        for i in range(n_intervals):
            schedule.append({
                "hour": i,
                "quantity": qty_per_interval,
                "estimated_price": starting_price * (1 + 0.001 * i),
            })

    recommendation = (
        f"{schedule_type.upper()}: Split {total_quantity:.0f} units "
        f"over {urgency_hours} hours. "
        f"Estimated cost: {total_impact_bps:.0f} bps. "
        f"Participation rate: {participation_rate:.1%}. "
        f"Follow {n_intervals} execution intervals."
    )

    return {
        "schedule": schedule,
        "n_intervals": n_intervals,
        "schedule_type": schedule_type,
        "participation_rate": participation_rate,
        "market_impact_bps": market_impact_bps,
        "timing_risk_bps": time_risk_bps,
        "total_impact_bps": total_impact_bps,
        "execution_recommendation": recommendation,
    }
