"""
VANTEX City research: WEEKLY STOCK RANKER (machine learning, walk-forward). Research only: places NO orders.

Why (2026-11-19, after ~55 failed day-trading tests): day trades pay costs every day and the gap-up corner is crowded.
This follows the published machine-learning approach (Gu, Kelly & Xiu 2020): rank ALL liquid stocks every week by how likely
each is to beat the others over the next week, hold the best, trade once a week.
  universe   every Friday close (last session of each week): US stocks (active + delisted) with price >= $5 and
             20-day average dollar volume >= $20M
  inputs     ~20 per stock, all from data up to that close: returns over 1 week / 1 / 3 / 6 / 12-1 months, volatility,
             distance from 20-day and 52-week highs, volume surge, liquidity, price, biggest daily move (lottery),
             overnight vs. intraday return over 20 and 60 days, gap frequency, plus the market's own 1-month return
  target     the stock's percentile rank of next week's return (next open -> open after the next rebalance)
  model      gradient-boosted trees, fixed settings. WALK-FORWARD: for each year 2019-2026, train only on weeks that
             ended before that year (with a 1-week gap), then test on that year. Nothing is tuned on test years.
  portfolio  equal weight in the 20 best scores, rebalanced weekly at the next open; costs 0.05% per side on the
             traded part (and a 0.10% check).  Variant: cash when SPY closed below its 200-day average (Faber 2007 rule).
  compared   SPY buy and hold, equal weight in the whole universe, 20 random stocks a week, the 20 WORST scores.

  python city_ranker.py   -> live-replay/ranker.md / ranker.json / ranker_latest_picks.json
"""
import json, math, os, random, sys, time
from collections import defaultdict
from datetime import date, datetime, timedelta

import numpy as np

from city_engine import Data
from city_replay import ET, log, publish
from city_overnight import universe

TOP = 20
TEST_YEARS = list(range(2019, 2027))
COSTS = (0.0005, 0.0010)
FEATS = ['r5', 'r21', 'r63', 'r126', 'r252_21', 'vol21', 'vol63', 'hi20', 'hi252', 'vsurge', 'log_adv', 'log_px', 'maxr21',
         'on20', 'id20', 'on60', 'id60', 'gaps21', 'spy21', 'spy_vol21']

# ------------------------------------------------------------------ data
def load(D, syms, s0, s1):
    """{sym: (days list, o, h, l, c, v as float64 arrays)}"""
    out = {}; t0 = time.time()
    for k in range(0, len(syms), 100):
        for s, L in D.bars(syms[k:k + 100], '1Day', s0, s1, 'sip', 'all').items():
            if len(L) < 300: continue
            out[s] = ([x['t'][:10] for x in L],) + tuple(np.array([x[f] for x in L], dtype=np.float64) for f in 'ohlcv')
        if k % 1000 == 0: log(k, 'symbols', len(out), round(time.time() - t0), 's')
    return out

def roll_sum(x, n):
    c = np.concatenate([[0.0], np.cumsum(x)]); out = np.full(len(x), np.nan); out[n - 1:] = c[n:] - c[:-n]; return out

def roll_max(x, n):
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        w = np.lib.stride_tricks.sliding_window_view(x, n); out[n - 1:] = w.max(axis=1)
    return out

def features(S):
    """per-day feature arrays for one stock (index i uses data up to the close of day i only)"""
    ds, o, h, l, c, v = S
    n = len(c)
    with np.errstate(divide='ignore', invalid='ignore'):
        lc = np.log(np.where(c > 0, c, np.nan)); lo = np.log(np.where(o > 0, o, np.nan))
        r = np.concatenate([[np.nan], np.diff(lc)])                                   # close-to-close log return
        on = np.concatenate([[np.nan], lo[1:] - lc[:-1]])                              # overnight
        idr = lc - lo                                                                  # intraday
        def ret(k): x = np.full(n, np.nan); x[k:] = lc[k:] - lc[:-k]; return x
        dv = c * v
        f = dict(r5=ret(5), r21=ret(21), r63=ret(63), r126=ret(126),
                 vol21=np.sqrt(roll_sum(np.nan_to_num(r) ** 2, 21) / 21), vol63=np.sqrt(roll_sum(np.nan_to_num(r) ** 2, 63) / 63),
                 hi20=c / roll_max(h, 20) - 1, hi252=c / roll_max(h, 252) - 1,
                 vsurge=np.log(roll_sum(v, 5) / 5 / (roll_sum(v, 63) / 63)),
                 adv=roll_sum(dv, 20) / 20, log_px=np.log(np.where(c > 0, c, np.nan)),
                 maxr21=roll_max(np.nan_to_num(r, nan=0.0), 21),
                 on20=roll_sum(np.nan_to_num(on), 20), id20=roll_sum(np.nan_to_num(idr), 20),
                 on60=roll_sum(np.nan_to_num(on), 60), id60=roll_sum(np.nan_to_num(idr), 60),
                 gaps21=roll_sum((np.abs(np.nan_to_num(on)) > 0.02).astype(float), 21))
        f['r252_21'] = ret(252) - ret(21) if n > 252 else np.full(n, np.nan)        # 12-month return skipping the last month
        f['log_adv'] = np.log(f['adv'])
    return f

def week_ends(cal):
    """last trading day of each ISO week"""
    out = []
    for k, d in enumerate(cal):
        if k + 1 == len(cal) or date.fromisoformat(cal[k + 1]).isocalendar()[:2] != date.fromisoformat(d).isocalendar()[:2]: out.append(d)
    return out

def build_rows(stocks, cal, spy):
    """one row per (rebalance day, liquid stock): features + forward return next open -> open after the next rebalance"""
    wk = week_ends(cal); pos = {d: k for k, d in enumerate(cal)}
    spy_c = np.array([spy[d][1] for d in cal]); spy_lr = np.concatenate([[np.nan], np.diff(np.log(spy_c))])
    spy21 = {cal[k]: math.log(spy_c[k] / spy_c[k - 21]) for k in range(21, len(cal))}
    spyv = {cal[k]: float(np.sqrt(np.nanmean(spy_lr[k - 20:k + 1] ** 2))) for k in range(21, len(cal))}
    sma200 = {cal[k]: float(spy_c[k - 199:k + 1].mean()) for k in range(199, len(cal))}
    nxt = {wk[j]: wk[j + 1] for j in range(len(wk) - 1)}
    rows = defaultdict(list)
    for s, S in stocks.items():
        ds = S[0]; ix = {d: i for i, d in enumerate(ds)}; f = features(S)
        o, c = S[1], S[4]
        for d in wk:
            i = ix.get(d)
            if i is None or i < 260 or d not in nxt or d not in spy21: continue
            if c[i] < 5 or not (f['adv'][i] >= 20e6): continue
            x = [f[k][i] if k in f else None for k in FEATS[:-2]] + [spy21[d], spyv[d]]
            if any(v is None or not np.isfinite(v) for v in x): continue
            # forward: buy next session open, sell the open of the session after the next rebalance
            k_in = pos[d] + 1; k_out = pos[nxt[d]] + 1
            fwd = None
            if k_out < len(cal):
                a, b = cal[k_in], cal[k_out]
                if a in ix and b in ix and o[ix[a]] > 0: fwd = o[ix[b]] / o[ix[a]] - 1
                elif a in ix and o[ix[a]] > 0:                                  # stopped trading: last close before the exit
                    last = max((j for j in range(ix[a], len(ds)) if ds[j] < b), default=None)
                    if last is not None: fwd = c[last] / o[ix[a]] - 1
            rows[d].append(dict(sym=s, x=x, fwd=fwd))
    return rows, sma200, nxt, pos

def rank_target(L):
    """percentile rank of the forward return within the week (0..1)"""
    vals = sorted((r['fwd'], k) for k, r in enumerate(L) if r['fwd'] is not None)
    out = {}
    for j, (_, k) in enumerate(vals): out[k] = j / max(1, len(vals) - 1)
    return out

def portfolio(weeks, picks, cost):
    """weeks: sorted rebalance days; picks: day -> list of (sym, fwd). Equal weight, turnover-based costs."""
    prev = set(); eq = 1.0; peak = 1.0; dd = 0.0; rets = []
    for d in weeks:
        P = [(s, f) for s, f in picks.get(d, []) if f is not None]
        if not P: rets.append((d, -cost if prev else 0.0)); prev = set(); continue      # selling everything costs too
        cur = {s for s, _ in P}; w = 1.0 / len(P)
        traded = len(cur - prev) * w + len(prev - cur) * (1.0 / max(1, len(prev)))   # buys + sells as a share of the account
        r = sum(f for _, f in P) * w - traded * cost
        rets.append((d, r)); prev = cur
        eq *= 1 + r; peak = max(peak, eq); dd = max(dd, 1 - eq / peak)
    return rets

def stats(rets):
    if not rets: return dict(weeks=0)
    xs = np.array([r for _, r in rets]); eq = np.cumprod(1 + xs); peak = np.maximum.accumulate(eq)
    yrs = defaultdict(lambda: 1.0)
    for d, r in rets: yrs[d[:4]] *= 1 + r
    n_years = len(xs) / 52
    return dict(weeks=len(xs), total_pct=round(100 * (eq[-1] - 1), 1), cagr_pct=round(100 * (eq[-1] ** (1 / n_years) - 1), 1) if n_years > 0 else None,
                sharpe=round(xs.mean() / xs.std(ddof=1) * math.sqrt(52), 2) if xs.std() > 0 else None, max_dd_pct=round(100 * float((1 - eq / peak).max()), 1),
                win_weeks_pct=round(100 * float((xs > 0).mean()), 1), by_year={y: round(100 * (v - 1), 1) for y, v in sorted(yrs.items())})

def main():
    from sklearn.ensemble import HistGradientBoostingRegressor
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    D = Data(key, sec); uni = universe(key, sec)
    s0 = datetime(2015, 1, 1, tzinfo=ET); s1 = datetime.now(ET) - timedelta(minutes=20)
    sp = D.bars(['SPY'], '1Day', s0, s1, 'sip', 'all').get('SPY', [])
    cal = [x['t'][:10] for x in sp]; spy = {x['t'][:10]: (x['o'], x['c']) for x in sp}
    stocks = load(D, sorted(uni), s0, s1); log('stocks', len(stocks))
    rows, sma200, nxt, pos = build_rows(stocks, cal, spy); weeks = sorted(rows); log('weeks', len(weeks), 'rows', sum(len(v) for v in rows.values()))
    del stocks
    rng = random.Random(9); picks = defaultdict(dict); deciles = defaultdict(list); imp_all = {}
    for Y in TEST_YEARS:
        train_w = [d for d in weeks if d < f'{Y}-01-01'][:-1]                        # 1-week gap before the test year
        test_w = [d for d in weeks if d[:4] == str(Y)]
        if not test_w or len(train_w) < 100: continue
        Xtr, ytr = [], []
        for d in train_w:
            L = rows[d]; t = rank_target(L)
            for k, r in enumerate(L):
                if k in t: Xtr.append(r['x']); ytr.append(t[k])
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=500, l2_regularization=1.0, random_state=7)
        m.fit(np.array(Xtr), np.array(ytr)); log(Y, 'trained on', len(ytr))
        for d in test_w:
            L = rows[d]; sc = m.predict(np.array([r['x'] for r in L]))
            order = np.argsort(-sc); fl = lambda idx: [(L[k]['sym'], L[k]['fwd']) for k in idx]
            picks['model top 20'][d] = fl(order[:TOP]); picks['model worst 20'][d] = fl(order[-TOP:])
            picks['random 20'][d] = fl(rng.sample(range(len(L)), min(TOP, len(L))))
            picks['whole universe (equal weight)'][d] = fl(range(len(L)))
            picks['model top 20, cash when SPY < 200-day avg'][d] = fl(order[:TOP]) if spy[d][1] >= sma200.get(d, 0) else []
            valid = [(sc[k], L[k]['fwd']) for k in range(len(L)) if L[k]['fwd'] is not None]
            valid.sort()
            for q in range(10):
                part = valid[q * len(valid) // 10:(q + 1) * len(valid) // 10]
                if part: deciles[q].append(sum(f for _, f in part) / len(part))
    test_weeks = sorted(set(picks['model top 20']))
    res = {}; rows_md = ['| strategy | cost/side | weeks | total | per year | Sharpe | max drawdown | weeks up | by year |', '|---|---|---|---|---|---|---|---|---|']
    for name in ['model top 20', 'model top 20, cash when SPY < 200-day avg', 'random 20', 'whole universe (equal weight)', 'model worst 20']:
        for c in COSTS:
            S = stats(portfolio(test_weeks, picks[name], c)); res[f'{name} | {c}'] = S
            rows_md.append(f"| {name} | {c * 100:.2f}% | {S['weeks']} | {S['total_pct']:+}% | {S['cagr_pct']:+}% | {S['sharpe']} | {S['max_dd_pct']}% | {S['win_weeks_pct']}% | "
                           f"{', '.join(f'{y}: {v:+}%' for y, v in S['by_year'].items())} |")
    # SPY buy and hold over the same weeks (next open -> open after next rebalance)
    spy_r = []
    for d in test_weeks:
        k_in, k_out = pos[d] + 1, pos[nxt[d]] + 1
        if k_out < len(cal): spy_r.append((d, spy[cal[k_out]][0] / spy[cal[k_in]][0] - 1))
    S = stats(spy_r); res['SPY buy and hold'] = S
    rows_md.append(f"| SPY buy and hold | - | {S['weeks']} | {S['total_pct']:+}% | {S['cagr_pct']:+}% | {S['sharpe']} | {S['max_dd_pct']}% | {S['win_weeks_pct']}% | "
                   f"{', '.join(f'{y}: {v:+}%' for y, v in S['by_year'].items())} |")
    dec = ['| score decile (all test weeks) | avg weekly return |', '|---|---|'] + [f"| {q + 1}{' (best)' if q == 9 else ' (worst)' if q == 0 else ''} | {100 * sum(v) / len(v):+.3f}% |" for q, v in sorted(deciles.items())]
    latest = sorted(picks['model top 20'])[-1] if picks['model top 20'] else None
    md = ['# VANTEX City research: weekly machine-learning stock ranker (walk-forward)', '',
          f'Liquid US stocks ($5+, $20M+/day), ranked every Friday close; hold the top {TOP} for a week. Each year 2019-2026 is predicted by a model trained only on earlier years. '
          'Costs on the traded part only.', ''] + rows_md + ['', '## Does a better score mean a better week? (all test years)', ''] + dec + [
          '', 'Prices adjusted for splits and dividends. Delisted stocks included where Alpaca has their bars. Fills at the official open. A backtest is not proof.']
    publish({}); publish({'ranker.md': '\n'.join(md) + '\n', 'ranker.json': res,
                          'ranker_latest_picks.json': dict(week=latest, picks=[s for s, _ in picks['model top 20'].get(latest, [])])})
    log('done')

if __name__ == '__main__':
    main()
