# Vantex lab 8 - locked tiny-float pullback rule (exploratory history) - 2026-11-15T15:12:42-05:00

EXPLORATORY ONLY. These dates were used while building labs 5-7, so this is not an independent test. Only the forward paper test (sessions after 2026-11-13) can confirm or reject the rule.

## Verdict
Exploratory replay, NEW rule base case: 29 trades, expectancy -0.546 R, day-clustered 95% CI [-1.154, 0.311]. Whatever this shows, it is not independent confirmation; the strategy stays paper-only until the forward test decides.

## Data / implementation checks
- Signals use only bars that have ended (a 1-minute bar is known at its end; 5-minute ATR uses completed bars only; VWAP through the signal bar; premarket high fixed at 9:30).
- Shares outstanding: last SEC count filed strictly before the session, split-adjusted; prior close = previous session raw close.
- Entry quote: first valid SIP quote with timestamp strictly after the signal bar end; skipped if it arrives > 1 s later. Quotes before the signal are never used.
- Exits: every SIP quote from entry to 15:45 is walked in time order; the first BID that crosses the stop/target decides, so gaps and halts fill at the real reopening bid. Bar fallback (stop first, at min(stop, open, close) - 1%) only for 15-minute chunks with no quotes at all.
- Quote sizes: SIP switched from round lots to shares on 2025-11-03 (Alpaca changelog); whether Alpaca history before that date is in lots is calibrated at run time from SPY quotes (see data_errors.quote_size_units).
- Fees: SEC Section 31 $27.80/M until 2025-05-13, $0 from 2025-05-14, $20.60/M from 2026-04-04; FINRA TAF $0.000166/sh (max $8.30) in 2025, $0.000195 (max $9.79) in 2026. Labs 5-7 charged $27.80/M throughout (slightly too high).
- Known limitation: entry assumes the bar is known at hh:mm:00.000 and fills at the next quote within 1 s (as specified); real data/order latency would be slightly worse.
- Known limitation: VWAP uses (high+low+close)/3 per 1-minute bar, not the exchange VWAP; the 5-minute ATR is a simple mean of true ranges over clock buckets (premarket buckets may be far apart).
- Known limitation: no historical halt feed; "possible halt" = a gap of >= 5 minutes with no prints before the exit.
- Known limitation: the rule says median baseline; for thin premarket names the 20-session median is often 0, which makes the 3x test pass on any volume. Kept as written (locked); counted in coverage.
- Known limitation: survivorship - universe uses each symbol's CURRENT exchange (names since moved to OTC or delisted are dropped for all dates) and SEC's current ticker map (a reused ticker could map to the wrong company). This can make results look better than reality.
- Half-days: not traded, but kept for prior closes and baselines (so the session after a half-day is not dropped).
- With 1 share, the 2R "half" sells 0 shares (the share keeps trailing); odd counts round the half down.
- Earlier labs (flagged): lab 5 filled at the first quote up to 2 minutes after the signal and exited on bars with the entry spread; lab 5 SEC dilution flag silently failed; labs 5-7 used per-trade (not day-clustered) bootstraps; lab 7 E3 assumed premarket stops that Alpaca does not support.

## NEW rule
| case | trades | win % | expectancy R | 95% CI (day-clustered) | PF | end equity | max DD % | worst day % |
|---|---|---|---|---|---|---|---|---|
| base (0.5% slip) | 29 | 20.7 | -0.546 | [-1.154, 0.311] | 0.46 | $2401.69 | 5.33 | -0.55 |
| stress: 1.0% slip | 29 | 20.7 | -0.668 | [-1.235, 0.138] | 0.37 | $2381.29 | 5.85 | -0.55 |
| stress: halt/gap -10% | 29 | 20.7 | -0.673 | [-1.367, 0.23] | 0.4 | $2379.66 | 6.19 | -0.98 |
| stress: both | 29 | 20.7 | -0.783 | [-1.429, 0.061] | 0.34 | $2361.95 | 6.61 | -0.92 |

Gross expectancy (ask/bid, no slippage or fees): -0.297 R

### By month
```
{
 "2025-09": {
  "trades": 3,
  "sessions_with_trades": 3,
  "win_rate_pct": 33.3,
  "expectancy_R": -0.612,
  "ci95_R_day_clustered": [
   -1.152,
   0.42
  ],
  "profit_factor": 0.19,
  "median_R": -1.105
 },
 "2025-10": {
  "trades": 1,
  "sessions_with_trades": 1,
  "win_rate_pct": 0.0,
  "expectancy_R": -1.276,
  "ci95_R_day_clustered": null,
  "profit_factor": 0.0,
  "median_R": -1.276
 },
 "2026-01": {
  "trades": 3,
  "sessions_with_trades": 2,
  "win_rate_pct": 66.7,
  "expectancy_R": 2.738,
  "ci95_R_day_clustered": [
   -1.076,
   4.644
  ],
  "profit_factor": 8.63,
  "median_R": 0.402
 },
 "2026-02": {
  "trades": 4,
  "sessions_with_trades": 4,
  "win_rate_pct": 25.0,
  "expectancy_R": -0.591,
  "ci95_R_day_clustered": [
   -1.317,
   0.685
  ],
  "profit_factor": 0.35,
  "median_R": -1.139
 },
 "2026-03": {
  "trades": 2,
  "sessions_with_trades": 2,
  "win_rate_pct": 0.0,
  "expectancy_R": -1.138,
  "ci95_R_day_clustered": [
   -1.179,
   -1.097
  ],
  "profit_factor": 0.0,
  "median_R": -1.138
 },
 "2026-05": {
  "trades": 1,
  "sessions_with_trades": 1,
  "win_rate_pct": 0.0,
  "expectancy_R": -1.274,
  "ci95_R_day_clustered": null,
  "profit_factor": 0.0,
  "median_R": -1.274
 },
 "2026-06": {
  "trades": 1,
  "sessions_with_trades": 1,
  "win_rate_pct": 0.0,
  "expectancy_R": -1.194,
  "ci95_R_day_clustered": null,
  "profit_factor": 0.0,
  "median_R": -1.194
 },
 "2026-07": {
  "trades": 4,
  "sessions_with_trades": 4,
  "win_rate_pct": 0.0,
  "expectancy_R": -1.148,
  "ci95_R_day_clustered": [
   -1.218,
   -1.099
  ],
  "profit_factor": 0.0,
  "median_R": -1.12
 },
 "2026-08": {
  "trades": 2,
  "sessions_with_trades": 2,
  "win_rate_pct": 50.0,
  "expectancy_R": -0.173,
  "ci95_R_day_clustered": [
   -1.522,
   1.176
  ],
  "profit_factor": 0.77,
  "median_R": -0.173
 },
 "2026-09": {
  "trades": 4,
  "sessions_with_trades": 4,
  "win_rate_pct": 0.0,
  "expectancy_R": -1.296,
  "ci95_R_day_clustered": [
   -1.577,
   -1.098
  ],
  "profit_factor": 0.0,
  "median_R": -1.187
 },
 "2026-10": {
  "trades": 1,
  "sessions_with_trades": 1,
  "win_rate_pct": 100.0,
  "expectancy_R": 1.105,
  "ci95_R_day_clustered": null,
  "profit_factor": null,
  "median_R": 1.105
 },
 "2026-11": {
  "trades": 3,
  "sessions_with_trades": 3,
  "win_rate_pct": 0.0,
  "expectancy_R": -1.6,
  "ci95_R_day_clustered": [
   -2.21,
   -1.094
  ],
  "profit_factor": 0.0,
  "median_R": -1.497
 }
}
```
### By shares outstanding (proxy)
```
{
 "<1M": {
  "trades": 12,
  "sessions_with_trades": 12,
  "win_rate_pct": 8.3,
  "expectancy_R": -1.043,
  "ci95_R_day_clustered": [
   -1.387,
   -0.541
  ],
  "profit_factor": 0.09,
  "median_R": -1.127
 },
 "1-2M": {
  "trades": 10,
  "sessions_with_trades": 10,
  "win_rate_pct": 20.0,
  "expectancy_R": -0.812,
  "ci95_R_day_clustered": [
   -1.347,
   -0.095
  ],
  "profit_factor": 0.22,
  "median_R": -1.218
 },
 "2-3.5M": {
  "trades": 4,
  "sessions_with_trades": 4,
  "win_rate_pct": 50.0,
  "expectancy_R": -0.364,
  "ci95_R_day_clustered": [
   -1.139,
   0.411
  ],
  "profit_factor": 0.36,
  "median_R": -0.365
 },
 "3.5-5M": {
  "trades": 3,
  "sessions_with_trades": 3,
  "win_rate_pct": 33.3,
  "expectancy_R": 2.087,
  "ci95_R_day_clustered": [
   -1.522,
   8.887
  ],
  "profit_factor": 3.39,
  "median_R": -1.103
 }
}
```
### Exits
```
{
 "2R half": 6,
 "trail": 6,
 "stop": 23
}
```
### Skips
```
{
 "no fresh quote within 1 s": 575,
 "spread > 1.5%": 47,
 "stop > 8% below entry": 65
}
```
Entry quote age ms: {'median': 163.2, 'max': 900.2}, median spread %: 0.83

## LAB5 rule
| case | trades | win % | expectancy R | 95% CI (day-clustered) | PF | end equity | max DD % | worst day % |
|---|---|---|---|---|---|---|---|---|
| base (0.5% slip) | 624 | 24.7 | -0.448 | [-0.555, -0.339] | 0.46 | $1272.15 | 49.41 | -2.0 |
| stress: 1.0% slip | 624 | 22.9 | -0.579 | [-0.677, -0.479] | 0.35 | $1045.61 | 58.34 | -2.12 |
| stress: halt/gap -10% | 624 | 24.4 | -0.489 | [-0.601, -0.375] | 0.43 | $1194.35 | 52.5 | -2.77 |
| stress: both | 624 | 22.6 | -0.616 | [-0.717, -0.512] | 0.33 | $993.65 | 60.41 | -2.78 |

Gross expectancy (ask/bid, no slippage or fees): -0.241 R

### By month
```
{
 "2025-09": {
  "trades": 47,
  "sessions_with_trades": 18,
  "win_rate_pct": 27.7,
  "expectancy_R": -0.583,
  "ci95_R_day_clustered": [
   -0.981,
   -0.194
  ],
  "profit_factor": 0.33,
  "median_R": -1.095
 },
 "2025-10": {
  "trades": 47,
  "sessions_with_trades": 20,
  "win_rate_pct": 31.9,
  "expectancy_R": -0.31,
  "ci95_R_day_clustered": [
   -0.696,
   -0.007
  ],
  "profit_factor": 0.57,
  "median_R": -1.07
 },
 "2025-11": {
  "trades": 22,
  "sessions_with_trades": 15,
  "win_rate_pct": 45.5,
  "expectancy_R": 0.153,
  "ci95_R_day_clustered": [
   -0.44,
   0.859
  ],
  "profit_factor": 1.29,
  "median_R": -0.202
 },
 "2025-12": {
  "trades": 39,
  "sessions_with_trades": 17,
  "win_rate_pct": 15.4,
  "expectancy_R": -0.737,
  "ci95_R_day_clustered": [
   -0.969,
   -0.421
  ],
  "profit_factor": 0.23,
  "median_R": -1.086
 },
 "2026-01": {
  "trades": 42,
  "sessions_with_trades": 20,
  "win_rate_pct": 19.0,
  "expectancy_R": -0.568,
  "ci95_R_day_clustered": [
   -0.894,
   -0.156
  ],
  "profit_factor": 0.36,
  "median_R": -1.073
 },
 "2026-02": {
  "trades": 33,
  "sessions_with_trades": 16,
  "win_rate_pct": 30.3,
  "expectancy_R": 0.014,
  "ci95_R_day_clustered": [
   -0.526,
   0.519
  ],
  "profit_factor": 1.02,
  "median_R": -1.044
 },
 "2026-03": {
  "trades": 40,
  "sessions_with_trades": 18,
  "win_rate_pct": 17.5,
  "expectancy_R": -0.58,
  "ci95_R_day_clustered": [
   -0.863,
   -0.291
  ],
  "profit_factor": 0.28,
  "median_R": -1.064
 },
 "2026-04": {
  "trades": 44,
  "sessions_with_trades": 17,
  "win_rate_pct": 34.1,
  "expectancy_R": -0.225,
  "ci95_R_day_clustered": [
   -0.681,
   0.305
  ],
  "profit_factor": 0.7,
  "median_R": -1.051
 },
 "2026-05": {
  "trades": 56,
  "sessions_with_trades": 17,
  "win_rate_pct": 17.9,
  "expectancy_R": -0.622,
  "ci95_R_day_clustered": [
   -0.838,
   -0.353
  ],
  "profit_factor": 0.25,
  "median_R": -1.059
 },
 "2026-06": {
  "trades": 39,
  "sessions_with_trades": 16,
  "win_rate_pct": 33.3,
  "expectancy_R": -0.366,
  "ci95_R_day_clustered": [
   -0.832,
   0.202
  ],
  "profit_factor": 0.5,
  "median_R": -1.064
 },
 "2026-07": {
  "trades": 48,
  "sessions_with_trades": 20,
  "win_rate_pct": 25.0,
  "expectancy_R": -0.566,
  "ci95_R_day_clustered": [
   -0.862,
   -0.318
  ],
  "profit_factor": 0.36,
  "median_R": -1.054
 },
 "2026-08": {
  "trades": 56,
  "sessions_with_trades": 21,
  "win_rate_pct": 19.6,
  "expectancy_R": -0.491,
  "ci95_R_day_clustered": [
   -0.846,
   -0.04
  ],
  "profit_factor": 0.46,
  "median_R": -1.074
 },
 "2026-09": {
  "trades": 53,
  "sessions_with_trades": 19,
  "win_rate_pct": 22.6,
  "expectancy_R": -0.498,
  "ci95_R_day_clustered": [
   -0.882,
   -0.059
  ],
  "profit_factor": 0.44,
  "median_R": -1.057
 },
 "2026-10": {
  "trades": 45,
  "sessions_with_trades": 19,
  "win_rate_pct": 22.2,
  "expectancy_R": -0.374,
  "ci95_R_day_clustered": [
   -0.724,
   0.073
  ],
  "profit_factor": 0.54,
  "median_R": -1.046
 },
 "2026-11": {
  "trades": 13,
  "sessions_with_trades": 7,
  "win_rate_pct": 15.4,
  "expectancy_R": -0.656,
  "ci95_R_day_clustered": [
   -1.126,
   -0.128
  ],
  "profit_factor": 0.23,
  "median_R": -1.074
 }
}
```
### By shares outstanding (proxy)
```
{
 "<1M": {
  "trades": 261,
  "sessions_with_trades": 171,
  "win_rate_pct": 21.8,
  "expectancy_R": -0.537,
  "ci95_R_day_clustered": [
   -0.681,
   -0.379
  ],
  "profit_factor": 0.37,
  "median_R": -1.064
 },
 "1-2M": {
  "trades": 120,
  "sessions_with_trades": 99,
  "win_rate_pct": 21.7,
  "expectancy_R": -0.584,
  "ci95_R_day_clustered": [
   -0.776,
   -0.389
  ],
  "profit_factor": 0.3,
  "median_R": -1.054
 },
 "2-3.5M": {
  "trades": 121,
  "sessions_with_trades": 100,
  "win_rate_pct": 23.1,
  "expectancy_R": -0.482,
  "ci95_R_day_clustered": [
   -0.737,
   -0.182
  ],
  "profit_factor": 0.45,
  "median_R": -1.082
 },
 "3.5-5M": {
  "trades": 122,
  "sessions_with_trades": 103,
  "win_rate_pct": 35.2,
  "expectancy_R": -0.088,
  "ci95_R_day_clustered": [
   -0.363,
   0.218
  ],
  "profit_factor": 0.88,
  "median_R": -1.043
 }
}
```
### Exits
```
{
 "2R half": 104,
 "trail": 100,
 "stop": 405,
 "15:45 exit": 115,
 "15:45 exit (bar fallback)": 4
}
```
### Skips
```
{
 "no fresh quote within 1 s": 10299,
 "spread > 1.5%": 458,
 "displayed ask size < order size": 15
}
```
Entry quote age ms: {'median': 246.25, 'max': 994.7}, median spread %: 0.6964999999999999

## Data errors and quote-size calibration
```
{
 "total": 0,
 "detail": {
  "lab8": {
   "quote_requests": 15710,
   "quotes_invalid_locked_crossed_or_zero": 163300
  },
  "lab5_helpers": {
   "requests": 17940
  },
  "lab6_helpers": {
   "requests": 4170,
   "no_cik": 18,
   "facts_missing": 44,
   "splits_found": 1059
  }
 },
 "quote_size_units": {
  "value": 100,
  "evidence": "SPY median ask size 3.0 before vs 480.0 after -> old data in round lots"
 }
}
```
## Alert outcomes (NEW rule)
```
{
 "no signal: reclaim volume < 2x median of prior five 1-min bars": 511,
 "signal": 716,
 "no signal: never broke premarket high in window": 10896,
 "no signal: no VWAP pullback": 504,
 "no signal: no close back above VWAP": 313,
 "no signal: signal close > 10% above VWAP": 14
}
```
## Counters
```
{
 "LAB5 skip: no fresh quote within 1 s": 10299,
 "LAB5 exit_quote_chunks": 3249,
 "NEW skip: no fresh quote within 1 s": 575,
 "NEW exit_quote_chunks": 42,
 "LAB5 too extended, keep watching": 188,
 "LAB5 skip: spread > 1.5%": 458,
 "NEW skip: spread > 1.5%": 47,
 "LAB5 skip: displayed ask size < order size": 15,
 "LAB5 stale_time_exit_quote": 76,
 "NEW skip: stop > 8% below entry": 65,
 "LAB5 no_quote_at_1545": 4,
 "LAB5 exit_chunks_without_quotes": 9
}
```
## Coverage
```
{
 "universe_symbols": 6532,
 "with_daily_bars": 5631,
 "ever_in_price_band": 3809,
 "symbols_with_sec_counts": 3168,
 "stock_days_in_price_band": 892734,
 "excluded_shares_unknown: no SEC count": 131148,
 "excluded_incomplete_history(<20 daily bars)": 8067,
 "excluded_shares_unknown: no count filed yet": 14757,
 "excluded_split_day": 186,
 "eligible_stock_days(tiny shares, in band)": 88597,
 "excluded_shares_unknown: count too old": 51948,
 "alerts": 12954,
 "alerts_with_zero_median_baseline": 7146,
 "universe_excluded": {
  "name says ETF/fund/warrant/right/unit/preferred/note": 2174,
  "exchange (OTC/ARCA/BATS/other)": 22507,
  "symbol format (class/when-issued/odd)": 1242,
  "5-letter warrant/right/unit suffix": 1002
 },
 "splits_feed_ok": true
}
```
## Files
- lab8_alerts.jsonl: every eligible alert
- lab8_trades.jsonl: every fill with quote time/age/spread/size and exit legs
- lab8_skips.jsonl: every skipped signal and why
- lab8_equity.json: daily equity curves

## Rerun
`python lab8.py history` (GitHub Actions: lab8.yml / lab8-forward.yml)
