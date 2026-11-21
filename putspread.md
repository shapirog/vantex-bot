# VANTEX City research: selling put credit spreads (Feb 2024 - now)

Sell a put ~2% (weekly) or ~5% (monthly) below the price, buy one further below; credit at daily VWAPs minus 3% per leg. Return = profit / money at risk. Dollar columns: $500 at risk per trade, every signal taken (several trades open at once).

| underlyings | expiry | exits | trades | win rate | avg return on risk | median | worst trade | lost ~all | t-stat | months | avg month ($500/trade) | months up | worst month | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SPY/QQQ/IWM/DIA | ~1 week | hold to expiry | 527 | 83.5% | +1.62% | +10.94% | -100.0% | 9.1% | 0.97 | 33 | $+129 | 67% | 2026-03: $-5,369 | $+4,262 |
| SPY/QQQ/IWM/DIA | ~1 week | managed (50% profit / 2x stop) | 527 | 59.4% | -2.15% | +4.7% | -100.0% | 0.2% | -2.08 | 34 | $-166 | 35% | 2024-12: $-1,167 | $-5,659 |
| SPY/QQQ/IWM/DIA | ~1 month | hold to expiry | 508 | 91.7% | +5.59% | +9.56% | -100.0% | 3.1% | 4.46 | 30 | $+473 | 83% | 2025-03: $-5,775 | $+14,203 |
| SPY/QQQ/IWM/DIA | ~1 month | managed (50% profit / 2x stop) | 508 | 53.7% | -2.45% | +3.05% | -74.1% | 0.0% | -2.91 | 32 | $-195 | 38% | 2026-03: $-1,906 | $-6,233 |
| SPY/QQQ/IWM/DIA | ~1 month, $5 wide (small account) | hold to expiry | 486 | 91.6% | +3.45% | +8.09% | -100.0% | 6.2% | 2.35 | 30 | $+280 | 80% | 2025-03: $-6,743 | $+8,390 |
| SPY/QQQ/IWM/DIA | ~1 month, $5 wide (small account) | managed (50% profit / 2x stop) | 486 | 32.9% | -6.62% | -9.04% | -100.0% | 0.2% | -7.03 | 32 | $-503 | 9% | 2026-06: $-1,570 | $-16,082 |
| top-15 stocks | ~1 week | hold to expiry | 1875 | 65.9% | +0.2% | +18.22% | -100.0% | 27.7% | 0.04 | 33 | $+56 | 45% | 2026-06: $-12,928 | $+1,859 |
| top-15 stocks | ~1 week | managed (50% profit / 2x stop) | 1875 | 46.0% | -9.22% | -19.09% | -100.0% | 8.5% | -2.57 | 34 | $-2,542 | 15% | 2024-07: $-12,793 | $-86,420 |
| top-15 stocks | ~1 month | hold to expiry | 1868 | 72.6% | -3.56% | +21.5% | -100.0% | 22.9% | -2.69 | 30 | $-1,109 | 50% | 2025-03: $-18,443 | $-33,283 |
| top-15 stocks | ~1 month | managed (50% profit / 2x stop) | 1868 | 40.0% | -17.86% | -24.54% | -100.0% | 3.1% | -20.5 | 33 | $-5,055 | 9% | 2026-06: $-14,985 | $-166,822 |

SPY buy and hold over the same span: +38.7%.

## $2,500 account, monthly $5-wide ETF spreads, held to expiry

Start $2,500; each week open at most one 1-contract spread per ETF while total money at risk stays <= the account. End: $4,825 (+93.0%), worst drop 56.4%, trades 177, by year {'2024': 4299.0, '2025': 8407.0, '2026': 4825.0}.

Daily VWAPs, not live quotes: a real order may get a worse credit. Early assignment and dividends are ignored (European-style settlement at the expiration close). A backtest is not proof.
