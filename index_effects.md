# VANTEX City research batch 6: index-ETF timing effects

Published rules, fixed parameters, SPY/QQQ minute data (regular session only). Costs are per side; Sharpe is annualized from each effect's own trade frequency, so compare it with the buy-and-hold row, not raw totals (most of these are in the market only part of the time).

| effect | period | cost/side | trades | win rate | avg per trade | total | Sharpe | max drawdown |
|---|---|---|---|---|---|---|---|---|
| X1 SPY overnight only | dev 2023-06..2025-12 | 0.01% | 649 | 57.2% | 0.0432% | +30.87% | 1.16 | 16.5% |
| X1 SPY overnight only | dev 2023-06..2025-12 | 0.03% | 649 | 53.3% | 0.0032% | +0.95% | 0.09 | 18.2% |
| X1 SPY overnight only | test 2026 | 0.01% | 219 | 56.6% | 0.0287% | +6.12% | 0.82 | 7.5% |
| X1 SPY overnight only | test 2026 | 0.03% | 219 | 50.7% | -0.0113% | -2.78% | -0.32 | 9.0% |
| X2 QQQ overnight only | dev 2023-06..2025-12 | 0.01% | 649 | 57.6% | 0.0646% | +49.11% | 1.32 | 18.8% |
| X2 QQQ overnight only | dev 2023-06..2025-12 | 0.03% | 649 | 54.7% | 0.0246% | +15.02% | 0.5 | 20.8% |
| X2 QQQ overnight only | test 2026 | 0.01% | 219 | 53.9% | 0.0202% | +3.59% | 0.35 | 9.4% |
| X2 QQQ overnight only | test 2026 | 0.03% | 219 | 51.1% | -0.0198% | -5.1% | -0.35 | 10.5% |
| X3 SPY intraday only | dev 2023-06..2025-12 | 0.01% | 649 | 53.8% | 0.0035% | +0.18% | 0.07 | 17.5% |
| X3 SPY intraday only | dev 2023-06..2025-12 | 0.03% | 649 | 50.4% | -0.0365% | -22.72% | -0.72 | 29.7% |
| X3 SPY intraday only | test 2026 | 0.01% | 220 | 49.5% | -0.0264% | -6.12% | -0.62 | 12.9% |
| X3 SPY intraday only | test 2026 | 0.03% | 220 | 48.2% | -0.0664% | -14.02% | -1.57 | 16.6% |
| X4 SPY intraday momentum (long-only) | dev 2023-06..2025-12 | 0.01% | 389 | 44.0% | -0.0246% | -9.21% | -1.97 | 9.2% |
| X4 SPY intraday momentum (long-only) | dev 2023-06..2025-12 | 0.03% | 389 | 32.4% | -0.0646% | -22.29% | -5.18 | 22.3% |
| X4 SPY intraday momentum (long-only) | test 2026 | 0.01% | 119 | 34.5% | -0.0272% | -3.2% | -2.71 | 3.7% |
| X4 SPY intraday momentum (long-only) | test 2026 | 0.03% | 119 | 27.7% | -0.0672% | -7.7% | -6.7 | 7.7% |
| X5 SPY pre-FOMC drift | dev 2023-06..2025-12 | 0.01% | 21 | 61.9% | 0.1563% | +3.31% | 0.91 | 1.0% |
| X5 SPY pre-FOMC drift | dev 2023-06..2025-12 | 0.03% | 21 | 57.1% | 0.1162% | +2.45% | 0.67 | 1.1% |
| X5 SPY pre-FOMC drift | test 2026 | 0.01% | 7 | 42.9% | -0.1263% | -0.88% | -0.95 | 1.4% |
| X5 SPY pre-FOMC drift | test 2026 | 0.03% | 7 | 42.9% | -0.1662% | -1.16% | -1.25 | 1.6% |
| X6 volatility-managed SPY (monthly) | dev 2023-06..2025-12 | 0.01% | 31 | 74.2% | 1.5117% | +56.64% | 1.57 | 7.8% |
| X6 volatility-managed SPY (monthly) | dev 2023-06..2025-12 | 0.03% | 31 | 74.2% | 1.5084% | +56.48% | 1.57 | 7.8% |
| X6 volatility-managed SPY (monthly) | test 2026 | 0.01% | 10 | 60.0% | 1.1357% | +11.24% | 1.02 | 4.9% |
| X6 volatility-managed SPY (monthly) | test 2026 | 0.03% | 10 | 60.0% | 1.1316% | +11.2% | 1.01 | 4.9% |
| SPY buy and hold (open to open, monthly) | dev 2023-06..2025-12 | 0.00% | 31 | 74.2% | 1.7827% | +69.97% | 1.8 | 7.8% |
| SPY buy and hold (open to open, monthly) | test 2026 | 0.00% | 10 | 60.0% | 1.1702% | +11.63% | 1.05 | 4.9% |

FOMC dates are the published calendar of scheduled decisions. Half days are skipped for the 15:30-16:00 test. A backtest is not proof.
