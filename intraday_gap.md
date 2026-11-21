# VANTEX City research: ChatGPT ideas #4 and #5 on 1-minute bars

Wait for the gap to prove itself after the open, then trade the next minute. Costs included. Dev = Jun 2023 - Dec 2025, test = 2026.

| rule | period | trades | win rate | avg net | median | avg w/o best 5 | profit factor | t-stat | avg at 2x costs |
|---|---|---|---|---|---|---|---|---|---|
| G4 gap-up survivor (long) | dev | 3629 | 33.4% | -0.126% | -0.931% | -0.234% | 0.9 | -1.61 | -0.296% |
| G4 gap-up survivor (long) | test | 1953 | 35.2% | -0.086% | -0.775% | -0.149% | 0.92 | -1.23 | -0.249% |
| G5 failed opening range (short, ETB) | dev | 4016 | 51.3% | 0.527% | 0.106% | 0.497% | 1.43 | 8.07 | 0.388% |
| G5 failed opening range (short, ETB) | test | 2760 | 43.8% | -0.36% | -0.345% | -0.402% | 0.74 | -5.77 | -0.5% |
| G5L mirror: opening range breakout (long) | dev | 3568 | 41.7% | -0.373% | -0.681% | -0.449% | 0.79 | -4.39 | -0.513% |
| G5L mirror: opening range breakout (long) | test | 2613 | 48.6% | 0.021% | -0.115% | -0.028% | 1.02 | 0.27 | -0.119% |

## By year

| rule | year | trades | win rate | avg net |
|---|---|---|---|---|
| G4 gap-up survivor (long) | 2023 | 502 | 34.3% | 0.078% |
| G4 gap-up survivor (long) | 2024 | 1358 | 37.7% | 0.08% |
| G4 gap-up survivor (long) | 2025 | 1769 | 29.9% | -0.342% |
| G4 gap-up survivor (long) | 2026 | 1953 | 35.2% | -0.086% |
| G5 failed opening range (short, ETB) | 2023 | 355 | 49.0% | -0.163% |
| G5 failed opening range (short, ETB) | 2024 | 1273 | 42.5% | -0.164% |
| G5 failed opening range (short, ETB) | 2025 | 2388 | 56.4% | 0.998% |
| G5 failed opening range (short, ETB) | 2026 | 2760 | 43.8% | -0.36% |
| G5L mirror: opening range breakout (long) | 2023 | 388 | 45.9% | -0.146% |
| G5L mirror: opening range breakout (long) | 2024 | 1176 | 48.9% | 0.27% |
| G5L mirror: opening range breakout (long) | 2025 | 2004 | 36.6% | -0.795% |
| G5L mirror: opening range breakout (long) | 2026 | 2613 | 48.6% | 0.021% |

G4 volume check uses the City volume curve x 20-day average volume (substitution, see file header). Shorts assume Alpaca easy-to-borrow (free) using TODAY's flags. Historical SIP minute bars; the live free feed is 15 minutes delayed (IEX real-time only), so a live version would need the $99/month real-time plan or IEX bars. A backtest is not proof.
