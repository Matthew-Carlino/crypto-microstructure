# Cryptocurrency Market Microstructure Analysis Toolkit

A Python toolkit for analyzing cryptocurrency market microstructure using publicly available trade data. This project demonstrates fundamental concepts in market microstructure, transaction cost analysis (TCA), and order flow dynamics through empirical analysis of Binance trading data.

## Motivation

Market microstructure is the study of the structure and functioning of securities markets — how prices are determined, how information is incorporated, and how trading costs arise. This toolkit applies classical microstructure theory to modern cryptocurrency markets, enabling researchers and traders to quantify spread dynamics, identify toxic order flow, and measure execution quality.

## Key Features

- **Microstructure Metrics**: Effective spread, realized spread, price impact, Kyle's lambda, Roll's estimator, Volume-Synchronized Probability of Informed Trading (VPIN)
- **Order Flow Analysis**: Order flow imbalance, trade sign autocorrelation, asymmetric information detection
- **Transaction Cost Analysis (TCA)**: Arrival price slippage, implementation shortfall decomposition, maker vs. taker analysis
- **Data Pipeline**: Automatic historical trade fetching from Binance public API, caching, efficient processing
- **Visualization**: Intraday spread patterns, VPIN time series, order flow heatmaps, price impact scatter plots
- **Optimal Execution**: Simplified Almgren-Chriss style execution schedule recommendations

## Data Source

This project uses publicly available Binance `/api/v3/aggTrades` endpoint — **no API key required**. Data is cached locally in Parquet format for efficient reuse.

## Installation

```bash
git clone https://github.com/yourusername/crypto-microstructure.git
cd crypto-microstructure
pip install -r requirements.txt
```

## Quick Start

### Using the CLI

```bash
# Analyze BTC-USDT for January 2025
python scripts/analyze.py --symbol BTCUSDT --start 2025-01-01 --end 2025-01-31 --output results/

# Analyze with custom metrics
python scripts/analyze.py --symbol ETHUSDT --start 2025-02-01 --end 2025-02-07 \
  --metrics spread vpin kyle_lambda --freq 5min
```

### Using Python API

```python
from src.data_loader import BinanceTradeLoader
from src.microstructure import compute_spreads, compute_vpin, order_flow_imbalance
import pandas as pd

# Load trades
loader = BinanceTradeLoader()
trades = loader.load_cached_trades('BTCUSDT', start='2025-01-01', end='2025-01-31')

# Compute microstructure metrics
spreads = compute_spreads(trades, freq='1min')
vpin = compute_vpin(trades, bucket_size=50)
ofi = order_flow_imbalance(trades, freq='5min')

print(f"Mean effective spread: {spreads['effective_spread'].mean():.2%}")
print(f"VPIN range: [{vpin.min():.3f}, {vpin.max():.3f}]")
```

### Jupyter Notebook Analysis

```bash
jupyter notebook notebooks/analysis.ipynb
```

The notebook includes end-to-end analysis with intraday pattern discovery, VPIN interpretation, and practical TCA examples.

## Methodology

### Core Metrics

**Effective Spread**: The difference between execution price and the midpoint, normalized by midpoint. Captures realized execution costs.

**Realized Spread**: The difference between execution price and the subsequent short-term midpoint, identifying if traders pay price impact (adverse selection) or benefit from momentum.

**Kyle's Lambda**: Price impact per unit of signed order flow (Kyle 1985). Estimated as the slope in a regression of price changes on buy/sell imbalance.

**Roll's Spread**: Econometric estimator of the bid-ask spread from observed prices alone, based on price covariance structure (Roll 1984).

**VPIN (Volume-Synchronized Probability of Informed Trading)**: Measures the probability that a given dollar volume of trading originates from informed traders. Uses a simple cutoff rule on order flow imbalance within buckets of equal signed volume (Easley et al. 2012).

**Order Flow Imbalance (OFI)**: Ratio of signed buy volume to total volume within a period. Positive values indicate buyer aggression.

**Trade Sign Autocorrelation**: Examines whether buy/sell signs are serially correlated, indicating microstructure noise (mean reversion) or momentum.

### References

- Kyle, A. S. (1985). "Continuous Auctions and Insider Trading." Econometrica.
- Roll, R. (1984). "A Simple Implicit Measure of the Effective Bid-Ask Spread in an Efficient Market." Journal of Finance.
- Easley, D., López de Prado, M. M., & O'Hara, M. (2012). "Flow Toxicity and Liquidity in a High-Frequency World." Review of Financial Studies.
- Almgren, R., & Chriss, N. (2001). "Optimal Execution of Portfolio Transactions." Journal of Risk.

## Project Structure

```
crypto-microstructure/
├── README.md                      # This file
├── requirements.txt               # Python dependencies
├── src/
│   ├── __init__.py
│   ├── data_loader.py            # Binance data fetching and caching
│   ├── microstructure.py         # Core microstructure metrics
│   ├── tca.py                    # Transaction cost analysis
│   └── visualization.py          # Plotting utilities
├── scripts/
│   └── analyze.py                # CLI entry point
├── notebooks/
│   └── analysis.ipynb            # Full end-to-end analysis notebook
├── tests/
│   └── test_microstructure.py    # Unit tests
├── data/                         # Local cache (ignored by git)
└── results/                      # Output directory

```

## Example Output

Running the analysis produces:

- **Microstructure metrics** (CSV): spread, price impact, Kyle's lambda by time interval
- **Visualizations** (PNG): intraday spread patterns, VPIN time series, order flow heatmaps
- **TCA summary** (JSON): cost decomposition, maker/taker comparison, execution quality metrics

See `results/` for example outputs.

## Testing

```bash
pytest tests/ -v
```

## Notes for Quant Interviews

This toolkit demonstrates:

1. **Market Microstructure Theory**: Implementation of classical metrics (Kyle, Roll, VPIN) with proper academic attribution
2. **Data Engineering**: Efficient caching, pagination, rate limit handling, vectorized pandas operations
3. **Statistical Rigor**: Proper aggregation, survivor bias awareness, event study design
4. **Clean Code**: Type hints, docstrings, logging, PEP 8 compliance, testability
5. **Domain Knowledge**: Understanding of maker/taker dynamics, order flow toxicity, execution costs in real markets

The project is intentionally focused on **analysis and research**, not trading strategies, showing that the author understands the difference between measurement and prediction.

## License

MIT

## Contact

For questions or collaboration: matthew@example.com
