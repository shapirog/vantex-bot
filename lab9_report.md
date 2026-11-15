# Vantex lab 9 - day-1 close to day-2 (history) - 2026-11-15T17:43:52-05:00

## VERDICT: FAIL
```
{
 "train mean > 0": false,
 "test mean > 0 and CI low > 0": false,
 "test profit factor >= 1.2": false,
 "test trades >= 100": false,
 "$2,500 ends test period up": false
}
```
## Train
```
{
 "trades": 38,
 "win_rate_pct": 18.4,
 "mean_pct": -13.34,
 "median_pct": -15.64,
 "ci95_pct_day_clustered": [
  -18.77,
  -7.52
 ],
 "profit_factor": 0.23,
 "best_pct": 44.2,
 "worst_pct": -51.0
}
```
## Test
```
{
 "trades": 21,
 "win_rate_pct": 19.0,
 "mean_pct": -6.09,
 "median_pct": -15.6,
 "ci95_pct_day_clustered": [
  -18.03,
  9.9
 ],
 "profit_factor": 0.59,
 "best_pct": 124.0,
 "worst_pct": -35.0
}
```
## All
```
{
 "trades": 59,
 "win_rate_pct": 18.6,
 "mean_pct": -10.76,
 "median_pct": -15.6,
 "ci95_pct_day_clustered": [
  -16.51,
  -3.62
 ],
 "profit_factor": 0.34,
 "best_pct": 124.0,
 "worst_pct": -51.0
}
```
## Accounts ($2,500)
```
{
 "all": {
  "end_equity": 1667.43,
  "net_pct": -33.3,
  "max_dd_pct": 36.17,
  "worst_day_pct": -3.25
 },
 "test": {
  "end_equity": 2293.45,
  "net_pct": -8.26,
  "max_dd_pct": 12.04,
  "worst_day_pct": -2.27
 },
 "all_with_1pct_slippage": {
  "end_equity": 1607.22,
  "net_pct": -35.71,
  "max_dd_pct": 38.03,
  "worst_day_pct": -3.31
 }
}
```
Gross mean (ask in, bid out, no costs): -9.86%
## Exits
```
{
 "stop": 19,
 "15:45 exit": 15,
 "stop (gap at open)": 22,
 "+20% half": 10,
 "15:45 exit (no quote: -10% placeholder)": 3
}
```
## Skips
```
{
 "spread > 2%": 18,
 "no quote within 60 s of 15:51": 5
}
```
## By month
```
{
 "2025-09": {
  "trades": 3,
  "win_rate_pct": 0.0,
  "mean_pct": -11.59,
  "median_pct": -15.51,
  "ci95_pct_day_clustered": [
   -15.51,
   -9.63
  ],
  "profit_factor": 0.0,
  "best_pct": -3.6,
  "worst_pct": -15.7
 },
 "2025-10": {
  "trades": 7,
  "win_rate_pct": 0.0,
  "mean_pct": -20.69,
  "median_pct": -16.76,
  "ci95_pct_day_clustered": [
   -31.59,
   -13.24
  ],
  "profit_factor": 0.0,
  "best_pct": -7.2,
  "worst_pct": -49.2
 },
 "2025-11": {
  "trades": 2,
  "win_rate_pct": 50.0,
  "mean_pct": 16.85,
  "median_pct": 16.85,
  "ci95_pct_day_clustered": [
   -10.46,
   44.15
  ],
  "profit_factor": 4.22,
  "best_pct": 44.2,
  "worst_pct": -10.5
 },
 "2025-12": {
  "trades": 4,
  "win_rate_pct": 25.0,
  "mean_pct": -12.71,
  "median_pct": -14.09,
  "ci95_pct_day_clustered": [
   -34.24,
   10.2
  ],
  "profit_factor": 0.29,
  "best_pct": 20.4,
  "worst_pct": -43.0
 },
 "2026-01": {
  "trades": 5,
  "win_rate_pct": 40.0,
  "mean_pct": -11.91,
  "median_pct": -15.79,
  "ci95_pct_day_clustered": [
   -28.75,
   -0.68
  ],
  "profit_factor": 0.19,
  "best_pct": 12.0,
  "worst_pct": -34.4
 },
 "2026-02": {
  "trades": 5,
  "win_rate_pct": 20.0,
  "mean_pct": -26.77,
  "median_pct": -21.66,
  "ci95_pct_day_clustered": [
   -41.11,
   -21.22
  ],
  "profit_factor": 0.05,
  "best_pct": 7.5,
  "worst_pct": -51.0
 },
 "2026-03": {
  "trades": 7,
  "win_rate_pct": 28.6,
  "mean_pct": -4.15,
  "median_pct": -8.83,
  "ci95_pct_day_clustered": [
   -10.77,
   2.32
  ],
  "profit_factor": 0.69,
  "best_pct": 34.8,
  "worst_pct": -43.7
 },
 "2026-04": {
  "trades": 5,
  "win_rate_pct": 0.0,
  "mean_pct": -17.56,
  "median_pct": -15.54,
  "ci95_pct_day_clustered": [
   -24.8,
   -12.49
  ],
  "profit_factor": 0.0,
  "best_pct": -10.5,
  "worst_pct": -31.1
 },
 "2026-05": {
  "trades": 4,
  "win_rate_pct": 0.0,
  "mean_pct": -22.01,
  "median_pct": -20.07,
  "ci95_pct_day_clustered": [
   -28.81,
   -17.04
  ],
  "profit_factor": 0.0,
  "best_pct": -15.6,
  "worst_pct": -32.3
 },
 "2026-06": {
  "trades": 2,
  "win_rate_pct": 50.0,
  "mean_pct": -9.26,
  "median_pct": -9.26,
  "ci95_pct_day_clustered": [
   -23.46,
   4.95
  ],
  "profit_factor": 0.21,
  "best_pct": 4.9,
  "worst_pct": -23.5
 },
 "2026-07": {
  "trades": 4,
  "win_rate_pct": 25.0,
  "mean_pct": -5.67,
  "median_pct": -4.43,
  "ci95_pct_day_clustered": [
   -12.58,
   0.0
  ],
  "profit_factor": 0.07,
  "best_pct": 1.7,
  "worst_pct": -15.5
 },
 "2026-08": {
  "trades": 2,
  "win_rate_pct": 0.0,
  "mean_pct": -16.73,
  "median_pct": -16.73,
  "ci95_pct_day_clustered": [
   -17.68,
   -15.79
  ],
  "profit_factor": 0.0,
  "best_pct": -15.8,
  "worst_pct": -17.7
 },
 "2026-09": {
  "trades": 4,
  "win_rate_pct": 25.0,
  "mean_pct": 14.46,
  "median_pct": -15.54,
  "ci95_pct_day_clustered": [
   -30.16,
   89.09
  ],
  "profit_factor": 1.88,
  "best_pct": 124.0,
  "worst_pct": -35.0
 },
 "2026-10": {
  "trades": 3,
  "win_rate_pct": 33.3,
  "mean_pct": 1.0,
  "median_pct": -15.6,
  "ci95_pct_day_clustered": [
   -32.06,
   50.64
  ],
  "profit_factor": 1.06,
  "best_pct": 50.6,
  "worst_pct": -32.1
 },
 "2026-11": {
  "trades": 2,
  "win_rate_pct": 0.0,
  "mean_pct": -13.04,
  "median_pct": -13.04,
  "ci95_pct_day_clustered": [
   -15.61,
   -10.46
  ],
  "profit_factor": 0.0,
  "best_pct": -10.5,
  "worst_pct": -15.6
 }
}
```
## What ALL qualifying runners did on day 2 (descriptive)
```
{
 "runners": 82,
 "with_day2_data": 81,
 "d2_open_pct": {
  "median": -5.7,
  "p25": -16.5,
  "p75": 0.8
 },
 "d2_high_pct": {
  "median": 1.5,
  "p25": -7.4,
  "p75": 16.6
 },
 "d2_low_pct": {
  "median": -18.4,
  "p25": -31.7,
  "p75": -8.0
 },
 "d2_close_pct": {
  "median": -10.0,
  "p25": -20.4,
  "p75": 4.4
 },
 "share_closing_day2_above_1550_price_pct": 28.4,
 "share_opening_below_minus15_pct": 25.9,
 "share_touching_plus20_pct": 21.0
}
```
## Coverage
```
{
 "daily_prefilter_pass": 4106,
 "excluded_shares_unknown: no SEC count": 349,
 "excluded_split": 50,
 "excluded_shares_unknown: count too old": 286,
 "excluded_shares_unknown: no count filed yet": 94,
 "pairs": 297,
 "universe_excluded": {
  "name says ETF/fund/warrant/right/unit/preferred/note": 2174,
  "exchange (OTC/ARCA/BATS/other)": 22507,
  "symbol format (class/when-issued/odd)": 1242,
  "5-letter warrant/right/unit suffix": 1002
 }
}
```
## Data
```
{
 "lab8": {
  "quote_requests": 668,
  "quotes_invalid_locked_crossed_or_zero": 23001
 },
 "lab5": {
  "requests": 1521
 },
 "lab6": {
  "requests": 4173,
  "no_cik": 18,
  "facts_missing": 44,
  "splits_found": 1079
 },
 "lab9": {
  "no_quote_at_1545": 3
 },
 "quote_sizes": {
  "value": 100,
  "evidence": "SPY median ask size 3.0 before vs 480.0 after -> old data in round lots"
 }
}
```
## Limitations
- Shares outstanding is a float proxy.
- Survivorship: current exchange listing and current SEC ticker map.
- Premarket day-2 moves cannot be stopped (no premarket stops); gap-downs fill at the first regular-session bid.
- One quote at entry; size check uses displayed ask only.
- Exploratory history: the forward test is the real judge.
