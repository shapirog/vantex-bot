# Vantex lab 3 — 2026-11-15T06:21:01-05:00

Calendar: {'first_tradable': '2016-10-17', 'last': '2026-11-13', 'sessions': 2534, 'train': '2016-10-17 -> 2023-12-29', 'test': '2024-01-02 -> 2026-11-13'}

## Audit reproduction (lab 2 RSI2)
### SPY
| step | train trades | train PF | train ret | test trades | test PF | test ret | test maxDD |
|---|---|---|---|---|---|---|---|
| as reported by lab 2 (same-close fills, simple RSI, 0.02% slip) | 154 | 1.26 | 15.9% | 78 | 3.02 | 35.8% | 4.5% |
| + fill at the NEXT OPEN instead of the signal close | 154 | 1.5 | 31.1% | 78 | 3.25 | 38.7% | 5.8% |
| + standard Wilder RSI(2) | 53 | 1.27 | 7.7% | 31 | 3.06 | 18.5% | 5.8% |
| + SMA200/SMA5 include today (standard) | 55 | 1.28 | 8.3% | 33 | 4.57 | 22.3% | 2.4% |
| + 0.05% slippage per side (canonical) | 55 | 1.17 | 4.8% | 33 | 3.97 | 19.9% | 2.5% |
### QQQ
| step | train trades | train PF | train ret | test trades | test PF | test ret | test maxDD |
|---|---|---|---|---|---|---|---|
| as reported by lab 2 (same-close fills, simple RSI, 0.02% slip) | 147 | 1.21 | 15.5% | 74 | 1.86 | 31.5% | 9.2% |
| + fill at the NEXT OPEN instead of the signal close | 147 | 1.68 | 60.5% | 74 | 1.83 | 31.3% | 9.6% |
| + standard Wilder RSI(2) | 52 | 1.14 | 4.0% | 32 | 1.89 | 14.3% | 8.8% |
| + SMA200/SMA5 include today (standard) | 54 | 1.61 | 16.0% | 33 | 2.19 | 18.6% | 6.5% |
| + 0.05% slippage per side (canonical) | 54 | 1.46 | 12.3% | 33 | 2.02 | 16.3% | 6.6% |
## Canonical RSI(2)
| run | period | trades | total ret | CAGR | maxDD | PF $ | win | exposure | bench ret | bench CAGR | bench maxDD |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SPY 25% fractional | full 2016-10-17→2026-11-13 | 89 | 5.95% | 0.58% | 4.06% | 1.61 | 66.3% | 11.6% | 313.99% | 15.15% | 33.79% |
| SPY 25% fractional | train_<2024 2016-10-17→2023-12-29 | 56 | 1.24% | 0.17% | 4.06% | 1.15 | 60.7% | 11.1% | 152.57% | 13.74% | 33.79% |
| SPY 25% fractional | test_2024+ 2024-01-02→2026-11-13 | 33 | 4.65% | 1.59% | 1.24% | 3.91 | 75.8% | 12.8% | 63.91% | 18.76% | 18.75% |
| SPY 50% fractional | full 2016-10-17→2026-11-13 | 89 | 12.12% | 1.14% | 8.03% | 1.62 | 66.3% | 11.6% | 313.99% | 15.15% | 33.79% |
| SPY 50% fractional | train_<2024 2016-10-17→2023-12-29 | 56 | 2.4% | 0.33% | 8.03% | 1.15 | 60.7% | 11.1% | 152.57% | 13.74% | 33.79% |
| SPY 50% fractional | test_2024+ 2024-01-02→2026-11-13 | 33 | 9.5% | 3.21% | 2.47% | 3.88 | 75.8% | 12.8% | 63.91% | 18.76% | 18.75% |
| SPY 100% fractional | full 2016-10-17→2026-11-13 | 89 | 25.08% | 2.25% | 15.68% | 1.63 | 66.3% | 11.6% | 313.99% | 15.15% | 33.79% |
| SPY 100% fractional | train_<2024 2016-10-17→2023-12-29 | 56 | 4.45% | 0.61% | 15.68% | 1.14 | 60.7% | 11.1% | 152.57% | 13.74% | 33.79% |
| SPY 100% fractional | test_2024+ 2024-01-02→2026-11-13 | 33 | 19.76% | 6.47% | 4.89% | 3.82 | 75.8% | 12.8% | 63.91% | 18.76% | 18.75% |
| SPY 50% whole shares ($2,500 start) | full 2016-10-17→2026-11-13 | 89 | 9.76% | 0.93% | 7.69% | 1.54 | 66.3% | 11.6% | 313.99% | 15.15% | 33.79% |
| SPY 50% whole shares ($2,500 start) | train_<2024 2016-10-17→2023-12-29 | 56 | 1.83% | 0.25% | 7.69% | 1.12 | 60.7% | 11.1% | 152.57% | 13.74% | 33.79% |
| SPY 50% whole shares ($2,500 start) | test_2024+ 2024-01-02→2026-11-13 | 33 | 7.8% | 2.65% | 1.89% | 3.9 | 75.8% | 12.8% | 63.91% | 18.76% | 18.75% |
| SPY 100% whole shares ($2,500 start) | full 2016-10-17→2026-11-13 | 89 | 21.07% | 1.92% | 15.23% | 1.56 | 66.3% | 11.6% | 313.99% | 15.15% | 33.79% |
| SPY 100% whole shares ($2,500 start) | train_<2024 2016-10-17→2023-12-29 | 56 | 3.29% | 0.45% | 15.23% | 1.11 | 60.7% | 11.1% | 152.57% | 13.74% | 33.79% |
| SPY 100% whole shares ($2,500 start) | test_2024+ 2024-01-02→2026-11-13 | 33 | 17.21% | 5.68% | 4.63% | 3.88 | 75.8% | 12.8% | 63.91% | 18.76% | 18.75% |
| QQQ 25% fractional | full 2016-10-17→2026-11-13 | 87 | 7.09% | 0.68% | 2.87% | 1.65 | 66.7% | 12.4% | 524.78% | 19.95% | 35.0% |
| QQQ 25% fractional | train_<2024 2016-10-17→2023-12-29 | 54 | 3.02% | 0.41% | 2.87% | 1.45 | 63.0% | 11.3% | 270.95% | 19.98% | 35.0% |
| QQQ 25% fractional | test_2024+ 2024-01-02→2026-11-13 | 33 | 3.95% | 1.36% | 2.25% | 1.98 | 72.7% | 15.4% | 68.43% | 19.88% | 22.77% |
| QQQ 50% fractional | full 2016-10-17→2026-11-13 | 87 | 14.5% | 1.35% | 5.71% | 1.65 | 66.7% | 12.4% | 524.78% | 19.95% | 35.0% |
| QQQ 50% fractional | train_<2024 2016-10-17→2023-12-29 | 54 | 6.06% | 0.82% | 5.71% | 1.45 | 63.0% | 11.3% | 270.95% | 19.98% | 35.0% |
| QQQ 50% fractional | test_2024+ 2024-01-02→2026-11-13 | 33 | 7.96% | 2.7% | 4.48% | 1.95 | 72.7% | 15.4% | 68.43% | 19.88% | 22.77% |
| QQQ 100% fractional | full 2016-10-17→2026-11-13 | 87 | 30.26% | 2.66% | 11.33% | 1.63 | 66.7% | 12.4% | 524.78% | 19.95% | 35.0% |
| QQQ 100% fractional | train_<2024 2016-10-17→2023-12-29 | 54 | 12.11% | 1.6% | 11.33% | 1.43 | 63.0% | 11.3% | 270.95% | 19.98% | 35.0% |
| QQQ 100% fractional | test_2024+ 2024-01-02→2026-11-13 | 33 | 16.19% | 5.36% | 8.87% | 1.89 | 72.7% | 15.4% | 68.43% | 19.88% | 22.77% |
| QQQ 50% whole shares ($2,500 start) | full 2016-10-17→2026-11-13 | 87 | 12.18% | 1.15% | 5.0% | 1.64 | 66.7% | 12.4% | 524.78% | 19.95% | 35.0% |
| QQQ 50% whole shares ($2,500 start) | train_<2024 2016-10-17→2023-12-29 | 54 | 5.3% | 0.72% | 5.0% | 1.43 | 63.0% | 11.3% | 270.95% | 19.98% | 35.0% |
| QQQ 50% whole shares ($2,500 start) | test_2024+ 2024-01-02→2026-11-13 | 33 | 6.53% | 2.22% | 4.06% | 2.02 | 72.7% | 15.4% | 68.43% | 19.88% | 22.77% |
| QQQ 100% whole shares ($2,500 start) | full 2016-10-17→2026-11-13 | 87 | 29.16% | 2.57% | 10.76% | 1.65 | 66.7% | 12.4% | 524.78% | 19.95% | 35.0% |
| QQQ 100% whole shares ($2,500 start) | train_<2024 2016-10-17→2023-12-29 | 54 | 11.64% | 1.54% | 10.76% | 1.44 | 63.0% | 11.3% | 270.95% | 19.98% | 35.0% |
| QQQ 100% whole shares ($2,500 start) | test_2024+ 2024-01-02→2026-11-13 | 33 | 15.69% | 5.2% | 7.5% | 1.95 | 72.7% | 15.4% | 68.43% | 19.88% | 22.77% |
## SPY + QQQ combined
| run | period | trades | total ret | CAGR | maxDD | PF $ | win | exposure | bench ret | bench CAGR | bench maxDD |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SPY+QQQ pooled cap 50% | full 2016-10-17→2026-11-13 | 175 | 17.12% | 1.58% | 6.31% | 1.7 | 66.9% | 15.6% | 313.99% | 15.15% | 33.79% |
| SPY+QQQ pooled cap 50% | train_<2024 2016-10-17→2023-12-29 | 109 | 7.96% | 1.07% | 6.31% | 1.48 | 62.4% | 14.5% | 152.57% | 13.74% | 33.79% |
| SPY+QQQ pooled cap 50% | test_2024+ 2024-01-02→2026-11-13 | 66 | 8.49% | 2.87% | 3.5% | 2.13 | 74.2% | 18.4% | 63.91% | 18.76% | 18.75% |
| SPY+QQQ pooled cap 100% | full 2016-10-17→2026-11-13 | 176 | 36.24% | 3.12% | 12.5% | 1.69 | 66.5% | 15.6% | 313.99% | 15.15% | 33.79% |
| SPY+QQQ pooled cap 100% | train_<2024 2016-10-17→2023-12-29 | 110 | 16.04% | 2.09% | 12.5% | 1.47 | 61.8% | 14.5% | 152.57% | 13.74% | 33.79% |
| SPY+QQQ pooled cap 100% | test_2024+ 2024-01-02→2026-11-13 | 66 | 17.41% | 5.74% | 6.94% | 2.09 | 74.2% | 18.4% | 63.91% | 18.76% | 18.75% |
## ETF universe
| run | period | trades | total ret | CAGR | maxDD | PF $ | win | exposure | bench ret | bench CAGR | bench maxDD |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SPY | full 2016-10-17→2026-11-13 | 89 | 12.12% | 1.14% | 8.03% | 1.62 | 66.3% | 11.6% | 313.99% | 15.15% | 33.79% |
| SPY | train_<2024 2016-10-17→2023-12-29 | 56 | 2.4% | 0.33% | 8.03% | 1.15 | 60.7% | 11.1% | 152.57% | 13.74% | 33.79% |
| SPY | test_2024+ 2024-01-02→2026-11-13 | 33 | 9.5% | 3.21% | 2.47% | 3.88 | 75.8% | 12.8% | 63.91% | 18.76% | 18.75% |
| QQQ | full 2016-10-17→2026-11-13 | 87 | 14.5% | 1.35% | 5.71% | 1.65 | 66.7% | 12.4% | 524.78% | 19.95% | 35.0% |
| QQQ | train_<2024 2016-10-17→2023-12-29 | 54 | 6.06% | 0.82% | 5.71% | 1.45 | 63.0% | 11.3% | 270.95% | 19.98% | 35.0% |
| QQQ | test_2024+ 2024-01-02→2026-11-13 | 33 | 7.96% | 2.7% | 4.48% | 1.95 | 72.7% | 15.4% | 68.43% | 19.88% | 22.77% |
| IWM | full 2016-10-17→2026-11-13 | 74 | 6.36% | 0.61% | 10.61% | 1.22 | 68.9% | 11.2% | 161.39% | 10.01% | 41.27% |
| IWM | train_<2024 2016-10-17→2023-12-29 | 44 | -3.93% | -0.56% | 10.61% | 0.82 | 61.4% | 10.2% | 83.51% | 8.8% | 41.27% |
| IWM | test_2024+ 2024-01-02→2026-11-13 | 30 | 10.71% | 3.6% | 3.89% | 2.55 | 80.0% | 13.6% | 42.44% | 13.09% | 27.5% |
| DIA | full 2016-10-17→2026-11-13 | 95 | 13.87% | 1.3% | 6.26% | 1.63 | 69.5% | 12.9% | 250.99% | 13.28% | 36.82% |
| DIA | train_<2024 2016-10-17→2023-12-29 | 63 | 5.19% | 0.71% | 6.26% | 1.34 | 69.8% | 11.7% | 142.09% | 13.07% | 36.82% |
| DIA | test_2024+ 2024-01-02→2026-11-13 | 32 | 8.24% | 2.79% | 2.33% | 2.31 | 68.8% | 15.7% | 44.98% | 13.79% | 15.95% |
| XLF | full 2016-10-17→2026-11-13 | 78 | 8.18% | 0.78% | 6.06% | 1.3 | 65.4% | 11.3% | 264.7% | 13.71% | 42.86% |
| XLF | train_<2024 2016-10-17→2023-12-29 | 51 | 1.35% | 0.19% | 6.06% | 1.06 | 60.8% | 10.5% | 124.18% | 11.87% | 42.86% |
| XLF | test_2024+ 2024-01-02→2026-11-13 | 27 | 6.74% | 2.3% | 3.02% | 2.06 | 74.1% | 13.5% | 62.68% | 18.45% | 15.54% |
| XLK | full 2016-10-17→2026-11-13 | 79 | 16.12% | 1.49% | 6.12% | 1.59 | 64.6% | 11.4% | 697.94% | 22.9% | 33.56% |
| XLK | train_<2024 2016-10-17→2023-12-29 | 49 | 4.23% | 0.58% | 6.06% | 1.25 | 57.1% | 10.2% | 343.53% | 22.99% | 33.56% |
| XLK | test_2024+ 2024-01-02→2026-11-13 | 30 | 11.4% | 3.83% | 6.12% | 2.09 | 76.7% | 14.4% | 79.9% | 22.66% | 25.66% |
| XLI | full 2016-10-17→2026-11-13 | 92 | 16.15% | 1.5% | 9.63% | 1.64 | 67.4% | 13.1% | 250.17% | 13.25% | 42.33% |
| XLI | train_<2024 2016-10-17→2023-12-29 | 60 | 3.55% | 0.49% | 9.63% | 1.19 | 63.3% | 12.2% | 128.05% | 12.14% | 42.33% |
| XLI | test_2024+ 2024-01-02→2026-11-13 | 32 | 12.17% | 4.08% | 2.5% | 3.02 | 75.0% | 15.4% | 53.55% | 16.09% | 18.49% |
| XLP | full 2016-10-17→2026-11-13 | 78 | -2.24% | -0.22% | 7.27% | 0.87 | 59.0% | 11.8% | 131.8% | 8.7% | 24.5% |
| XLP | train_<2024 2016-10-17→2023-12-29 | 56 | -3.01% | -0.42% | 7.27% | 0.78 | 62.5% | 11.8% | 67.95% | 7.47% | 24.5% |
| XLP | test_2024+ 2024-01-02→2026-11-13 | 22 | 0.8% | 0.28% | 2.77% | 1.23 | 50.0% | 11.9% | 38.02% | 11.86% | 9.69% |
| XLY | full 2016-10-17→2026-11-13 | 92 | 35.86% | 3.09% | 5.02% | 2.88 | 75.0% | 11.8% | 239.79% | 12.91% | 39.67% |
| XLY | train_<2024 2016-10-17→2023-12-29 | 62 | 17.29% | 2.24% | 5.02% | 2.19 | 72.6% | 11.5% | 147.41% | 13.41% | 39.67% |
| XLY | test_2024+ 2024-01-02→2026-11-13 | 30 | 15.84% | 5.25% | 2.78% | 5.1 | 80.0% | 12.6% | 37.34% | 11.67% | 26.01% |
| XLU | full 2016-10-17→2026-11-13 | 71 | -1.59% | -0.16% | 12.18% | 0.94 | 60.6% | 10.7% | 151.51% | 9.59% | 36.09% |
| XLU | train_<2024 2016-10-17→2023-12-29 | 45 | -6.58% | -0.94% | 10.51% | 0.66 | 55.6% | 9.8% | 66.93% | 7.38% | 36.09% |
| XLU | test_2024+ 2024-01-02→2026-11-13 | 26 | 5.35% | 1.83% | 2.97% | 1.81 | 69.2% | 12.8% | 50.67% | 15.33% | 16.04% |
| XLE | full 2016-10-17→2026-11-13 | 74 | -7.03% | -0.72% | 16.46% | 0.85 | 54.1% | 11.9% | 180.73% | 10.79% | 66.82% |
| XLE | train_<2024 2016-10-17→2023-12-29 | 49 | -4.31% | -0.61% | 16.46% | 0.87 | 57.1% | 11.0% | 66.38% | 7.33% | 66.82% |
| XLE | test_2024+ 2024-01-02→2026-11-13 | 25 | -2.84% | -1.0% | 9.5% | 0.81 | 48.0% | 14.1% | 68.73% | 19.96% | 20.13% |
| XLV | full 2016-10-17→2026-11-13 | 81 | 2.92% | 0.29% | 8.29% | 1.14 | 63.0% | 12.0% | 221.72% | 12.3% | 28.4% |
| XLV | train_<2024 2016-10-17→2023-12-29 | 55 | -0.54% | -0.08% | 8.29% | 0.97 | 61.8% | 11.6% | 121.99% | 11.72% | 28.4% |
| XLV | test_2024+ 2024-01-02→2026-11-13 | 26 | 3.48% | 1.2% | 3.5% | 1.8 | 65.4% | 12.9% | 44.92% | 13.78% | 17.11% |
| XLB | full 2016-10-17→2026-11-13 | 84 | 6.99% | 0.67% | 7.79% | 1.22 | 63.1% | 13.1% | 175.04% | 10.57% | 37.27% |
| XLB | train_<2024 2016-10-17→2023-12-29 | 53 | 7.02% | 0.95% | 5.09% | 1.37 | 66.0% | 11.6% | 114.11% | 11.16% | 37.27% |
| XLB | test_2024+ 2024-01-02→2026-11-13 | 31 | -0.03% | -0.01% | 5.18% | 1.0 | 58.1% | 17.1% | 28.46% | 9.1% | 23.17% |
| POOLED 13 ETFs, cap 50% | full 2016-10-17→2026-11-13 | 924 | 14.1% | 1.32% | 13.35% | 1.16 | 66.1% | 47.9% | 313.99% | 15.15% | 33.79% |
| POOLED 13 ETFs, cap 50% | train_<2024 2016-10-17→2023-12-29 | 601 | -1.32% | -0.19% | 13.35% | 0.98 | 64.7% | 44.1% | 152.57% | 13.74% | 33.79% |
| POOLED 13 ETFs, cap 50% | test_2024+ 2024-01-02→2026-11-13 | 323 | 15.63% | 5.18% | 9.11% | 1.55 | 68.7% | 57.4% | 63.91% | 18.76% | 18.75% |
## Leveraged (SSO/QLD)
| run | period | trades | total ret | CAGR | maxDD | PF $ | win | exposure | bench ret | bench CAGR | bench maxDD |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SPY signal -> SSO at 12.5% (half of 25%) | full 2016-10-17→2026-11-13 | 89 | 6.34% | 0.61% | 4.0% | 1.65 | 67.4% | 11.6% | 727.06% | 23.34% | 59.22% |
| SPY signal -> SSO at 12.5% (half of 25%) | train_<2024 2016-10-17→2023-12-29 | 56 | 1.47% | 0.2% | 4.0% | 1.18 | 60.7% | 11.1% | 292.38% | 20.92% | 59.22% |
| SPY signal -> SSO at 12.5% (half of 25%) | test_2024+ 2024-01-02→2026-11-13 | 33 | 4.81% | 1.65% | 1.26% | 4.01 | 78.8% | 12.8% | 110.78% | 29.61% | 35.2% |
| SPY signal -> SSO at 25.0% (half of 50%) | full 2016-10-17→2026-11-13 | 89 | 12.94% | 1.22% | 7.9% | 1.65 | 67.4% | 11.6% | 727.06% | 23.34% | 59.22% |
| SPY signal -> SSO at 25.0% (half of 50%) | train_<2024 2016-10-17→2023-12-29 | 56 | 2.85% | 0.39% | 7.9% | 1.17 | 60.7% | 11.1% | 292.38% | 20.92% | 59.22% |
| SPY signal -> SSO at 25.0% (half of 50%) | test_2024+ 2024-01-02→2026-11-13 | 33 | 9.81% | 3.31% | 2.51% | 3.98 | 78.8% | 12.8% | 110.78% | 29.61% | 35.2% |
| SPY signal -> SSO at 50.0% (half of 100%) | full 2016-10-17→2026-11-13 | 89 | 26.92% | 2.4% | 15.45% | 1.66 | 67.4% | 11.6% | 727.06% | 23.34% | 59.22% |
| SPY signal -> SSO at 50.0% (half of 100%) | train_<2024 2016-10-17→2023-12-29 | 56 | 5.35% | 0.73% | 15.45% | 1.16 | 60.7% | 11.1% | 292.38% | 20.92% | 59.22% |
| SPY signal -> SSO at 50.0% (half of 100%) | test_2024+ 2024-01-02→2026-11-13 | 33 | 20.47% | 6.69% | 4.97% | 3.91 | 78.8% | 12.8% | 110.78% | 29.61% | 35.2% |
| QQQ signal -> QLD at 12.5% (half of 25%) | full 2016-10-17→2026-11-13 | 87 | 7.04% | 0.68% | 2.9% | 1.63 | 67.8% | 12.4% | 1434.74% | 31.14% | 63.69% |
| QQQ signal -> QLD at 12.5% (half of 25%) | train_<2024 2016-10-17→2023-12-29 | 54 | 3.01% | 0.41% | 2.9% | 1.43 | 64.8% | 11.3% | 631.18% | 31.84% | 63.69% |
| QQQ signal -> QLD at 12.5% (half of 25%) | test_2024+ 2024-01-02→2026-11-13 | 33 | 3.92% | 1.35% | 2.24% | 1.96 | 72.7% | 15.4% | 109.9% | 29.42% | 42.29% |
| QQQ signal -> QLD at 25.0% (half of 50%) | full 2016-10-17→2026-11-13 | 87 | 14.4% | 1.34% | 5.79% | 1.62 | 67.8% | 12.4% | 1434.74% | 31.14% | 63.69% |
| QQQ signal -> QLD at 25.0% (half of 50%) | train_<2024 2016-10-17→2023-12-29 | 54 | 6.02% | 0.81% | 5.79% | 1.43 | 64.8% | 11.3% | 631.18% | 31.84% | 63.69% |
| QQQ signal -> QLD at 25.0% (half of 50%) | test_2024+ 2024-01-02→2026-11-13 | 33 | 7.91% | 2.68% | 4.46% | 1.92 | 72.7% | 15.4% | 109.9% | 29.42% | 42.29% |
| QQQ signal -> QLD at 50.0% (half of 100%) | full 2016-10-17→2026-11-13 | 87 | 30.04% | 2.64% | 11.5% | 1.61 | 67.8% | 12.4% | 1434.74% | 31.14% | 63.69% |
| QQQ signal -> QLD at 50.0% (half of 100%) | train_<2024 2016-10-17→2023-12-29 | 54 | 12.02% | 1.59% | 11.5% | 1.42 | 64.8% | 11.3% | 631.18% | 31.84% | 63.69% |
| QQQ signal -> QLD at 50.0% (half of 100%) | test_2024+ 2024-01-02→2026-11-13 | 33 | 16.08% | 5.33% | 8.83% | 1.86 | 72.7% | 15.4% | 109.9% | 29.42% | 42.29% |
## Stress
```
{
 "SPY": {
  "base (0.05%, next open)": {
   "total_ret_pct": 25.08,
   "cagr_pct": 2.25,
   "max_dd_pct": 15.68,
   "trades": 89,
   "pf_dollars": 1.63
  },
  "slippage 0.10%": {
   "total_ret_pct": 14.44,
   "cagr_pct": 1.35,
   "max_dd_pct": 17.18,
   "trades": 89,
   "pf_dollars": 1.35
  },
  "slippage 0.25%": {
   "total_ret_pct": -12.35,
   "cagr_pct": -1.3,
   "max_dd_pct": 21.73,
   "trades": 89,
   "pf_dollars": 0.73
  },
  "fills one session late": {
   "total_ret_pct": 36.17,
   "cagr_pct": 3.11,
   "max_dd_pct": 15.14,
   "trades": 88,
   "pf_dollars": 1.73
  },
  "fills at next CLOSE": {
   "total_ret_pct": 25.63,
   "cagr_pct": 2.29,
   "max_dd_pct": 17.38,
   "trades": 89,
   "pf_dollars": 1.59
  },
  "10% of signals missed (200 runs)": {
   "total_ret_p5": 17.52,
   "total_ret_median": 23.5,
   "total_ret_p95": 30.48
  },
  "25% of signals missed (200 runs)": {
   "total_ret_p5": 11.18,
   "total_ret_median": 20.81,
   "total_ret_p95": 33.23
  }
 },
 "QQQ": {
  "base (0.05%, next open)": {
   "total_ret_pct": 30.26,
   "cagr_pct": 2.66,
   "max_dd_pct": 11.33,
   "trades": 87,
   "pf_dollars": 1.63
  },
  "slippage 0.10%": {
   "total_ret_pct": 19.42,
   "cagr_pct": 1.78,
   "max_dd_pct": 12.71,
   "trades": 87,
   "pf_dollars": 1.4
  },
  "slippage 0.25%": {
   "total_ret_pct": -7.99,
   "cagr_pct": -0.82,
   "max_dd_pct": 16.8,
   "trades": 87,
   "pf_dollars": 0.85
  },
  "fills one session late": {
   "total_ret_pct": 36.92,
   "cagr_pct": 3.17,
   "max_dd_pct": 11.17,
   "trades": 87,
   "pf_dollars": 1.62
  },
  "fills at next CLOSE": {
   "total_ret_pct": 32.87,
   "cagr_pct": 2.86,
   "max_dd_pct": 13.68,
   "trades": 87,
   "pf_dollars": 1.71
  },
  "10% of signals missed (200 runs)": {
   "total_ret_p5": 21.0,
   "total_ret_median": 29.61,
   "total_ret_p95": 39.56
  },
  "25% of signals missed (200 runs)": {
   "total_ret_p5": 16.48,
   "total_ret_median": 29.19,
   "total_ret_p95": 45.4
  }
 }
}
```
## Intraday 10:00 → 15:30 SPY
| version | period | days | trades | mean bp | t | PF | total ret | maxDD |
|---|---|---|---|---|---|---|---|---|
| long_short|bar_open|delay0 | 2016-2023 | 1994 | 1989 | -3.04 | -4.05 | 0.73 | -46.0% | 46.79% |
| long_short|bar_open|delay0 | 2024+ | 715 | 712 | -2.7 | -3.28 | 0.69 | -17.63% | 17.63% |
| long_short|bar_open|delay1 | 2016-2023 | 1994 | 1989 | -2.8 | -3.82 | 0.74 | -43.35% | 44.28% |
| long_short|bar_open|delay1 | 2024+ | 715 | 712 | -2.79 | -3.54 | 0.67 | -18.14% | 18.14% |
| long_short|bar_open|delay2 | 2016-2023 | 1994 | 1989 | -2.84 | -3.94 | 0.73 | -43.71% | 44.83% |
| long_short|bar_open|delay2 | 2024+ | 715 | 712 | -2.86 | -3.69 | 0.66 | -18.57% | 18.57% |
| long_short|bar_open|delay3 | 2016-2023 | 1994 | 1989 | -2.53 | -3.52 | 0.75 | -40.12% | 41.17% |
| long_short|bar_open|delay3 | 2024+ | 715 | 712 | -2.71 | -3.57 | 0.67 | -17.67% | 17.67% |
| long_short|bar_open|delay4 | 2016-2023 | 1994 | 1989 | -2.36 | -3.26 | 0.77 | -38.13% | 39.16% |
| long_short|bar_open|delay4 | 2024+ | 715 | 712 | -2.74 | -3.63 | 0.67 | -17.82% | 17.82% |
| long_short|bar_open|delay5 | 2016-2023 | 1994 | 1989 | -2.36 | -3.28 | 0.77 | -38.04% | 39.17% |
| long_short|bar_open|delay5 | 2024+ | 715 | 712 | -2.74 | -3.61 | 0.67 | -17.85% | 17.85% |
| long_short|worst_in_bar|delay0 | 2016-2023 | 1994 | 1989 | -5.95 | -8.05 | 0.53 | -69.69% | 69.8% |
| long_short|worst_in_bar|delay0 | 2024+ | 715 | 712 | -5.1 | -6.36 | 0.49 | -30.55% | 30.55% |
| long_short|worst_in_bar|delay1 | 2016-2023 | 1994 | 1989 | -5.54 | -7.69 | 0.55 | -67.12% | 67.28% |
| long_short|worst_in_bar|delay1 | 2024+ | 715 | 712 | -4.97 | -6.4 | 0.49 | -29.9% | 29.9% |
| long_short|worst_in_bar|delay2 | 2016-2023 | 1994 | 1989 | -5.49 | -7.7 | 0.55 | -66.82% | 67.06% |
| long_short|worst_in_bar|delay2 | 2024+ | 715 | 712 | -4.91 | -6.47 | 0.49 | -29.63% | 29.63% |
| long_short|worst_in_bar|delay3 | 2016-2023 | 1994 | 1989 | -5.14 | -7.25 | 0.56 | -64.36% | 64.5% |
| long_short|worst_in_bar|delay3 | 2024+ | 715 | 712 | -4.71 | -6.28 | 0.5 | -28.6% | 28.6% |
| long_short|worst_in_bar|delay4 | 2016-2023 | 1994 | 1989 | -4.9 | -6.9 | 0.57 | -62.63% | 62.75% |
| long_short|worst_in_bar|delay4 | 2024+ | 715 | 712 | -4.59 | -6.15 | 0.51 | -28.0% | 28.0% |
| long_short|worst_in_bar|delay5 | 2016-2023 | 1994 | 1989 | -5.13 | -7.37 | 0.56 | -64.3% | 64.38% |
| long_short|worst_in_bar|delay5 | 2024+ | 715 | 712 | -4.89 | -6.54 | 0.49 | -29.53% | 29.53% |
| long_only|bar_open|delay0 | 2016-2023 | 1994 | 1097 | -3.65 | -4.2 | 0.65 | -33.27% | 33.84% |
| long_only|bar_open|delay0 | 2024+ | 715 | 411 | -2.61 | -2.71 | 0.67 | -10.25% | 10.66% |
| long_only|bar_open|delay1 | 2016-2023 | 1994 | 1097 | -3.28 | -3.79 | 0.68 | -30.54% | 31.41% |
| long_only|bar_open|delay1 | 2024+ | 715 | 411 | -2.72 | -2.89 | 0.65 | -10.66% | 11.04% |
| long_only|bar_open|delay2 | 2016-2023 | 1994 | 1097 | -3.28 | -3.65 | 0.68 | -30.54% | 31.27% |
| long_only|bar_open|delay2 | 2024+ | 715 | 411 | -2.85 | -3.1 | 0.63 | -11.12% | 11.36% |
| long_only|bar_open|delay3 | 2016-2023 | 1994 | 1097 | -3.18 | -3.61 | 0.68 | -29.77% | 30.49% |
| long_only|bar_open|delay3 | 2024+ | 715 | 411 | -2.84 | -3.12 | 0.63 | -11.08% | 11.43% |
| long_only|bar_open|delay4 | 2016-2023 | 1994 | 1097 | -2.97 | -3.21 | 0.69 | -28.21% | 29.01% |
| long_only|bar_open|delay4 | 2024+ | 715 | 411 | -2.87 | -3.16 | 0.64 | -11.17% | 11.49% |
| long_only|bar_open|delay5 | 2016-2023 | 1994 | 1097 | -3.06 | -3.37 | 0.69 | -28.83% | 29.71% |
| long_only|bar_open|delay5 | 2024+ | 715 | 411 | -2.81 | -3.05 | 0.64 | -10.96% | 11.19% |
| long_only|worst_in_bar|delay0 | 2016-2023 | 1994 | 1097 | -6.18 | -7.3 | 0.48 | -49.46% | 49.69% |
| long_only|worst_in_bar|delay0 | 2024+ | 715 | 411 | -4.67 | -4.89 | 0.49 | -17.54% | 17.77% |
| long_only|worst_in_bar|delay1 | 2016-2023 | 1994 | 1097 | -5.74 | -6.62 | 0.51 | -46.98% | 47.24% |
| long_only|worst_in_bar|delay1 | 2024+ | 715 | 411 | -4.73 | -5.07 | 0.47 | -17.74% | 17.84% |
| long_only|worst_in_bar|delay2 | 2016-2023 | 1994 | 1097 | -5.75 | -6.59 | 0.5 | -47.05% | 47.27% |
| long_only|worst_in_bar|delay2 | 2024+ | 715 | 411 | -4.75 | -5.19 | 0.46 | -17.8% | 17.84% |
| long_only|worst_in_bar|delay3 | 2016-2023 | 1994 | 1097 | -5.5 | -6.34 | 0.51 | -45.58% | 45.81% |
| long_only|worst_in_bar|delay3 | 2024+ | 715 | 411 | -4.66 | -5.11 | 0.47 | -17.5% | 17.53% |
| long_only|worst_in_bar|delay4 | 2016-2023 | 1994 | 1097 | -5.36 | -6.02 | 0.52 | -44.7% | 44.96% |
| long_only|worst_in_bar|delay4 | 2024+ | 715 | 411 | -4.49 | -4.95 | 0.49 | -16.91% | 16.93% |
| long_only|worst_in_bar|delay5 | 2016-2023 | 1994 | 1097 | -5.51 | -6.45 | 0.5 | -45.6% | 45.83% |
| long_only|worst_in_bar|delay5 | 2024+ | 715 | 411 | -4.49 | -4.93 | 0.49 | -16.92% | 16.92% |
| always_long|bar_open|delay0 | 2016-2023 | 1994 | 1994 | -3.34 | -4.46 | 0.7 | -49.23% | 49.59% |
| always_long|bar_open|delay0 | 2024+ | 715 | 715 | -2.39 | -2.92 | 0.72 | -15.86% | 17.07% |
| always_long|bar_open|delay1 | 2016-2023 | 1994 | 1994 | -3.17 | -4.33 | 0.71 | -47.4% | 47.73% |
| always_long|bar_open|delay1 | 2024+ | 715 | 715 | -2.43 | -3.1 | 0.71 | -16.08% | 17.23% |
| always_long|bar_open|delay2 | 2016-2023 | 1994 | 1994 | -3.13 | -4.36 | 0.71 | -46.99% | 47.31% |
| always_long|bar_open|delay2 | 2024+ | 715 | 715 | -2.5 | -3.23 | 0.69 | -16.48% | 17.66% |
| always_long|bar_open|delay3 | 2016-2023 | 1994 | 1994 | -3.33 | -4.65 | 0.69 | -49.05% | 49.29% |
| always_long|bar_open|delay3 | 2024+ | 715 | 715 | -2.64 | -3.5 | 0.68 | -17.35% | 18.79% |
| always_long|bar_open|delay4 | 2016-2023 | 1994 | 1994 | -3.27 | -4.53 | 0.69 | -48.48% | 48.75% |
| always_long|bar_open|delay4 | 2024+ | 715 | 715 | -2.65 | -3.52 | 0.68 | -17.35% | 18.83% |
| always_long|bar_open|delay5 | 2016-2023 | 1994 | 1994 | -3.36 | -4.7 | 0.68 | -49.38% | 49.63% |
| always_long|bar_open|delay5 | 2024+ | 715 | 715 | -2.57 | -3.4 | 0.68 | -16.9% | 18.16% |
| always_long|worst_in_bar|delay0 | 2016-2023 | 1994 | 1994 | -6.29 | -8.52 | 0.51 | -71.81% | 71.81% |
| always_long|worst_in_bar|delay0 | 2024+ | 715 | 715 | -4.81 | -5.98 | 0.51 | -29.21% | 29.82% |
| always_long|worst_in_bar|delay1 | 2016-2023 | 1994 | 1994 | -5.91 | -8.2 | 0.52 | -69.54% | 69.59% |
| always_long|worst_in_bar|delay1 | 2024+ | 715 | 715 | -4.58 | -5.85 | 0.51 | -28.06% | 28.57% |
| always_long|worst_in_bar|delay2 | 2016-2023 | 1994 | 1994 | -6.05 | -8.49 | 0.51 | -70.38% | 70.41% |
| always_long|worst_in_bar|delay2 | 2024+ | 715 | 715 | -4.66 | -6.1 | 0.5 | -28.46% | 28.9% |
| always_long|worst_in_bar|delay3 | 2016-2023 | 1994 | 1994 | -5.96 | -8.45 | 0.51 | -69.85% | 69.88% |
| always_long|worst_in_bar|delay3 | 2024+ | 715 | 715 | -4.66 | -6.1 | 0.5 | -28.44% | 28.99% |
| always_long|worst_in_bar|delay4 | 2016-2023 | 1994 | 1994 | -5.88 | -8.25 | 0.51 | -69.35% | 69.39% |
| always_long|worst_in_bar|delay4 | 2024+ | 715 | 715 | -4.46 | -5.9 | 0.52 | -27.41% | 27.95% |
| always_long|worst_in_bar|delay5 | 2016-2023 | 1994 | 1994 | -6.05 | -8.69 | 0.5 | -70.36% | 70.39% |
| always_long|worst_in_bar|delay5 | 2024+ | 715 | 715 | -4.52 | -5.96 | 0.51 | -27.71% | 28.21% |
## Overnight after a down day
```
{
 "SPY": {
  "lab2_signal_at_close": {
   "2016-2023": {
    "trades": 900,
    "pf": 0.8,
    "mean_bp": -5.43,
    "total_ret_pct": -40.39,
    "max_dd_pct": 43.25
   },
   "2024+": {
    "trades": 317,
    "pf": 0.85,
    "mean_bp": -3.66,
    "total_ret_pct": -11.64,
    "max_dd_pct": 14.98
   }
  },
  "executable_1550_decision": {
   "2016-2023": {
    "trades": 886,
    "pf": 0.78,
    "mean_bp": -6.17,
    "total_ret_pct": -43.7,
    "max_dd_pct": 46.57
   },
   "2024+": {
    "trades": 319,
    "pf": 0.92,
    "mean_bp": -2.05,
    "total_ret_pct": -7.09,
    "max_dd_pct": 12.5
   }
  }
 },
 "QQQ": {
  "lab2_signal_at_close": {
   "2016-2023": {
    "trades": 870,
    "pf": 0.85,
    "mean_bp": -5.05,
    "total_ret_pct": -37.92,
    "max_dd_pct": 40.35
   },
   "2024+": {
    "trades": 313,
    "pf": 0.96,
    "mean_bp": -1.59,
    "total_ret_pct": -6.27,
    "max_dd_pct": 15.72
   }
  },
  "executable_1550_decision": {
   "2016-2023": {
    "trades": 885,
    "pf": 0.86,
    "mean_bp": -4.73,
    "total_ret_pct": -36.74,
    "max_dd_pct": 39.23
   },
   "2024+": {
    "trades": 327,
    "pf": 0.98,
    "mean_bp": -0.65,
    "total_ret_pct": -3.72,
    "max_dd_pct": 14.73
   }
  }
 }
}
```
## Options data probe
No historical option quotes (bid/ask) from this data source. Per the rules, the 45-60 DTE call-spread test is NOT run; trade-based bars or modeled prices are not executable fills.
## Risk of ruin
```
{
 "SPY RSI2 100% of equity": {
  "21_sessions": {
   "p_drawdown_25pct": 0.0,
   "p_drawdown_50pct": 0.0,
   "p_ruin_99pct": 0.0,
   "p_reach_32x": 0.0,
   "end_equity_p5": 2442.0,
   "end_equity_median": 2500.0,
   "end_equity_p95": 2557.0,
   "paths": 5000
  },
  "252_sessions": {
   "p_drawdown_25pct": 0.0,
   "p_drawdown_50pct": 0.0,
   "p_ruin_99pct": 0.0,
   "p_reach_32x": 0.0,
   "end_equity_p5": 2349.0,
   "end_equity_median": 2564.0,
   "end_equity_p95": 2764.0,
   "paths": 5000
  }
 },
 "QQQ RSI2 100% of equity": {
  "21_sessions": {
   "p_drawdown_25pct": 0.0,
   "p_drawdown_50pct": 0.0,
   "p_ruin_99pct": 0.0,
   "p_reach_32x": 0.0,
   "end_equity_p5": 2430.0,
   "end_equity_median": 2500.0,
   "end_equity_p95": 2577.0,
   "paths": 5000
  },
  "252_sessions": {
   "p_drawdown_25pct": 0.0,
   "p_drawdown_50pct": 0.0,
   "p_ruin_99pct": 0.0,
   "p_reach_32x": 0.0,
   "end_equity_p5": 2311.0,
   "end_equity_median": 2570.0,
   "end_equity_p95": 2823.0,
   "paths": 5000
  }
 },
 "SPY+QQQ pooled cap 50%": {
  "21_sessions": {
   "p_drawdown_25pct": 0.0,
   "p_drawdown_50pct": 0.0,
   "p_ruin_99pct": 0.0,
   "p_reach_32x": 0.0,
   "end_equity_p5": 2470.0,
   "end_equity_median": 2501.0,
   "end_equity_p95": 2537.0,
   "paths": 5000
  },
  "252_sessions": {
   "p_drawdown_25pct": 0.0,
   "p_drawdown_50pct": 0.0,
   "p_ruin_99pct": 0.0,
   "p_reach_32x": 0.0,
   "end_equity_p5": 2425.0,
   "end_equity_median": 2541.0,
   "end_equity_p95": 2658.0,
   "paths": 5000
  }
 },
 "SPY+QQQ pooled cap 100%": {
  "21_sessions": {
   "p_drawdown_25pct": 0.0,
   "p_drawdown_50pct": 0.0,
   "p_ruin_99pct": 0.0,
   "p_reach_32x": 0.0,
   "end_equity_p5": 2434.0,
   "end_equity_median": 2500.0,
   "end_equity_p95": 2572.0,
   "paths": 5000
  },
  "252_sessions": {
   "p_drawdown_25pct": 0.0,
   "p_drawdown_50pct": 0.0,
   "p_ruin_99pct": 0.0,
   "p_reach_32x": 0.0,
   "end_equity_p5": 2349.0,
   "end_equity_median": 2582.0,
   "end_equity_p95": 2819.0,
   "paths": 5000
  }
 },
 "13-ETF pool cap 50%": {
  "21_sessions": {
   "p_drawdown_25pct": 0.0,
   "p_drawdown_50pct": 0.0,
   "p_ruin_99pct": 0.0,
   "p_reach_32x": 0.0,
   "end_equity_p5": 2430.0,
   "end_equity_median": 2506.0,
   "end_equity_p95": 2562.0,
   "paths": 5000
  },
  "252_sessions": {
   "p_drawdown_25pct": 0.0,
   "p_drawdown_50pct": 0.0,
   "p_ruin_99pct": 0.0,
   "p_reach_32x": 0.0,
   "end_equity_p5": 2308.0,
   "end_equity_median": 2537.0,
   "end_equity_p95": 2763.0,
   "paths": 5000
  }
 },
 "LOTTERY (hypothetical): SPY+QQQ cap 100% daily returns x10, like deep-leverage options": {
  "21_sessions": {
   "p_drawdown_25pct": 12.12,
   "p_drawdown_50pct": 1.78,
   "p_ruin_99pct": 0.0,
   "p_reach_32x": 0.0,
   "end_equity_p5": 1817.0,
   "end_equity_median": 2500.0,
   "end_equity_p95": 3228.0,
   "paths": 5000
  },
  "252_sessions": {
   "p_drawdown_25pct": 59.48,
   "p_drawdown_50pct": 27.06,
   "p_ruin_99pct": 0.0,
   "p_reach_32x": 0.0,
   "end_equity_p5": 906.0,
   "end_equity_median": 2724.0,
   "end_equity_p95": 6615.0,
   "paths": 5000
  }
 },
 "note": "Block bootstrap (10-session blocks) of this strategy's own historical daily account returns, 2016-2026. Assumes the future looks like a reshuffled past; real crashes can be worse. 32x needs ~17.9% per session for 21 sessions."
}
```
## Trials
```
{
 "prior": {
  "lab2 ORB grid (2 universes x 288)": 576,
  "lab2 NOISE (2 x 4)": 8,
  "lab2 LASTHR (2 x 6)": 12,
  "lab2 GAPFADE (2 x 8)": 16,
  "lab2 VWAPPB (2 x 2-4)": 6,
  "lab2 OVERNIGHT (2 x 2)": 4,
  "lab2 RSI2 (2 x 2 thresholds)": 4,
  "lab2 options re-runs of every intraday family": 12,
  "lab1 (OVN, ORB5, ORB15, IDX + options)": 8,
  "live options bot replay (3 setups)": 3
 },
 "prior_total": 649,
 "this_lab_pre_registered": [
  "canonical RSI2 SPY",
  "canonical RSI2 QQQ",
  "ETF universe pooled",
  "SSO/QLD",
  "10:00->15:30 SPY",
  "overnight executable"
 ],
 "note": "The 2024+ daily test was seen once in lab 2 when choosing threshold 10 over 5 (2 thresholds x 2 symbols). April-November 2026 intraday results are selection-contaminated: lab 1 -> lab 2 changes were made after seeing them."
}
```
## Data quality
```
{
 "SPY": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 0
 },
 "QQQ": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 0
 },
 "IWM": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 0
 },
 "DIA": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 0
 },
 "XLF": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 2
 },
 "XLK": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 1
 },
 "XLI": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 0
 },
 "XLP": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 0
 },
 "XLY": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 0
 },
 "XLU": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 0
 },
 "XLE": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 3
 },
 "XLV": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 0
 },
 "XLB": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 0
 },
 "SSO": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 6
 },
 "QLD": {
  "first": "2016-01-04",
  "last": "2026-11-13",
  "bars": 2733,
  "missing_trading_days": 0,
  "missing_sample": [],
  "non_trading_day_bars": 0,
  "duplicate_days": 0,
  "bad_prices": 0,
  "daily_moves_over_15pct": 4
 }
}
```
