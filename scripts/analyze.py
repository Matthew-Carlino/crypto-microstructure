#!/usr/bin/env python
"""
CLI tool for comprehensive market microstructure analysis.

Usage:
    python scripts/analyze.py --symbol BTCUSDT --start 2025-01-01 --end 2025-01-31 --output results/

Options:
    --symbol: Trading pair (e.g., BTCUSDT)
    --start: Start date as YYYY-MM-DD
    --end: End date as YYYY-MM-DD
    --output: Output directory for results
    --metrics: Specific metrics to compute (spread, vpin, kyle_lambda, roll, ofi, tca)
    --freq: Time frequency for aggregation (1min, 5min, 1h, etc.)
    --loglevel: Logging level (DEBUG, INFO, WARNING, ERROR)
"""

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from src.data_loader import BinanceTradeLoader
from src.microstructure import (
    autocorrelation_analysis,
    compute_kyle_lambda,
    compute_roll_spread,
    compute_spreads,
    compute_vpin,
    order_flow_imbalance,
)
from src.tca import maker_taker_analysis
from src.visualization import (
    plot_intraday_spread,
    plot_maker_taker_analysis,
    plot_order_flow_heatmap,
    plot_price_impact,
    plot_vpin_timeseries,
)

logger = logging.getLogger(__name__)


def setup_logging(level: str) -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def run_analysis(
    symbol: str,
    start: str,
    end: str,
    output_dir: Path,
    metrics: list,
    freq: str,
) -> None:
    """
    Run complete microstructure analysis.

    Args:
        symbol: Trading pair (e.g., BTCUSDT)
        start: Start date YYYY-MM-DD
        end: End date YYYY-MM-DD
        output_dir: Output directory
        metrics: List of metrics to compute
        freq: Aggregation frequency
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    logger.info(f"Loading {symbol} trades from {start} to {end}")
    loader = BinanceTradeLoader()
    trades = loader.load_cached_trades(symbol, start, end)

    if trades.empty:
        logger.error(f"No trades found for {symbol}")
        return

    logger.info(f"Loaded {len(trades)} trades")

    # Store metadata
    metadata = {
        "symbol": symbol,
        "start": start,
        "end": end,
        "n_trades": len(trades),
        "date_range": f"{trades['timestamp'].min()} to {trades['timestamp'].max()}",
        "price_range": f"{trades['price'].min():.2f} to {trades['price'].max():.2f}",
        "total_volume": trades['qty'].sum(),
    }
    logger.info(f"Metadata: {metadata}")

    # Compute spreads
    if "spread" in metrics:
        logger.info("Computing spreads...")
        spreads = compute_spreads(trades, freq=freq)
        if not spreads.empty:
            spreads.to_csv(output_dir / "spreads.csv")
            logger.info(f"Mean effective spread: {spreads['effective_spread'].mean():.4f}")

            # Plot
            fig = plot_intraday_spread(spreads)
            if fig:
                fig.savefig(output_dir / "spreads.png", dpi=100, bbox_inches="tight")
                logger.info("Saved spreads plot")

    # Compute VPIN
    if "vpin" in metrics:
        logger.info("Computing VPIN...")
        vpin = compute_vpin(trades, bucket_size=100000)
        if not vpin.empty:
            vpin_df = pd.DataFrame({"vpin": vpin})
            vpin_df.to_csv(output_dir / "vpin.csv")
            logger.info(f"VPIN range: [{vpin.min():.3f}, {vpin.max():.3f}]")

            # Plot
            fig = plot_vpin_timeseries(vpin, price_series=trades.set_index("timestamp")["price"])
            if fig:
                fig.savefig(output_dir / "vpin.png", dpi=100, bbox_inches="tight")
                logger.info("Saved VPIN plot")

    # Compute Kyle's lambda
    if "kyle_lambda" in metrics:
        logger.info("Computing Kyle's lambda...")
        kyle = compute_kyle_lambda(trades, freq=freq)
        if not kyle.empty:
            kyle.to_csv(output_dir / "kyle_lambda.csv")
            logger.info(f"Mean Kyle's lambda: {kyle['kyle_lambda'].mean():.6f}")

    # Compute Roll spread
    if "roll" in metrics:
        logger.info("Computing Roll spread estimator...")
        roll = compute_roll_spread(trades, freq=freq)
        if not roll.empty:
            roll.to_csv(output_dir / "roll_spread.csv")
            logger.info(f"Mean Roll spread: {roll['roll_spread'].mean():.4f}")

    # Compute order flow imbalance
    if "ofi" in metrics:
        logger.info("Computing order flow imbalance...")
        ofi = order_flow_imbalance(trades, freq=freq)
        if not ofi.empty:
            ofi.to_csv(output_dir / "ofi.csv")
            logger.info(f"Mean OFI: {ofi['ofi'].mean():.4f}")

            # Plot heatmap
            fig = plot_order_flow_heatmap(ofi)
            if fig:
                fig.savefig(output_dir / "ofi_heatmap.png", dpi=100, bbox_inches="tight")
                logger.info("Saved OFI heatmap")

            # Plot scatter
            fig = plot_price_impact(trades, freq=freq)
            if fig:
                fig.savefig(output_dir / "price_impact.png", dpi=100, bbox_inches="tight")
                logger.info("Saved price impact plot")

    # Maker vs. taker analysis
    if "tca" in metrics:
        logger.info("Computing maker/taker analysis...")
        mt = maker_taker_analysis(trades, freq=freq)
        if not mt.empty:
            mt.to_csv(output_dir / "maker_taker.csv")
            logger.info(
                f"Taker cost premium: {mt['taker_cost_bps'].mean():.1f} bps on average"
            )

            # Plot
            fig = plot_maker_taker_analysis(mt)
            if fig:
                fig.savefig(output_dir / "maker_taker.png", dpi=100, bbox_inches="tight")
                logger.info("Saved maker/taker plot")

    # Trade sign autocorrelation
    logger.info("Computing trade sign autocorrelation...")
    autocorr = autocorrelation_analysis(trades, lags=20)
    logger.info(
        f"Mean autocorrelation: {autocorr['mean_autocorr']:.4f} "
        f"(Pattern: {autocorr['dominant_pattern']})"
    )

    # Save summary
    summary = {
        "metadata": metadata,
        "vpin": {
            "min": compute_vpin(trades).min(),
            "max": compute_vpin(trades).max(),
        } if "vpin" in metrics else None,
        "autocorrelation": {
            "mean": float(autocorr["mean_autocorr"]),
            "dominant_pattern": autocorr["dominant_pattern"],
        },
    }

    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    logger.info(f"Analysis complete. Results saved to {output_dir}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Cryptocurrency Market Microstructure Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--symbol", required=True, help="Trading pair (e.g., BTCUSDT)")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", default="results/", help="Output directory")
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=["spread", "vpin", "kyle_lambda", "ofi", "tca"],
        help="Metrics to compute",
    )
    parser.add_argument("--freq", default="1h", help="Aggregation frequency (1min, 5min, 1h, etc.)")
    parser.add_argument("--loglevel", default="INFO", help="Logging level")

    args = parser.parse_args()

    setup_logging(args.loglevel)
    logger.info(f"Starting analysis: {args.symbol} ({args.start} to {args.end})")

    try:
        run_analysis(
            symbol=args.symbol,
            start=args.start,
            end=args.end,
            output_dir=args.output,
            metrics=args.metrics,
            freq=args.freq,
        )
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
