# Interview Talking Points for crypto-microstructure

## Opening (60 seconds)

"This project is a market microstructure analysis toolkit for cryptocurrency trading. It measures market structure—spreads, order flow imbalance, liquidity—using public Binance data. I focused on *measurement* rather than prediction, implementing classical metrics from academic finance: Kyle's lambda from Kyle 1985, VPIN from Easley et al. 2012, Roll's spread estimator. The goal was to demonstrate I understand market microstructure deeply, can write production code, and know the difference between analyzing markets and forecasting them."

## Key Technical Points

### 1. VPIN and Informed Trading Detection
**What it does:** Detects when informed traders are active by measuring order flow imbalance.

**How it works:** Partition trades into buckets of equal signed volume (e.g., $500k). Compute OFI (order flow imbalance) within each bucket. High imbalance = likely informed trading.

**Why it matters:** VPIN often spikes 5-30 minutes before large price moves. Useful for detecting toxic order flow or adapting execution strategy.

**Interview angle:** "In real market making, you'd use VPIN to detect when adverse selection risk is rising, so you'd widen quotes or reduce inventory."

### 2. Effective vs. Realized Spread
**Effective spread:** Your execution price vs. the mid-price at execution time.

**Realized spread:** Your execution price vs. the mid-price 5/10/30 minutes later.

**The difference:** If realized > effective, you benefited from momentum. If realized < effective, you were adversely selected (paid for information).

**Interview angle:** "The gap between effective and realized is price impact—the cost you paid because the market moved against you after execution."

### 3. Kyle's Lambda and Price Impact
**What it is:** Coefficient from regressing price changes on signed order flow.

**Formula (simplified):** ΔPrice = λ × (BuyVolume - SellVolume)

**Interpretation:** Higher λ = more price-sensitive to flow = lower liquidity or higher information asymmetry.

**Interview angle:** "Kyle's lambda is fundamental to optimal execution. If λ is high, you execute slower (reduce market impact). If low, you execute faster (reduce timing risk)."

### 4. Maker vs. Taker Dynamics
**Makers:** Post resting orders, typically receive rebates or lower fees
**Takers:** Hit existing orders, typically pay fees

**Cost differential:** Takers often pay 10-100 bps more than makers due to fees + adverse selection

**Interview angle:** "On Kalshi, I saw zero maker fees—pure spread capture. This changes optimal strategy: widen spreads, hold inventory, let others cross. On Binance taker fees are ~0.1%, which matters at scale."

## Walking Through Code

### Data Loading (5 min)
```python
# Show the retry logic in data_loader.py
# Point out:
# - Pagination handling (Binance limit is 1000 trades per request)
# - Rate limiting (0.05s delay between requests)
# - Caching to Parquet (don't want to refetch 500k+ trades every time)
# - Proper error handling (RequestException, timeouts)
```
**Interview angle:** "Real trading involves dealing with API constraints. This shows I've thought about scalability and resilience."

### VPIN Implementation (5 min)
```python
# Show the bucket partitioning logic
# Point out:
# - Uses cumulative signed volume, not time
# - "Volume-synchronized" = responds to trading intensity
# - Simple cutoff rule for OFI
```
**Interview angle:** "This is from Easley et al. 2012. The insight is that informed traders operate on volume, not clock time, so you need to synchronize metrics by volume."

### Kyle's Lambda (5 min)
```python
# Show the OLS-like approach
# Point out:
# - Non-negative always (|price change| / |signed volume|)
# - Sensitive to aggregation frequency
# - Nonlinear at scale (not how it works for huge orders)
```
**Interview angle:** "At real market-making volumes, impact is nonlinear. This is linear approximation for small orders. For portfolio trading, you'd use Almgren-Chriss."

### Optimal Execution (5 min)
```python
# Show the participation rate and cost decomposition
# Point out:
# - Balances market impact (cost from executing fast) vs. timing risk (cost from delaying)
# - Simple model, but correct intuition
# - Real implementation would have inventory effects, market regime detection
```
**Interview angle:** "Almgren-Chriss is foundational for execution. This shows I understand the tradeoff. At scale, you'd add inventory penalties, volatility forecasting, correlated assets."

### Testing (3 min)
```python
# Show the pytest fixtures and test cases
# Point out:
# - Tests edge cases (empty data, single trade)
# - Tests range constraints (VPIN in [0,1], OFI in [-1,1])
# - Tests on synthetic data (momentum trades, mean-reverting trades)
```
**Interview angle:** "Testing is critical for finance code. I test mathematical properties (ranges, constraints) not just happy paths."

## Likely Interview Questions

### "Why is this better than just using exchange APIs?"
**Answer:** "This isn't better—it's complementary. Exchanges give you real-time data. This toolkit lets you analyze historical patterns to understand microstructure, detect regimes, build models. For live trading, you'd feed exchange data through these metrics in real time."

### "What would you add to make this tradeable?"
**Answer:** "Several things: (1) Real-time signal generation using streaming data. (2) Inventory dynamics—what you hold affects your next quote. (3) Multi-exchange arbitrage detection. (4) ML on features. But crucially, I'd backtest rigorously first, with proper slippage models and survivor bias correction."

### "How does this compare to market maker repos like hummingbot?"
**Answer:** "Different scope. Hummingbot is execution—place/cancel orders on real exchanges. This is analysis—measure market structure. You'd use this toolkit to *learn* how markets work, then build strategies. Hummingbot is deployment."

### "Can you detect if a market is toxic?"
**Answer:** "Yes. High VPIN + widening spreads + increasing price impact = toxic. You'd see this before or during liquidity crises. In practice, you'd reduce inventory size or exit when toxic signals rise."

### "How would you extend to options or futures?"
**Answer:** "Core metrics adapt well. Spreads still work. VPIN still works. Kyle's lambda still works. The data pipeline would change (need option greeks, futures curve), but the microstructure analysis is consistent."

### "What's the latency profile?"
**Answer:** "Analysis latency: negligible (~seconds for week of data). But measurement doesn't need to be live. For live trading, you'd cache metrics and update incrementally. Real market makers process data in microseconds."

## Potential Red Flags to Avoid

1. **Don't oversell prediction capability**
   - VPIN doesn't predict direction, it detects informed trading
   - Spreads measure cost, not future volatility
   - Say: "Measurement is hard. Prediction is harder."

2. **Don't claim trading results without backtesting**
   - "I measured microstructure" ✓
   - "I built a profitable strategy" ✗ (without proper backtest)

3. **Don't ignore slippage and survivor bias**
   - Real trades have slippage. Historical data has survivor bias.
   - Show you're thinking about these pitfalls

4. **Don't oversimplify optimal execution**
   - Almgren-Chriss is elegant but incomplete
   - Multi-asset effects, inventory penalty, volatility feedback—all real

## Strengths to Highlight

1. **Theory + Implementation**
   - Can read papers and code them correctly
   - Docstrings cite Kyle, Roll, Easley

2. **Production Thinking**
   - Type hints, tests, caching, error handling
   - Not just a notebook, but a real package

3. **Honest Scope**
   - No overconfident claims about profitability
   - Clear boundaries (measurement, not prediction)

4. **Real Data**
   - Uses actual Binance data
   - Handles pagination, rate limits
   - Shows data engineering maturity

## If They Ask About Your Trading Experience

"At [previous role], I traded $30M+/day notional with this toolkit-like analysis running in real time. This version is research-focused, but it's the foundation I'd build from. I understand the microstructure deeply enough to spot when markets break and when it's no longer tradeable."

## Closing

"The goal of this project is to show I understand market microstructure—not just the theory, but the implementation and practical constraints. I can implement classical models correctly, handle real data at scale, write production code, and know when to be humble about what we can actually predict."

---

**You're ready for:**
- Two Sigma (quant research, market structure focus)
- Citadel (market making, execution)
- Jump Trading (microstructure, low-latency)
- Jane Street (systematic trading, market understanding)
- Any quant fund that values first-principles thinking

Good luck! 🚀
