# VANTEX City: market-wide scanner and paper trader

The City engine scans every eligible US stock once a minute from 4:00 AM to 8:00 PM ET on market days. It explains what it
finds and paper-trades only when a complete setup passes every rule. Everything runs on GitHub Actions. The City page
(vantexcity.com, **HQ** tab) reads the results. **Paper trading only.** There is no live mode, no live endpoint and no live order path.

## Files

| File | What it does |
|---|---|
| `vantex_core.py` | All decision logic: scanner math, news tagging, breakout/breakdown confirmation, fakeout flags, sizing, risk lockouts, fees and the fill model. It has no network code. |
| `city_broker.py` | The only code that can send orders. The host is fixed to `paper-api.alpaca.markets`. It re-checks the paper key (PK…) and the paper account (PA…) before every order. |
| `city_engine.py` | The live loop. It covers the universe, whole-market snapshots, candidate lists, deep analysis, news, market context, paper orders and logs, and publishes to the `live-city` branch. |
| `city_replay.py` | Replays past sessions minute by minute (no look-ahead) and runs the dev / out-of-sample evaluation. Publishes to `live-replay`. |
| `city_config.json` | Every filter, threshold and risk limit. Edit it on GitHub; the engine re-reads it every 5 minutes. |
| `hq.js` | The HQ tab, the ticker chart and the City effects (HQ beacon, breadth sky). It only reads published JSON. |
| `tests/` | 54 tests: scanner math, signal rules, sizing, lockouts, stale feed, paper-only routing, the engine against a simulated market, and a replay look-ahead canary. |
| `.github/workflows/city.yml` | Runs the tests, then the engine. It relays itself every 5.5 h, and the Keeper restarts it if it stops. |
| `.github/workflows/city-tests.yml` | Runs the tests on every commit to the City files. |
| `.github/workflows/city-replay.yml` | Runs a replay of one session, or the evaluation. |

## Secrets (Settings → Secrets and variables → Actions)

| Secret | Needed | Notes |
|---|---|---|
| `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` | yes (already set) | **Paper** keys only. The engine refuses to start with any other key. |
| `VANTEX_PAPER_ACCOUNT` | optional | Your paper account number (PA…). If it's set, orders are refused for any other account. |
| `NTFY_TOPIC` | optional (already set) | Phone alert for each paper order. |
| `SEC_UA` | optional (already set) | Lets the engine look up share counts for market cap. |

## Data: what the feed really is

Alpaca is the only market-data provider connected. The engine checks your plan when it starts and labels everything with it:

| Plan | Scanner | Charts / features | Spreads | New paper entries |
|---|---|---|---|---|
| **Free (current)** | all eligible stocks, **15 minutes delayed** (SIP) | 15 minutes delayed | IEX quotes only (one exchange) | **blocked** (delayed + partial data) |
| Algo Trader Plus (~$99/mo) | all stocks, real time | real time | real-time SIP (all exchanges) | allowed when every other rule passes |

- **News:** Alpaca news (Benzinga wire) is the only news source. There is no social-media feed and no SEC filings feed.
- **Scheduled events:** no economic calendar is connected, so the City says so instead of guessing.
- **Halts:** Alpaca has no halt feed. A liquid stock with no trades for 5+ minutes is flagged as a "possible halt" and blocked.
- **Sectors:** shown from the sector ETFs (XLK, XLF, …). Individual stocks have no sector label.
- **Market cap:** only where the SEC has a share count. Otherwise it shows "unknown".
- **Coverage:** every stock Alpaca lists on NASDAQ/NYSE/AMEX/ARCA/BATS, minus non-common shares (ETFs, funds, warrants, units, rights, preferreds, notes), stocks with less than 15 days of history, and anything outside the filters. Every exclusion and its reason is in `coverage.json`. HQ → Data & health → "Why wasn't a stock scanned?" looks it up.

## Rules (defaults in `city_config.json`)

- **Candidates:** gainers and decliners (±3%), unusual volume (3× for the time of day), new 20-day highs and lows, and stocks near key levels. A candidate is something to **watch**, not permission to trade.
- **Ranking:** relative volume, liquidity, how far the setup has developed, volume with the move, spread, warnings and catalyst. The biggest % gainer does not win by default. Stocks that already ran are labelled **extended**.
- **Long breakout:** a 1-minute close (or 5-minute, configurable) beyond the opening range, premarket high, prior-day high or 20-day high. It also needs supporting time-of-day volume, a hold or retest, an acceptable spread and liquidity, and VWAP/trend that don't contradict. Bearish breakdowns use the same rules, mirrored.
- **Warnings:** immediate reversal, long wicks, weak follow-through on falling volume, a single outlier print, far from VWAP, wide spread, thin trading, possible halt, a quote that disagrees with the last price, and 1-minute vs 5-minute trend conflict.
- **Statuses:** confirmed, developing, extended, rejected, watching. Only **confirmed** can become an order. Everything else shows **WAIT / NO TRADE** with the reason.
- **Orders:** a limit at the ask +0.05% with an attached stop and a 2R target (bracket). It's cancelled after 60 s if it doesn't fill, and the failed or partial fill is logged. A stop is not guaranteed in a halt or gap.
- **Risk ($2,500 defaults):**
  - 0.5% risk per trade ($12.50); shares = risk ÷ stop distance, never sized from buying power
  - 1.5% daily loss lockout ($37.50)
  - at most 2 positions, 50% exposure and 25% in one stock
  - one entry per stock per day: no averaging down, no sizing up after a loss
  - entries 9:35–15:30, everything closed at 15:50
  - the day-trade limit under $25K is respected
- **Shorts:** `"allow_short_orders": false`. Bearish setups are watch-only until you turn it on.
- **Pause:** in `control.json` set `"city": "pause"` (no new entries), `"city": "stop"` (close the City's positions) or `"city": "on"`. `"trading": "pause"/"stop"` applies to the City too.

## Running it

1. The Keeper starts the engine every weekday at about 3:55 AM ET. To start it by hand, go to Actions → **Vantex City engine** → Run workflow.
2. Open vantexcity.com → **HQ** (bottom tab), or tap the **MARKET HQ** sign on the river island in the City.
3. **Replay:** Actions → **Vantex City replay and evaluation** → mode `replay`, with a date or blank for the last session. Then use HQ → Replay → Load and watch.
4. **Evaluation:** the same workflow with mode `eval`:
   - Split `dev` (sessions Sep 2025 – Apr 2026) is for judging and tuning the rules.
   - Split `test` (May 2026 on) is the untouched out-of-sample check. Run it **once**, after the rules are final.

## What the tests and replay do and don't show

- The tests prove the plumbing:
  - the math is right
  - orders can only reach the paper host
  - delayed, stale or paused states block entries
  - the replay can't see the future: changing every price after 10:00 leaves every decision before 10:00 identical
- They do **not** show the strategy makes money. Every strategy tested in labs 3–11 lost money after costs.
- A profitable replay or evaluation would still not prove future results. The sample is small, and the stock list is today's, so delisted stocks are missing (survivorship).
- In replay, halts are only inferred from missing minutes. News headlines are as stored now.
