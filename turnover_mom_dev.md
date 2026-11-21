# Strategy B - one-month momentum x turnover (proxy) - dev - 2023-06-01 to 2025-12-31

About 61.2 stocks held each month; 1895 stock-months at the lowest cost.

| run | months | total return | Sharpe | max drawdown | beta vs SPY | avg invested | by year |
|---|---|---|---|---|---|---|---|
| signal@0.05% | 31 | -39.7% | -0.61 | 50.0% | 1.372 | 100.0% | 2023: -4.3%, 2024: -4.5%, 2025: -34.1% |
| signal@0.25% | 31 | -46.8% | -0.79 | 54.0% | 1.367 | 100.0% | 2023: -6.9%, 2024: -9.0%, 2025: -37.2% |
| signal@0.50% | 31 | -54.4% | -1.02 | 59.1% | 1.36 | 100.0% | 2023: -10.1%, 2024: -14.3%, 2025: -40.8% |
| placebo@0.05% | 31 | +49.9% | 1.01 | 16.3% | 1.122 | 100.0% | 2023: +14.8%, 2024: +11.7%, 2025: +16.9% |
| placebo@0.25% | 31 | +32.4% | 0.72 | 17.3% | 1.117 | 100.0% | 2023: +11.7%, 2024: +6.4%, 2025: +11.4% |
| placebo@0.50% | 31 | +13.4% | 0.37 | 18.5% | 1.112 | 100.0% | 2023: +7.8%, 2024: +0.2%, 2025: +4.9% |
| signal@gross | 31 | -37.9% | -0.56 | 48.9% | 1.373 | 100.0% | 2023: -3.6%, 2024: -3.3%, 2025: -33.3% |
| SPY buy and hold (same open-to-open months) | 31 | +70.0% | 1.8 | 7.8% | 1.0 | 100.0% | 2023: +14.2%, 2024: +26.4%, 2025: +17.7% |

Average stock-month return with the 10 best removed (0.05% cost): -2.5088%.
Placebo = same number of random eligible stocks each month.

## Data limits

- SUBSTITUTION: turnover = this month's volume / average monthly volume over the prior 12 months (no shares-outstanding history). Not the paper's measure.
- Point-in-time universe: Alpaca active + inactive symbols only; older delistings may be missing (survivorship risk).
- Prices adjusted with today's split/dividend factors. Delisted positions exit at the last available close (flagged in the CSV).
