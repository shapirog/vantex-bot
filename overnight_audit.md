# Strategy A (overnight bias) audit

Research only. Theoretical fills at the daily bar close and next open (consolidated last trade / first trade, close to but not exactly the official auction prices). Alpaca paper fills are simulated against quotes and are NOT evidence of auction slippage.

## 1. Is the screen picking real signals?

Average month: 1645 stocks tested, 224 pass the 5% screen (13.6%); about 82 would pass by chance alone. FDR q=10% keeps 68, FDR q=5% keeps 31.

| month-end | tested | passed 5% | expected by chance | FDR 10% | FDR 5% |
|---|---|---|---|---|---|
| 2023-04-28 | 1306 | 12 | 65.3 | 0 | 0 |
| 2023-05-31 | 1356 | 10 | 67.8 | 0 | 0 |
| 2023-06-30 | 1424 | 20 | 71.2 | 0 | 0 |
| 2023-07-31 | 1350 | 46 | 67.5 | 5 | 5 |
| 2023-08-31 | 1307 | 61 | 65.4 | 2 | 2 |
| 2023-09-29 | 1369 | 104 | 68.5 | 6 | 3 |
| 2023-10-31 | 1323 | 90 | 66.2 | 5 | 1 |
| 2023-11-30 | 1358 | 102 | 67.9 | 5 | 1 |
| 2023-12-29 | 1481 | 120 | 74.0 | 7 | 3 |
| 2024-01-31 | 1406 | 140 | 70.3 | 3 | 2 |
| 2024-02-29 | 1489 | 171 | 74.5 | 4 | 2 |
| 2024-03-28 | 1509 | 233 | 75.5 | 24 | 13 |
| 2024-04-30 | 1421 | 215 | 71.0 | 24 | 11 |
| 2024-05-31 | 1459 | 268 | 73.0 | 44 | 15 |
| 2024-06-28 | 1521 | 285 | 76.0 | 47 | 13 |
| 2024-07-31 | 1501 | 344 | 75.0 | 136 | 72 |
| 2024-08-30 | 1452 | 352 | 72.6 | 133 | 54 |
| 2024-09-30 | 1525 | 448 | 76.2 | 200 | 101 |
| 2024-10-31 | 1469 | 368 | 73.5 | 128 | 51 |
| 2024-11-29 | 1622 | 390 | 81.1 | 149 | 77 |
| 2024-12-31 | 1625 | 465 | 81.2 | 218 | 90 |
| 2025-01-31 | 1602 | 549 | 80.1 | 380 | 162 |
| 2025-02-28 | 1660 | 645 | 83.0 | 546 | 246 |
| 2025-03-31 | 1661 | 529 | 83.1 | 223 | 67 |
| 2025-04-30 | 1648 | 129 | 82.4 | 8 | 2 |
| 2025-05-30 | 1642 | 88 | 82.1 | 6 | 4 |
| 2025-06-30 | 1726 | 154 | 86.3 | 9 | 8 |
| 2025-07-31 | 1727 | 139 | 86.4 | 13 | 9 |
| 2025-08-29 | 1775 | 126 | 88.8 | 10 | 7 |
| 2025-09-30 | 1835 | 100 | 91.8 | 14 | 11 |
| 2025-10-31 | 1804 | 173 | 90.2 | 18 | 12 |
| 2025-11-28 | 1827 | 110 | 91.4 | 11 | 10 |
| 2025-12-31 | 1813 | 99 | 90.7 | 10 | 8 |
| 2026-01-30 | 1864 | 114 | 93.2 | 13 | 10 |
| 2026-02-27 | 1911 | 109 | 95.6 | 13 | 6 |
| 2026-03-31 | 1904 | 83 | 95.2 | 4 | 2 |
| 2026-04-30 | 1890 | 233 | 94.5 | 16 | 4 |
| 2026-05-29 | 1991 | 305 | 99.6 | 29 | 7 |
| 2026-06-30 | 2077 | 273 | 103.9 | 16 | 6 |
| 2026-07-31 | 1944 | 271 | 97.2 | 58 | 39 |
| 2026-08-31 | 1963 | 339 | 98.2 | 115 | 28 |
| 2026-09-30 | 1980 | 393 | 99.0 | 135 | 84 |
| 2026-10-30 | 1922 | 289 | 96.1 | 78 | 52 |
| 2026-11-16 | 1958 | 380 | 97.9 | 133 | 65 |

## dev

| screen | names | cost/side | total | Sharpe | max drawdown | beta | by year |
|---|---|---|---|---|---|---|---|
| published 5% | 223.9 | 0.0 bp | +85.48% | 1.9 | 17.5% | 1.19 | 2023: +13.5%, 2024: +33.2%, 2025: +22.8% |
| published 5% | 223.9 | 0.5 bp | +74.02% | 1.71 | 17.7% | 1.19 | 2023: +11.9%, 2024: +29.9%, 2025: +19.7% |
| published 5% | 223.9 | 1.0 bp | +63.26% | 1.52 | 18.2% | 1.19 | 2023: +10.4%, 2024: +26.6%, 2025: +16.8% |
| published 5% | 223.9 | 2.5 bp | +34.82% | 0.95 | 19.6% | 1.19 | 2023: +6.0%, 2024: +17.4%, 2025: +8.3% |
| published 5% | 223.9 | 5.0 bp | -2.02% | 0.0 | 21.8% | 1.19 | 2023: -1.0%, 2024: +3.5%, 2025: -4.4% |
| FDR q=10% | 75.9 | 0.0 bp | +76.1% | 1.62 | 17.4% | 1.008 | 2023: +1.7%, 2024: +32.7%, 2025: +30.5% |
| FDR q=10% | 75.9 | 0.5 bp | +69.12% | 1.51 | 17.7% | 1.008 | 2023: +1.5%, 2024: +30.0%, 2025: +28.2% |
| FDR q=10% | 75.9 | 1.0 bp | +62.42% | 1.4 | 17.9% | 1.008 | 2023: +1.2%, 2024: +27.3%, 2025: +26.0% |
| FDR q=10% | 75.9 | 2.5 bp | +43.86% | 1.06 | 19.3% | 1.008 | 2023: +0.5%, 2024: +19.7%, 2025: +19.6% |
| FDR q=10% | 75.9 | 5.0 bp | +17.51% | 0.51 | 21.6% | 1.009 | 2023: -0.7%, 2024: +8.0%, 2025: +9.6% |
| FDR q=5% | 33.8 | 0.0 bp | +49.01% | 1.27 | 17.7% | 0.902 | 2023: +0.6%, 2024: +28.9%, 2025: +15.0% |
| FDR q=5% | 33.8 | 0.5 bp | +44.19% | 1.17 | 17.9% | 0.902 | 2023: +0.4%, 2024: +26.7%, 2025: +13.3% |
| FDR q=5% | 33.8 | 1.0 bp | +39.53% | 1.07 | 18.2% | 0.903 | 2023: +0.3%, 2024: +24.6%, 2025: +11.6% |
| FDR q=5% | 33.8 | 2.5 bp | +26.42% | 0.77 | 18.9% | 0.903 | 2023: -0.1%, 2024: +18.5%, 2025: +6.8% |
| FDR q=5% | 33.8 | 5.0 bp | +7.25% | 0.28 | 20.7% | 0.905 | 2023: -0.7%, 2024: +9.0%, 2025: -0.8% |

| screen | break-even cost per side | daily turnover |
|---|---|---|
| published 5% | 5.01 bp | 196.8% of capital |
| FDR q=10% | 7.32 bp | 124.7% of capital |
| FDR q=5% | 6.39 bp | 101.4% of capital |

- Random portfolios (1000): strategy gross +85.48% vs random median +49.02% (95th percentile +57.73%); the strategy beats 100.0% of them.
- Block bootstrap (21-day blocks): 0.0 bp: annual return 95% CI [6.37, 49.72]%, Sharpe [0.5, 3.51], P(loss) 0.005; 1.0 bp: annual return 95% CI [1.38, 42.33]%, Sharpe [0.17, 3.02], P(loss) 0.017; 2.5 bp: annual return 95% CI [-6.18, 32.46]%, Sharpe [-0.34, 2.45], P(loss) 0.095
- Average stock-night (gross): 0.047%; without the 10 best: 0.042%.
- Without overnight moves over 25% (possible bad adjustments): gross total 73.55%.
- SPY overnight only: 45.09%; SPY buy and hold: 67.84%.

### $30,000 whole-share sizing (ranked versions are adaptations)

| method | names | cost | total | Sharpe | max drawdown | idle cash | orders/day | largest position |
|---|---|---|---|---|---|---|---|---|
| all qualifying | all | 0.0 bp/side | +68.29% | 2.12 | 8.7% | 27.3% | 308.7 | 10.0% |
| all qualifying | all | 1.0 bp/side | +52.34% | 1.75 | 8.7% | 28.4% | 302.5 | 10.0% |
| all qualifying | all | 2.5 bp/side | +32.48% | 1.2 | 8.5% | 30.0% | 292.9 | 10.0% |
| all qualifying | all | $0.005/share/side | +34.33% | 1.25 | 8.9% | 29.7% | 295.0 | 10.0% |
| t-statistic | 25 | 0.0 bp/side | +158.58% | 2.21 | 15.3% | 4.0% | 48.2 | 10.0% |
| t-statistic | 25 | 1.0 bp/side | +126.62% | 1.92 | 15.5% | 4.1% | 48.1 | 10.0% |
| t-statistic | 25 | 2.5 bp/side | +89.26% | 1.51 | 15.4% | 4.5% | 48.1 | 10.0% |
| t-statistic | 25 | $0.005/share/side | +87.78% | 1.5 | 15.4% | 4.4% | 48.1 | 10.0% |
| t-statistic | 50 | 0.0 bp/side | +118.24% | 2.1 | 14.8% | 7.2% | 93.5 | 10.0% |
| t-statistic | 50 | 1.0 bp/side | +90.92% | 1.75 | 15.0% | 7.2% | 93.4 | 10.0% |
| t-statistic | 50 | 2.5 bp/side | +61.14% | 1.32 | 15.0% | 7.7% | 93.3 | 10.0% |
| t-statistic | 50 | $0.005/share/side | +64.67% | 1.37 | 14.9% | 7.4% | 93.4 | 10.0% |
| t-statistic | 100 | 0.0 bp/side | +80.56% | 1.9 | 14.0% | 13.2% | 172.0 | 10.0% |
| t-statistic | 100 | 1.0 bp/side | +60.98% | 1.55 | 14.0% | 13.9% | 171.1 | 10.0% |
| t-statistic | 100 | 2.5 bp/side | +36.47% | 1.05 | 14.3% | 14.9% | 169.6 | 10.0% |
| t-statistic | 100 | $0.005/share/side | +40.8% | 1.14 | 14.3% | 14.6% | 170.0 | 10.0% |
| intercept | 25 | 0.0 bp/side | +211.87% | 1.69 | 24.0% | 4.0% | 47.5 | 10.0% |
| intercept | 25 | 1.0 bp/side | +178.27% | 1.54 | 24.7% | 4.1% | 47.4 | 10.0% |
| intercept | 25 | 2.5 bp/side | +130.04% | 1.28 | 25.1% | 4.3% | 47.4 | 10.0% |
| intercept | 25 | $0.005/share/side | +97.96% | 1.08 | 25.6% | 4.4% | 47.4 | 10.0% |
| intercept | 50 | 0.0 bp/side | +146.23% | 1.58 | 24.8% | 4.8% | 93.5 | 10.0% |
| intercept | 50 | 1.0 bp/side | +117.59% | 1.38 | 25.2% | 4.8% | 93.5 | 10.0% |
| intercept | 50 | 2.5 bp/side | +79.92% | 1.07 | 25.4% | 5.2% | 93.4 | 10.0% |
| intercept | 50 | $0.005/share/side | +63.31% | 0.92 | 25.8% | 5.3% | 93.3 | 10.0% |
| intercept | 100 | 0.0 bp/side | +87.12% | 1.42 | 24.0% | 10.0% | 174.9 | 10.0% |
| intercept | 100 | 1.0 bp/side | +66.48% | 1.18 | 24.3% | 10.4% | 174.6 | 10.0% |
| intercept | 100 | 2.5 bp/side | +39.48% | 0.81 | 25.0% | 11.0% | 174.1 | 10.0% |
| intercept | 100 | $0.005/share/side | +36.32% | 0.76 | 25.7% | 11.0% | 174.1 | 10.0% |
| intercept lower bound | 25 | 0.0 bp/side | +210.56% | 1.78 | 21.9% | 4.0% | 47.6 | 10.0% |
| intercept lower bound | 25 | 1.0 bp/side | +175.29% | 1.61 | 22.7% | 4.1% | 47.6 | 10.0% |
| intercept lower bound | 25 | 2.5 bp/side | +128.98% | 1.34 | 23.0% | 4.3% | 47.5 | 10.0% |
| intercept lower bound | 25 | $0.005/share/side | +101.62% | 1.16 | 23.6% | 4.3% | 47.5 | 10.0% |
| intercept lower bound | 50 | 0.0 bp/side | +136.4% | 1.69 | 21.8% | 5.6% | 93.5 | 10.0% |
| intercept lower bound | 50 | 1.0 bp/side | +109.9% | 1.47 | 22.3% | 5.7% | 93.5 | 10.0% |
| intercept lower bound | 50 | 2.5 bp/side | +74.4% | 1.13 | 22.5% | 5.9% | 93.4 | 10.0% |
| intercept lower bound | 50 | $0.005/share/side | +65.17% | 1.03 | 22.8% | 5.9% | 93.4 | 10.0% |
| intercept lower bound | 100 | 0.0 bp/side | +78.94% | 1.52 | 19.4% | 11.6% | 173.3 | 10.0% |
| intercept lower bound | 100 | 1.0 bp/side | +59.67% | 1.24 | 19.4% | 12.1% | 172.8 | 10.0% |
| intercept lower bound | 100 | 2.5 bp/side | +35.32% | 0.84 | 19.4% | 12.9% | 171.7 | 10.0% |
| intercept lower bound | 100 | $0.005/share/side | +35.24% | 0.83 | 19.7% | 12.8% | 171.9 | 10.0% |

## 2026 (already examined)

| screen | names | cost/side | total | Sharpe | max drawdown | beta | by year |
|---|---|---|---|---|---|---|---|
| published 5% | 227.0 | 0.0 bp | +17.62% | 1.53 | 9.3% | 1.217 | 2026: +17.6% |
| published 5% | 227.0 | 0.5 bp | +15.07% | 1.33 | 9.5% | 1.217 | 2026: +15.1% |
| published 5% | 227.0 | 1.0 bp | +12.58% | 1.13 | 9.8% | 1.217 | 2026: +12.6% |
| published 5% | 227.0 | 2.5 bp | +5.43% | 0.54 | 10.4% | 1.217 | 2026: +5.4% |
| published 5% | 227.0 | 5.0 bp | -5.51% | -0.45 | 13.1% | 1.217 | 2026: -5.5% |
| FDR q=10% | 43.3 | 0.0 bp | +13.91% | 1.24 | 9.5% | 0.807 | 2026: +13.9% |
| FDR q=10% | 43.3 | 0.5 bp | +11.99% | 1.08 | 9.6% | 0.807 | 2026: +12.0% |
| FDR q=10% | 43.3 | 1.0 bp | +10.11% | 0.93 | 9.7% | 0.807 | 2026: +10.1% |
| FDR q=10% | 43.3 | 2.5 bp | +4.65% | 0.47 | 10.1% | 0.806 | 2026: +4.7% |
| FDR q=10% | 43.3 | 5.0 bp | -3.85% | -0.29 | 13.9% | 0.806 | 2026: -3.8% |
| FDR q=5% | 21.3 | 0.0 bp | +13.02% | 1.72 | 4.9% | 0.402 | 2026: +13.0% |
| FDR q=5% | 21.3 | 0.5 bp | +11.69% | 1.55 | 5.1% | 0.402 | 2026: +11.7% |
| FDR q=5% | 21.3 | 1.0 bp | +10.38% | 1.39 | 5.4% | 0.402 | 2026: +10.4% |
| FDR q=5% | 21.3 | 2.5 bp | +6.54% | 0.91 | 6.4% | 0.402 | 2026: +6.5% |
| FDR q=5% | 21.3 | 5.0 bp | +0.43% | 0.1 | 8.5% | 0.402 | 2026: +0.4% |

| screen | break-even cost per side | daily turnover |
|---|---|---|
| published 5% | 3.87 bp | 200.0% of capital |
| FDR q=10% | 4.05 bp | 154.7% of capital |
| FDR q=5% | 5.31 bp | 107.9% of capital |

- Random portfolios (1000): strategy gross +17.62% vs random median +10.89% (95th percentile +14.56%); the strategy beats 99.8% of them.
- Block bootstrap (21-day blocks): 0.0 bp: annual return 95% CI [-12.3, 45.86]%, Sharpe [-0.89, 3.16], P(loss) 0.142; 1.0 bp: annual return 95% CI [-15.78, 38.77]%, Sharpe [-1.2, 2.78], P(loss) 0.219; 2.5 bp: annual return 95% CI [-22.72, 29.02]%, Sharpe [-1.85, 2.11], P(loss) 0.443
- Average stock-night (gross): 0.068%; without the 10 best: 0.058%.
- Without overnight moves over 25% (possible bad adjustments): gross total 14.13%.
- SPY overnight only: 9.92%; SPY buy and hold: 9.16%.

### $30,000 whole-share sizing (ranked versions are adaptations)

| method | names | cost | total | Sharpe | max drawdown | idle cash | orders/day | largest position |
|---|---|---|---|---|---|---|---|---|
| all qualifying | all | 0.0 bp/side | +10.38% | 1.22 | 8.1% | 31.2% | 325.8 | 1.2% |
| all qualifying | all | 1.0 bp/side | +7.36% | 0.9 | 8.5% | 31.6% | 323.3 | 1.2% |
| all qualifying | all | 2.5 bp/side | +2.55% | 0.35 | 9.0% | 32.2% | 319.8 | 1.2% |
| all qualifying | all | $0.005/share/side | +1.96% | 0.28 | 9.2% | 32.3% | 319.4 | 1.2% |
| t-statistic | 25 | 0.0 bp/side | +14.11% | 1.03 | 11.2% | 2.6% | 50.0 | 4.0% |
| t-statistic | 25 | 1.0 bp/side | +9.31% | 0.72 | 11.5% | 2.8% | 50.0 | 4.0% |
| t-statistic | 25 | 2.5 bp/side | +2.27% | 0.24 | 13.0% | 2.9% | 50.0 | 4.0% |
| t-statistic | 25 | $0.005/share/side | +3.6% | 0.33 | 12.5% | 3.0% | 50.0 | 4.0% |
| t-statistic | 50 | 0.0 bp/side | +11.31% | 0.98 | 11.2% | 6.3% | 99.4 | 2.0% |
| t-statistic | 50 | 1.0 bp/side | +7.12% | 0.65 | 11.6% | 6.5% | 99.4 | 2.0% |
| t-statistic | 50 | 2.5 bp/side | +0.81% | 0.14 | 13.7% | 6.5% | 99.4 | 2.0% |
| t-statistic | 50 | $0.005/share/side | +1.88% | 0.23 | 13.1% | 6.6% | 99.4 | 2.0% |
| t-statistic | 100 | 0.0 bp/side | +13.97% | 1.39 | 9.4% | 14.5% | 186.2 | 1.2% |
| t-statistic | 100 | 1.0 bp/side | +9.52% | 0.99 | 9.7% | 15.1% | 185.5 | 1.2% |
| t-statistic | 100 | 2.5 bp/side | +4.14% | 0.47 | 10.2% | 15.3% | 184.9 | 1.2% |
| t-statistic | 100 | $0.005/share/side | +5.28% | 0.58 | 10.4% | 15.3% | 184.9 | 1.2% |
| intercept | 25 | 0.0 bp/side | -17.3% | -0.6 | 31.3% | 2.5% | 50.0 | 4.0% |
| intercept | 25 | 1.0 bp/side | -21.09% | -0.78 | 33.2% | 2.5% | 50.0 | 4.0% |
| intercept | 25 | 2.5 bp/side | -25.29% | -1.0 | 36.4% | 2.7% | 49.9 | 4.0% |
| intercept | 25 | $0.005/share/side | -29.65% | -1.24 | 39.6% | 3.0% | 49.8 | 4.0% |
| intercept | 50 | 0.0 bp/side | -5.83% | -0.14 | 19.6% | 6.2% | 98.2 | 2.0% |
| intercept | 50 | 1.0 bp/side | -9.06% | -0.3 | 21.8% | 6.3% | 98.2 | 2.0% |
| intercept | 50 | 2.5 bp/side | -14.82% | -0.6 | 25.8% | 6.6% | 98.1 | 2.0% |
| intercept | 50 | $0.005/share/side | -18.65% | -0.82 | 28.3% | 6.8% | 98.0 | 2.0% |
| intercept | 100 | 0.0 bp/side | -0.12% | 0.08 | 11.2% | 15.3% | 182.0 | 1.2% |
| intercept | 100 | 1.0 bp/side | -4.17% | -0.2 | 13.6% | 15.6% | 181.5 | 1.2% |
| intercept | 100 | 2.5 bp/side | -9.24% | -0.57 | 17.2% | 16.0% | 180.7 | 1.2% |
| intercept | 100 | $0.005/share/side | -10.47% | -0.66 | 18.1% | 16.3% | 180.4 | 1.2% |
| intercept lower bound | 25 | 0.0 bp/side | -11.75% | -0.45 | 27.3% | 2.7% | 50.0 | 4.0% |
| intercept lower bound | 25 | 1.0 bp/side | -15.74% | -0.67 | 29.5% | 2.9% | 50.0 | 4.0% |
| intercept lower bound | 25 | 2.5 bp/side | -20.88% | -0.96 | 33.0% | 2.9% | 50.0 | 4.0% |
| intercept lower bound | 25 | $0.005/share/side | -24.12% | -1.15 | 35.0% | 2.9% | 50.0 | 4.0% |
| intercept lower bound | 50 | 0.0 bp/side | -0.19% | 0.09 | 14.9% | 7.5% | 97.7 | 2.0% |
| intercept lower bound | 50 | 1.0 bp/side | -3.84% | -0.12 | 17.3% | 7.6% | 97.6 | 2.0% |
| intercept lower bound | 50 | 2.5 bp/side | -9.04% | -0.44 | 21.0% | 8.2% | 97.4 | 2.0% |
| intercept lower bound | 50 | $0.005/share/side | -11.32% | -0.59 | 22.7% | 8.3% | 97.3 | 2.0% |
| intercept lower bound | 100 | 0.0 bp/side | +6.53% | 0.6 | 8.6% | 16.1% | 182.2 | 1.2% |
| intercept lower bound | 100 | 1.0 bp/side | +2.5% | 0.28 | 8.9% | 16.3% | 181.7 | 1.2% |
| intercept lower bound | 100 | 2.5 bp/side | -2.42% | -0.14 | 10.5% | 16.5% | 181.1 | 1.2% |
| intercept lower bound | 100 | $0.005/share/side | -2.63% | -0.16 | 10.6% | 16.6% | 181.0 | 1.2% |

## Execution facts (official Alpaca docs, checked 2026-11-17)

- Market-on-open = time_in_force "opg"; orders after 9:28 am ET are rejected until 7:00 pm, then queue for the next open. Unfilled opg orders are cancelled after the open.
- Market-on-close = time_in_force "cls"; orders after 3:50 pm ET are rejected until 7:00 pm. Routed to the primary exchange closing auction.
- Fractional (dollar) orders are NOT supported for opg / cls, so whole shares only. The docs mark opg/cls with a "contact sales" asterisk.
- Paper trading is a simulation against quotes: not routed to an exchange, no market impact, no latency slippage, random 10% partial fills.

Sector concentration could not be measured: no point-in-time sector data is available to this system.
