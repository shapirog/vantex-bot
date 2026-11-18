"""
VANTEX City: FORWARD TEST of the Vantex Score model. Records picks only: places NO orders.

Approved by Guillo on 2026-11-18 ("Go"). Rule fixed before the first forward day (from model_followup.md):
  liquid gap-ups (prior close >= $5, 20-day average dollar volume >= $20M, opening >= 2% above yesterday's close) whose model
  score is in the TOP 10% of 2026's liquid candidates (cutoff = 90th percentile of 2026 liquid scores, frozen in cutoff.json on
  the first run). The same model as city_model.py: same features, same learn period (Jun 2023 - Jun 2025), same settings.
  Also logged: the top 3 liquid scores each day (weaker in the backtest, kept for comparison) and all liquid candidates (baseline).
Two prices are scored at the close:
  open   9:30 official open -> close   (what the backtest measured)
  10:00  9:59 bar close -> close        (what the free, 15-minute-delayed data could actually trade)
Costs per side by liquidity (0.05-0.10% here).
  python city_model_forward.py pick    (~10:05 ET)  -> branch live-forward: picks/<day>.json
  python city_model_forward.py close   (~16:30 ET)  -> fills in the results, updates summary.json
"""
import json, math, os, sys
from datetime import date, datetime, timedelta

from city_engine import Data, to_bar
from city_replay import ET, OUT, log, publish
from city_overnight import universe
from city_news_study import load_ohlcv
from city_model import FEATS, LEARN, build, row_feats, split_of
from city_swing import cost_pct

BRANCH = 'live-forward'

def today_opens(D, syms, day):
    """first regular-session 1-minute bar of `day` for each symbol -> open price (SIP, fetched after 9:47 so it is not 'recent')"""
    a = datetime.combine(day, datetime.min.time(), ET) + timedelta(hours=9, minutes=30)
    M = D.bars(syms, '1Min', a, a + timedelta(minutes=3), 'sip', 'raw'); out = {}
    for s, L in M.items():
        b = [x for x in map(to_bar, L) if x.m >= 570]
        if b: out[s] = b[0].o
    return out

def train(stocks, spy):
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingRegressor
    rows = [r for r in build(stocks, spy) if split_of(r['day'])]
    for r in rows: r['split'] = split_of(r['day'])
    learn = [r for r in rows if r['split'] == 'learn']
    X = lambda L: np.array([[r[k] for k in FEATS] for r in L], dtype=float)
    m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200, l2_regularization=1.0, random_state=7)
    m.fit(X(learn), np.clip(np.array([r['y'] for r in learn]), -0.5, 0.5))
    liq = [r for r in rows if r['split'] == 'test' and r['px'] >= 5 and r['adv'] >= 20e6]
    sc = sorted(m.predict(X(liq))) if liq else [0.0]
    return m, X, sc[int(0.9 * (len(sc) - 1))]

def load_branch(name, default):
    publish({}, branch=BRANCH)
    try: return json.load(open(f'{OUT}/{name}'))
    except Exception: return default

def do_pick(D, key, sec, day):
    uni = universe(key, sec)
    s0 = datetime(2023, 3, 1, tzinfo=ET); s1 = datetime.combine(day, datetime.min.time(), ET) - timedelta(minutes=1)   # daily bars are stamped at midnight ET: exclude today
    sp = D.bars(['SPY'], '1Day', s0, s1, 'sip', 'all').get('SPY', [])
    spy = {sp[k]['t'][:10]: sp[k]['o'] / sp[k - 1]['c'] - 1 for k in range(1, len(sp))}
    stocks = load_ohlcv(D, sorted(uni), s0, s1); log('stocks', len(stocks))
    opens = today_opens(D, sorted(stocks) + ['SPY'], day)
    if 'SPY' not in opens: log('no SPY bars today: market closed, nothing to do'); return
    m, X, cut = train(stocks, spy)
    frozen = load_branch('cutoff.json', None)
    if frozen is None: frozen = dict(cutoff=cut, frozen_on=day.isoformat()); publish({'cutoff.json': frozen}, branch=BRANCH)
    cut = frozen['cutoff']
    spy_gap = opens['SPY'] / sp[-1]['c'] - 1; cands = []
    for s, S in stocks.items():
        if s not in opens or S['d'][-1] >= day.isoformat(): continue
        T = {k: S[k] + [opens[s]] for k in ('o', 'h', 'l', 'c')}; T['v'] = S['v'] + [0]; T['d'] = S['d'] + [day.isoformat()]
        f = row_feats(T, len(T['d']) - 1)                                      # uses only today's open + earlier days
        if f: cands.append(dict(f, sym=s))
    for r in cands: r['spy_gap'] = spy_gap; r['breadth'] = math.log(1 + len(cands)); r['weekday'] = day.weekday()
    if cands:
        for r, p in zip(cands, m.predict(X(cands))): r['score'] = float(p)
    liq = sorted([r for r in cands if r['px'] >= 5 and r['adv'] >= 20e6], key=lambda r: -r['score'])
    keep = lambda r: dict(sym=r['sym'], score=round(r['score'] * 100, 3), gap_pct=round(r['gap'] * 100, 2), prev_close=r['px'], open=round(r['px'] * (1 + r['gap']), 4), adv_m=round(r['adv'] / 1e6, 1))
    rec = dict(day=day.isoformat(), cutoff=round(cut * 100, 3), candidates=len(cands), liquid_candidates=len(liq),
               top_decile=[keep(r) for r in liq if r['score'] >= cut], top3=[keep(r) for r in liq[:3]], all_liquid=[keep(r) for r in liq],
               picked_at=datetime.now(ET).isoformat(timespec='minutes'))
    publish({f'picks/{day.isoformat()}.json': rec}, branch=BRANCH)
    log('picks', len(rec['top_decile']), [p['sym'] for p in rec['top_decile']], 'top3', [p['sym'] for p in rec['top3']])

def score_day(D, rec):
    syms = sorted({p['sym'] for p in rec['all_liquid']})
    if not syms: return rec
    day = date.fromisoformat(rec['day']); a = datetime.combine(day, datetime.min.time(), ET) + timedelta(hours=9, minutes=30)
    M = D.bars(syms, '1Min', a, a + timedelta(hours=6, minutes=30), 'sip', 'raw')
    d0 = datetime.combine(day, datetime.min.time(), ET)
    Dd = D.bars(syms, '1Day', d0, min(d0 + timedelta(hours=23), datetime.now(ET) - timedelta(minutes=16)), 'sip', 'raw')   # free plan: nothing newer than 15 min        # daily bars are stamped at midnight ET
    px = {}
    for s in syms:
        b = sorted((x for x in map(to_bar, M.get(s, [])) if 570 <= x.m < 960), key=lambda x: x.t)
        dd = Dd.get(s) or []
        if not b or not dd: continue
        p1000 = [x.c for x in b if x.m <= 599]
        px[s] = dict(open=dd[-1]['o'], p1000=p1000[-1] if p1000 else None, close=dd[-1]['c'])
    for grp in ('top_decile', 'top3', 'all_liquid'):
        for p in rec[grp]:
            q = px.get(p['sym'])
            if not q: continue
            c = cost_pct(p['adv_m'] * 1e6)
            p['close'] = q['close']; p['official_open'] = q['open']
            p['net_open_pct'] = round(100 * (q['close'] * (1 - c) / (q['open'] * (1 + c)) - 1), 3)
            if q['p1000']: p['net_1000_pct'] = round(100 * (q['close'] * (1 - c) / (q['p1000'] * (1 + c)) - 1), 3)
    rec['scored_at'] = datetime.now(ET).isoformat(timespec='minutes')
    return rec

def summary(recs):
    out = dict(days=len(recs), started=min((r['day'] for r in recs), default=None), updated=datetime.now(ET).isoformat(timespec='minutes'),
               note='forward test: picks recorded each morning, no orders. Backtest 2026 for the top-decile rule: +0.88% gross open->close, 54% up.')
    for grp in ('top_decile', 'top3', 'all_liquid'):
        for k in ('net_open_pct', 'net_1000_pct'):
            xs = [p[k] for r in recs for p in r[grp] if k in p]
            out[f'{grp} | {k}'] = dict(n=len(xs), avg=round(sum(xs) / len(xs), 3) if xs else None, win_pct=round(100 * sum(x > 0 for x in xs) / len(xs), 1) if xs else None)
    return out

def do_close(D, day):
    rec = load_branch(f'picks/{day.isoformat()}.json', None)
    if rec is None: log('no picks today'); return
    rec = score_day(D, rec)
    recs = []
    for fn in sorted(os.listdir(f'{OUT}/picks')):
        if fn == f'{day.isoformat()}.json': recs.append(rec); continue
        try: recs.append(json.load(open(f'{OUT}/picks/{fn}')))
        except Exception: pass
    recs = [r for r in recs if r.get('scored_at')]
    publish({f'picks/{day.isoformat()}.json': rec, 'summary.json': summary(recs)}, branch=BRANCH)
    log('scored', day, summary(recs))

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'pick'
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    D = Data(key, sec); day = date.fromisoformat(os.environ['FWD_DAY']) if os.environ.get('FWD_DAY') else datetime.now(ET).date()
    if mode == 'pick': do_pick(D, key, sec, day)
    else: do_close(D, day)

if __name__ == '__main__':
    main()
