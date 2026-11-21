# VANTEX City research batch 4: portfolio rotations - test - 2026-01-01 to 2026-11-10

3056 liquid stocks. Trades at the open of each rebalance day, costs by liquidity on both sides, decisions use the prior close.

| strategy | periods | total return | worst drawdown | Sharpe | % periods up | by year |
|---|---|---|---|---|---|---|
| L1. Large-cap momentum (top 20 of 500, monthly) | 9 | +0.3% | 36.5% | 0.31 | 55.6% | 2026: +0.3% |
| L2. Large-cap momentum + SPY trend filter | 9 | -26.4% | 36.5% | -0.49 | 44.4% | 2026: -26.4% |
| L3. ETF dual momentum (SPY / EFA / bonds) | 9 | +1.7% | 4.2% | 0.26 | 55.6% | 2026: +1.7% |
| L4. Weekly short-term reversal (20 biggest losers of 500) | 45 | -26.1% | 44.4% | -0.83 | 44.4% | 2026: -26.1% |
| L5. Low volatility (20 calmest of 500, monthly) | 9 | +8.7% | 9.3% | 0.63 | 55.6% | 2026: +8.7% |
| Buy and hold SPY | 10 | +11.6% | 4.9% | 1.05 | 60.0% | 2026: +11.6% |

A strategy is only interesting if it beats buy-and-hold SPY on risk-adjusted return (Sharpe) or drawdown, not just on total return in one stretch.
Survivorship bias: today's stock list only (small for the 500 most-traded stocks, not zero). A backtest is not proof.
