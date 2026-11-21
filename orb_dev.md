# VANTEX City strategy test: 5-minute opening-range breakout on stocks in play - dev - 60 sessions

One strategy, published rules, full real-time market data (what entries would need live), costs included: half the quoted spread in and out, 0.02% extra slippage, SEC/FINRA fees. Every in-play stock that triggers is taken. $2,500 start, 0.5% risk per trade.


| rule set | trades | win rate | avg win | avg loss | expectancy | profit factor | net P&L | max drawdown | Sharpe |
|---|---|---|---|---|---|---|---|---|---|
| F1. ORB as published (long + short, stop 10% ATR, exit at close) | 717 | 17.6% | 5.91R | -1.46R | -0.166R | 0.93 | $-141.22 | $352.05 | -0.97 |
| F2. Same, long only | 361 | 17.5% | 6.73R | -1.47R | -0.037R | 1.02 | $24.65 | $245.78 | 0.22 |
| F3. Same entries, exit at 2R target instead of the close | 711 | 37.6% | 1.49R | -1.45R | -0.347R | 0.67 | $-479.2 | $506.41 | -8.26 |
| F4. Same, wider stop (25% ATR), exit at close | 715 | 32.7% | 2.08R | -1.13R | -0.081R | 0.97 | $-79.53 | $467.03 | -0.43 |

## Why candidates were not traded (F1)

- range never broken: 246
- spread too wide at entry: 190
- no trades in the first 5 minutes: 49
- size rounds to 0 shares: 43
- no quote at entry: 3
- first candle flat (no direction): 1

Approximation: first-5-minute relative volume = first-5-minute volume / (14-day average daily volume x share of a normal day done by 9:35, measured on SPY).
A backtest is not proof. The Oct-Nov test period stays untouched until one rule set earns it.
