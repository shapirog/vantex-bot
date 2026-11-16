# Vantex lab 10 - EMA 9 x VWAP cross (3-minute) - 2026-11-16T18:16:42-05:00

EMA9 x VWAP(hlcc4) cross, 3-min candles, stop-and-reverse, flat 15:57, 0.03% slippage

## All 40 symbols pooled
```
{
 "train": {
  "trades": 17542,
  "win_rate_pct": 28.5,
  "mean_bps": -5.91,
  "total_pct": -1036.5,
  "profit_factor": 0.85,
  "ci95_mean_bps_day_clustered": [
   -9.36,
   -2.03
  ]
 },
 "test": {
  "trades": 14307,
  "win_rate_pct": 29.4,
  "mean_bps": -4.88,
  "total_pct": -698.1,
  "profit_factor": 0.88,
  "ci95_mean_bps_day_clustered": [
   -7.68,
   -1.85
  ]
 },
 "train_long": {
  "trades": 8882,
  "win_rate_pct": 27.5,
  "mean_bps": -9.39,
  "total_pct": -833.6,
  "profit_factor": 0.77,
  "ci95_mean_bps_day_clustered": [
   -14.86,
   -4.04
  ]
 },
 "test_long": {
  "trades": 7121,
  "win_rate_pct": 27.9,
  "mean_bps": -6.74,
  "total_pct": -479.7,
  "profit_factor": 0.83,
  "ci95_mean_bps_day_clustered": [
   -11.88,
   -1.49
  ]
 }
}
```
## "Best stock" picked on TRAIN, judged on TEST
```
{
 "best3_on_train": [
  "CVNA",
  "UPST",
  "INTC"
 ],
 "their_train": {
  "trades": 1288,
  "win_rate_pct": 32.1,
  "mean_bps": 5.79,
  "total_pct": 74.5,
  "profit_factor": 1.12,
  "ci95_mean_bps_day_clustered": [
   -2.81,
   15.45
  ]
 },
 "their_test": {
  "trades": 1026,
  "win_rate_pct": 32.5,
  "mean_bps": -1.94,
  "total_pct": -19.9,
  "profit_factor": 0.96,
  "ci95_mean_bps_day_clustered": [
   -9.63,
   6.41
  ]
 },
 "their_test_long": {
  "trades": 510,
  "win_rate_pct": 31.8,
  "mean_bps": -5.18,
  "total_pct": -26.4,
  "profit_factor": 0.9,
  "ci95_mean_bps_day_clustered": [
   -17.64,
   7.7
  ]
 },
 "best1": "CVNA",
 "best1_test": {
  "trades": 347,
  "win_rate_pct": 30.3,
  "mean_bps": -5.96,
  "total_pct": -20.7,
  "profit_factor": 0.89,
  "ci95_mean_bps_day_clustered": [
   -18.3,
   7.99
  ]
 },
 "best1_test_account": {
  "end_equity": 1976.46,
  "max_dd_pct": 31.1
 }
}
```
Positive in BOTH periods: ['INTC', 'SHOP']

## Every symbol (sorted by test)
| symbol | train trades | train bps/trade | train PF | test trades | test bps/trade | test PF | test long-only bps |
|---|---|---|---|---|---|---|---|
| RIOT | 470 | -7.51 | 0.9 | 331 | 13.58 | 1.2 | 11.94 |
| SHOP | 424 | 0.24 | 1.01 | 342 | 5.4 | 1.14 | 5.13 |
| INTC | 405 | 2.8 | 1.06 | 300 | 5.2 | 1.09 | 5.77 |
| ARM | 442 | -6.7 | 0.84 | 307 | 1.9 | 1.03 | 4.15 |
| NFLX | 425 | -8.62 | 0.7 | 341 | 0.09 | 1.0 | -5.81 |
| F | 473 | -4.86 | 0.79 | 340 | -0.07 | 1.0 | -4.04 |
| SOFI | 444 | -4.51 | 0.91 | 325 | -0.15 | 1.0 | -7.74 |
| HOOD | 437 | -2.45 | 0.95 | 338 | -0.49 | 0.99 | -4.76 |
| SMCI | 425 | -6.95 | 0.87 | 372 | -0.53 | 0.99 | -14.47 |
| RIVN | 519 | -13.82 | 0.76 | 431 | -1.21 | 0.97 | -3.09 |
| AMD | 394 | -2.53 | 0.94 | 336 | -1.82 | 0.96 | -3.95 |
| AAPL | 451 | -7.16 | 0.71 | 341 | -1.97 | 0.91 | 0.71 |
| PLTR | 435 | -9.76 | 0.78 | 307 | -2.38 | 0.94 | 3.11 |
| UPST | 434 | 4.46 | 1.08 | 379 | -3.91 | 0.92 | -7.46 |
| MSTR | 450 | -3.6 | 0.94 | 344 | -4.35 | 0.93 | -3.8 |
| BAC | 421 | -5.75 | 0.75 | 349 | -4.46 | 0.8 | -8.71 |
| SPY | 408 | -6.32 | 0.59 | 381 | -4.69 | 0.63 | -5.93 |
| QQQ | 434 | -7.07 | 0.63 | 370 | -4.89 | 0.73 | -7.53 |
| MSFT | 443 | -6.47 | 0.71 | 349 | -5.09 | 0.8 | -5.56 |
| AVGO | 407 | -7.87 | 0.79 | 317 | -5.26 | 0.85 | -9.38 |
| MARA | 479 | -9.15 | 0.88 | 370 | -5.4 | 0.93 | -7.12 |
| IWM | 404 | -3.85 | 0.81 | 340 | -5.68 | 0.69 | -7.86 |
| DIA | 411 | -7.2 | 0.55 | 347 | -5.92 | 0.58 | -6.86 |
| NVDA | 439 | -3.97 | 0.87 | 361 | -5.92 | 0.82 | -10.51 |
| CVNA | 449 | 9.76 | 1.2 | 347 | -5.96 | 0.89 | -12.17 |
| BA | 471 | -15.16 | 0.52 | 411 | -6.09 | 0.8 | -13.32 |
| CRWD | 442 | -9.04 | 0.77 | 335 | -6.35 | 0.87 | 3.41 |
| UBER | 406 | -8.2 | 0.74 | 374 | -6.39 | 0.79 | -4.09 |
| MU | 419 | -7.54 | 0.85 | 358 | -7.04 | 0.87 | -8.11 |
| GOOGL | 384 | -3.89 | 0.86 | 398 | -7.34 | 0.73 | -10.27 |
| AMZN | 424 | -5.48 | 0.8 | 368 | -7.64 | 0.71 | -9.86 |
| JPM | 408 | -7.28 | 0.7 | 383 | -8.29 | 0.61 | -9.81 |
| DKNG | 507 | -10.32 | 0.76 | 399 | -8.3 | 0.83 | -7.06 |
| XOM | 418 | -6.08 | 0.75 | 344 | -8.39 | 0.64 | -6.48 |
| COIN | 439 | -1.23 | 0.98 | 341 | -8.45 | 0.84 | -15.87 |
| AFRM | 493 | -3.06 | 0.94 | 352 | -9.29 | 0.81 | -6.34 |
| META | 436 | -9.09 | 0.66 | 375 | -10.74 | 0.69 | -16.14 |
| TSLA | 452 | -4.75 | 0.87 | 400 | -13.52 | 0.65 | -9.88 |
| SOUN | 492 | -15.81 | 0.79 | 426 | -15.21 | 0.73 | -18.78 |
| SNOW | 428 | -5.96 | 0.85 | 378 | -18.23 | 0.63 | -19.99 |

## Notes
- Stock moves stand in for calls/puts (no historical option quotes). Options add leverage, time decay and spread.
- Day-trade limit: under $25K only 3 day trades per 5 days in a margin account; accounts here ignore it (upper bound).
- The reel shows a monthly P&L screenshot; it does not show the rules for exits, position size or which tickers.
