# Strategy A - overnight bias - dev - 2023-06-01 to 2025-12-31

Each month about 215.0 of 1565.0 eligible stocks passed the overnight-bias test. Trades: buy at the close, sell at the next open, every session. 145525 stock-nights at the lowest cost.

| run | days | total return | Sharpe | max drawdown | beta vs SPY | avg invested | by year |
|---|---|---|---|---|---|---|---|
| signal@0.05% | 649 | -3.5% | -0.04 | 22.0% | 0.054 | 98.4% | 2023: -1.4%, 2024: +2.8%, 2025: -4.8% |
| signal@0.25% | 649 | -92.5% | -7.64 | 92.6% | 0.055 | 98.4% | 2023: -42.9%, 2024: -62.5%, 2025: -65.0% |
| signal@0.50% | 649 | -99.7% | -17.15 | 99.7% | 0.057 | 98.4% | 2023: -71.1%, 2024: -89.4%, 2025: -90.0% |
| placebo@0.05% | 649 | -24.3% | -0.89 | 27.0% | 0.056 | 98.4% | 2023: -9.5%, 2024: -0.5%, 2025: -16.0% |
| placebo@0.25% | 649 | -94.1% | -9.54 | 94.1% | 0.057 | 98.4% | 2023: -47.6%, 2024: -63.7%, 2025: -69.1% |
| placebo@0.50% | 649 | -99.8% | -20.3 | 99.8% | 0.058 | 98.4% | 2023: -73.5%, 2024: -89.7%, 2025: -91.1% |
| signal@gross | 649 | +82.8% | 1.86 | 17.5% | 0.054 | 100.0% | 2023: +13.0%, 2024: +32.2%, 2025: +22.3% |
| SPY buy and hold | 649 | +69.1% | 1.4 | 18.8% | 1.0 | 100.0% | 2023: +15.0%, 2024: +24.9%, 2025: +17.7% |

Average stock-night return with the 10 best removed (0.05% cost): -0.0576%.
Placebo = same number of random eligible stocks each month. A real signal should clearly beat its placebo at the same cost.

## Data limits

- Point-in-time universe: Alpaca active + inactive symbols only; stocks delisted long ago or renamed may be missing (survivorship risk).
- Prices are adjusted with today's split/dividend factors, not as-traded; overnight returns over dividend dates are approximated.
- Inactive (delisted) symbols in the universe: 1001 of 6414.
- Fills assume the official close and next official open (auction prices); real market-on-close / market-on-open fills can differ.
