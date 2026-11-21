# VANTEX City research: range trading (buy the bottom of a repeating range, sell the top)

Range = last 20 sessions, 6-25% wide, at least 2 touches of the top and of the bottom, not trending. Buy limit at bottom + 1%, target top - 2%, stop bottom - 3%. Dollar columns assume $250 per trade (every signal taken, so busy weeks have many trades). CONTROL = buy at the open on a random range day instead of at the bottom. Dev = 2019-2024, test = 2025-now.

| rule | period | trades | win rate | avg per trade | median | profit factor | t-stat | avg week ($250/trade) | weeks up | avg month | months up | worst month |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DAY | dev | 99473 | 45.0% | -0.157% | -0.149% | 0.78 | -28.93 | $-125 | 44.1% | $-541 | 33.3% | $-3,195 |
| DAY | test | 39515 | 46.0% | -0.137% | -0.119% | 0.82 | -14.44 | $-137 | 38.4% | $-589 | 30.4% | $-2,778 |
| WEEK | dev | 52042 | 46.1% | +0.039% | -0.509% | 1.02 | 2.08 | $+16 | 58.0% | $+70 | 56.2% | $-6,294 |
| WEEK | test | 21161 | 44.1% | -0.045% | -0.766% | 0.97 | -1.44 | $-24 | 57.6% | $-104 | 60.9% | $-4,827 |
| MONTH | dev | 42747 | 38.4% | +0.224% | -3.592% | 1.09 | 7.61 | $+76 | 62.7% | $+328 | 58.9% | $-6,931 |
| MONTH | test | 16630 | 35.8% | +0.04% | -3.922% | 1.02 | 0.82 | $+17 | 58.6% | $+73 | 60.9% | $-7,748 |
| CONTROL DAY | dev | 84377 | 49.0% | -0.146% | -0.026% | 0.79 | -23.28 | $-98 | 36.6% | $-429 | 23.6% | $-1,939 |
| CONTROL DAY | test | 33996 | 50.4% | -0.085% | +0.009% | 0.88 | -7.79 | $-73 | 45.5% | $-316 | 30.4% | $-1,533 |
| CONTROL WEEK | dev | 65178 | 59.4% | -0.0% | +0.463% | 1.0 | -0.02 | $-0 | 58.7% | $-1 | 52.1% | $-4,917 |
| CONTROL WEEK | test | 26343 | 59.0% | +0.003% | +0.501% | 1.0 | 0.13 | $+2 | 56.6% | $+10 | 65.2% | $-4,475 |
| CONTROL MONTH | dev | 52899 | 66.8% | +0.159% | +1.07% | 1.08 | 6.36 | $+66 | 63.5% | $+289 | 58.9% | $-9,393 |
| CONTROL MONTH | test | 20571 | 66.2% | +0.104% | +1.122% | 1.05 | 2.46 | $+54 | 63.6% | $+233 | 60.9% | $-7,716 |

Stocks in a range right now: 604 (see range_now.json, nearest the bottom first).

Daily bars: a day-trade target cannot be checked against the entry inside one day, so the DAY rule only exits at the stop or the close. A backtest is not proof.
