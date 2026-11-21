# VANTEX City research: news + volume study

Jun 2026 to 2026-11-17. 5480 stocks with daily bars, 219609 news items ({'dropped: no symbol / 3+ symbols': 69490, 'kept pre': 101854, 'kept intra': 48009}). Dev = Jun-Sep, test = Oct-now. All numbers are per trade, after estimated costs (both sides). Long only.

## Rules

| rule | period | trades | win rate | avg net | median | avg without best 5 | profit factor | t-stat | avg at 2x costs |
|---|---|---|---|---|---|---|---|---|---|
| C1 control: gap >= 4%, no news (open->close) | dev | 3031 | 38.8% | -1.186% | -1.577% | -1.715% | 0.73 | -3.51 | -1.664% |
| C1 control: gap >= 4%, no news (open->close) | test | 984 | 38.0% | -2.143% | -1.563% | -2.672% | 0.53 | -5.13 | -2.712% |
| C2 control: volume spike, no news (next open->close) | dev | 507 | 42.8% | -1.185% | -1.221% | -2.282% | 0.8 | -1.47 | -1.892% |
| C2 control: volume spike, no news (next open->close) | test | 96 | 44.8% | -0.995% | -1.189% | -3.172% | 0.84 | -0.58 | -1.824% |
| N1 news gap-and-go (open->close) | dev | 1377 | 40.8% | -1.257% | -1.108% | -1.467% | 0.64 | -5.3 | -1.548% |
| N1 news gap-and-go (open->close) | test | 714 | 47.8% | -0.399% | -0.2% | -0.608% | 0.86 | -1.33 | -0.723% |
| N1s news gap-and-go, 7% stop / 15% target | dev | 1377 | 38.7% | -0.929% | -1.55% | -0.987% | 0.69 | -5.61 | -1.222% |
| N1s news gap-and-go, 7% stop / 15% target | test | 714 | 44.8% | -0.368% | -0.642% | -0.475% | 0.86 | -1.61 | -0.69% |
| N2 day-2 continuation (next open->close) | dev | 103 | 44.7% | -0.67% | -0.363% | -1.375% | 0.72 | -1.18 | -1.021% |
| N2 day-2 continuation (next open->close) | test | 57 | 47.4% | -0.431% | -0.255% | -1.337% | 0.79 | -0.66 | -0.728% |
| N3 episodic pivot (stop at pivot low, 10 days) | dev | 106 | 27.4% | -2.811% | -3.38% | -4.178% | 0.47 | -2.72 | -3.116% |
| N3 episodic pivot (stop at pivot low, 10 days) | test | 42 | 14.3% | -4.338% | -4.86% | -5.955% | 0.18 | -4.21 | -4.618% |
| N4 post-earnings drift (20 days) | dev | 352 | 44.3% | -2.483% | -1.62% | -3.007% | 0.62 | -3.4 | -2.738% |
| N4 post-earnings drift (20 days) | test | 17 | 47.1% | -9.915% | -3.986% | -22.231% | 0.39 | -1.33 | -10.109% |
| N5 intraday news, next day (open->close) | dev | 292 | 41.8% | -0.318% | -0.602% | -0.641% | 0.82 | -1.16 | -0.487% |
| N5 intraday news, next day (open->close) | test | 135 | 47.4% | 0.024% | -0.071% | -0.289% | 1.02 | 0.07 | -0.124% |

## By price (both periods)

| rule | price | trades | win rate | avg net |
|---|---|---|---|---|
| C1 control: gap >= 4%, no news (open->close) | under $1 | 245 | 23.3% | -2.432% |
| C1 control: gap >= 4%, no news (open->close) | $1-5 | 1295 | 35.8% | -1.476% |
| C1 control: gap >= 4%, no news (open->close) | $5-20 | 1299 | 40.3% | -1.945% |
| C1 control: gap >= 4%, no news (open->close) | $20+ | 1176 | 43.0% | -0.571% |
| C2 control: volume spike, no news (next open->close) | under $1 | 56 | 32.1% | -3.099% |
| C2 control: volume spike, no news (next open->close) | $1-5 | 256 | 47.3% | 0.738% |
| C2 control: volume spike, no news (next open->close) | $5-20 | 189 | 40.7% | -1.957% |
| C2 control: volume spike, no news (next open->close) | $20+ | 102 | 43.1% | -3.352% |
| N1 news gap-and-go (open->close) | under $1 | 42 | 33.3% | -3.101% |
| N1 news gap-and-go (open->close) | $1-5 | 344 | 34.6% | -3.088% |
| N1 news gap-and-go (open->close) | $5-20 | 578 | 43.6% | -0.718% |
| N1 news gap-and-go (open->close) | $20+ | 1127 | 46.0% | -0.362% |
| N1s news gap-and-go, 7% stop / 15% target | under $1 | 42 | 26.2% | -4.252% |
| N1s news gap-and-go, 7% stop / 15% target | $1-5 | 344 | 31.1% | -1.889% |
| N1s news gap-and-go, 7% stop / 15% target | $5-20 | 578 | 40.5% | -0.657% |
| N1s news gap-and-go, 7% stop / 15% target | $20+ | 1127 | 44.5% | -0.297% |
| N2 day-2 continuation (next open->close) | under $1 | 2 | 0.0% | -11.962% |
| N2 day-2 continuation (next open->close) | $1-5 | 18 | 27.8% | -1.566% |
| N2 day-2 continuation (next open->close) | $5-20 | 54 | 44.4% | -0.688% |
| N2 day-2 continuation (next open->close) | $20+ | 86 | 51.2% | -0.05% |
| N3 episodic pivot (stop at pivot low, 10 days) | $1-5 | 34 | 20.6% | -3.835% |
| N3 episodic pivot (stop at pivot low, 10 days) | $5-20 | 41 | 29.3% | -3.4% |
| N3 episodic pivot (stop at pivot low, 10 days) | $20+ | 73 | 21.9% | -2.882% |
| N4 post-earnings drift (20 days) | under $1 | 4 | 25.0% | -15.646% |
| N4 post-earnings drift (20 days) | $1-5 | 29 | 37.9% | -7.912% |
| N4 post-earnings drift (20 days) | $5-20 | 101 | 42.6% | -2.97% |
| N4 post-earnings drift (20 days) | $20+ | 235 | 46.4% | -1.917% |
| N5 intraday news, next day (open->close) | $1-5 | 24 | 45.8% | -0.391% |
| N5 intraday news, next day (open->close) | $5-20 | 80 | 40.0% | -0.484% |
| N5 intraday news, next day (open->close) | $20+ | 323 | 44.3% | -0.129% |

## Event study: does news change what a gap does?

| period | news | gap at open | stock-days | open->close avg | open->close up % |
|---|---|---|---|---|---|
| dev | good news | +0%..+4% | 12967 | -0.063% | 46.7% |
| dev | good news | +10%..+20% | 251 | -0.942% | 42.2% |
| dev | good news | +4%..+10% | 995 | -0.39% | 43.1% |
| dev | good news | -10%..-4% | 787 | -0.348% | 49.3% |
| dev | good news | -100%..-10% | 341 | 1.29% | 55.1% |
| dev | good news | -4%..+0% | 10022 | -0.135% | 46.2% |
| dev | good news | >= +20% | 131 | -5.348% | 35.1% |
| dev | negative news | +0%..+4% | 647 | -0.723% | 41.9% |
| dev | negative news | +10%..+20% | 14 | -3.442% | 35.7% |
| dev | negative news | +4%..+10% | 65 | -1.338% | 33.8% |
| dev | negative news | -10%..-4% | 153 | 0.169% | 51.0% |
| dev | negative news | -100%..-10% | 99 | -3.555% | 39.4% |
| dev | negative news | -4%..+0% | 693 | -0.599% | 43.3% |
| dev | negative news | >= +20% | 19 | -16.027% | 26.3% |
| dev | no news | +0%..+4% | 91716 | -0.154% | 44.4% |
| dev | no news | +10%..+20% | 282 | 0.255% | 40.4% |
| dev | no news | +4%..+10% | 2435 | -0.674% | 42.1% |
| dev | no news | -10%..-4% | 2817 | 0.909% | 53.7% |
| dev | no news | -100%..-10% | 637 | 0.879% | 53.5% |
| dev | no news | -4%..+0% | 71664 | -0.133% | 46.7% |
| dev | no news | >= +20% | 314 | -1.789% | 32.8% |
| test | good news | +0%..+4% | 6253 | -0.105% | 47.7% |
| test | good news | +10%..+20% | 154 | 0.299% | 50.6% |
| test | good news | +4%..+10% | 510 | 0.357% | 51.0% |
| test | good news | -10%..-4% | 548 | -0.71% | 48.2% |
| test | good news | -100%..-10% | 223 | -0.971% | 43.5% |
| test | good news | -4%..+0% | 4936 | -0.222% | 48.3% |
| test | good news | >= +20% | 50 | -5.609% | 38.0% |
| test | negative news | +0%..+4% | 171 | -1.093% | 40.9% |
| test | negative news | +10%..+20% | 5 | 2.542% | 60.0% |
| test | negative news | +4%..+10% | 17 | 0.829% | 52.9% |
| test | negative news | -10%..-4% | 30 | -1.226% | 50.0% |
| test | negative news | -100%..-10% | 39 | -2.597% | 41.0% |
| test | negative news | -4%..+0% | 171 | -0.625% | 45.6% |
| test | negative news | >= +20% | 4 | -6.458% | 50.0% |
| test | no news | +0%..+4% | 31511 | -0.254% | 43.3% |
| test | no news | +10%..+20% | 94 | -2.727% | 37.2% |
| test | no news | +4%..+10% | 823 | -0.712% | 41.6% |
| test | no news | -10%..-4% | 1141 | -0.404% | 44.3% |
| test | no news | -100%..-10% | 204 | -3.538% | 46.1% |
| test | no news | -4%..+0% | 24126 | -0.317% | 47.0% |
| test | no news | >= +20% | 67 | -10.435% | 25.4% |

## By news type (good pre-open news, any gap)

| period | news type (pre-open, good) | stock-days | avg gap | open->close avg | up % | open->5-day close avg |
|---|---|---|---|---|---|---|
| dev | ANALYST | 8454 | +0.19% | -0.044% | 47.0% | -0.10% |
| dev | CONTRACT | 1333 | +0.39% | -0.162% | 46.7% | -1.09% |
| dev | DEAL | 2046 | +0.56% | -0.442% | 42.7% | -0.98% |
| dev | EARNINGS | 4734 | +0.33% | +0.061% | 49.2% | +0.43% |
| dev | FINANCING | 615 | +0.14% | -0.140% | 46.5% | -0.88% |
| dev | PARTNERSHIP | 2621 | +0.25% | -0.189% | 45.1% | -0.61% |
| dev | PATENT | 188 | -0.67% | -0.485% | 46.3% | -0.92% |
| dev | PRODUCT | 3627 | +0.16% | -0.261% | 45.8% | -0.53% |
| dev | REGULATORY | 1160 | +0.31% | -0.324% | 43.0% | -0.75% |
| dev | TRIAL | 716 | -0.40% | -0.189% | 46.5% | -1.04% |
| test | ANALYST | 4737 | +0.05% | -0.089% | 48.9% | -0.20% |
| test | CONTRACT | 459 | -0.31% | -0.375% | 44.0% | -1.91% |
| test | DEAL | 792 | +0.47% | -0.278% | 46.6% | -1.38% |
| test | EARNINGS | 3515 | -0.11% | -0.117% | 49.4% | +0.23% |
| test | FINANCING | 235 | -0.11% | -0.249% | 46.4% | -0.68% |
| test | PARTNERSHIP | 871 | +0.17% | -0.251% | 46.6% | -1.42% |
| test | PATENT | 33 | +0.01% | -3.314% | 33.3% | -9.29% |
| test | PRODUCT | 1284 | +0.09% | -0.247% | 46.7% | -0.61% |
| test | REGULATORY | 389 | +0.57% | -0.155% | 46.0% | +0.14% |
| test | TRIAL | 359 | -0.15% | -1.166% | 43.5% | -1.52% |

## News coverage

- dev: 551 of 1436 stock-days that gapped up 10%+ had pre-open news in Alpaca's feed
- test: 275 of 534 stock-days that gapped up 10%+ had pre-open news in Alpaca's feed

Controls C1/C2 use the same entries with no news in the last 3 days. Daily bars only: same-day stop/target order assumed stop-first. Official opening prices can be better than a real order would get, especially under $5. A backtest is not proof.
