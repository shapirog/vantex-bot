# Vantex lab 11 - Stocks in Play 5-min ORB - 2026-11-16T10:51:44-05:00

300 sessions 2025-09-04 -> 2026-11-13
## Signals
```
{
 "trades": 4758,
 "longs": 2448,
 "shorts": 2310,
 "mean_gross_R_all": -0.316,
 "mean_gross_R_longs": -0.333,
 "stopped_pct": 91.3,
 "picks": {
  "picked": 5997,
  "no_trigger_or_flat_candle": 1239
 }
}
```
## $2,500 cash account -> margin at $25K (the plan)
```
{
 "start": 2500.0,
 "end_equity": 678.63,
 "net_pct": -72.9,
 "max_dd_pct": 73.0,
 "worst_day_pct": -1.69,
 "reached_25k_on": null,
 "trades": 523,
 "longs": 523,
 "shorts": 0,
 "skipped": {
  "skipped_short_cash": 2310,
  "skipped_no_buying_power": 1925
 },
 "win_rate_pct": 5.7,
 "expectancy_R": -0.736,
 "profit_factor": 0.35
}
```
### same, 0.10% slippage per side
```
{
 "start": 2500.0,
 "end_equity": 484.93,
 "net_pct": -80.6,
 "max_dd_pct": 80.7,
 "worst_day_pct": -1.63,
 "reached_25k_on": null,
 "trades": 519,
 "longs": 519,
 "shorts": 0,
 "skipped": {
  "skipped_short_cash": 2310,
  "skipped_no_buying_power": 1929
 },
 "win_rate_pct": 6.4,
 "expectancy_R": -0.975,
 "profit_factor": 0.3
}
```
## $2,500 cash only
```
{
 "start": 2500.0,
 "end_equity": 678.63,
 "net_pct": -72.9,
 "max_dd_pct": 73.0,
 "worst_day_pct": -1.69,
 "reached_25k_on": null,
 "trades": 523,
 "longs": 523,
 "shorts": 0,
 "skipped": {
  "skipped_short_cash": 2310,
  "skipped_no_buying_power": 1925
 },
 "win_rate_pct": 5.7,
 "expectancy_R": -0.736,
 "profit_factor": 0.35
}
```
## The paper's setup: $25,000 margin, longs + shorts, 4x cap
```
{
 "start": 25000.0,
 "end_equity": 404.83,
 "net_pct": -98.4,
 "max_dd_pct": 98.4,
 "worst_day_pct": -4.49,
 "reached_25k_on": null,
 "trades": 944,
 "longs": 481,
 "shorts": 463,
 "skipped": {
  "skipped_no_buying_power": 3814
 },
 "win_rate_pct": 5.5,
 "expectancy_R": -0.75,
 "profit_factor": 0.34
}
```
### same, 0.10% slippage per side
```
{
 "start": 25000.0,
 "end_equity": 82.12,
 "net_pct": -99.7,
 "max_dd_pct": 99.7,
 "worst_day_pct": -4.81,
 "reached_25k_on": null,
 "trades": 944,
 "longs": 471,
 "shorts": 473,
 "skipped": {
  "skipped_no_buying_power": 3814
 },
 "win_rate_pct": 5.6,
 "expectancy_R": -0.994,
 "profit_factor": 0.28
}
```
## By month (gross R per trade)
```
{
 "2025-09": {
  "trades": 295,
  "mean_gross_R": -0.355
 },
 "2025-10": {
  "trades": 352,
  "mean_gross_R": -0.33
 },
 "2025-11": {
  "trades": 272,
  "mean_gross_R": -0.162
 },
 "2025-12": {
  "trades": 340,
  "mean_gross_R": -0.284
 },
 "2026-01": {
  "trades": 323,
  "mean_gross_R": -0.396
 },
 "2026-02": {
  "trades": 296,
  "mean_gross_R": -0.327
 },
 "2026-03": {
  "trades": 358,
  "mean_gross_R": -0.16
 },
 "2026-04": {
  "trades": 344,
  "mean_gross_R": -0.094
 },
 "2026-05": {
  "trades": 325,
  "mean_gross_R": -0.35
 },
 "2026-06": {
  "trades": 332,
  "mean_gross_R": -0.155
 },
 "2026-07": {
  "trades": 362,
  "mean_gross_R": -0.49
 },
 "2026-08": {
  "trades": 325,
  "mean_gross_R": -0.133
 },
 "2026-09": {
  "trades": 327,
  "mean_gross_R": -0.575
 },
 "2026-10": {
  "trades": 346,
  "mean_gross_R": -0.481
 },
 "2026-11": {
  "trades": 161,
  "mean_gross_R": -0.554
 }
}
```
## Notes
- Paper period 2016-2023 (+41.6%/yr, Sharpe 2.81 reported). This test uses only data AFTER publication.
- Fills: stop-order entry at the level (gap -> open), stop exits at the stop (gap -> open); same-minute entry+stop = stopped.
- Cash account: longs only; margin account (>= $25K): longs + shorts, borrow assumed available, no borrow fees modeled.
- Survivorship: current Alpaca listing; delisted names missing.
