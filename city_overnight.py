"""
VANTEX City research: Strategy A, OVERNIGHT BIAS. Research only: no orders, no live code.

Rules (fixed before testing, not tuned on 2026):
  universe   US common stocks, price >= $5 and trailing 20-session average dollar volume >= $20M, measured at each month-end
             with data available then. Delisted (inactive) symbols Alpaca still has bars for are included.
  signal     at each month-end, for every eligible stock with >= 220 of the prior 252 sessions:
               overnight r_on = log(open_t / close_t-1), daily r_d = log(close_t / close_t-1)
               OLS  r_on = a + b * r_d ; select when the intercept a > 0 with one-sided t >= 1.645 (5%)
  trading    the selection is known after the month-end close, so it trades from the NEXT session's close:
             each session buy at the close, sell at the next open; equal weight, each capped at 5% (cash otherwise).
  costs      0.05% / 0.25% / 0.50% per side, every night (two sides per night), plus SEC/FINRA fees on sales.
  placebo    the same number of stocks picked at random from the eligible list each month (fixed seed).
Data limits (reported in the output): Alpaca only knows stocks that existed recently (inactive list is partial), adjusted
prices are today's adjustments, and there is no point-in-time index membership.

  python city_overnight.py dev   -> Jun 2023 - Dec 2025   -> live-replay/overnight_dev.md / .json / .csv
  python city_overnight.py test  -> 2026 (out of sample)
"""
import csv, io, json, math, os, random, re, sys, time
from collections import defaultdict
from datetime import date, datetime, timedelta

import requests

import vantex_core as V
from city_engine import Data, NAME_EXCLUDE
from city_replay import ET, TRADE, log, publish

SPLITS = {'dev': (date(2023, 6, 1), date(2025, 12, 31)), 'test': (date(2026, 1, 1), None)}
COSTS = (0.0005, 0.0025, 0.0050)
LOOKBACK, MIN_OBS, TCRIT, CAP = 252, 220, 1.645, 0.05

def universe(key, sec):
    """active + inactive US common stocks on the main exchanges (names that look like funds, warrants, units, preferreds removed)"""
    h = {'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': sec}; out = {}
    for status in ('active', 'inactive'):
        r = requests.get(f'{TRADE}/v2/assets', headers=h, params=dict(status=status, asset_class='us_equity'), timeout=90)
        for x in (r.json() if r.ok else []):
            if x.get('exchange') in ('NASDAQ', 'NYSE', 'AMEX') and x['symbol'].isalpha() and not any(re.search(rx, (x.get('name') or '').lower()) for _, rx in NAME_EXCLUDE):
                out[x['symbol']] = status
    return out

def load_all(D, syms, s0, s1, log_every=1000):
    """{sym: (days, open, close, volume)} from daily bars adjusted for splits and dividends"""
    stocks = {}; t0 = time.time()
    for k in range(0, len(syms), 100):
        for s, L in D.bars(syms[k:k + 100], '1Day', s0, s1, 'sip', 'all').items():
            if len(L) >= 60: stocks[s] = ([x['t'][:10] for x in L], [x['o'] for x in L], [x['c'] for x in L], [x['v'] for x in L])
        if k % log_every == 0: log(k, 'symbols loaded', len(stocks), round(time.time() - t0), 's')
    return stocks

def month_ends(days):
    return [d for k, d in enumerate(days) if k + 1 == len(days) or d[:7] != days[k + 1][:7]]

def eligible(S, i):
    ds, op, cl, vol = S
    if i < 20 or cl[i] < 5: return False
    return sum(cl[j] * vol[j] for j in range(i - 19, i + 1)) / 20 >= 20e6

def overnight_t(S, i):
    """one-sided t-stat of the intercept of r_on on r_d over the 252 sessions ending at i (None if too little data)"""
    ds, op, cl, vol = S
    xs, ys = [], []
    for j in range(max(1, i - LOOKBACK + 1), i + 1):
        if cl[j - 1] > 0 and op[j] > 0 and cl[j] > 0:
            ys.append(math.log(op[j] / cl[j - 1])); xs.append(math.log(cl[j] / cl[j - 1]))
    n = len(xs)
    if n < MIN_OBS: return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0: return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx; a = my - b * mx
    s2 = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys)) / (n - 2)
    se_a = math.sqrt(s2 * (1 / n + mx * mx / sxx))
    return a / se_a if se_a > 0 else None

def index(stocks): return {s: {d: i for i, d in enumerate(S[0])} for s, S in stocks.items()}

def selections(stocks, idx, cal, start, end, rng):
    """month -> (selected symbols, random placebo of the same size, number eligible)"""
    out = {}
    for me in month_ends(cal):
        if me < (date.fromisoformat(start) - timedelta(days=35)).isoformat() or me > end: continue
        elig, sel = [], []
        for s, S in stocks.items():
            i = idx[s].get(me)
            if i is None or not eligible(S, i): continue
            elig.append(s); t = overnight_t(S, i)
            if t is not None and t >= TCRIT: sel.append(s)
        out[me] = (sorted(sel), sorted(rng.sample(elig, min(len(sel), len(elig)))), len(elig))
    return out

def run_nights(stocks, idx, cal, sel, start, end, which, cost, trades=None):
    """daily equity curve: buy at the close of session t, sell at the open of t+1, only on sessions after the selection is known"""
    mes = sorted(sel); rets = []; expo = []
    for k in range(len(cal) - 1):
        d, nxt = cal[k], cal[k + 1]
        if d < start or d > end: continue
        prior = [m for m in mes if m < d]                                    # selection made at a month-end strictly before today
        if not prior: rets.append((d, 0.0)); expo.append(0.0); continue
        names = sel[prior[-1]][which]
        legs = []
        for s in names:
            i = idx[s].get(d); j = idx[s].get(nxt)
            if i is None or j is None or j != i + 1: continue                 # no next-session open (halt, delisting): skipped, not assumed
            S = stocks[s]; buy = S[2][i] * (1 + cost); sell = S[1][j] * (1 - cost)
            legs.append((s, buy, sell, sell / buy - 1))
        if not legs: rets.append((d, 0.0)); expo.append(0.0); continue
        w = min(CAP, 1.0 / len(legs)); e = w * len(legs)
        r = sum(w * x[3] for x in legs) - sum(w * 0.0000278 for _ in legs)   # sale fees (SEC + TAF) approximated as a small % of proceeds
        rets.append((d, r)); expo.append(e)
        if trades is not None:
            for s, b, sl, rr in legs: trades.append((d, nxt, s, round(b, 4), round(sl, 4), round(rr * 100, 4), round(w, 4)))
    return rets, expo

def curve_stats(rets, expo, spy_rets, per_year=252):
    if not rets: return dict(days=0)
    eq, peak, dd = 1.0, 1.0, 0.0; years = defaultdict(lambda: 1.0)
    for d, r in rets: eq *= 1 + r; peak = max(peak, eq); dd = max(dd, (peak - eq) / peak * 100); years[d[:4]] *= 1 + r
    xs = [r for _, r in rets]; mu = sum(xs) / len(xs); sd = (sum((x - mu) ** 2 for x in xs) / max(1, len(xs) - 1)) ** 0.5
    sp = dict(spy_rets); pairs = [(sp[d], r) for d, r in rets if d in sp]
    beta = None
    if len(pairs) > 20:
        ma = sum(p[0] for p in pairs) / len(pairs); mb = sum(p[1] for p in pairs) / len(pairs)
        va = sum((p[0] - ma) ** 2 for p in pairs); beta = round(sum((p[0] - ma) * (p[1] - mb) for p in pairs) / va, 3) if va else None
    return dict(days=len(xs), total_return_pct=round((eq - 1) * 100, 1), sharpe=round(mu / sd * per_year ** 0.5, 2) if sd else None,
                max_drawdown_pct=round(dd, 1), beta_vs_spy=beta, avg_exposure_pct=round(100 * sum(expo) / len(expo), 1) if expo else None,
                by_year={y: round((v - 1) * 100, 1) for y, v in sorted(years.items())})

def spy_daily(D, s0, s1, start, end):
    L = D.bars(['SPY'], '1Day', s0, s1, 'sip', 'all').get('SPY', [])
    ds = [x['t'][:10] for x in L]; cl = [x['c'] for x in L]
    return ds, [(ds[k], cl[k] / cl[k - 1] - 1) for k in range(1, len(L)) if start <= ds[k] <= end]

def without_top(trades_rows, n=10):
    """total of nightly trade returns (%) with the n best removed: a diagnostic, not a portfolio result"""
    r = sorted((t[5] for t in trades_rows), reverse=True)
    return round(sum(r[n:]) / max(1, len(r) - n), 4) if r else None

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    split = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else 'dev'
    a, b = SPLITS[split]; b = b or (date.today() - timedelta(days=7)); start, end = a.isoformat(), b.isoformat()
    D = Data(key, sec); uni = universe(key, sec)
    s0 = datetime.combine(a - timedelta(days=430), datetime.min.time(), ET)
    s1 = min(datetime.combine(b + timedelta(days=10), datetime.min.time(), ET), datetime.now(ET) - timedelta(days=1))
    stocks = load_all(D, sorted(uni), s0, s1)
    cal, spy = spy_daily(D, s0, s1, start, end)
    idx = index(stocks); sel = selections(stocks, idx, cal, start, end, random.Random(7))
    res = {}; csv_rows = []
    for which, label in ((0, 'signal'), (1, 'placebo')):
        for c in COSTS:
            rows = [] if (which == 0 and c == COSTS[0]) else None
            rets, expo = run_nights(stocks, idx, cal, sel, start, end, which, c, rows)
            res[f'{label}@{c * 100:.2f}%'] = curve_stats(rets, expo, spy)
            if rows is not None: csv_rows = rows
    gross, _ = run_nights(stocks, idx, cal, sel, start, end, 0, 0.0)
    res['signal@gross'] = curve_stats(gross, [1] * len(gross), spy)
    sel_sizes = [len(v[0]) for v in sel.values()]; elig = [v[2] for v in sel.values()]
    spy_stats = curve_stats(spy, [1.0] * len(spy), spy)
    limits = ['Point-in-time universe: Alpaca active + inactive symbols only; stocks delisted long ago or renamed may be missing (survivorship risk).',
              'Prices are adjusted with today\'s split/dividend factors, not as-traded; overnight returns over dividend dates are approximated.',
              f"Inactive (delisted) symbols in the universe: {sum(1 for v in uni.values() if v == 'inactive')} of {len(uni)}.",
              'Fills assume the official close and next official open (auction prices); real market-on-close / market-on-open fills can differ.']
    out = dict(strategy='A overnight bias', split=split, period=[start, end], results=res, spy=spy_stats,
               selection=dict(months=len(sel), avg_selected=round(sum(sel_sizes) / max(1, len(sel_sizes)), 1), avg_eligible=round(sum(elig) / max(1, len(elig)), 1),
                              last=list(sel.items())[-1][1][0][:30] if sel else []),
               trades=len(csv_rows), avg_trade_pct_without_top10=without_top(csv_rows), data_limits=limits, updated=datetime.now(ET).isoformat(timespec='seconds'))
    rows = ['| run | days | total return | Sharpe | max drawdown | beta vs SPY | avg invested | by year |', '|---|---|---|---|---|---|---|---|']
    for k, v in list(res.items()) + [('SPY buy and hold', spy_stats)]:
        if not v.get('days'): continue
        rows.append(f"| {k} | {v['days']} | {v['total_return_pct']:+}% | {v['sharpe']} | {v['max_drawdown_pct']}% | {v['beta_vs_spy']} | {v['avg_exposure_pct']}% | "
                    f"{', '.join(f'{y}: {x:+}%' for y, x in v['by_year'].items())} |")
    md = [f"# Strategy A - overnight bias - {split} - {start} to {end}", '',
          f"Each month about {out['selection']['avg_selected']} of {out['selection']['avg_eligible']} eligible stocks passed the overnight-bias test. "
          f"Trades: buy at the close, sell at the next open, every session. {len(csv_rows)} stock-nights at the lowest cost.", ''] + rows + ['',
          f"Average stock-night return with the 10 best removed (0.05% cost): {out['avg_trade_pct_without_top10']}%.",
          'Placebo = same number of random eligible stocks each month. A real signal should clearly beat its placebo at the same cost.', '',
          '## Data limits', ''] + [f'- {x}' for x in limits]
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(['buy_day', 'sell_day', 'symbol', 'buy_at_close', 'sell_at_open', 'return_pct', 'weight']); w.writerows(csv_rows)
    publish({})
    publish({f'overnight_{split}.json': out, f'overnight_{split}.md': '\n'.join(md) + '\n', f'overnight_{split}_trades.csv': buf.getvalue()})

if __name__ == '__main__':
    main()
