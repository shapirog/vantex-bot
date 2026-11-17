"""
VANTEX City research: Strategy B, ONE-MONTH MOMENTUM CONDITIONAL ON TURNOVER. Research only: no orders, no live code.

Rules (fixed before testing, long side only):
  universe   price >= $5 and trailing 20-session average dollar volume >= $20M at the month-end (same as Strategy A),
             active + inactive (delisted) symbols Alpaca still has bars for.
  rank       at each month-end: the completed month's return, and the month's TURNOVER.
             Keep the top turnover quintile, then buy the top return quintile inside it.
  trade      buy at the next session's open, hold until the open of the first session after the next month-end; monthly.
  weights    equal, each capped at 5% (cash for the rest).
  costs      0.05% / 0.25% / 0.50% per side, plus fees. Placebo: same number of random eligible stocks each month.

DATA SUBSTITUTION (flagged in every report): the published signal uses shares traded / shares outstanding. Alpaca has no
point-in-time shares-outstanding history, so turnover here is RELATIVE turnover = this month's share volume / the stock's
average monthly share volume over the prior 12 months. That ranks unusual trading activity, which is close to but not the
same as the paper's measure. Treat any result as a test of the proxy, not of the published signal.

  python city_turnover_mom.py dev   -> Jun 2023 - Dec 2025  -> live-replay/turnover_mom_dev.md / .json / .csv
  python city_turnover_mom.py test  -> 2026 (out of sample)
"""
import csv, io, json, math, os, random, sys
from collections import defaultdict
from datetime import date, datetime, timedelta

from city_engine import Data
from city_replay import ET, log, publish
from city_overnight import SPLITS, COSTS, CAP, universe, load_all, month_ends, eligible, index, spy_daily, without_top

def month_slices(ds):
    """month -> (first index, last index) inside one stock's history"""
    out = {}
    for i, d in enumerate(ds):
        m = d[:7]
        if m not in out: out[m] = [i, i]
        else: out[m][1] = i
    return out

def picks_for(stocks, idx, cal, start, end, rng):
    """month-end -> (picks, placebo picks, eligible count). Uses only data up to and including that month-end close."""
    mes = [m for m in month_ends(cal) if (date.fromisoformat(start) - timedelta(days=35)).isoformat() <= m <= end]
    sl = {s: month_slices(S[0]) for s, S in stocks.items()}
    out = {}
    for me in mes:
        rows = []
        for s, S in stocks.items():
            i = idx[s].get(me)
            if i is None or not eligible(S, i): continue
            months = sorted(m for m in sl[s] if m <= me[:7])
            if len(months) < 14 or months[-1] != me[:7]: continue
            a, b_ = sl[s][months[-1]]; pa, pb = sl[s][months[-2]]
            ret = S[2][b_] / S[2][pb] - 1                                  # completed month: last close vs prior month's last close
            vol_m = sum(S[3][a:b_ + 1])
            prior = [sum(S[3][x:y + 1]) for x, y in (sl[s][m] for m in months[-13:-1])]
            base = sum(prior) / len(prior) if prior else 0
            if base <= 0: continue
            rows.append((s, ret, vol_m / base))
        if len(rows) < 25: out[me] = ([], [], len(rows)); continue
        rows.sort(key=lambda r: -r[2]); hi_turn = rows[:max(1, len(rows) // 5)]
        hi_turn.sort(key=lambda r: -r[1]); picks = [r[0] for r in hi_turn[:max(1, len(hi_turn) // 5)]]
        out[me] = (picks, rng.sample([r[0] for r in rows], len(picks)), len(rows))
    return out

def run_months(stocks, idx, cal, picks, start, end, which, cost, trades=None):
    """period returns from the open after month-end m to the open after month-end m+1"""
    pos = {d: k for k, d in enumerate(cal)}; mes = sorted(picks); out = []; expo = []
    for k in range(len(mes) - 1):
        me, nme = mes[k], mes[k + 1]
        if pos.get(me) is None or pos.get(nme) is None or pos[me] + 1 >= len(cal) or pos[nme] + 1 >= len(cal): continue
        d_in, d_out = cal[pos[me] + 1], cal[pos[nme] + 1]
        if d_in < start or d_in > end: continue
        legs = []
        for s in picks[me][which]:
            i, j = idx[s].get(d_in), idx[s].get(d_out)
            S = stocks[s]
            if i is None: continue
            if j is None:                                                   # delisted or halted before the exit: last available close, flagged
                last = max((x for x in idx[s] if x < d_out), default=None)
                if last is None or last < d_in: continue
                j_ = idx[s][last]; px_out = S[2][j_]; note = 'exit at last available close'
            else: px_out = S[1][j]; note = ''
            buy = S[1][i] * (1 + cost); sell = px_out * (1 - cost); legs.append((s, buy, sell, sell / buy - 1, note))
        if not legs: out.append((d_in, 0.0)); expo.append(0.0); continue
        w = min(CAP, 1.0 / len(legs)); r = sum(w * x[3] for x in legs); out.append((d_in, r)); expo.append(w * len(legs))
        if trades is not None:
            for s, b, sl_, rr, note in legs: trades.append((d_in, d_out, s, round(b, 4), round(sl_, 4), round(rr * 100, 3), round(w, 4), note))
    return out, expo

def stats(rets, expo, spy_month):
    if not rets: return dict(months=0)
    eq, peak, dd = 1.0, 1.0, 0.0; years = defaultdict(lambda: 1.0)
    for d, r in rets: eq *= 1 + r; peak = max(peak, eq); dd = max(dd, (peak - eq) / peak * 100); years[d[:4]] *= 1 + r
    xs = [r for _, r in rets]; mu = sum(xs) / len(xs); sd = (sum((x - mu) ** 2 for x in xs) / max(1, len(xs) - 1)) ** 0.5
    pairs = [(spy_month[d], r) for d, r in rets if d in spy_month]; beta = None
    if len(pairs) > 5:
        ma = sum(p[0] for p in pairs) / len(pairs); mb = sum(p[1] for p in pairs) / len(pairs); va = sum((p[0] - ma) ** 2 for p in pairs)
        beta = round(sum((p[0] - ma) * (p[1] - mb) for p in pairs) / va, 3) if va else None
    return dict(months=len(xs), total_return_pct=round((eq - 1) * 100, 1), sharpe=round(mu / sd * 12 ** 0.5, 2) if sd else None,
                max_drawdown_pct=round(dd, 1), beta_vs_spy=beta, avg_exposure_pct=round(100 * sum(expo) / len(expo), 1),
                by_year={y: round((v - 1) * 100, 1) for y, v in sorted(years.items())})

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    split = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else 'dev'
    a, b = SPLITS[split]; b = b or (date.today() - timedelta(days=7)); start, end = a.isoformat(), b.isoformat()
    D = Data(key, sec); uni = universe(key, sec)
    s0 = datetime.combine(a - timedelta(days=430), datetime.min.time(), ET)
    s1 = min(datetime.combine(b + timedelta(days=45), datetime.min.time(), ET), datetime.now(ET) - timedelta(days=1))
    stocks = load_all(D, sorted(uni), s0, s1); idx = index(stocks)
    L = D.bars(['SPY'], '1Day', s0, s1, 'sip', 'all').get('SPY', [])
    cal = [x['t'][:10] for x in L]; spy_op = {x['t'][:10]: x['o'] for x in L}
    picks = picks_for(stocks, idx, cal, start, end, random.Random(11))
    mes = sorted(picks); pos = {d: k for k, d in enumerate(cal)}; spy_month = {}
    for k in range(len(mes) - 1):
        if pos[mes[k]] + 1 < len(cal) and pos[mes[k + 1]] + 1 < len(cal):
            d_in, d_out = cal[pos[mes[k]] + 1], cal[pos[mes[k + 1]] + 1]
            if start <= d_in <= end: spy_month[d_in] = spy_op[d_out] / spy_op[d_in] - 1
    res = {}; csv_rows = []
    for which, label in ((0, 'signal'), (1, 'placebo')):
        for c in COSTS:
            rows = [] if (which == 0 and c == COSTS[0]) else None
            r, e = run_months(stocks, idx, cal, picks, start, end, which, c, rows)
            res[f'{label}@{c * 100:.2f}%'] = stats(r, e, spy_month)
            if rows is not None: csv_rows = rows
    g, e = run_months(stocks, idx, cal, picks, start, end, 0, 0.0); res['signal@gross'] = stats(g, e, spy_month)
    spy_stats = stats(sorted(spy_month.items()), [1.0] * len(spy_month), spy_month)
    sizes = [len(v[0]) for v in picks.values()]
    limits = ['SUBSTITUTION: turnover = this month\'s volume / average monthly volume over the prior 12 months (no shares-outstanding history). Not the paper\'s measure.',
              'Point-in-time universe: Alpaca active + inactive symbols only; older delistings may be missing (survivorship risk).',
              'Prices adjusted with today\'s split/dividend factors. Delisted positions exit at the last available close (flagged in the CSV).']
    out = dict(strategy='B one-month momentum x turnover (proxy)', split=split, period=[start, end], results=res, spy=spy_stats,
               avg_picks=round(sum(sizes) / max(1, len(sizes)), 1), trades=len(csv_rows), avg_trade_pct_without_top10=without_top([(0, 0, 0, 0, 0, r[5]) for r in csv_rows]),
               data_limits=limits, last_picks=list(picks.items())[-1][1][0] if picks else [], updated=datetime.now(ET).isoformat(timespec='seconds'))
    rows = ['| run | months | total return | Sharpe | max drawdown | beta vs SPY | avg invested | by year |', '|---|---|---|---|---|---|---|---|']
    for k, v in list(res.items()) + [('SPY buy and hold (same open-to-open months)', spy_stats)]:
        if not v.get('months'): continue
        rows.append(f"| {k} | {v['months']} | {v['total_return_pct']:+}% | {v['sharpe']} | {v['max_drawdown_pct']}% | {v['beta_vs_spy']} | {v['avg_exposure_pct']}% | "
                    f"{', '.join(f'{y}: {x:+}%' for y, x in v['by_year'].items())} |")
    md = [f"# Strategy B - one-month momentum x turnover (proxy) - {split} - {start} to {end}", '',
          f"About {out['avg_picks']} stocks held each month; {len(csv_rows)} stock-months at the lowest cost.", ''] + rows + ['',
          f"Average stock-month return with the 10 best removed (0.05% cost): {out['avg_trade_pct_without_top10']}%.",
          'Placebo = same number of random eligible stocks each month.', '', '## Data limits', ''] + [f'- {x}' for x in limits]
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(['buy_day', 'sell_day', 'symbol', 'buy_open', 'sell', 'return_pct', 'weight', 'note']); w.writerows(csv_rows)
    publish({})
    publish({f'turnover_mom_{split}.json': out, f'turnover_mom_{split}.md': '\n'.join(md) + '\n', f'turnover_mom_{split}_trades.csv': buf.getvalue()})

if __name__ == '__main__':
    main()
