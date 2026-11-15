# Vantex lab 4 — 2026-11-15T07:40:02-05:00
298 sessions 2025-09-08 → 2026-11-13, universe 14570 symbols, split 2026-07-10

## Census
```
{
 "stock_days_hit_10pct": 43693,
 "closed_up_20pct": 5288,
 "closed_up_50pct": 641,
 "base_rate_hit10_closes_20pct": 12.1,
 "base_rate_hit10_closes_below_10pct": 50.1,
 "base_rate_hit10_closes_red": 7.6,
 "movers20_gapped_10pct": 41.1,
 "movers20_news_before_open": 26.3,
 "movers20_news_before_flag": 26.7,
 "movers20_no_news_all_day": 68.2,
 "all_hit10_news_before_flag": 17.3,
 "movers20_tag_counts": [
  [
   "OTHER",
   1390
  ],
  [
   "EARNINGS",
   472
  ],
  [
   "AI",
   154
  ],
  [
   "DEAL",
   108
  ],
  [
   "PARTNER",
   100
  ],
  [
   "TRIAL",
   87
  ],
  [
   "FDA",
   65
  ],
  [
   "OFFERING",
   62
  ],
  [
   "CONTRACT",
   60
  ],
  [
   "CRYPTO",
   31
  ],
  [
   "SPLIT",
   10
  ],
  [
   "UPLIST",
   9
  ],
  [
   "DELIST",
   4
  ],
  [
   "BANKRUPT",
   3
  ]
 ],
 "hit10_tag_counts": [
  [
   "OTHER",
   6537
  ],
  [
   "EARNINGS",
   2031
  ],
  [
   "AI",
   757
  ],
  [
   "PARTNER",
   518
  ],
  [
   "TRIAL",
   443
  ],
  [
   "DEAL",
   410
  ],
  [
   "CONTRACT",
   388
  ],
  [
   "FDA",
   317
  ],
  [
   "OFFERING",
   271
  ],
  [
   "CRYPTO",
   167
  ],
  [
   "SPLIT",
   51
  ],
  [
   "UPLIST",
   32
  ],
  [
   "DELIST",
   15
  ],
  [
   "BANKRUPT",
   7
  ]
 ],
 "after_first_+10%_to_close": {
  "n": 43639,
  "median_pct": -0.4,
  "mean_pct": -0.13,
  "pct_positive": 45.3,
  "p10": -9.1,
  "p90": 8.5
 },
 "after_flag_to_close_news_before_flag": {
  "n": 7541,
  "median_pct": -0.4,
  "mean_pct": -0.14,
  "pct_positive": 46.2
 },
 "after_flag_to_close_no_news_before_flag": {
  "n": 36098,
  "median_pct": -0.5,
  "mean_pct": -0.13,
  "pct_positive": 45.2
 },
 "after_flag_to_close_by_tag_before_open": {
  "FDA": {
   "n": 266,
   "median_pct": -1.2,
   "mean_pct": -1.77,
   "pct_positive": 42.9
  },
  "TRIAL": {
   "n": 415,
   "median_pct": -0.6,
   "mean_pct": -0.36,
   "pct_positive": 47.5
  },
  "DEAL": {
   "n": 350,
   "median_pct": -0.5,
   "mean_pct": -1.59,
   "pct_positive": 41.4
  },
  "CONTRACT": {
   "n": 343,
   "median_pct": -1.1,
   "mean_pct": -2.16,
   "pct_positive": 42.6
  },
  "PARTNER": {
   "n": 443,
   "median_pct": -1.2,
   "mean_pct": -1.15,
   "pct_positive": 42.0
  },
  "EARNINGS": {
   "n": 1829,
   "median_pct": 0.3,
   "mean_pct": 0.59,
   "pct_positive": 51.4
  },
  "AI": {
   "n": 602,
   "median_pct": -1.1,
   "mean_pct": -1.45,
   "pct_positive": 43.4
  },
  "CRYPTO": {
   "n": 125,
   "median_pct": -2.5,
   "mean_pct": -6.49,
   "pct_positive": 36.0
  },
  "UPLIST": {
   "n": 32,
   "median_pct": -2.5,
   "mean_pct": -2.02,
   "pct_positive": 46.9
  },
  "OFFERING": {
   "n": 208,
   "median_pct": -1.0,
   "mean_pct": 0.35,
   "pct_positive": 43.8
  },
  "SPLIT": {
   "n": 46,
   "median_pct": -2.5,
   "mean_pct": -0.65,
   "pct_positive": 39.1
  },
  "DELIST": {
   "n": 12,
   "median_pct": 2.0,
   "mean_pct": 1.67,
   "pct_positive": 58.3
  },
  "OTHER": {
   "n": 5164,
   "median_pct": -0.3,
   "mean_pct": 0.08,
   "pct_positive": 46.9
  }
 }
}
```
## Strategies (per trade, all days)
| strategy | slip | trades | win | mean | median | PF | mean CI95 |
|---|---|---|---|---|---|---|---|
| A CHASE10 | slip 0.25% | 40129 | 39.4% | -0.6% | -1.41% | 0.81 | [-0.69, -0.5] |
| A CHASE10 | slip 0.50% | 40129 | 35.9% | -1.09% | -1.9% | 0.68 | [-1.19, -1.0] |
| A CHASE10 | slip 1.00% | 40129 | 29.5% | -2.08% | -2.88% | 0.49 | [-2.17, -1.98] |
| A CHASE10 +NEWS | slip 0.25% | 3627 | 39.7% | -0.72% | -1.68% | 0.79 | [-0.99, -0.42] |
| A CHASE10 +NEWS | slip 0.50% | 3627 | 36.6% | -1.22% | -2.17% | 0.68 | [-1.48, -0.92] |
| A CHASE10 +NEWS | slip 1.00% | 3627 | 32.1% | -2.2% | -3.14% | 0.5 | [-2.46, -1.91] |
| B GAP-ORB5 | slip 0.25% | 3683 | 34.6% | -0.15% | -2.83% | 0.96 | [-0.69, 0.53] |
| B GAP-ORB5 | slip 0.50% | 3683 | 32.7% | -0.65% | -3.31% | 0.85 | [-1.19, 0.03] |
| B GAP-ORB5 | slip 1.00% | 3683 | 29.2% | -1.63% | -4.27% | 0.66 | [-2.17, -0.97] |
| B GAP-ORB5 +NEWS | slip 0.25% | 701 | 35.5% | -1.08% | -2.5% | 0.72 | [-1.76, -0.32] |
| B GAP-ORB5 +NEWS | slip 0.50% | 701 | 33.2% | -1.57% | -2.99% | 0.63 | [-2.25, -0.81] |
| B GAP-ORB5 +NEWS | slip 1.00% | 701 | 29.2% | -2.55% | -3.95% | 0.47 | [-3.23, -1.8] |
| C PM-HIGH | slip 0.25% | 1825 | 41.7% | 0.03% | -2.69% | 1.01 | [-0.42, 0.47] |
| C PM-HIGH | slip 0.50% | 1825 | 40.0% | -0.47% | -3.18% | 0.89 | [-0.92, -0.03] |
| C PM-HIGH | slip 1.00% | 1825 | 36.4% | -1.46% | -4.14% | 0.7 | [-1.9, -1.03] |
| C PM-HIGH +NEWS | slip 0.25% | 365 | 39.5% | -0.27% | -3.1% | 0.93 | [-1.18, 0.74] |
| C PM-HIGH +NEWS | slip 0.50% | 365 | 37.5% | -0.77% | -3.58% | 0.83 | [-1.67, 0.24] |
| C PM-HIGH +NEWS | slip 1.00% | 365 | 35.6% | -1.75% | -4.54% | 0.65 | [-2.65, -0.76] |
| D LIVE-MOM | slip 0.25% | 20417 | 47.6% | 1.35% | -0.49% | 1.92 | [1.27, 1.43] |
| D LIVE-MOM | slip 0.50% | 20417 | 45.2% | 0.85% | -0.99% | 1.49 | [0.77, 0.93] |
| D LIVE-MOM | slip 1.00% | 20417 | 40.1% | -0.16% | -1.97% | 0.93 | [-0.24, -0.08] |
| D LIVE-MOM +NEWS | slip 0.25% | 1817 | 41.9% | 0.73% | -0.89% | 1.44 | [0.48, 0.98] |
| D LIVE-MOM +NEWS | slip 0.50% | 1817 | 39.7% | 0.22% | -1.39% | 1.12 | [-0.02, 0.47] |
| D LIVE-MOM +NEWS | slip 1.00% | 1817 | 33.8% | -0.77% | -2.37% | 0.7 | [-1.02, -0.52] |

## First 70% vs last 30% (0.5% slip) and $2,500 account
| strategy | first70 PF | first70 mean | last30 PF | last30 mean | account all | maxDD | account last30 |
|---|---|---|---|---|---|---|---|
| A CHASE10 | 0.69 | -1.07% | 0.67 | -1.14% | $125.12 (-95.0%) | 95.1% | -65.9% |
| A CHASE10 +NEWS | 0.71 | -1.11% | 0.63 | -1.41% | $103.37 (-95.9%) | 96.3% | -71.4% |
| B GAP-ORB5 | 0.86 | -0.61% | 0.81 | -0.71% | $151.1 (-94.0%) | 94.6% | -48.3% |
| B GAP-ORB5 +NEWS | 0.62 | -1.67% | 0.64 | -1.41% | $119.43 (-95.2%) | 95.7% | -65.1% |
| C PM-HIGH | 0.87 | -0.58% | 0.93 | -0.31% | $1138.02 (-54.5%) | 71.6% | 6.6% |
| C PM-HIGH +NEWS | 0.89 | -0.51% | 0.73 | -1.16% | $1305.93 (-47.8%) | 60.5% | -37.8% |
| D LIVE-MOM | 1.5 | 0.89% | 1.45 | 0.73% | $3508.98 (40.4%) | 35.0% | -9.9% |
| D LIVE-MOM +NEWS | 1.09 | 0.18% | 1.17 | 0.3% | $3609.27 (44.4%) | 35.6% | 3.5% |

## Last session movers
| sym | day % | gap % | flag min | after flag→close | news before open | strategies |
|---|---|---|---|---|---|---|
| VTSI | 61.8 | 33.6 | 570 | 21.1 | VirTra Q3 EPS $0.19 Beats $(0.03) Estimate, Sales $7.623M Beat $4.390M Estimate; Why Is VirTra Stock Surging Friday? | {'A CHASE10': 16.4, 'B GAP-ORB5': 11.6, 'A CHASE10 +NEWS': 16.4, 'B GAP-ORB5 +NEWS': 11.6} |
| BGIN | 40.6 | -8.3 | 597 | 27.6 |  | {'A CHASE10': 28.3, 'D LIVE-MOM': 13.4} |
| SHIM | 38.9 | 34.2 | 570 | 3.5 | Shimmick Lowers FY2026 Sales Guidance from $525.000M-$575.000M to $500.000M-$525.000M vs $499.800M Est; Shimmick Q3 Adj. | {'A CHASE10': -15.2, 'B GAP-ORB5': 1.8, 'A CHASE10 +NEWS': -15.2, 'B GAP-ORB5 +NEWS': 1.8} |
| SBC | 37.6 | 18.9 | 570 | 15.9 | SBC Medical Announces Strategic Capital And Business Alliance Agreement With NeuroBrain To Co-Develop Six Medi; SBC Medi | {'A CHASE10': 13.5, 'D LIVE-MOM': 6.1, 'B GAP-ORB5': 7.7, 'A CHASE10 +NEWS': 13.5, 'D LIVE-MOM +NEWS': 6.1, 'B GAP-ORB5 +NEWS': 7.7} |
| BKHA | 35.8 | 14.4 | 570 | 18.7 |  | {'A CHASE10': -9.4, 'B GAP-ORB5': 19.1} |
| LFMD | 32.6 | 12.7 | 570 | 17.7 | LifeMD Lowers FY2026 Sales Guidance from $205.500M-$212.500M to $188.000M-$191.000M vs $207.582M Est; LifeMD Sees Q4 Sal | {'A CHASE10': 16.5, 'B GAP-ORB5': 9.2, 'A CHASE10 +NEWS': 16.5, 'B GAP-ORB5 +NEWS': 9.2} |
| NMAX | 31.4 | 26.9 | 570 | 3.6 | Newsmax Raises FY2026 Sales Guidance from $212.000M-$216.000M to $226.000M-$230.000M vs $214.767M Est; Newsmax Q3 EPS $0 | {'A CHASE10': -8.9, 'B GAP-ORB5': -3.7, 'A CHASE10 +NEWS': -8.9, 'B GAP-ORB5 +NEWS': -3.7} |
| LFTO | 30.6 | 27.1 | 570 | 2.8 | Liftoff Mobile Sees Q4 Sales $244.000M-$249.000M vs $232.513M Est; Liftoff Mobile Raises FY2026 Sales Guidance from $870 | {'A CHASE10': -8.9, 'B GAP-ORB5': -6.4, 'A CHASE10 +NEWS': -8.9, 'C PM-HIGH': -8.9, 'B GAP-ORB5 +NEWS': -6.4, 'C PM-HIGH +NEWS': -8.9} |
| BIRD | 28.8 | 12.6 | 570 | 14.4 | Smartbird Q3 EPS $(0.31) Beats $(1.32) Estimate; Smartbird CEO Says Several Prospective Customer Discussions Have Advanc | {'A CHASE10': 13.3, 'D LIVE-MOM': -6.7, 'B GAP-ORB5': 12.4} |
| FRMI | 26.7 | 1.2 | 940 | 15.2 |  | {'D LIVE-MOM': 21.1} |
| HAWK | 23.8 | 13.5 | 570 | 9.1 | Hawkeye 360 Raises FY2026 Sales Guidance from $215.000M-$220.000M to $225.000M-$227.000M vs $217.212M Est; Hawkeye 360 Q | {'A CHASE10': 8.1, 'B GAP-ORB5': 0.1, 'A CHASE10 +NEWS': 8.1, 'B GAP-ORB5 +NEWS': 0.1} |
| XCH | 23.8 | 7.5 | 574 | 12.5 |  | {'A CHASE10': 14.4} |
| CBRX | 20.9 | 22.3 | 570 | -1.2 |  | {'A CHASE10': -8.9, 'C PM-HIGH': -8.9} |
| SNAL | 19.7 | 19.3 | 570 | 0.4 | Snail Q3 EPS $0.75 Vs $(1.05) YoY, Rev $33.1M Vs $13.8M YoY; Snail Q3 ARK: Survival Ascended Units Sold ~1.2M; Total Uni | {'A CHASE10': -8.9, 'B GAP-ORB5': -0.6, 'A CHASE10 +NEWS': -8.9, 'B GAP-ORB5 +NEWS': -0.6} |
| TREO | 19.1 | -0.9 | 749 | 8.3 |  | {'A CHASE10': 6.4} |
| DAMD | 18.2 | 6.9 | 577 | 7.5 |  | {'A CHASE10': 5.5, 'D LIVE-MOM': -0.5} |
| OBIO | 17.9 | 1.6 | 818 | 7.1 | BTIG Maintains Buy on Orchestra BioMed Hldgs, Raises Price Target to $12 | {'A CHASE10': 6.5, 'D LIVE-MOM': 12.6} |
| NUAI | 17.6 | 8.1 | 570 | 7.0 |  | {'A CHASE10': 7.4, 'D LIVE-MOM': -1.0} |
| MODD | 16.6 | -1.2 | 838 | 6.0 |  | {'A CHASE10': -4.9} |
| AIMD | 16.0 | -14.2 | 753 | 5.5 | Ainos Secures $9 Million Purchase Agreement with ASE Technology for AI Nose Systems | {'A CHASE10': 4.4, 'A CHASE10 +NEWS': 4.4} |
| NGEN | 15.3 | 3.1 | 630 | 4.9 |  | {'A CHASE10': 3.0, 'D LIVE-MOM': 7.1} |
| REED | 14.8 | -4.9 | 638 | 4.3 |  | {'A CHASE10': 2.2} |
| TNDM | 14.6 | 8.5 | 575 | 4.2 | Tandem Diabetes Care Receives FDA Clearance For Tandem Mobi As Tubeless Automated Insulin Delivery System With; Tandem D | {'A CHASE10': 3.3, 'D LIVE-MOM': -1.9, 'A CHASE10 +NEWS': 3.3, 'D LIVE-MOM +NEWS': -1.9} |
| CDNL | 14.5 | 2.3 | 571 | 4.1 | Law Firms Investigate Potential Securities Fraud at Cardinal Infrastructure Group | {'A CHASE10': 2.6} |
| UNIT | 13.5 | 0.2 | 834 | 3.2 | BofA Adjusts Price Target on Uniti Group to $4.75; Citi Maintains Hold Rating on Uniti Group, Lowers Price Target to $5 | {'A CHASE10': 1.2, 'D LIVE-MOM': -1.7} |
| CORD | 12.8 | 2.5 | 578 | 2.6 |  | {'A CHASE10': 0.4, 'D LIVE-MOM': -4.7} |
| BRCB | 11.9 | 0.2 | 935 | 1.8 |  | {} |
| LRMR | 11.9 | 11.5 | 570 | 0.3 |  | {'A CHASE10': 0.2, 'B GAP-ORB5': -5.9} |
| NU | 11.7 | 4.5 | 668 | 1.6 | Nu Holdings Q3 EPS $0.22, Inline, Sales $5.820B Beat $5.684B Estimate; Nu Holdings Reports Strong Q3: EPS in Line, Reven | {'A CHASE10': -0.0, 'D LIVE-MOM': 2.0, 'A CHASE10 +NEWS': -0.0, 'D LIVE-MOM +NEWS': 2.0} |
| WRAP | 11.3 | 0.0 | 710 | 1.2 |  | {'A CHASE10': 0.2, 'D LIVE-MOM': 4.9} |
| SEAT | 11.2 | -1.6 | 593 | 0.7 |  | {'A CHASE10': -1.7} |
| HCAT | 11.0 | 0.7 | 826 | 0.9 |  | {'A CHASE10': -0.1} |
| LUCK | 10.6 | 1.6 | 585 | 0.3 |  | {'A CHASE10': -0.9} |
| KLXE | 10.3 | 0.0 | 946 | 0.3 | KLX Energy Services Files Prospectus To Offer Up To 59.4M Shares Of Common Stock By Selling Stockholders | {} |
| TOP | 10.2 | -2.3 | 959 | 0.2 |  | {} |
| EOSU | 10.1 | 5.0 | 950 | -0.4 |  | {} |
| BEZ | 10.0 | 1.6 | 592 | 0.0 |  | {'A CHASE10': -1.3, 'D LIVE-MOM': -3.4} |
| NCMI | 10.0 | 0.6 | 954 | 0.0 |  | {'D LIVE-MOM': -1.6} |
| STVN | 10.0 | 2.2 | 870 | 0.0 |  | {'A CHASE10': 0.3} |
| PRME | 9.8 | 4.1 | 649 | -0.2 | Prime Medicine Closes Underwritten Public Offering Of 41,071,428 Common Shares For Gross Proceeds Of ~$143.7M; Prime Med | {'A CHASE10': -0.9, 'D LIVE-MOM': 0.1, 'A CHASE10 +NEWS': -0.9, 'D LIVE-MOM +NEWS': 0.1} |
