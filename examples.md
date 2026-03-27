# Usage Examples

## 1. Command-Line Analysis

### Analyze BTC-USDT with all metrics
```bash
python scripts/analyze.py --symbol BTCUSDT --start 2025-02-01 --end 2025-02-08
```

### Output
- `results/spreads.csv` — Time series of spread metrics
- `results/vpin.csv` — VPIN values per trade
- `results/ofi.csv` — Order flow imbalance
- `results/kyle_lambda.csv` — Kyle's lambda coefficient
- `results/maker_taker.csv` — Maker/taker volume and costs
- `results/summary.json` — Summary statistics
- `results/*.png` — Publication-quality visualizations

### Specific metrics only
```bash
python scripts/analyze.py --symbol ETHUSDT --start 2025-02-01 --end 2025-02-07 \
  --metrics spread vpin ofi --freq 5min
```

## 2. Python API Usage

### Load and analyze data
```python
from src.data_loader import BinanceTradeLoader
from src.microstructure import compute_spreads, compute_vpin, order_flow_imbalance

# Load trades
loader = BinanceTradeLoader()
trades = loader.load_cached_trades('BTCUSDT', start='2025-02-01', end='2025-02-08')

# Compute metrics
spreads = compute_spreads(trades, freq='1h')
vpin = compute_vpin(trades, bucket_size=500000)
ofi = order_flow_imbalance(trades, freq='5min')

print(f"Mean spread: {spreads['effective_spread'].mean():.4f}")
print(f"VPIN range: [{vpin.min():.3f}, {vpin.max():.3f}]")
print(f"Mean OFI: {ofi['ofi'].mean():.4f}")
```

### Custom analysis
```python
from src.microstructure import autocorrelation_analysis
from src.tca import maker_taker_analysis

# Detect microstructure patterns
autocorr = autocorrelation_analysis(trades, lags=20)
print(f"Pattern: {autocorr['dominant_pattern']}")
print(f"Mean autocorrelation: {autocorr['mean_autocorr']:.4f}")

# Compare maker vs. taker costs
mt = maker_taker_analysis(trades, freq='1h')
print(f"Avg taker cost premium: {mt['taker_cost_bps'].mean():.1f} bps")
```

### Transaction cost analysis
```python
from src.tca import arrival_price_slippage, implementation_shortfall

# Simulate execution
arrival_price = 100.0
executed_prices = [100.05, 100.08, 100.10, 100.07]
executed_quantities = [0.1, 0.2, 0.15, 0.25]

# Arrival price slippage
slippage = arrival_price_slippage(executed_prices, executed_quantities, arrival_price)
print(f"VWAP: {slippage['vwap']:.2f}")
print(f"Slippage: {slippage['slippage_bps']:.1f} bps")

# Implementation shortfall
IS = implementation_shortfall(arrival_price, 1.0, executed_prices, executed_quantities)
print(f"Total cost: ${IS['total_cost']:.2f} ({IS['cost_bps']:.1f} bps)")
```

### Optimal execution
```python
from src.tca import optimal_execution_schedule

# Get execution recommendations
result = optimal_execution_schedule(
    total_quantity=100,           # 100 BTC
    urgency_hours=4,              # 4-hour execution window
    volatility=0.02,              # 2% daily volatility
    avg_hourly_volume=1000000,    # typical hourly volume
    starting_price=45000,         # current price
)

print(result['execution_recommendation'])
# Output: VWAP_FRONT_LOADED: Split 100 units over 4 hours...
```

## 3. Jupyter Notebook

Run the full interactive analysis:
```bash
jupyter notebook notebooks/analysis.ipynb
```

The notebook includes:
- Data loading and exploration
- Spread dynamics visualization
- VPIN analysis with price overlay
- Order flow heatmaps by hour/day
- Kyle's lambda over time
- Maker vs. taker patterns
- TCA examples
- Microstructure pattern detection

## 4. Testing

```bash
pytest tests/ -v
pytest tests/test_microstructure.py::TestComputeSpreads -v
```

## 5. Cache Management

Clear data cache:
```python
from src.data_loader import BinanceTradeLoader

loader = BinanceTradeLoader()
loader.clear_cache()  # Clear all
loader.clear_cache(symbol='BTCUSDT')  # Clear specific symbol
```

## 6. Advanced: Custom Metrics

Extend the framework with custom metrics:

```python
import pandas as pd
from src.microstructure import order_flow_imbalance
from src.data_loader import BinanceTradeLoader

def custom_momentum_indicator(trades_df, window=20):
    """Custom momentum indicator based on order flow."""
    ofi = order_flow_imbalance(trades_df, freq='5min')
    ofi['momentum'] = ofi['ofi'].rolling(window).mean()
    return ofi['momentum']

# Use it
loader = BinanceTradeLoader()
trades = loader.load_cached_trades('BTCUSDT', '2025-02-01', '2025-02-08')
momentum = custom_momentum_indicator(trades)
print(momentum.describe())
```

## 7. Integration with Backtesting

Use microstructure metrics as features in your own backtesting framework:

```python
from src.microstructure import compute_spreads, order_flow_imbalance
from src.data_loader import BinanceTradeLoader
import pandas as pd

# Load data
loader = BinanceTradeLoader()
trades = loader.load_cached_trades('BTCUSDT', '2025-02-01', '2025-02-08')

# Extract features
spreads = compute_spreads(trades, freq='1h')
ofi = order_flow_imbalance(trades, freq='1h')

# Merge features
features = pd.DataFrame({
    'spread': spreads['effective_spread'],
    'ofi': ofi['ofi'],
    'volume': ofi['total_volume'],
})

# Use in your strategy
# features.to_csv('market_features.csv')
```

## Performance Notes

- Data loading: ~1-2 minutes for a month of BTC-USDT trades (500k-1M trades)
- VPIN computation: ~10-30 seconds depending on bucket size
- All computations are vectorized using NumPy/Pandas for efficiency
- Parquet caching eliminates redundant API calls

## Troubleshooting

### "No trades found" error
- Check date format: must be YYYY-MM-DD
- Verify symbol exists on Binance
- Try a different date range
- Check internet connection (fetching from Binance API)

### Rate limiting
- Binance API has per-IP rate limits
- Script automatically handles retry with exponential backoff
- Caching prevents redundant requests

### Memory issues with large date ranges
- VPIN bucketing with very large buckets is memory-efficient
- For multi-month analysis, process in weekly chunks:
  ```python
  for start, end in date_ranges:
      trades = loader.load_cached_trades('BTCUSDT', start, end)
      results = process(trades)
      save_results(results)
  ```
