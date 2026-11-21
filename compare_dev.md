# VANTEX City rule comparison - dev - 20 sessions

Same days, same data, same costs and fills for every variant. Every confirmed signal is taken (no day-trade limit) so each rule set is judged on enough trades.

| rule set | trades | win rate | net P&L after costs | avg R | worst day | max drawdown |
|---|---|---|---|---|---|---|
| A. Original rules | 143 | 30.8% | $-245.27 | -0.349 | ('2026-06-18', -51.4) | $300.73 |
| B. Strong stocks with real news | 3 | 33.3% | $0.72 | -0.085 | ('2026-07-02', -12.68) | $21.77 |
| C. Strong stocks, news not required | 19 | 21.1% | $-91.29 | -0.412 | ('2026-08-14', -33.59) | $113.36 |
| D. Strong + news, pullback entry | 1 | 0.0% | $-12.42 | -1.052 | ('2026-08-06', -12.42) | $12.42 |
| E. Strong, pullback entry, news not required | 3 | 0.0% | $-35.28 | -1.023 | ('2026-07-10', -12.45) | $35.28 |

## What each rule set is
- **A. Original rules**: every confirmed breakout or breakdown, any stock in the universe
- **B. Strong stocks with real news**: longs only on stocks already up 10%+ on the day, 5x normal volume, a fresh verified catalyst (news or an SEC 8-K), and no dilution news or filings
- **C. Strong stocks, news not required**: longs only on stocks already up 10%+ on the day with 5x normal volume and no dilution news or filings
- **D. Strong + news, pullback entry**: same stocks as B, but waits for the first pullback after the high of day that holds above VWAP, buys the turn back up, stop under the pullback low
- **E. Strong, pullback entry, news not required**: same stocks as C, with the pullback entry from D

## News check: stocks up 10%+ on 5x volume

175 strong movers; 53 had news before the move was seen; 54 had any news in the feed that day; 0 had an SEC 8-K catalyst; 31 had a verified catalyst (news or SEC); 2 had dilution/negative news (0 from SEC filings).

| day | stock | time | change | volume | news before | news all day | verified | negative | headline |
|---|---|---|---|---|---|---|---|---|---|
| 2026-06-09 | FAC | 9:31 | +36.2% | 12.7x | 0 | 0 | no | - |  |
| 2026-06-09 | AHMA | 9:31 | +121.1% | 18.6x | 0 | 0 | no | - |  |
| 2026-06-09 | AZI | 9:32 | +88.1% | 7.9x | 0 | 0 | no | - |  |
| 2026-06-09 | CHAI | 9:33 | +113.4% | 7.8x | 0 | 0 | no | - |  |
| 2026-06-09 | SLGB | 9:33 | +59.8% | 5.4x | 0 | 0 | no | - |  |
| 2026-06-09 | DAIC | 9:34 | +62.7% | 6.0x | 0 | 0 | no | - |  |
| 2026-06-09 | RNAC | 9:35 | +24.2% | 30.0x | 1 | 1 | yes PARTNERSHIP | - | Cartesian Therapeutics Announces Strategic Licensing Agreement with WestGene Biopharma |
| 2026-06-09 | MTEN | 9:37 | +91.5% | 5.1x | 0 | 0 | no | - |  |
| 2026-06-09 | RGNT | 9:40 | +23.2% | 7.1x | 0 | 0 | no | - |  |
| 2026-06-09 | JZXN | 9:44 | +55.5% | 5.3x | 0 | 0 | no | - |  |
| 2026-06-10 | FLD | 9:31 | +101.4% | 22.7x | 1 | 1 | no | - | Fold Eliminates Secured Debt and Secures $25 Million in Capital |
| 2026-06-10 | DSY | 9:31 | +22.5% | 12.8x | 0 | 1 | no | - |  |
| 2026-06-10 | ESYN | 9:31 | +23.9% | 5.1x | 1 | 1 | no | - | HWH International Stock Experiences Significant After-Hours Surge |
| 2026-06-10 | LUD | 9:31 | +23.9% | 6.9x | 0 | 0 | no | - |  |
| 2026-06-10 | CHNR | 9:31 | +21.3% | 7.1x | 0 | 0 | no | - |  |
| 2026-06-10 | BQ | 9:35 | +39.3% | 9.1x | 0 | 0 | no | - |  |
| 2026-06-10 | PMA | 10:03 | +23.9% | 5.0x | 1 | 1 | yes DEAL | - | Ming Shing Group Holdings Limited Completes Acquisition of PMA Nano Carbon Tech Limited |
| 2026-06-10 | DOGZ | 10:33 | +20.5% | 9.9x | 0 | 0 | no | - |  |
| 2026-06-10 | KMRK | 12:41 | +35.0% | 19.6x | 0 | 0 | no | - |  |
| 2026-06-11 | EDHL | 9:31 | +147.5% | 7.1x | 0 | 0 | no | - |  |
| 2026-06-11 | GLXG | 9:32 | +23.1% | 5.2x | 0 | 0 | no | - |  |
| 2026-06-11 | PPBT | 9:37 | +22.1% | 5.6x | 0 | 0 | no | - |  |
| 2026-06-11 | CAST | 9:58 | +30.2% | 18.9x | 0 | 0 | no | - |  |
| 2026-06-11 | TMDE | 10:04 | +24.5% | 6.3x | 0 | 0 | no | - |  |
| 2026-06-11 | RKDA | 10:27 | +32.7% | 5.1x | 0 | 0 | no | - |  |
| 2026-06-11 | DTSS | 11:33 | +19.0% | 5.2x | 0 | 0 | no | - |  |
| 2026-06-15 | JRSH | 9:31 | +44.3% | 11.2x | 0 | 0 | no | - |  |
| 2026-06-15 | CUPR | 9:31 | +33.2% | 7.0x | 0 | 0 | no | - |  |
| 2026-06-15 | CTM | 9:31 | +29.6% | 9.2x | 1 | 1 | yes CONTRACT,PARTNERSHIP | - | Castellum, Inc. Joint Venture Awarded U.S. Navy Logistics IT Contract |
| 2026-06-15 | NIXX | 9:31 | +25.7% | 9.3x | 1 | 1 | yes PARTNERSHIP | - | Tachyon9 Announces Strategic Partnership with Nidar Infrastructure for Nakota AI Data Campus |
| 2026-06-15 | CNTX | 9:31 | +76.7% | 10.6x | 1 | 1 | yes TRIAL | - | Context Therapeutics Announces Positive Interim Phase 1 Clinical Data for CTIM-76 |
| 2026-06-15 | CAST | 9:33 | +19.3% | 5.0x | 0 | 0 | no | - |  |
| 2026-06-15 | AHMA | 9:37 | +12.7% | 6.3x | 0 | 0 | no | - |  |
| 2026-06-15 | GELS | 9:43 | +38.4% | 5.3x | 0 | 0 | no | - |  |
| 2026-06-18 | WOK | 9:31 | +56.9% | 6.8x | 1 | 1 | yes REVERSE_SPLIT | REVERSE_SPLIT | WORK Medical Technology Announces 1-for-100 Reverse Stock Split |
| 2026-06-18 | LPA | 9:31 | +16.2% | 7.1x | 1 | 1 | no | - | Logistic Properties of the Americas to Sell Peru Logistics Park for $145 Million |
| 2026-06-18 | WKSP | 9:32 | +21.6% | 8.0x | 1 | 1 | no | - | Worksport Announces $1.20 per Share Direct Investment at 100% Premium |
| 2026-06-18 | APWC | 9:37 | +10.6% | 19.0x | 0 | 0 | no | - |  |
| 2026-06-18 | LNKS | 9:45 | +10.8% | 7.2x | 2 | 2 | yes DEAL | - | Linkers Industries Limited Announces Entry into a Material Definitive Agreement |
| 2026-06-18 | ATPC | 10:38 | +14.9% | 16.6x | 0 | 0 | no | - |  |
| 2026-06-29 | DCOY | 9:31 | +33.1% | 9.6x | 1 | 1 | no | - | Decoy Therapeutics Announces Up to $21 Million Private Placement Financing |
| 2026-06-29 | SRFM | 9:31 | +22.2% | 9.8x | 1 | 1 | yes PARTNERSHIP | - | Palantir and Surf Air Mobility Expand Partnership to Accelerate SurfOS Commercialization |
| 2026-06-29 | CHTR | 9:31 | +11.3% | 6.6x | 1 | 3 | no | - | SpaceX in Partnership Talks with Charter Communications |
| 2026-06-29 | PETS | 9:31 | +20.1% | 7.9x | 1 | 1 | yes DEAL | - | SilverCape Investments Submits Revised Acquisition Proposal for PetMed Express |
| 2026-06-29 | UPC | 9:31 | +10.5% | 11.6x | 0 | 0 | no | - |  |
| 2026-06-29 | EVMN | 9:35 | +13.6% | 12.7x | 1 | 2 | yes TRIAL | - | Evommune Announces Top-line Results from EVO756 Phase 2b Trial in Moderate-to-Severe Chronic Spontaneous Urticaria |
| 2026-06-29 | NNBR | 10:34 | +10.1% | 14.4x | 1 | 1 | no | - | NN, Inc. Announces Significant New Awards for NVIDIA Data Center Liquid Cooled Products |
| 2026-07-01 | CANF | 9:31 | +13.2% | 10.4x | 0 | 0 | no | - |  |
| 2026-07-01 | TC | 9:32 | +21.9% | 13.1x | 1 | 1 | no | - | Token Cat Shares Halted on Circuit Breaker |
| 2026-07-01 | DXF | 9:38 | +11.8% | 14.1x | 0 | 0 | no | - |  |
| 2026-07-01 | TONX | 9:38 | +16.2% | 16.7x | 1 | 1 | no | - | TON Strategy Company Enters Rule 10b5-1 Trading Plan for Share Repurchases |
| 2026-07-01 | AMCI | 9:41 | +21.7% | 20.4x | 0 | 0 | no | - |  |
| 2026-07-01 | BLNE | 9:49 | +10.1% | 16.3x | 1 | 1 | yes DEAL | - | Beeline Holdings Completes Acquisition of MagicBlocks |
| 2026-07-01 | CODX | 9:53 | +40.9% | 21.1x | 1 | 1 | yes REGULATORY | - | Co-Diagnostics Completes Clinical and Analytical Studies for FDA 510(k) Submission |
| 2026-07-02 | CWD | 9:31 | +13.0% | 13.6x | 1 | 1 | yes FINANCING | - | Caliber Advances Real Estate Fund Tokenization Strategy with Chainlink |
| 2026-07-02 | CETX | 9:31 | +13.5% | 7.1x | 1 | 1 | yes DEAL | - | Cemtrex Completes Acquisition of Plant Engineering Services |
| 2026-07-02 | CSTE | 9:33 | +10.4% | 25.0x | 0 | 0 | no | - |  |
| 2026-07-02 | SURG | 10:32 | +11.6% | 9.3x | 1 | 1 | no | - | SurgePays Amends Wholesale Wireless Network Agreement to Improve Financial Position |
| 2026-07-02 | CLRO | 13:43 | +29.2% | 15.7x | 0 | 0 | no | - |  |
| 2026-07-10 | GMM | 9:31 | +14.4% | 8.9x | 0 | 0 | no | - |  |
| 2026-07-10 | CDTG | 9:33 | +16.0% | 5.9x | 0 | 0 | no | - |  |
| 2026-07-10 | WDFC | 9:35 | +11.0% | 12.2x | 2 | 2 | yes EARNINGS | - | WD-40 Company Raises Full-Year Outlook Following Strong Fiscal Third-Quarter Results |
| 2026-07-10 | JZXN | 9:44 | +19.4% | 27.5x | 0 | 0 | no | - |  |
| 2026-07-10 | CHSN | 10:07 | +11.8% | 7.1x | 0 | 0 | no | - |  |
| 2026-07-10 | INUV | 10:07 | +14.5% | 7.1x | 1 | 1 | no | - | Inuvo, Inc. Publishes Updated Investor Presentation |
| 2026-07-10 | WOK | 10:30 | +10.4% | 5.1x | 0 | 0 | no | - |  |
| 2026-07-10 | CPHI | 11:22 | +48.0% | 13.2x | 0 | 0 | no | - |  |
| 2026-07-17 | PSNYW | 9:31 | +68.6% | 16.8x | 0 | 0 | no | - |  |
| 2026-07-17 | STXS | 9:31 | +11.9% | 14.9x | 1 | 1 | no | - | Stereotaxis Files Resale Registration for Up to 108.9 Million Shares |
| 2026-07-17 | GIPR | 9:31 | +24.1% | 10.0x | 0 | 0 | no | - |  |
| 2026-07-17 | WYHG | 9:41 | +11.3% | 6.4x | 0 | 0 | no | - |  |
| 2026-07-17 | BIYA | 9:51 | +12.8% | 5.4x | 0 | 0 | no | - |  |
| 2026-07-17 | GLXG | 10:51 | +34.0% | 5.5x | 0 | 0 | no | - |  |
| 2026-07-17 | KLRS | 11:26 | +39.3% | 9.6x | 1 | 1 | no | - | Kalaris Therapeutics Reports Positive Additional Data from Phase 1a Trial of TH103 |
| 2026-07-17 | HPAI | 15:30 | +23.3% | 10.0x | 0 | 0 | no | - |  |
| 2026-07-21 | PYPD | 9:31 | +23.1% | 10.2x | 0 | 0 | no | - |  |
| 2026-07-21 | SLGB | 9:32 | +17.4% | 6.4x | 0 | 0 | no | - |  |
| 2026-07-21 | HIHO | 9:35 | +18.2% | 5.5x | 1 | 1 | yes EARNINGS | - | Highway Holdings Reports Fiscal First Quarter 2027 Results |
| 2026-07-21 | CCTG | 9:39 | +18.7% | 8.8x | 0 | 0 | no | - |  |
| 2026-07-21 | PWCM | 10:00 | +11.1% | 5.9x | 1 | 1 | no | - | LM Funding America Announces Corporate Name Change to PowerCompute, Inc. |
| 2026-07-21 | IMNN | 10:07 | +10.8% | 11.9x | 0 | 0 | no | - |  |
| 2026-07-21 | MWC | 10:16 | +10.8% | 44.5x | 0 | 0 | no | - |  |
| 2026-07-21 | DFNS | 14:01 | +23.2% | 13.9x | 1 | 1 | no | - | T3 Defense Subsidiary ITS Delivers Custom Composite Materials Production Line |
| 2026-07-23 | WBUY | 9:32 | +10.6% | 14.7x | 0 | 0 | no | - |  |
| 2026-07-23 | JEM | 9:38 | +12.7% | 13.7x | 0 | 0 | no | - |  |
| 2026-07-23 | PLAG | 9:42 | +12.5% | 5.3x | 0 | 0 | no | - |  |
| 2026-07-23 | MCRP | 9:44 | +11.4% | 7.7x | 0 | 0 | no | - |  |
| 2026-07-23 | CJMB | 10:00 | +13.3% | 14.9x | 0 | 0 | no | - |  |
| 2026-07-23 | SORA | 10:35 | +26.1% | 12.5x | 0 | 0 | no | - |  |
| 2026-07-23 | WLDS | 10:50 | +13.9% | 16.0x | 0 | 0 | no | - |  |
| 2026-08-06 | ENSC | 9:31 | +14.4% | 5.2x | 0 | 0 | no | - |  |
| 2026-08-06 | CLRO | 9:32 | +21.5% | 15.7x | 0 | 0 | no | - |  |
| 2026-08-06 | PAVS | 9:32 | +19.6% | 5.3x | 0 | 0 | no | - |  |
| 2026-08-06 | LCUT | 9:34 | +12.9% | 20.4x | 1 | 1 | no | - | Lifetime Brands, Inc. Reports Second Quarter 2026 Financial Results and Declares Quarterly Dividend |
| 2026-08-06 | ASPN | 9:36 | +10.4% | 12.9x | 1 | 2 | no | - | Aspen Aerogels to Present at the 29th Annual Oppenheimer Technology, Internet & Communications Conference |
| 2026-08-06 | WYHG | 9:49 | +14.4% | 8.9x | 0 | 0 | no | - |  |
| 2026-08-06 | FVN | 9:50 | +23.9% | 5.1x | 0 | 0 | no | - |  |
| 2026-08-06 | AZI | 10:07 | +13.4% | 19.4x | 0 | 0 | no | - |  |
| 2026-08-06 | AEVA | 10:41 | +10.2% | 7.3x | 1 | 2 | yes EARNINGS | - | Aeva Technologies, Inc. Reports Second Quarter 2026 Financial Results |
| 2026-08-06 | CELZ | 10:50 | +10.4% | 7.5x | 0 | 0 | no | - |  |
| 2026-08-06 | BYAH | 12:29 | +87.9% | 11.5x | 0 | 0 | no | - |  |
| 2026-08-14 | WETO | 9:31 | +18.8% | 5.7x | 0 | 0 | no | - |  |
| 2026-08-14 | INV | 9:31 | +25.7% | 13.6x | 1 | 1 | no | - | Innventure, Inc. Reports Second Quarter 2026 Financial Results |
| 2026-08-14 | AKAN | 9:32 | +19.1% | 5.6x | 0 | 0 | no | - |  |
| 2026-08-14 | DARE | 9:32 | +57.0% | 6.5x | 0 | 0 | no | - |  |
| 2026-08-14 | CAPR | 9:36 | +10.5% | 7.5x | 1 | 1 | no | - | Capricor Therapeutics Reports Second Quarter 2026 Financial Results |
| 2026-08-14 | MDXH | 9:38 | +23.7% | 10.7x | 0 | 0 | no | - |  |
| 2026-08-14 | MF | 9:42 | +31.2% | 6.9x | 0 | 0 | no | - |  |
| 2026-08-14 | ONFO | 10:11 | +64.5% | 11.3x | 0 | 0 | no | - |  |
| 2026-08-14 | AEHL | 10:28 | +38.7% | 5.4x | 0 | 0 | no | - |  |
| 2026-08-14 | LFS | 12:16 | +62.4% | 13.2x | 0 | 0 | no | - |  |
| 2026-08-18 | SLE | 9:31 | +24.5% | 11.0x | 0 | 0 | no | - |  |
| 2026-08-18 | ENRD | 9:31 | +27.4% | 12.9x | 2 | 2 | yes EARNINGS | - | Einride AB Announces First Half 2026 Financial Results |
| 2026-08-18 | HDSN | 9:31 | +10.3% | 16.3x | 0 | 0 | no | - |  |
| 2026-08-18 | SGLY | 9:33 | +80.5% | 5.2x | 0 | 0 | no | - |  |
| 2026-08-18 | FFR | 9:44 | +14.4% | 15.4x | 0 | 0 | no | - |  |
| 2026-08-18 | TDTH | 9:45 | +15.6% | 5.7x | 0 | 0 | no | - |  |
| 2026-08-18 | EJH | 9:58 | +13.1% | 24.9x | 0 | 0 | no | - |  |
| 2026-08-18 | DUOT | 10:08 | +10.2% | 11.5x | 3 | 3 | yes EARNINGS | - | Duos Technologies Group, Inc. Reports Second Quarter 2026 Financial Results |
| 2026-08-18 | SAGT | 10:12 | +12.7% | 12.6x | 0 | 0 | no | - |  |
| 2026-08-18 | CDTG | 14:26 | +98.3% | 10.2x | 0 | 0 | no | - |  |
| 2026-08-18 | PSIG | 15:04 | +11.2% | 12.8x | 0 | 0 | no | - |  |
| 2026-08-19 | YJ | 9:31 | +20.0% | 8.4x | 0 | 0 | no | - |  |
| 2026-08-19 | FEMY | 9:31 | +13.3% | 30.3x | 0 | 0 | no | - |  |
| 2026-08-19 | CAST | 9:32 | +12.9% | 5.4x | 0 | 0 | no | - |  |
| 2026-08-19 | TNON | 9:36 | +11.3% | 10.6x | 0 | 0 | no | - |  |
| 2026-08-19 | MSS | 9:37 | +18.3% | 5.2x | 0 | 0 | no | - |  |
| 2026-08-19 | RDAC | 9:38 | +79.2% | 6.3x | 0 | 0 | no | - |  |
| 2026-08-19 | VRAX | 9:42 | +11.0% | 9.9x | 0 | 0 | no | - |  |
| 2026-08-19 | RNTZ | 10:01 | +42.4% | 6.3x | 0 | 0 | no | - |  |
| 2026-08-19 | QTEX | 10:18 | +16.0% | 11.6x | 0 | 0 | no | - |  |
| 2026-08-19 | OLOX | 10:25 | +10.0% | 11.3x | 0 | 0 | no | - |  |
| 2026-08-19 | GDC | 11:20 | +27.7% | 11.0x | 0 | 0 | no | - |  |
| 2026-08-19 | ZSTK | 12:39 | +111.5% | 12.7x | 0 | 0 | no | - |  |
| 2026-08-28 | QNRX | 9:31 | +20.4% | 12.6x | 0 | 0 | no | - |  |
| 2026-08-28 | KZIA | 9:31 | +13.5% | 9.3x | 2 | 3 | yes OFFERING | OFFERING | Kazia Therapeutics Announces Proposed Public Offering |
| 2026-08-28 | AFRM | 9:31 | +13.9% | 13.4x | 2 | 3 | yes ANALYST | - | RBC Raises Price Target on Affirm Holdings to $96 From $80 |
| 2026-08-28 | AEMD | 9:32 | +19.3% | 10.3x | 0 | 0 | no | - |  |
| 2026-08-28 | XLAB | 9:42 | +22.6% | 5.4x | 0 | 0 | no | - |  |
| 2026-08-28 | PAAI | 10:40 | +20.1% | 8.5x | 0 | 0 | no | - |  |
| 2026-08-28 | KXIN | 13:15 | +11.2% | 8.4x | 0 | 0 | no | - |  |
| 2026-08-28 | DUO | 14:38 | +12.5% | 10.3x | 0 | 0 | no | - |  |
| 2026-09-09 | TTAN | 9:31 | +19.2% | 11.7x | 2 | 5 | yes EARNINGS | - | ServiceTitan Appoints Rikus Pretorius as Chief Revenue Officer |
| 2026-09-09 | IRD | 9:34 | +11.6% | 14.1x | 1 | 2 | yes TRIAL | - | Opus Genetics Announces Positive Low Dose Cohort 1 Data from Phase 1/2 Clinical Trial of OPGx-BEST1 |
| 2026-09-09 | CRMT | 9:34 | +27.6% | 6.5x | 1 | 1 | yes EARNINGS | - | America's Car-Mart Reports Financial Results for First Quarter Ended July 31, 2026 |
| 2026-09-09 | PYXS | 9:36 | +10.4% | 6.7x | 2 | 2 | yes TRIAL | - | Pyxis Oncology Announces Positive Updated Data from Phase 1 Monotherapy Study of MICVO |
| 2026-09-09 | LASE | 9:39 | +18.6% | 12.3x | 0 | 0 | no | - |  |
| 2026-09-09 | OPTH | 9:47 | +10.2% | 15.3x | 1 | 1 | no | - | Optimi Health Corp. News Announcement |
| 2026-09-09 | FTFT | 11:19 | +48.1% | 8.2x | 0 | 0 | no | - |  |
| 2026-09-16 | XBIO | 9:31 | +23.0% | 6.6x | 1 | 1 | yes DEAL | - | Xenetic Biosciences Enters Definitive Share Exchange Agreement to Acquire Santersus AG |
| 2026-09-16 | ENRD | 9:31 | +11.1% | 9.9x | 1 | 1 | yes ANALYST | - | Canaccord Genuity Initiates Einride With Buy Rating |
| 2026-09-16 | BZAI | 9:31 | +17.3% | 19.1x | 0 | 0 | no | - |  |
| 2026-09-16 | ZTG | 9:32 | +80.9% | 5.7x | 0 | 0 | no | - |  |
| 2026-09-16 | MYSE | 9:32 | +21.6% | 6.6x | 1 | 1 | yes PARTNERSHIP | - | Myseum.AI, Inc. Announces Partnership with FUJIFILM North America Corporation |
| 2026-09-16 | CODX | 9:32 | +15.1% | 24.1x | 2 | 2 | yes REGULATORY | - | Co-Diagnostics Reaches Proposed $6.5 Million Settlement in Securities Litigation |
| 2026-09-16 | BYAH | 9:46 | +41.9% | 15.4x | 0 | 0 | no | - |  |
| 2026-09-16 | PRFX | 10:18 | +13.9% | 9.3x | 0 | 0 | no | - |  |
| 2026-09-16 | MEDS | 10:49 | +18.4% | 13.2x | 0 | 0 | no | - |  |
| 2026-09-16 | QCLS | 11:33 | +16.2% | 18.6x | 1 | 1 | no | - | Q/C Technologies Appoints Dr. Yossef Ehrlichman as Chief Technology Officer |
| 2026-09-16 | JZXN | 11:42 | +24.0% | 5.3x | 0 | 0 | no | - |  |
| 2026-09-16 | BENF | 12:05 | +34.3% | 5.1x | 0 | 0 | no | - |  |
| 2026-09-16 | CUPR | 13:42 | +11.9% | 7.2x | 0 | 0 | no | - |  |
| 2026-09-16 | TPST | 14:19 | +14.6% | 8.3x | 0 | 0 | no | - |  |
| 2026-09-23 | TLSI | 9:31 | +11.8% | 19.5x | 1 | 1 | yes REGULATORY | - | TriSalus Life Sciences Receives FDA 510(k) Clearance for TriNav® Advance |
| 2026-09-23 | IPDN | 9:33 | +41.5% | 8.2x | 0 | 0 | no | - |  |
| 2026-09-23 | DCOY | 9:33 | +19.2% | 5.1x | 1 | 1 | no | - | Decoy Therapeutics Announces Refined Strategy for Pan-Filovirus Program via FDA Animal Rule Pathway |
| 2026-09-23 | MSS | 9:37 | +10.0% | 16.5x | 0 | 0 | no | - |  |
| 2026-09-23 | GYGY | 9:42 | +22.6% | 11.4x | 1 | 1 | yes PRODUCT | - | Game Your Game Announces Full Commercial Availability of Next-Generation GameGolf KZN AI™ |
| 2026-09-23 | LGCL | 9:58 | +10.8% | 8.5x | 0 | 0 | no | - |  |
| 2026-09-23 | FLYE | 10:25 | +10.5% | 9.2x | 0 | 0 | no | - |  |
| 2026-09-23 | AUUD | 10:30 | +23.7% | 12.3x | 0 | 0 | no | - |  |
| 2026-09-23 | GNPX | 12:03 | +10.7% | 10.8x | 0 | 0 | no | - |  |
| 2026-09-23 | ARTL | 12:56 | +59.0% | 9.2x | 0 | 0 | no | - |  |
| 2026-09-23 | BFRG | 14:33 | +10.5% | 9.0x | 0 | 0 | no | - |  |
| 2026-09-23 | VSA | 15:03 | +26.4% | 11.4x | 0 | 0 | no | - |  |
