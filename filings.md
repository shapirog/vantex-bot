# VANTEX City research: SEC filings (ChatGPT ideas #1 and #3)

New activist 13D filings found for tradable stocks: 3342; insider open-market buys: 74289; insider clusters: 2042. Enter the open after the filing day, hold 20 sessions (2 x ATR stop). Costs included.

| rule | stocks | period | trades | win rate | avg net (20 days) | median | avg w/o best 5 | t-stat | vs SPY | random-stock placebo | at 2x costs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 activist 13D (new stake) | all ($1+, $1M+/day) | dev | 768 | 38.8% | -1.803% | -4.022% | -3.294% | -1.67 | -3.056% | -0.325% | -2.223% |
| F1 activist 13D (new stake) | all ($1+, $1M+/day) | test | 261 | 38.3% | -1.502% | -5.428% | -4.08% | -0.8 | -2.606% | -1.435% | -1.935% |
| F1 activist 13D (new stake) | liquid ($5+, $20M+/day) | dev | 249 | 37.8% | -4.212% | -3.177% | -5.377% | -3.36 | -5.366% | -0.92% | -4.345% |
| F1 activist 13D (new stake) | liquid ($5+, $20M+/day) | test | 81 | 33.3% | -1.832% | -6.203% | -5.168% | -0.85 | -2.491% | -1.609% | -1.969% |
| F3 insider buying cluster | all ($1+, $1M+/day) | dev | 983 | 52.2% | 2.171% | 0.871% | 1.499% | 3.84 | +0.877% | 1.622% | 1.824% |
| F3 insider buying cluster | all ($1+, $1M+/day) | test | 111 | 45.9% | -1.472% | -3.095% | -2.925% | -1.21 | -1.425% | 3.068% | -1.729% |
| F3 insider buying cluster | liquid ($5+, $20M+/day) | dev | 458 | 58.1% | 3.111% | 1.849% | 2.029% | 4.07 | +1.629% | 2.805% | 2.971% |
| F3 insider buying cluster | liquid ($5+, $20M+/day) | test | 67 | 43.3% | -2.636% | -4.373% | -4.333% | -2.08 | -1.919% | 3.59% | -2.759% |

"vs SPY" = average net return minus SPY over the same days. Placebo = a random tradable stock entered the same day with the same exit. Filing dates only (not times), so entries are one day later than the earliest possible. 13D ticker mapping uses today's SEC list (survivorship). A backtest is not proof.
