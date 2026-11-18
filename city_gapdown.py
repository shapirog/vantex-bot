"""
VANTEX City research: GAP-DOWN BOUNCE in strong large stocks (published rule, Quantitativo "Mind the gap", 2024-25). Research only.

Rule (fixed before testing; the article does not publish its gap threshold, so 2% is the main setting and 1% / 3% are shown
only as a sensitivity check, not to pick the best):
  universe   each day: the 500 stocks with the highest 60-session average dollar volume (a point-in-time stand-in for the S&P 500),
             price >= $5, active + delisted symbols
  signal     the stock OPENS below the prior close by >= 2% and the open is above its 200-session moving average of closes
  trade      buy at the open (market-on-open style), sell at the NEXT day's open
  sizing     up to 10 positions, 10% each; if more than 10 qualify, the 10 least volatile (20-session std of daily returns)
  costs      0.05% / 0.10% / 0.25% per side (the article: very sensitive to slippage)
Dev = Jun 2023 - Dec 2025, test = 2026. Daily data only; the opening price is the official open.

  python city_gapdown.py   -> live-replay/gapdown.md / .json
"""
import json, os, sys
from collections import defaultdict
from datetime import date, datetime, timedelta

from city_engine import Data
from city_replay import ET, log, publish
from city_overnight import universe, load_all, index

PERIODS = {'dev 2023-06..2025-12': ('2023-06-01', '2025-12-31'), 'test 2026': ('2026-01-01', '2026-12-31')}
COSTS = (0.0005, 0.0010, 0.0025)
THRESH = (0.02, 0.01, 0.03)

def daily_candidates(stocks, cal, top=500):
    """day -> list of (sym, i, gap, vol20) that pass the universe + trend filter, gap not applied yet. Uses only data before the open
    (plus the open itself)."""
    idx = index(stocks); out = {}
    pre = {}
    for s, (ds, op, cl, vol) in stocks.items():
        dv = [c * v for c, v in zip(cl, vol)]; p = [0.0]
        for x in dv: p.append(p[-1] + x)
        pc = [0.0]
        for x in cl: pc.append(pc[-1] + x)
        pre[s] = (p, pc)
    for k, d in enumerate(cal):
        rows = []
        for s, S in stocks.items():
            i = idx[s].get(d)
            if i is None or i < 200: continue
            ds, op, cl, vol = S; p, pc = pre[s]
            if cl[i - 1] < 5: continue
            adv = (p[i] - p[i - 60]) / 60
            rows.append((adv, s, i))
        rows.sort(reverse=True); sel = []
        for adv, s, i in rows[:top]:
            ds, op, cl, vol = stocks[s]; p, pc = pre[s]
            sma200 = (pc[i] - pc[i - 200]) / 200
            if op[i] <= sma200: continue
            r = [cl[j] / cl[j - 1] - 1 for j in range(i - 20, i)]; mu = sum(r) / 20
            sel.append((s, i, op[i] / cl[i - 1] - 1, (sum((x - mu) ** 2 for x in r) / 19) ** 0.5))
        out[d] = sel
    return out

def simulate(stocks, cands, cal, a, b, thr, cost, slots=10):
    rets = []; trades = 0; wins = 0
    for d in cal:
        if not (a <= d <= b): continue
        picks = sorted([x for x in cands.get(d, []) if x[2] <= -thr], key=lambda x: x[3])[:slots]
        r = 0.0
        for s, i, g, v in picks:
            ds, op, cl, vol = stocks[s]
            if i + 1 >= len(ds): continue
            x = op[i + 1] * (1 - cost) / (op[i] * (1 + cost)) - 1; r += x / slots; trades += 1; wins += x > 0
        rets.append((d, r))
    return rets, trades, wins

def stats(rets, trades, wins):
    eq, peak, dd = 1.0, 1.0, 0.0; yrs = defaultdict(lambda: 1.0)
    for d, r in rets: eq *= 1 + r; peak = max(peak, eq); dd = max(dd, (peak - eq) / peak); yrs[d[:4]] *= 1 + r
    xs = [r for _, r in rets]; n = len(xs); mu = sum(xs) / n if n else 0; sd = (sum((x - mu) ** 2 for x in xs) / max(1, n - 1)) ** 0.5
    return dict(days=n, trades=trades, win_pct=round(100 * wins / trades, 1) if trades else None, total_pct=round((eq - 1) * 100, 1),
                sharpe=round(mu / sd * 252 ** 0.5, 2) if sd else None, max_dd_pct=round(dd * 100, 1), by_year={y: round((v - 1) * 100, 1) for y, v in sorted(yrs.items())})

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    D = Data(key, sec); uni = universe(key, sec)
    s0 = datetime(2022, 6, 1, tzinfo=ET); s1 = datetime.now(ET) - timedelta(days=1)
    stocks = load_all(D, sorted(uni), s0, s1)
    spy = D.bars(['SPY'], '1Day', s0, s1, 'sip', 'all').get('SPY', []); cal = [x['t'][:10] for x in spy]
    spo = {x['t'][:10]: x['o'] for x in spy}
    cands = daily_candidates(stocks, cal); log('candidates built')
    out = {}; rows = ['| gap threshold | period | cost/side | trades | win rate | total | Sharpe | max drawdown | by year |', '|---|---|---|---|---|---|---|---|---|']
    for thr in THRESH:
        for per, (a, b) in PERIODS.items():
            for c in COSTS:
                S = stats(*simulate(stocks, cands, cal, a, b, thr, c)); out[f'{thr} | {per} | {c}'] = S
                rows.append(f"| {thr * 100:.0f}%{' (main)' if thr == 0.02 else ''} | {per} | {c * 100:.2f}% | {S['trades']} | {S['win_pct']}% | {S['total_pct']:+}% | {S['sharpe']} | {S['max_dd_pct']}% | "
                            f"{', '.join(f'{y}: {v:+}%' for y, v in S['by_year'].items())} |")
    for per, (a, b) in PERIODS.items():
        ds = [d for d in cal if a <= d <= b]; k = cal.index(ds[-1])
        bh = spo[cal[min(k + 1, len(cal) - 1)]] / spo[ds[0]] - 1; out[f'SPY | {per}'] = round(bh * 100, 1)
        rows.append(f"| SPY buy and hold | {per} | - | - | - | {bh * 100:+.1f}% | - | - | - |")
    md = ['# VANTEX City research: gap-down bounce in strong large stocks', '',
          'Buy at the open after a gap down (stock above its 200-day average), sell at the next open; up to 10 x 10%. '
          'The 1% and 3% rows are only a sensitivity check; 2% was fixed as the main setting before running.', ''] + rows + ['',
          'Universe = top 500 by 60-day dollar volume each day (S&P 500 stand-in). Official opening prices; real market-on-open fills can differ. A backtest is not proof.']
    publish({}); publish({'gapdown.json': out, 'gapdown.md': '\n'.join(md) + '\n'})

if __name__ == '__main__':
    main()
