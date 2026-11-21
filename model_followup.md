# Vantex Score follow-ups

Same model and scores as model.md (nothing retrained or tuned).

| test | period | trades | win rate | avg net | median | t-stat | at 2x costs |
|---|---|---|---|---|---|---|---|
| S1 short bottom 5, 15% stop, borrow 0.5%/trade | learn | 2605 | 64.7% | 2.197% | 2.297% | 12.77 | 1.704% |
| S1 short bottom 5, 15% stop, borrow 2%/trade | learn | 2605 | 55.5% | 0.697% | 0.797% | 4.05 | 0.204% |
| L1 liquid ($5+, $20M+/day): buy top 3 | learn | 1563 | 58.2% | 3.47% | 0.998% | 11.72 | 3.324% |
| S1 short bottom 5, 15% stop, borrow 0.5%/trade | check | 640 | 53.4% | 0.221% | 0.642% | 0.64 | -0.137% |
| S1 short bottom 5, 15% stop, borrow 2%/trade | check | 640 | 45.6% | -1.279% | -0.858% | -3.74 | -1.637% |
| L1 liquid ($5+, $20M+/day): buy top 3 | check | 384 | 48.2% | 0.228% | -0.166% | 0.37 | 0.087% |
| S1 short bottom 5, 15% stop, borrow 0.5%/trade | test | 1105 | 50.9% | -0.052% | 0.112% | -0.22 | -0.38% |
| S1 short bottom 5, 15% stop, borrow 2%/trade | test | 1105 | 40.9% | -1.552% | -1.388% | -6.6 | -1.88% |
| L1 liquid ($5+, $20M+/day): buy top 3 | test | 663 | 45.1% | 0.183% | -0.564% | 0.46 | 0.042% |

## Liquid names only ($5+, $20M+/day), 2026 score deciles

| decile | stock-days | avg open->close (gross) | up % |
|---|---|---|---|
| 1 | 3193 | -0.078% | 47.9% |
| 2 | 3193 | -0.110% | 48.5% |
| 3 | 3193 | -0.141% | 47.2% |
| 4 | 3193 | -0.089% | 46.4% |
| 5 | 3193 | -0.239% | 44.0% |
| 6 | 3193 | -0.133% | 46.6% |
| 7 | 3193 | +0.180% | 51.0% |
| 8 | 3193 | +0.184% | 50.8% |
| 9 | 3193 | +0.256% | 49.9% |
| 10 | 3194 | +0.879% | 54.2% |

Short limits: shortable / easy-to-borrow flags are today's (no history), so some past picks may not have been shortable then. Borrow fees on crowded small caps can be far higher than 2% a day, and shorts can be recalled. Uptick-rule (SSR) days are not modelled. A backtest is not proof.
