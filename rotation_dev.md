# VANTEX City research batch 4: portfolio rotations - dev - 2023-06-01 to 2025-12-31

2910 liquid stocks. Trades at the open of each rebalance day, costs by liquidity on both sides, decisions use the prior close.

| strategy | periods | total return | worst drawdown | Sharpe | % periods up | by year |
|---|---|---|---|---|---|---|
| L1. Large-cap momentum (top 20 of 500, monthly) | 30 | +134.5% | 31.0% | 0.98 | 56.7% | 2023: +12.1%, 2024: +40.4%, 2025: +48.9% |
| L2. Large-cap momentum + SPY trend filter | 30 | +54.3% | 31.0% | 0.61 | 46.7% | 2023: -3.6%, 2024: +40.4%, 2025: +14.0% |
| L3. ETF dual momentum (SPY / EFA / bonds) | 30 | +47.5% | 9.3% | 1.4 | 73.3% | 2023: +4.5%, 2024: +24.9%, 2025: +12.9% |
| L4. Weekly short-term reversal (20 biggest losers of 500) | 135 | +38.7% | 36.1% | 0.52 | 51.9% | 2023: +22.3%, 2024: +8.3%, 2025: +4.7% |
| L5. Low volatility (20 calmest of 500, monthly) | 30 | +16.6% | 7.6% | 0.63 | 63.3% | 2023: +2.2%, 2024: +13.9%, 2025: +0.2% |
| Buy and hold SPY | 31 | +70.0% | 7.8% | 1.8 | 74.2% | 2023: +14.2%, 2024: +26.4%, 2025: +17.7% |

A strategy is only interesting if it beats buy-and-hold SPY on risk-adjusted return (Sharpe) or drawdown, not just on total return in one stretch.
Survivorship bias: today's stock list only (small for the 500 most-traded stocks, not zero). A backtest is not proof.
