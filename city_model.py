"""
VANTEX City research: OUR OWN MODEL ("Vantex Score"). Research only: places NO orders.

Idea (Guillo, 2026-11-17): build our own system with today's tools instead of copying old setups.
Every morning, every US stock (penny included) that OPENS at least 2% above yesterday's close is a candidate. A
machine-learning model (gradient-boosted trees) scores each candidate using only what is known at 9:30:
  the gap, the gap measured in the stock's own daily volatility, price, liquidity, yesterday's move / volume / close
  location, 5- and 20-day trend, distance from the 20-day high, how SPY opened, how many stocks are gapping up today, weekday.
It learns what the stock did from the open to the close (day trade). Each day the system buys the TOP 5 scores at the open.
Exits tested: hold to the close, and a 7% stop / 15% take-profit (stop first if both are touched in one day).
Honest test:
  learn     Jun 2023 - Jun 2025     (the model only ever sees these days)
  check     Jul 2025 - Dec 2025     (one look, used only to confirm it is not broken; nothing is tuned on it)
  TEST      Jan 2026 - now          (never seen; this is the number that counts)
Settings were fixed before the first run. Comparisons: all candidates, 5 random candidates per day, and the 5 LOWEST scores.
If the scores mean something, higher score buckets must earn more in the test period (the decile table).
Costs by liquidity per side (0.05%-0.5%, +1% under $1), and a 2x-cost check.

  python city_model.py   -> live-replay/model.md / .json / model_test_picks.csv
"""
import csv, io, json, math, os, random, sys, time
from collections import defaultdict
from datetime import datetime, timedelta

from city_engine import Data
from city_replay import ET, log, publish
from city_overnight import universe
from city_news_study import load_ohlcv, hold, cost, net

LEARN = ('2023-06-01', '2025-06-30'); CHECK = ('2025-07-01', '2025-12-31'); TEST = ('2026-01-01', '2099-12-31')
MIN_GAP, MIN_PX, MIN_ADV, TOP = 0.02, 1.0, 1e6, 5
FEATS = ['gap', 'gap_sigma', 'log_px', 'log_adv', 'r1', 'r5', 'r20', 'from_high20', 'rvol_prev', 'rng_prev', 'vol20',
         'spy_gap', 'breadth', 'weekday']

def row_feats(S, i):
    """features for day i known at the open (yesterday's data + today's open). None if not a candidate."""
    if i < 25: return None
    o, h, l, c, v = S['o'], S['h'], S['l'], S['c'], S['v']
    pc = c[i - 1]
    if o[i] <= 0 or min(c[i - 21:i]) <= 0 or min(h[i - 20:i]) <= 0: return None   # bad / zero bars
    gap = o[i] / pc - 1
    if gap < MIN_GAP or pc < MIN_PX: return None
    adv = sum(c[j] * v[j] for j in range(i - 20, i)) / 20
    if adv < MIN_ADV: return None
    rets = [c[j] / c[j - 1] - 1 for j in range(i - 20, i) if c[j - 1] > 0]
    mu = sum(rets) / len(rets); vol = (sum((x - mu) ** 2 for x in rets) / max(1, len(rets) - 1)) ** 0.5
    avgv = sum(v[i - 21:i - 1]) / 20
    return dict(gap=gap, gap_sigma=gap / vol if vol > 0 else 0.0, log_px=math.log(pc), log_adv=math.log(adv),
                r1=pc / c[i - 2] - 1, r5=pc / c[i - 6] - 1, r20=pc / c[i - 21] - 1, from_high20=pc / max(h[i - 20:i]) - 1,
                rvol_prev=v[i - 1] / avgv if avgv > 0 else 1.0, rng_prev=(pc - l[i - 1]) / (h[i - 1] - l[i - 1]) if h[i - 1] > l[i - 1] else 0.5,
                vol20=vol, adv=adv, px=pc)

def build(stocks, spy):
    """list of rows: dict(day, sym, i, feats..., y = open->close gross)"""
    rows = []; per_day = defaultdict(int)
    for s, S in stocks.items():
        for i in range(25, len(S['d'])):
            f = row_feats(S, i)
            if f is None: continue
            d = S['d'][i]; per_day[d] += 1
            rows.append(dict(f, day=d, sym=s, i=i, y=S['c'][i] / S['o'][i] - 1))
    for r in rows:
        r['spy_gap'] = spy.get(r['day'], 0.0); r['breadth'] = math.log(1 + per_day[r['day']])
        r['weekday'] = datetime.fromisoformat(r['day']).weekday()
    return rows

def split_of(d):
    if LEARN[0] <= d <= LEARN[1]: return 'learn'
    if CHECK[0] <= d <= CHECK[1]: return 'check'
    if d >= TEST[0]: return 'test'
    return None

def daily_picks(rows, score_key, how, rng=None):
    by = defaultdict(list)
    for r in rows: by[r['day']].append(r)
    out = []
    for d, L in sorted(by.items()):
        if how == 'top': out += sorted(L, key=lambda r: -r[score_key])[:TOP]
        elif how == 'bottom': out += sorted(L, key=lambda r: r[score_key])[:TOP]
        elif how == 'random': out += rng.sample(L, min(TOP, len(L)))
        else: out += L
    return out

def evaluate(picks, stocks, last_cal, stop_target=False):
    rs, rs2 = [], []
    for r in picks:
        S = stocks[r['sym']]; i = r['i']; c = cost(r['adv'], r['px'])
        if stop_target:
            x = hold(S, i, 1, stop=S['o'][i] * 0.93, target=S['o'][i] * 1.15, last_cal=last_cal)
            if x is None: continue
            px = x[0]
        else: px = S['c'][i]
        rs.append(net(S['o'][i], px, c)); rs2.append(net(S['o'][i], px, 2 * c))
    return summary(rs, rs2, picks)

def summary(rs, rs2, picks):
    if not rs: return dict(n=0)
    n = len(rs); mu = sum(rs) / n; sd = (sum((x - mu) ** 2 for x in rs) / max(1, n - 1)) ** 0.5
    srt = sorted(rs); wo = srt[:-10] if n > 20 else srt
    days = len({p['day'] for p in picks})
    return dict(trades=n, days=days, win_pct=round(100 * sum(x > 0 for x in rs) / n, 1), avg_pct=round(100 * mu, 3),
                median_pct=round(100 * srt[n // 2], 3), avg_without_best10_pct=round(100 * sum(wo) / len(wo), 3),
                t=round(mu / (sd / n ** 0.5), 2) if sd else None, avg_2x_cost_pct=round(100 * sum(rs2) / n, 3))

def portfolio_curve(picks, stocks):
    """equal 1/TOP of the account in each pick, each day; returns total % and max drawdown %"""
    by = defaultdict(list)
    for r in picks:
        S = stocks[r['sym']]; i = r['i']; by[r['day']].append(net(S['o'][i], S['c'][i], cost(r['adv'], r['px'])))
    eq, peak, dd = 1.0, 1.0, 0.0
    for d in sorted(by): eq *= 1 + sum(by[d]) / TOP; peak = max(peak, eq); dd = max(dd, 1 - eq / peak)
    return round((eq - 1) * 100, 1), round(dd * 100, 1)

def main():
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingRegressor
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    D = Data(key, sec); uni = universe(key, sec)
    s0 = datetime(2023, 3, 1, tzinfo=ET); s1 = datetime.now(ET) - timedelta(minutes=20)
    sp = D.bars(['SPY'], '1Day', s0, s1, 'sip', 'all').get('SPY', [])
    spy = {sp[k]['t'][:10]: sp[k]['o'] / sp[k - 1]['c'] - 1 for k in range(1, len(sp))}; last_cal = sp[-1]['t'][:10]
    stocks = load_ohlcv(D, sorted(uni), s0, s1); log('stocks', len(stocks))
    rows = [r for r in build(stocks, spy) if split_of(r['day'])]; log('candidate stock-days', len(rows))
    for r in rows: r['split'] = split_of(r['day'])
    X = lambda L: np.array([[r[k] for k in FEATS] for r in L], dtype=float)
    learn = [r for r in rows if r['split'] == 'learn']
    y = np.clip(np.array([r['y'] for r in learn]), -0.5, 0.5)                 # clip: a few +300% penny days must not drive the fit
    m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200, l2_regularization=1.0, random_state=7)
    m.fit(X(learn), y)
    pred = m.predict(X(rows))
    for r, p in zip(rows, pred): r['score'] = float(p)
    rng = random.Random(11); res = {}; md_rows = ['| period | picks | trades | win rate | avg net | median | avg w/o best 10 | t-stat | avg at 2x costs | account (5 x 20%) | max drawdown |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for sp_ in ('learn', 'check', 'test'):
        R = [r for r in rows if r['split'] == sp_]
        for how in ('top', 'top + 7% stop / 15% target', 'random', 'bottom', 'all'):
            base = 'top' if how.startswith('top') else how
            P = daily_picks(R, 'score', base, rng)
            S = evaluate(P, stocks, last_cal, stop_target='stop' in how)
            tot, dd = portfolio_curve(P, stocks) if base != 'all' and 'stop' not in how else (None, None)
            res[f'{sp_} | {how}'] = dict(S, account_total_pct=tot, max_dd_pct=dd)
            if S.get('trades'):
                md_rows.append(f"| {sp_} | {how} | {S['trades']} | {S['win_pct']}% | {S['avg_pct']}% | {S['median_pct']}% | {S['avg_without_best10_pct']}% | {S['t']} | {S['avg_2x_cost_pct']}% | "
                               f"{'' if tot is None else f'{tot:+}%'} | {'' if dd is None else f'{dd}%'} |")
    # decile table on the test period: does a higher score really mean a better day?
    T = sorted([r for r in rows if r['split'] == 'test'], key=lambda r: r['score']); dec = ['| score decile (test) | stock-days | avg open->close (gross) | up % |', '|---|---|---|---|']
    for k in range(10):
        L = T[k * len(T) // 10:(k + 1) * len(T) // 10]
        if L: dec.append(f"| {k + 1}{' (highest)' if k == 9 else ' (lowest)' if k == 0 else ''} | {len(L)} | {100 * sum(r['y'] for r in L) / len(L):+.3f}% | {100 * sum(r['y'] > 0 for r in L) / len(L):.1f}% |")
    # which inputs matter (permutation importance on the check period, small sample to keep it fast)
    imp = {}
    try:
        from sklearn.inspection import permutation_importance
        C = [r for r in rows if r['split'] == 'check']; C = random.Random(3).sample(C, min(20000, len(C)))
        pi = permutation_importance(m, X(C), np.clip(np.array([r['y'] for r in C]), -0.5, 0.5), n_repeats=3, random_state=0)
        imp = {k: round(float(v) * 1e4, 2) for k, v in sorted(zip(FEATS, pi.importances_mean), key=lambda x: -x[1])}
    except Exception as e: log('importance failed', e)
    tp = daily_picks([r for r in rows if r['split'] == 'test'], 'score', 'top')
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(['day', 'sym', 'score_pct', 'gap_pct', 'prev_close', 'open', 'close', 'open_to_close_pct'])
    for r in tp:
        S = stocks[r['sym']]; w.writerow([r['day'], r['sym'], round(100 * r['score'], 3), round(100 * r['gap'], 2), r['px'], S['o'][r['i']], S['c'][r['i']], round(100 * r['y'], 2)])
    md = ['# VANTEX City research: our own model (Vantex Score)', '',
          f'Candidates: every stock opening 2%+ above yesterday\'s close (price $1+, $1M+ daily dollar volume). {len(rows)} candidate stock-days. '
          'Model learns only Jun 2023 - Jun 2025. Each day it buys the top 5 scores at the open and sells at the close. Costs included.', ''] + md_rows + [
          '', '"random" = 5 random candidates per day; "bottom" = the 5 lowest scores; "all" = every candidate.', '', '## Does a higher score mean a better day? (2026, never seen)', ''] + dec + [
          '', '## What the model leans on (higher = more important, check period)', '', ', '.join(f'{k} {v}' for k, v in imp.items()), '',
          'Daily bars: the official open is used as the fill; a real order at 9:30 on a small stock can fill worse. Stop/target order inside a day is unknown (stop assumed first). A backtest is not proof.']
    publish({}); publish({'model.json': dict(results=res, importance=imp, rows=len(rows), updated=datetime.now(ET).isoformat(timespec='seconds')),
                          'model.md': '\n'.join(md) + '\n', 'model_test_picks.csv': buf.getvalue()})
    log('done')

if __name__ == '__main__':
    main()
