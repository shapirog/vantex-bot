# VANTEX City swing-strategy research - dev - 2023-06-01 to 2025-12-31

5092 stocks with data. Signal at the close, buy the next open, costs 0.05%-0.50% per side by liquidity plus fees. Buy-and-hold SPY over the same period: +69.0%.

| strategy | signals | win rate | avg win | avg loss | expectancy | without top 10 | avg return/trade | profit factor | avg days | $2,500 account | max drawdown |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S1. Gapper follow-through (up 10%+ on 3x volume, hold 5 days) | 3746 | 40.5% | 0.89R | -0.65R | -0.024R | -0.074R | -1.06% | 0.94 | 4.5 | $1625.66 (-35.0%) | 39.5% |
| S2. Big-catalyst hold (up 15%+ on 5x volume, hold 20 days) | 1243 | 35.1% | 1.4R | -0.86R | -0.066R | -0.139R | -3.14% | 0.88 | 14.2 | $2222.33 (-11.1%) | 25.2% |
| S3. RSI(2) pullback in an uptrend (exit above 5-day average) | 80804 | 63.0% | 0.24R | -0.39R | 0.008R | 0.007R | 0.11% | 1.05 | 3.7 | $2501.97 (+0.1%) | 15.6% |
| S4. 52-week-high breakout on volume (exit under 20-day average) | 10326 | 33.6% | 1.56R | -0.82R | -0.025R | -0.04R | -0.63% | 0.96 | 14.4 | $2197.27 (-12.1%) | 25.3% |

## Expectancy by year (R per trade)

- S1. Gapper follow-through (up 10%+ on 3x volume, hold 5 days): 2023: -0.055R (556), 2024: 0.026R (1528), 2025: -0.059R (1661), 2026: -0.64R (1)
- S2. Big-catalyst hold (up 15%+ on 5x volume, hold 20 days): 2023: -0.142R (182), 2024: 0.042R (495), 2025: -0.136R (565), 2026: 0.03R (1)
- S3. RSI(2) pullback in an uptrend (exit above 5-day average): 2023: -0.003R (13985), 2024: 0.001R (36777), 2025: 0.017R (29365), 2026: 0.221R (677)
- S4. 52-week-high breakout on volume (exit under 20-day average): 2023: -0.213R (1754), 2024: 0.064R (4902), 2025: -0.051R (3664), 2026: -0.82R (6)

Survivorship bias: today's stock list only, so stocks that were delisted (often after collapsing) are missing. That flatters buy strategies.
"Without top 10" removes the 10 best trades, to show whether a few lucky trades carry the result.
A backtest is not proof.
