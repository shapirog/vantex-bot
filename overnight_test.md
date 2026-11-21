# Strategy A - overnight bias - test - 2026-01-01 to 2026-11-10

Each month about 218.2 of 1967.7 eligible stocks passed the overnight-bias test. Trades: buy at the close, sell at the next open, every session. 48837 stock-nights at the lowest cost.

| run | days | total return | Sharpe | max drawdown | beta vs SPY | avg invested | by year |
|---|---|---|---|---|---|---|---|
| signal@0.05% | 216 | -5.6% | -0.47 | 13.5% | -0.079 | 100.0% | 2026: -5.6% |
| signal@0.25% | 216 | -60.2% | -8.35 | 60.8% | -0.079 | 100.0% | 2026: -60.2% |
| signal@0.50% | 216 | -86.5% | -18.25 | 86.6% | -0.078 | 100.0% | 2026: -86.5% |
| placebo@0.05% | 216 | -9.5% | -1.08 | 12.2% | -0.071 | 100.0% | 2026: -9.5% |
| placebo@0.25% | 216 | -61.8% | -10.9 | 62.0% | -0.07 | 100.0% | 2026: -61.8% |
| placebo@0.50% | 216 | -87.0% | -23.24 | 87.0% | -0.07 | 100.0% | 2026: -87.0% |
| signal@gross | 216 | +17.1% | 1.5 | 9.4% | -0.079 | 100.0% | 2026: +17.1% |
| SPY buy and hold | 216 | +10.8% | 0.93 | 8.9% | 1.0 | 100.0% | 2026: +10.8% |

Average stock-night return with the 10 best removed (0.05% cost): -0.0401%.
Placebo = same number of random eligible stocks each month. A real signal should clearly beat its placebo at the same cost.

## Data limits

- Point-in-time universe: Alpaca active + inactive symbols only; stocks delisted long ago or renamed may be missing (survivorship risk).
- Prices are adjusted with today's split/dividend factors, not as-traded; overnight returns over dividend dates are approximated.
- Inactive (delisted) symbols in the universe: 1001 of 6414.
- Fills assume the official close and next official open (auction prices); real market-on-close / market-on-open fills can differ.
