"""
VANTEX City research batch 6: index-ETF timing effects. Research only: places NO orders.

Why index ETFs: one position, tiny spreads (SPY/QQQ ~0.01%), auction orders available, no survivorship bias, works for
a small account. Every rule below is a published effect with fixed parameters (nothing tuned):
  X1  SPY overnight only      buy at the close, sell at the next open, every day           (Cliff, Cooper & Gulen 2008 ...)
  X2  QQQ overnight only      same on QQQ
  X3  SPY intraday only       buy at the open, sell at the close (the mirror image, for comparison)
  X4  intraday momentum       if SPY's return from the prior close to 10:00 is positive, buy at 15:30 and sell at the 16:00
                              close; if negative, stay out (long-only version of Gao, Han, Li & Zhou 2018)
  X5  pre-FOMC drift          buy SPY at the close the day before a scheduled Fed decision, sell at 14:00 on decision day
                              (Lucca & Moench 2015); dates are the published FOMC calendar
  X6  volatility-managed SPY  each month hold SPY at weight min(1, target / last month's realized variance), rest cash
                              (Moreira & Muir 2017; long-only, no leverage); target = average variance of the prior 12 months
Costs: 0.01% and 0.03% per side (auction-style fills vs. a cent or so of spread), plus SEC/FINRA fees on sales.
Both periods are reported in one run because nothing is chosen from the development period.

  python city_index.py   -> live-replay/index_effects.md / .json
"""
import json, math, os, sys
from collections import defaultdict
from datetime import date, datetime, timedelta

from city_engine import Data, to_bar
from city_replay import ET, log, publish

PERIODS = {'dev 2023-06..2025-12': ('2023-06-01', '2025-12-31'), 'test 2026': ('2026-01-01', '2026-12-31')}
COSTS = (0.0001, 0.0003)
FOMC = ['2023-06-14', '2023-07-26', '2023-09-20', '2023-11-01', '2023-12-13',
        '2024-01-31', '2024-03-20', '2024-05-01', '2024-06-12', '2024-07-31', '2024-09-18', '2024-11-07', '2024-12-18',
        '2025-01-29', '2025-03-19', '2025-05-07', '2025-06-18', '2025-07-30', '2025-09-17', '2025-10-29', '2025-12-10',
        '2026-01-28', '2026-03-18', '2026-04-29', '2026-06-17', '2026-07-29', '2026-09-16', '2026-10-28']

def daily_from_minutes(M):
    """day -> dict(open at 9:30, close at the last regular bar, px_1000 = close of the 9:59 bar, px_1530 = close of the 15:29 bar,
    px_1400 = close of the 13:59 bar). Only regular-session bars."""
    by = defaultdict(list)
    for b in M:
        if 570 <= b.m < 960: by[datetime.fromtimestamp(b.t, ET).date().isoformat()].append(b)
    out = {}
    for d, L in sorted(by.items()):
        L.sort(key=lambda b: b.m)
        def at(m):
            c = [b for b in L if b.m <= m]; return c[-1].c if c else None
        if L[0].m > 575 or L[-1].m < 950: continue                           # skip days with a broken session (half days stay: they end ~13:00)
        out[d] = dict(open=L[0].o, close=L[-1].c, px_1000=at(599), px_1530=at(929), px_1400=at(839), last_m=L[-1].m)
    return out

def series_stats(rets, per_year=252):
    if not rets: return dict(trades=0)
    eq, peak, dd = 1.0, 1.0, 0.0
    for _, r in rets: eq *= 1 + r; peak = max(peak, eq); dd = max(dd, (peak - eq) / peak * 100)
    xs = [r for _, r in rets]; mu = sum(xs) / len(xs); sd = (sum((x - mu) ** 2 for x in xs) / max(1, len(xs) - 1)) ** 0.5
    return dict(trades=len(xs), total_return_pct=round((eq - 1) * 100, 2), avg_pct=round(mu * 100, 4), win_rate_pct=round(100 * sum(x > 0 for x in xs) / len(xs), 1),
                sharpe=round(mu / sd * per_year ** 0.5, 2) if sd else None, max_drawdown_pct=round(dd, 1))

def overnight(D, a, b, c):
    ds = [d for d in sorted(D) if a <= d <= b]; all_ds = sorted(D); pos = {d: k for k, d in enumerate(all_ds)}
    return [(d, D[all_ds[pos[d] + 1]]['open'] * (1 - c) / (D[d]['close'] * (1 + c)) - 1) for d in ds if pos[d] + 1 < len(all_ds)]

def intraday(D, a, b, c):
    return [(d, D[d]['close'] * (1 - c) / (D[d]['open'] * (1 + c)) - 1) for d in sorted(D) if a <= d <= b]

def intraday_momentum(D, a, b, c):
    all_ds = sorted(D); pos = {d: k for k, d in enumerate(all_ds)}; out = []
    for d in all_ds:
        if not (a <= d <= b) or pos[d] == 0: continue
        x = D[d]; prev = D[all_ds[pos[d] - 1]]['close']
        if x['last_m'] < 955 or not x['px_1000'] or not x['px_1530']: continue          # half days: no 15:30-16:00 window
        if x['px_1000'] / prev - 1 > 0: out.append((d, x['close'] * (1 - c) / (x['px_1530'] * (1 + c)) - 1))
    return out

def pre_fomc(D, a, b, c):
    all_ds = sorted(D); pos = {d: k for k, d in enumerate(all_ds)}; out = []
    for f in FOMC:
        if not (a <= f <= b) or f not in pos or pos[f] == 0: continue
        prev = all_ds[pos[f] - 1]; px = D[f]['px_1400']
        if px: out.append((f, px * (1 - c) / (D[prev]['close'] * (1 + c)) - 1))
    return out

def vol_managed(D, a, b, c):
    """monthly; weight = min(1, mean variance of prior 12 months / last month's variance); trades at the first open of the month"""
    all_ds = sorted(D); months = defaultdict(list)
    for d in all_ds: months[d[:7]].append(d)
    ms = sorted(months); out = []; w_prev = 0.0
    var = {}
    for m in ms:
        L = months[m]; r = [D[L[k]]['close'] / D[L[k - 1]]['close'] - 1 for k in range(1, len(L))]
        var[m] = sum(x * x for x in r) / max(1, len(r))
    for k in range(13, len(ms) - 1):
        m, nxt = ms[k], ms[k + 1]
        first, first_next = months[m][0], months[nxt][0]
        if not (a <= first <= b): continue
        target = sum(var[x] for x in ms[k - 13:k - 1]) / 12; last = var[ms[k - 1]]
        w = min(1.0, target / last) if last > 0 else 1.0
        spy = D[first_next]['open'] / D[first]['open'] - 1
        turn = abs(w - w_prev) * c; w_prev = w
        out.append((first, w * spy - turn))
    return out

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    Dt = Data(key, sec)
    s0 = datetime(2022, 5, 1, tzinfo=ET); s1 = datetime.now(ET) - timedelta(days=1)
    data = {}
    for sym in ('SPY', 'QQQ'):
        raw = Dt.bars([sym], '1Min', s0, s1, 'sip', 'all').get(sym, [])
        data[sym] = daily_from_minutes([to_bar(b) for b in raw]); log(sym, 'days', len(data[sym]))
    out = {}; rows = ['| effect | period | cost/side | trades | win rate | avg per trade | total | Sharpe | max drawdown |', '|---|---|---|---|---|---|---|---|---|']
    tests = [('X1 SPY overnight only', lambda a, b, c: overnight(data['SPY'], a, b, c), 252),
             ('X2 QQQ overnight only', lambda a, b, c: overnight(data['QQQ'], a, b, c), 252),
             ('X3 SPY intraday only', lambda a, b, c: intraday(data['SPY'], a, b, c), 252),
             ('X4 SPY intraday momentum (long-only)', lambda a, b, c: intraday_momentum(data['SPY'], a, b, c), 252),
             ('X5 SPY pre-FOMC drift', lambda a, b, c: pre_fomc(data['SPY'], a, b, c), 8),
             ('X6 volatility-managed SPY (monthly)', lambda a, b, c: vol_managed(data['SPY'], a, b, c), 12),
             ('SPY buy and hold (open to open, monthly)', lambda a, b, c: vol_managed_bh(data['SPY'], a, b), 12)]
    for name, fn, py in tests:
        for per, (a, b) in PERIODS.items():
            for c in (COSTS if 'buy and hold' not in name else (0.0,)):
                S = series_stats(fn(a, b, c), py); out[f'{name} | {per} | {c * 100:.2f}%'] = S
                if S.get('trades'):
                    rows.append(f"| {name} | {per} | {c * 100:.2f}% | {S['trades']} | {S['win_rate_pct']}% | {S['avg_pct']}% | {S['total_return_pct']:+}% | {S['sharpe']} | {S['max_drawdown_pct']}% |")
    md = ['# VANTEX City research batch 6: index-ETF timing effects', '',
          'Published rules, fixed parameters, SPY/QQQ minute data (regular session only). Costs are per side; Sharpe is annualized from each '
          'effect\'s own trade frequency, so compare it with the buy-and-hold row, not raw totals (most of these are in the market only part of the time).', ''] + rows + ['',
          'FOMC dates are the published calendar of scheduled decisions. Half days are skipped for the 15:30-16:00 test. A backtest is not proof.']
    publish({})
    publish({'index_effects.json': out, 'index_effects.md': '\n'.join(md) + '\n'})

def vol_managed_bh(D, a, b):
    all_ds = sorted(D); months = defaultdict(list)
    for d in all_ds: months[d[:7]].append(d)
    ms = sorted(months)
    return [(months[ms[k]][0], D[months[ms[k + 1]][0]]['open'] / D[months[ms[k]][0]]['open'] - 1) for k in range(len(ms) - 1) if a <= months[ms[k]][0] <= b]

if __name__ == '__main__':
    main()
