# Vantex lab 7 - trading tiny-float premarket movers - 2026-11-15T19:33:01

## VERDICT: FAIL
Chosen on train: **E2 PM-high break | X3 +10%/-10%**
```
{
 "0 train: best combo mean > 0 and t >= 2": false,
 "1 test mean > 0 and CI low > 0": false,
 "2 test profit factor >= 1.2": false,
 "3 test trades >= 100": true,
 "4 $2,500 at 1% risk ends test above $2,500": false
}
```
## Chosen combo - train
```
{
 "trades": 248,
 "mean_pct": -1.94,
 "median_pct": -4.78,
 "win_rate_pct": 39.1,
 "profit_factor": 0.66,
 "t_stat": -3.1,
 "ci95_pct": [
  -3.14,
  -0.72
 ],
 "best_pct": 26.5,
 "worst_pct": -17.4
}
```
## Chosen combo - test
```
{
 "trades": 251,
 "mean_pct": -2.95,
 "median_pct": -8.36,
 "win_rate_pct": 36.3,
 "profit_factor": 0.55,
 "t_stat": -4.57,
 "ci95_pct": [
  -4.21,
  -1.67
 ],
 "best_pct": 26.8,
 "worst_pct": -21.4
}
```
## Test account at 1% risk
```
{
 "risk_pct": 1.0,
 "end_equity": 1460.43,
 "net_pct": -41.6,
 "max_dd_pct": 43.0
}
```
## Whole period accounts
```
{
 "1%": {
  "risk_pct": 1.0,
  "end_equity": 959.64,
  "net_pct": -61.6,
  "max_dd_pct": 62.4
 },
 "2%": {
  "risk_pct": 2.0,
  "end_equity": 369.71,
  "net_pct": -85.2,
  "max_dd_pct": 85.8
 },
 "5%": {
  "risk_pct": 5.0,
  "end_equity": 17.26,
  "net_pct": -99.3,
  "max_dd_pct": 99.4
 }
}
```
## $40K in 42 sessions
```
{
 "1%": {
  "p_reach_40k": 0.0,
  "p_double": 0.0,
  "p_half": 0.0,
  "median": 2189
 },
 "2%": {
  "p_reach_40k": 0.0,
  "p_double": 0.0,
  "p_half": 0.56,
  "median": 1920
 },
 "5%": {
  "p_reach_40k": 0.0,
  "p_double": 0.01,
  "p_half": 49.73,
  "median": 1253
 }
}
```
## All 16 combos (transparency only)
| combo | train n | train mean % | train t | test n | test mean % | test PF |
|---|---|---|---|---|---|---|
| E1 open | X1 hold, -25% stop | 1708 | -5.75 | -15.07 | 1763 | -4.21 | 0.54 |
| E1 open | X2 +20%/-15% | 1708 | -5.01 | -17.64 | 1763 | -4.17 | 0.47 |
| E1 open | X3 +10%/-10% | 1708 | -4.84 | -21.9 | 1763 | -3.88 | 0.42 |
| E1 open | X4 trail 15% | 1708 | -5.45 | -20.58 | 1763 | -4.6 | 0.36 |
| E2 PM-high break | X1 hold, -25% stop | 248 | -5.83 | -5.32 | 251 | 3.64 | 1.3 |
| E2 PM-high break | X2 +20%/-15% | 248 | -2.14 | -2.44 | 251 | -3.41 | 0.6 |
| E2 PM-high break | X3 +10%/-10% | 248 | -1.94 | -3.1 | 251 | -2.95 | 0.55 |
| E2 PM-high break | X4 trail 15% | 248 | -3.32 | -4.28 | 251 | -3.99 | 0.45 |
| E3 at alert | X1 hold, -25% stop | 1658 | -9.4 | -18.16 | 1757 | -6.31 | 0.53 |
| E3 at alert | X2 +20%/-15% | 1658 | -5.77 | -16.85 | 1757 | -5.24 | 0.47 |
| E3 at alert | X3 +10%/-10% | 1658 | -4.73 | -19.39 | 1757 | -4.64 | 0.4 |
| E3 at alert | X4 trail 15% | 1658 | -6.26 | -21.05 | 1757 | -5.49 | 0.38 |
| E4 VWAP reclaim | X1 hold, -25% stop | 1232 | -3.4 | -7.62 | 1342 | -2.49 | 0.68 |
| E4 VWAP reclaim | X2 +20%/-15% | 1232 | -2.69 | -8.13 | 1342 | -1.78 | 0.72 |
| E4 VWAP reclaim | X3 +10%/-10% | 1232 | -2.28 | -9.03 | 1342 | -1.48 | 0.71 |
| E4 VWAP reclaim | X4 trail 15% | 1232 | -3.15 | -10.1 | 1342 | -2.71 | 0.53 |

## Coverage
```
{
 "premarket_alerts": 14830,
 "tiny_float_alerts": 3616,
 "simulated_trades": 39836,
 "stats": {
  "quote": 9447,
  "no_quote": 512,
  "no_minute_bars": 35
 },
 "lab5_stats": {
  "requests": 10260,
  "quotes_found": 9447,
  "quotes_missing": 512
 },
 "splits_ok": true
}
```
## Limitations
- Shares outstanding stands in for float (true float is smaller).
- No historical halt feed: halts fill at the next bar.
- One SIP quote at entry; exits pay half the entry spread. Premarket stops are simulated (real premarket stop orders are not supported at Alpaca).
- Survivorship: Alpaca's asset list plus SEC's current ticker map.
- This is trial ~670 overall; only the single train-chosen combo can count.
