# Vantex lab 5 — 2026-11-15T11:50:05-05:00
300 sessions 2025-09-04 → 2026-11-13

## Coverage
```
{
 "universe_symbols": 6532,
 "with_daily_bars": 5629,
 "without_any_bars": 903,
 "in_price_band_at_some_point": 2268,
 "inactive_symbols_in_universe": 916,
 "examples_without_bars": [
  "AABA",
  "ABDC",
  "ACBI",
  "ACC",
  "ACETQ",
  "ACIA",
  "ACKIT",
  "ACLL",
  "ACSF",
  "ADMS",
  "ADSW",
  "AEGN",
  "AETI",
  "AFC",
  "AGC",
  "AGN",
  "AIMT",
  "AKCA",
  "AKP",
  "AKS",
  "ALAC",
  "ALDR",
  "ALGR",
  "ALN",
  "ALO",
  "ALOG",
  "ALSK",
  "ALTA",
  "ALXN",
  "AMAG"
 ]
}
{
 "name says ETF/fund/warrant/right/unit/preferred/note": 2174,
 "exchange (OTC/ARCA/BATS/other)": 22507,
 "symbol format (class/when-issued/odd)": 1242,
 "5-letter warrant/right/unit suffix": 1002
}
{
 "requests": 36694,
 "eligible_stock_days": 415088,
 "eligible_without_intraday_bars": 2493,
 "skipped: split day": 197,
 "skipped: too little history": 521,
 "sec_no_cik": 21407,
 "quotes_found": 17026,
 "quotes_missing": 1389
}
```
## Alerts
```
{
 "all": {
  "n": 38499,
  "alerts_before_plus10": 28970,
  "before10_then_reached_plus20_pct": 12.6,
  "before10_then_reached_plus50_pct": 1.7,
  "false_alerts_pct": 77.0,
  "reached_plus10_after_watch_pct": 23.0,
  "with_signal": 17980,
  "median_watch_rvol": 3.8
 },
 "premarket": {
  "n": 14830,
  "alerts_before_plus10": 9006,
  "before10_then_reached_plus20_pct": 23.2,
  "before10_then_reached_plus50_pct": 3.9,
  "false_alerts_pct": 65.0,
  "reached_plus10_after_watch_pct": 35.0,
  "with_signal": 6298,
  "median_watch_rvol": 3.9
 },
 "regular_session": {
  "n": 23669,
  "alerts_before_plus10": 19964,
  "before10_then_reached_plus20_pct": 7.8,
  "before10_then_reached_plus50_pct": 0.7,
  "false_alerts_pct": 84.6,
  "reached_plus10_after_watch_pct": 15.4,
  "with_signal": 11682,
  "median_watch_rvol": 3.7
 }
}
{
 "runner_days_plus50": 2261,
 "never_watched": 157,
 "watched_only_after_plus25": 1089,
 "watched_before_plus25": 1015,
 "runner_days_with_entry": 766,
 "never_watched_examples": [
  [
   "GIBO",
   "2026-06-30",
   2219
  ],
  [
   "WOLF",
   "2025-09-29",
   1726
  ],
  [
   "XFLT",
   "2026-03-23",
   411
  ],
  [
   "OXLC",
   "2025-09-08",
   400
  ],
  [
   "MWC",
   "2026-05-20",
   196
  ],
  [
   "BBCI",
   "2026-10-15",
   187
  ],
  [
   "YMAT",
   "2026-05-14",
   159
  ],
  [
   "YMAT",
   "2026-05-29",
   155
  ],
  [
   "SWRD",
   "2026-09-11",
   147
  ],
  [
   "DXST",
   "2026-06-09",
   145
  ],
  [
   "INHD",
   "2025-09-04",
   130
  ],
  [
   "CMCT",
   "2025-12-08",
   117
  ],
  [
   "USDE",
   "2026-07-02",
   112
  ],
  [
   "AMSS",
   "2026-05-27",
   111
  ],
  [
   "SNSC",
   "2026-08-20",
   107
  ]
 ]
}
```
## Trades (R multiples, per trade)
```
{
 "all": {
  "trades": 17980,
  "win_rate_pct": 26.0,
  "expectancy_R": -0.716,
  "profit_factor": 0.31,
  "hit_plus50_from_entry": 170,
  "median_mfe_pct": 1.21,
  "median_mae_pct": -3.02,
  "exits": {
   "stop": 9985,
   "15:45 close": 5506,
   "trail": 2445,
   "last bar": 44
  },
  "half_at_2R_pct": 14.3
 },
 "premarket_gappers": {
  "trades": 6298,
  "win_rate_pct": 26.9,
  "expectancy_R": -0.5,
  "profit_factor": 0.43,
  "hit_plus50_from_entry": 107,
  "median_mfe_pct": 1.78,
  "median_mae_pct": -3.48,
  "exits": {
   "15:45 close": 1504,
   "stop": 3733,
   "trail": 1055,
   "last bar": 6
  },
  "half_at_2R_pct": 17.2
 },
 "regular_session": {
  "trades": 11682,
  "win_rate_pct": 25.6,
  "expectancy_R": -0.832,
  "profit_factor": 0.27,
  "hit_plus50_from_entry": 63,
  "median_mfe_pct": 0.95,
  "median_mae_pct": -2.78,
  "exits": {
   "stop": 6252,
   "trail": 1390,
   "15:45 close": 4002,
   "last bar": 38
  },
  "half_at_2R_pct": 12.7
 },
 "premarket_high_break": {
  "trades": 9891,
  "win_rate_pct": 25.2,
  "expectancy_R": -0.908,
  "profit_factor": 0.26,
  "hit_plus50_from_entry": 116,
  "median_mfe_pct": 1.22,
  "median_mae_pct": -3.48,
  "exits": {
   "stop": 5448,
   "15:45 close": 3093,
   "trail": 1306,
   "last bar": 44
  },
  "half_at_2R_pct": 13.7
 },
 "consolidation_break": {
  "trades": 8089,
  "win_rate_pct": 27.1,
  "expectancy_R": -0.481,
  "profit_factor": 0.42,
  "hit_plus50_from_entry": 54,
  "median_mfe_pct": 1.2,
  "median_mae_pct": -2.53,
  "exits": {
   "15:45 close": 2413,
   "trail": 1139,
   "stop": 4537
  },
  "half_at_2R_pct": 15.0
 },
 "with_news_before_watch": {
  "trades": 3163,
  "win_rate_pct": 29.4,
  "expectancy_R": -0.399,
  "profit_factor": 0.5,
  "hit_plus50_from_entry": 29,
  "median_mfe_pct": 1.83,
  "median_mae_pct": -2.95,
  "exits": {
   "15:45 close": 1033,
   "stop": 1651,
   "trail": 479
  },
  "half_at_2R_pct": 16.0
 },
 "no_news": {
  "trades": 14817,
  "win_rate_pct": 25.3,
  "expectancy_R": -0.784,
  "profit_factor": 0.28,
  "hit_plus50_from_entry": 141,
  "median_mfe_pct": 1.1,
  "median_mae_pct": -3.03,
  "exits": {
   "stop": 8334,
   "trail": 1966,
   "15:45 close": 4473,
   "last bar": 44
  },
  "half_at_2R_pct": 13.9
 },
 "sec_dilution_flag": {
  "trades": 0
 },
 "no_dilution_flag": {
  "trades": 17980,
  "win_rate_pct": 26.0,
  "expectancy_R": -0.716,
  "profit_factor": 0.31,
  "hit_plus50_from_entry": 170,
  "median_mfe_pct": 1.21,
  "median_mae_pct": -3.02,
  "exits": {
   "stop": 9985,
   "15:45 close": 5506,
   "trail": 2445,
   "last bar": 44
  },
  "half_at_2R_pct": 14.3
 },
 "year_2025": {
  "trades": 4964,
  "win_rate_pct": 27.3,
  "expectancy_R": -0.701,
  "profit_factor": 0.33,
  "hit_plus50_from_entry": 46,
  "median_mfe_pct": 1.36,
  "median_mae_pct": -2.91,
  "exits": {
   "stop": 2789,
   "15:45 close": 1442,
   "trail": 724,
   "last bar": 9
  },
  "half_at_2R_pct": 15.4
 },
 "year_2026": {
  "trades": 13016,
  "win_rate_pct": 25.6,
  "expectancy_R": -0.722,
  "profit_factor": 0.31,
  "hit_plus50_from_entry": 124,
  "median_mfe_pct": 1.18,
  "median_mae_pct": -3.06,
  "exits": {
   "stop": 7196,
   "trail": 1721,
   "15:45 close": 4064,
   "last bar": 35
  },
  "half_at_2R_pct": 13.8
 }
}
```
## $2,500 account
| planned risk | end equity | net | max DD | trades | win | PF | expectancy R | worst trade | worst day | by year |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.5% ($500 cap - the rule) | $10.47 | -99.58% | 99.59% | 3137 | 28.7% | 0.29 | -0.883 | $-40.66 | -9.43% | {'2025': -1740.3, '2026': -749.23} |
| 0.5% (no $500 cap, cash only) | $10.49 | -99.58% | 99.59% | 3140 | 28.5% | 0.28 | -0.897 | $-40.41 | -7.81% | {'2025': -1730.94, '2026': -758.56} |
| 1.0% ($500 cap - the rule) | $9.47 | -99.62% | 99.63% | 1958 | 28.7% | 0.25 | -1.021 | $-37.83 | -7.89% | {'2025': -1613.67, '2026': -876.86} |
| 1.0% (no $500 cap, cash only) | $9.0 | -99.64% | 99.65% | 1944 | 27.9% | 0.24 | -1.056 | $-38.6 | -7.94% | {'2025': -1653.53, '2026': -837.47} |
| 2.0% ($500 cap - the rule) | $17.79 | -99.29% | 99.32% | 1334 | 29.3% | 0.45 | -0.435 | $-77.97 | -9.07% | {'2025': -1557.75, '2026': -924.46} |
| 2.0% (no $500 cap, cash only) | $19.21 | -99.23% | 99.31% | 1253 | 29.1% | 0.44 | -0.44 | $-65.66 | -8.91% | {'2025': -1422.69, '2026': -1058.1} |

## Risk of ruin (bootstrap of daily account returns)
```
{
 "0.5% ($500 cap)": {
  "21_sessions": {
   "p_down25": 87.5,
   "p_down50": 0.02,
   "p_ruin": 0.0,
   "p_reach_80k": 0.0,
   "end_p5": 1483,
   "end_median": 1705,
   "end_p95": 1963
  },
  "63_sessions": {
   "p_down25": 100.0,
   "p_down50": 99.94,
   "p_ruin": 0.0,
   "p_reach_80k": 0.0,
   "end_p5": 618,
   "end_median": 790,
   "end_p95": 1012
  }
 },
 "0.5% (no cap)": {
  "21_sessions": {
   "p_down25": 87.66,
   "p_down50": 0.02,
   "p_ruin": 0.0,
   "p_reach_80k": 0.0,
   "end_p5": 1483,
   "end_median": 1704,
   "end_p95": 1960
  },
  "63_sessions": {
   "p_down25": 100.0,
   "p_down50": 99.92,
   "p_ruin": 0.0,
   "p_reach_80k": 0.0,
   "end_p5": 620,
   "end_median": 790,
   "end_p95": 1014
  }
 },
 "1.0% ($500 cap)": {
  "21_sessions": {
   "p_down25": 82.8,
   "p_down50": 0.48,
   "p_ruin": 0.0,
   "p_reach_80k": 0.0,
   "end_p5": 1389,
   "end_median": 1687,
   "end_p95": 2068
  },
  "63_sessions": {
   "p_down25": 100.0,
   "p_down50": 99.0,
   "p_ruin": 0.0,
   "p_reach_80k": 0.0,
   "end_p5": 551,
   "end_median": 773,
   "end_p95": 1092
  }
 },
 "1.0% (no cap)": {
  "21_sessions": {
   "p_down25": 83.48,
   "p_down50": 0.62,
   "p_ruin": 0.0,
   "p_reach_80k": 0.0,
   "end_p5": 1382,
   "end_median": 1681,
   "end_p95": 2072
  },
  "63_sessions": {
   "p_down25": 100.0,
   "p_down50": 99.22,
   "p_ruin": 0.0,
   "p_reach_80k": 0.0,
   "end_p5": 540,
   "end_median": 766,
   "end_p95": 1091
  }
 },
 "2.0% ($500 cap)": {
  "21_sessions": {
   "p_down25": 71.26,
   "p_down50": 2.0,
   "p_ruin": 0.0,
   "p_reach_80k": 0.0,
   "end_p5": 1340,
   "end_median": 1768,
   "end_p95": 2351
  },
  "63_sessions": {
   "p_down25": 99.8,
   "p_down50": 89.92,
   "p_ruin": 0.0,
   "p_reach_80k": 0.0,
   "end_p5": 540,
   "end_median": 882,
   "end_p95": 1449
  }
 },
 "2.0% (no cap)": {
  "21_sessions": {
   "p_down25": 69.6,
   "p_down50": 2.1,
   "p_ruin": 0.0,
   "p_reach_80k": 0.0,
   "end_p5": 1347,
   "end_median": 1775,
   "end_p95": 2364
  },
  "63_sessions": {
   "p_down25": 99.72,
   "p_down50": 88.66,
   "p_ruin": 0.0,
   "p_reach_80k": 0.0,
   "end_p5": 547,
   "end_median": 894,
   "end_p95": 1479
  }
 }
}
```
## $80K math
```
{
 "goal": "$2,500 -> $80,000 = 32x",
 "per_session_needed_21": 17.94,
 "per_session_needed_63": 5.66,
 "note": "Shown as risk math only. The strategy is not tuned toward this target."
}
{
 "account": {
  "planned_risk_pct": 10.0,
  "end_equity": 17.48,
  "net_return_pct": -99.3,
  "max_dd_pct": 99.35,
  "trades_taken": 687,
  "skipped": {
   "size < 1 share or no settled cash": 17293
  },
  "win_rate_pct": 30.7,
  "profit_factor": 0.49,
  "expectancy_R": -0.398,
  "worst_trade_usd": -237.1,
  "worst_day_pct": -14.69,
  "by_year_usd": {
   "2025": -1604.19,
   "2026": -878.33
  }
 },
 "ruin": {
  "21_sessions": {
   "p_down25": 71.26,
   "p_down50": 16.26,
   "p_ruin": 0.0,
   "p_reach_80k": 0.0,
   "end_p5": 1062,
   "end_median": 1747,
   "end_p95": 3125
  },
  "63_sessions": {
   "p_down25": 96.76,
   "p_down50": 81.6,
   "p_ruin": 0.0,
   "p_reach_80k": 0.0,
   "end_p5": 358,
   "end_median": 875,
   "end_p95": 2206
  }
 }
}
```
## Case study 2026-11-13
| sym | prev close | day % | in band | WATCH | entry | result |
|---|---|---|---|---|---|---|
| AKAN | 0.6717 | 102.47 | True | 04:55 (11.3%, 3.7x) | 10:45 @ 1.002 | R=-1.02 ($-12.59) MFE 3.79% MAE -17.17% stop |
| ONFO | 0.3384 | 128.87 | False | 09:16 (12.9%, 25.1x) | [{'min': 575, 'why': 'no trade in the next 5 minutes'}] | - |
| GIPR | 0.235 | -5.7 | False | never met WATCH | - | - |
| FCUV | 3.0 | 136.0 | True | 07:49 (6.7%, 22.2x) | [{'min': 805, 'why': 'too extended: 12% above VWAP'}] | - |
| VTSI | 2.62 | 61.83 | True | 04:02 (29.0%, 5.1x) | 11:10 @ 3.8276 | R=-1.09 ($-13.5) MFE 0.06% MAE -5.16% stop |
| SLSN | 0.909 | 67.22 | True | 04:01 (34.2%, 4.5x) | [{'min': 685, 'why': 'too extended: 10% above VWAP'}, {'min': 730, 'why': 'too extended: 16% above VWAP'}] | - |
| WWB | None | None | None | no bar for 2026-11-13 | - | - |
| RAIN | 0.4737 | 58.31 | False | 04:01 (168.1%, 166.7x) | - | - |
| SLND | 0.63 | 49.22 | True | 04:01 (29.9%, 5.3x) | 12:56 @ 0.8209 | R=-1.14 ($-14.25) MFE 0.0% MAE -4.07% stop |
| SHIM | 2.34 | 38.89 | True | 07:30 (15.4%, 3.4x) | - | - |
| POLA | 0.283 | -4.35 | False | never met WATCH | - | - |
| SBC | 5.34 | 37.64 | False | 07:01 (6.5%, 3.6x) | 09:45 @ 6.4729 | R=2.78 ($26.4) MFE 8.14% MAE -1.13% trail |
| BZFD | 0.4051 | 29.25 | False | 09:51 (15.7%, 3.0x) | 12:00 @ 0.4904 | R=1.17 ($14.64) MFE 9.02% MAE -4.18% 15:45 close |
| AEI | 0.4001 | 32.24 | False | 06:41 (22.5%, 7.3x) | 13:50 @ 0.5345 | R=-1.11 ($-1.72) MFE 0.31% MAE -10.19% stop |
| BKHA | 5.375 | 35.81 | False | 04:02 (48.7%, 8.1x) | [{'min': 810, 'why': 'too extended: 29% above VWAP'}] | - |
| NMAX | 7.29 | 31.41 | False | 09:01 (21.1%, 3.5x) | 09:50 @ 9.3086 | R=1.83 ($20.19) MFE 6.26% MAE -0.95% trail |
| LFMD | 1.655 | 32.63 | True | 09:31 (12.4%, 6.0x) | 09:35 @ 1.9739 | R=2.16 ($26.74) MFE 18.54% MAE -2.48% trail |
| LFTO | 18.71 | 30.63 | False | 07:55 (22.9%, 3.5x) | 11:30 @ 23.8276 | R=-1.19 ($-11.1) MFE 0.43% MAE -2.17% stop |
| BGIN | 2.76 | 40.58 | True | 09:38 (3.4%, 14.6x) | 09:40 @ 2.8757 | R=2.12 ($26.13) MFE 25.19% MAE -3.33% trail |
| MOD | 106.1 | 27.86 | False | 07:45 (33.7%, 3.1x) | 09:35 @ 146.0114 | R=-1.08 ($-8.62) MFE 0.0% MAE -6.08% stop |
| KPTCY | None | None | None | no daily bars from Alpaca (not covered) | - | - |
| BIRD | 1.11 | 28.83 | True | 07:49 (12.8%, 3.1x) | 09:40 @ 1.3327 | R=-1.17 ($-14.62) MFE 7.3% MAE -6.2% stop |
| FRMI | 2.06 | 26.7 | True | never met WATCH | - | - |
| TGHL | 0.525 | 38.1 | True | 07:41 (4.8%, 3.2x) | 09:35 @ 0.6212 | R=-1.26 ($-15.74) MFE 0.0% MAE -12.53% stop |
| XCH | 4.12 | 23.79 | True | never met WATCH | - | - |
| CLRO | 3.48 | -3.16 | True | never met WATCH | - | - |
| HAWK | 14.67 | 23.79 | False | 09:31 (15.2%, 3.0x) | 10:35 @ 17.545 | R=-1.09 ($-13.45) MFE 1.74% MAE -3.56% stop |
| QUCY | 0.5644 | 12.15 | True | never met WATCH | - | - |
| PAVM | 1.339 | 21.73 | True | 08:57 (4.6%, 3.6x) | 12:26 @ 1.6333 | R=-4.0 ($-22.41) MFE 0.0% MAE -9.38% stop |
| MODD | 1.69 | 16.57 | True | never met WATCH | - | - |
| CNVS | 1.81 | 23.76 | True | 08:16 (14.9%, 4.8x) | 11:30 @ 2.2745 | R=-0.47 ($-5.89) MFE 0.0% MAE -5.04% 15:45 close |
| SSII | 1.32 | 25.76 | True | 14:08 (25.8%, 3.4x) | - | - |
| NXB | 1.17 | 19.66 | True | 12:05 (17.5%, 3.0x) | 13:52 @ 1.4529 | R=-1.04 ($-10.09) MFE 0.49% MAE -6.39% 15:45 close |
| CNSY | 0.7705 | 23.32 | True | 09:50 (24.4%, 3.4x) | 12:10 @ 1.1122 | R=-1.14 ($-14.27) MFE 5.2% MAE -6.49% stop |
| OBIO | 6.15 | 17.89 | False | 09:31 (3.1%, 5.0x) | 11:45 @ 6.4629 | R=1.94 ($24.02) MFE 6.45% MAE -1.13% trail |
| TREO | 3.3 | 19.09 | True | never met WATCH | - | - |
| CDXS | 0.9581 | 21.07 | True | 09:31 (16.4%, 7.0x) | 10:35 @ 1.1423 | R=-0.26 ($-1.49) MFE 5.05% MAE -4.14% 15:45 close |
| GYRO | 3.96 | 13.13 | True | 09:33 (5.1%, 64.2x) | - | - |

## Limitations
- Alpaca asset list is today's list (incl. inactive symbols it still carries), not a point-in-time listing history; delisted names Alpaca dropped are missing (survivorship bias remains).
- Common-stock filter is by exchange, symbol suffix and name keywords; some ETFs/units may slip through or real stocks be excluded.
- No historical trading-halt (LULD) feed: halts are approximated by filling at the next available bar.
- Quotes: one SIP quote snapshot at the fill minute; exits use the entry spread. Queue position/partial fills beyond the 10% participation cap are not modeled.
- News = Alpaca/Benzinga headlines; not every press release, exchange notice or SEC filing appears there.
- SEC: only tickers in today's SEC ticker map; renamed/delisted companies are missed; 3000 non-signal WATCH rows checked at most.
- Historical results are exploratory: ~650 prior trials, and recent months were viewed during development.
