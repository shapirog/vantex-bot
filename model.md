# VANTEX City research: our own model (Vantex Score)

Candidates: every stock opening 2%+ above yesterday's close (price $1+, $1M+ daily dollar volume). 182750 candidate stock-days. Model learns only Jun 2023 - Jun 2025. Each day it buys the top 5 scores at the open and sells at the close. Costs included.

| period | picks | trades | win rate | avg net | median | avg w/o best 10 | t-stat | avg at 2x costs | account (5 x 20%) | max drawdown |
|---|---|---|---|---|---|---|---|---|---|---|
| learn | top | 2605 | 63.4% | 7.152% | 2.903% | 6.663% | 20.93 | 6.701% | +8.693719163269744e+16% | 10.2% |
| learn | top + 7% stop / 15% target | 2605 | 54.8% | 2.706% | 1.312% | 2.659% | 16.02 | 2.276% |  |  |
| learn | random | 2605 | 38.5% | -0.576% | -1.056% | -0.952% | -2.65 | -0.995% | -97.2% | 98.6% |
| learn | bottom | 2605 | 15.2% | -8.592% | -8.174% | -9.716% | -13.49 | -9.081% | -100.0% | 100.0% |
| learn | all | 94708 | 39.5% | -0.856% | -0.907% | -0.9% | -29.58 | -1.23% |  |  |
| check | top | 640 | 43.6% | -0.237% | -1.102% | -1.218% | -0.44 | -0.626% | -42.9% | 63.4% |
| check | top + 7% stop / 15% target | 640 | 39.4% | -0.23% | -2.959% | -0.47% | -0.71 | -0.619% |  |  |
| check | random | 640 | 38.4% | -1.444% | -1.443% | -1.905% | -4.5 | -1.827% | -86.0% | 86.8% |
| check | bottom | 640 | 27.5% | -5.505% | -7.14% | -7.601% | -5.51 | -5.944% | -100.0% | 100.0% |
| check | all | 26584 | 39.2% | -1.021% | -1.089% | -1.079% | -20.0 | -1.377% |  |  |
| test | top | 1105 | 41.6% | -0.524% | -1.78% | -1.282% | -1.19 | -0.907% | -81.0% | 83.1% |
| test | top + 7% stop / 15% target | 1105 | 35.3% | -1.085% | -6.492% | -1.231% | -4.53 | -1.468% |  |  |
| test | random | 1105 | 40.4% | -0.775% | -1.003% | -1.158% | -3.26 | -1.096% | -84.7% | 85.5% |
| test | bottom | 1105 | 28.7% | -5.651% | -6.932% | -7.172% | -7.18 | -6.076% | -100.0% | 100.0% |
| test | all | 61458 | 43.3% | -0.51% | -0.546% | -0.555% | -15.84 | -0.814% |  |  |

"random" = 5 random candidates per day; "bottom" = the 5 lowest scores; "all" = every candidate.

## Does a higher score mean a better day? (2026, never seen)

| score decile (test) | stock-days | avg open->close (gross) | up % |
|---|---|---|---|
| 1 (lowest) | 6145 | -1.464% | 39.6% |
| 2 | 6146 | -0.625% | 40.8% |
| 3 | 6146 | -0.297% | 45.5% |
| 4 | 6146 | -0.336% | 44.2% |
| 5 | 6146 | -0.173% | 44.3% |
| 6 | 6145 | -0.215% | 44.9% |
| 7 | 6146 | +0.037% | 47.9% |
| 8 | 6146 | +0.210% | 49.6% |
| 9 | 6146 | +0.114% | 47.6% |
| 10 (highest) | 6146 | +0.705% | 52.5% |

## What the model leans on (higher = more important, check period)

from_high20 136.33, gap 123.93, spy_gap 92.45, log_px 60.18, breadth 32.76, rvol_prev 30.6, vol20 27.98, log_adv 20.5, weekday 17.93, r1 17.86, gap_sigma 14.79, rng_prev 13.34, r20 -5.67, r5 -6.6

Daily bars: the official open is used as the fill; a real order at 9:30 on a small stock can fill worse. Stop/target order inside a day is unknown (stop assumed first). A backtest is not proof.
