"""Vantex strategy lab 2: every serious day-trading idea, tested on real data with 1-minute AND 5-minute candles.
Read-only: places no trades.

How it stays honest
  - each strategy has a few settings to try; the best settings are chosen on the OLDER 70% of days only (TRAIN),
    then judged on the NEWEST 30% they never saw (TEST). Daily strategies: train 2016-2023, test 2024 onward.
  - PASS = profit factor 1.2+ on train AND on test, with enough trades. It also reports how many of the settings
    made money on test, so one lucky setting can't fool it.
  - costs on every trade: 0.02% slippage each way + SEC fee for stocks; options pay a 3-4% bid/ask spread.

Strategies
  ORB    opening-range breakout on stocks in play (Zarattini, Barbon & Aziz 2024). Settings: candle size the trades
         are simulated on (1-min or 5-min), range 5/15/30 min, top 4/10 by relative volume, relative volume 1x/2x,
         stop 5/10/25% of ATR, exit at close or at 3R, any gap or only gappers (3%+).
  NOISE  intraday momentum on SPY/QQQ (Zarattini, Aziz & Barbon "Beat the Market" 2024): trade breaks of the
         "noise area" (the typical distance from the open by that time of day over the last 14 days), checked every
         30 or 60 minutes, out when price falls back inside it / below VWAP, flat at the close.
  LASTHR market intraday momentum (Gao, Han, Li & Zhou 2018): the first half hour's return predicts the last half hour's.
  GAPFADE SPY/QQQ small opening gaps (0.2-1%) back toward yesterday's close.
  VWAPPB trend-day pullbacks to VWAP on SPY/QQQ.
  OVERNIGHT buy SPY/QQQ at the close, sell at the next open (daily data since 2016).
  RSI2   Connors RSI(2) dip buying in an uptrend (daily data since 2016).
Each intraday winner is also re-run with OPTIONS (same-day for SPY/QQQ, this week's for stocks; modeled prices).
Results: 'live-lab2' branch.
"""
import os, sys, json, math, time, subprocess, bisect, itertools
from collections import defaultdict
from datetime import datetime, timedelta, timezone, date
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import options as O

ET, req, TRADE, DATA = O.ET, O.req, O.TRADE, O.DATA
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 500
OUT = os.environ.get('VANTEX_LAB2_DIR', '/tmp/vantex-lab2')
START_EQ = 2500.0
IDX = ['SPY', 'QQQ']
STOCKS = list(dict.fromkeys(O.LIQUID + ['SMCI', 'ARM', 'SHOP', 'CRWD', 'SNOW', 'HOOD', 'SOFI', 'RIVN', 'NIO', 'INTC', 'DIS', 'JPM', 'XOM', 'LLY', 'WMT', 'COST']))
SLIP, SEC = 0.0002, 27.8e-6
SLIP_STK = 0.0005             # stop orders on fast stocks fill worse: 0.05% each way
STK_IV_MULT = 1.5             # stock options around news/earnings cost more than recent volatility suggests
HOT = {'PLTR', 'COIN', 'MSTR', 'SMCI', 'HOOD', 'ARM', 'SOFI', 'RIVN', 'NIO'}   # names picked with hindsight
SPREAD_IDX, SPREAD_STK, IV_MULT, IV_FLOOR, OPT_RISK = 0.03, 0.04, 1.1, 0.12, 0.15
LEV = 2.0
TRAIN_FRAC, PASS_PF = 0.70, 1.2

# ---------------- data ----------------
FEED = {'name': 'sip'}
def fetch(syms, tf, start, end, rth_only):
    """{sym: np.array[[day_ordinal, minute, o, h, l, c, v], ...]} using the full-market SIP feed for history."""
    out = {}
    for s in syms:
        rows, tok = [], None
        for _ in range(2000):
            p = dict(symbols=s, timeframe=tf, start=start.isoformat(), end=end.isoformat(), limit=10000, feed=FEED['name'], adjustment='all')
            if tok: p['page_token'] = tok
            r = req('GET', f'{DATA}/v2/stocks/bars', params=p)
            if r.status_code in (401, 403, 422) and FEED['name'] == 'sip':
                print('SIP history not allowed, using IEX:', r.text[:120], flush=True); FEED['name'] = 'iex'; continue
            if not r.ok: print('bars error', s, r.status_code, r.text[:120], flush=True); break
            j = r.json()
            for b in (j.get('bars') or {}).get(s, []):
                t = datetime.fromisoformat(b['t'].replace('Z', '+00:00')).astimezone(ET); m = t.hour * 60 + t.minute
                if rth_only and not (570 <= m < 960): continue
                rows.append((t.date().toordinal(), m, b['o'], b['h'], b['l'], b['c'], b['v']))
            tok = j.get('next_page_token')
            if not tok: break
        if rows: out[s] = np.array(rows, dtype=float)
    return out

def by_day(A):
    """split one symbol's minute array into {day_ordinal: rows}"""
    if A is None or not len(A): return {}
    d = A[:, 0].astype(int); cut = np.flatnonzero(np.diff(d)) + 1
    return {int(x[0, 0]): x[:, 1:] for x in np.split(A, cut)}           # cols: minute, o, h, l, c, v

def resample5(D):
    """1-minute day -> 5-minute day (minute, o, h, l, c, v)"""
    k = ((D[:, 0] - 570) // 5).astype(int); out = []
    for g in np.unique(k):
        x = D[k == g]; out.append((570 + g * 5, x[0, 1], x[:, 2].max(), x[:, 3].min(), x[-1, 4], x[:, 5].sum()))
    return np.array(out)

# ---------------- pricing / stats ----------------
def ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
def bs(S, K, T, vol, call):
    if T <= 1e-9 or vol <= 0: return max(0.0, (S - K) if call else (K - S))
    v = vol * math.sqrt(T); d1 = (math.log(S / K) + 0.5 * v * v) / v; d2 = d1 - v
    return S * ncdf(d1) - K * ncdf(d2) if call else K * ncdf(-d2) - S * ncdf(-d1)

def years_left(idx, day, m):
    left = max(0, 960 - m) / 390
    if idx: return left / 252
    dd = date.fromordinal(day); k = (4 - dd.weekday()) % 7
    if k < 2: k += 7
    return (sum(1 for i in range(1, k + 1) if (dd + timedelta(days=i)).weekday() < 5) + left) / 252

def option_ret(idx, day, d, s_in, m_in, s_out, m_out, vol):
    """Return of an at-the-money option bought at (s_in, m_in) and sold at (s_out, m_out), after the spread."""
    spr = SPREAD_IDX if idx else SPREAD_STK; step = 1 if idx else (1 if s_in < 50 else 2.5 if s_in < 200 else 5)
    K = round(s_in / step) * step
    if not idx: vol = vol / IV_MULT * STK_IV_MULT
    f0 = bs(s_in, K, years_left(idx, day, m_in), vol, d == 1); f1 = bs(s_out, K, years_left(idx, day, min(m_out, 960)), vol, d == 1)
    p0 = f0 + max(0.01, f0 * spr / 2); p1 = max(0.0, f1 - max(0.01, f1 * spr / 2))
    if f0 < 0.05: return None
    return (p1 - p0) / p0, p0

def stats(trades, n_days=None):
    """trades: list of dicts with 'ret' (fraction of equity) in time order."""
    if not trades: return dict(trades=0)
    r = np.array([t['ret'] for t in trades]); eq = START_EQ * np.cumprod(1 + r)
    w = r[r > 0].sum(); l = -r[r <= 0].sum(); pk = np.maximum.accumulate(np.concatenate([[START_EQ], eq]))
    dd = float(((pk[1:] - eq) / pk[1:]).max() * 100)
    return dict(trades=int(len(r)), win_rate=round(float((r > 0).mean() * 100), 1), pf=round(float(w / l), 2) if l > 0 else None,
                ret_pct=round(float((eq[-1] / START_EQ - 1) * 100), 1), max_dd_pct=round(dd, 1), avg_trade_pct=round(float(r.mean() * 100), 3),
                end_equity=round(float(eq[-1]), 2))

def walk(D, i0, d, entry, stop, target, mid_entry, last_min=959):
    """Follow bars from i0. On a breakout's own bar, only the close can stop it (the low came before the break)."""
    for i in range(i0, len(D)):
        m, o, h, l, c, v = D[i]
        if i == i0 and mid_entry: l, h = (min(c, entry), max(h, entry)) if d == 1 else (min(l, entry), max(c, entry))
        if d == 1:
            if l <= stop: return (min(stop, o) if i > i0 else stop), m, 'stop'
            if target is not None and h >= target: return (max(target, o) if i > i0 else target), m, 'target'
        else:
            if h >= stop: return (max(stop, o) if i > i0 else stop), m, 'stop'
            if target is not None and l <= target: return (min(target, o) if i > i0 else target), m, 'target'
        if m >= last_min: return c, m, 'close'
    return D[-1][4], D[-1][0], 'close'

def share_ret(entry, px, d, risk_frac_of_price, n_open):
    """Equity return of one stock trade sized to risk 1% of equity at the stop, capped by 2x buying power."""
    pos = min(0.01 / max(risk_frac_of_price, 1e-6), LEV / max(1, n_open))      # position value as a fraction of equity
    move = (px - entry) / entry * d
    return pos * (move - 2 * SLIP_STK - SEC)

# ---------------- strategies ----------------
class Data:
    pass

def prep_info(G, days):
    """ATR(14), average volume, 20-day volatility and opening-window volume history per stock and day."""
    info = defaultdict(dict)
    for s, A in G.daily.items():
        dd = A[:, 0].astype(int)
        for day in days:
            i = int(np.searchsorted(dd, day))
            if i < 21: continue
            p = A[i - 15:i]; c = p[:, 5]
            tr = np.maximum(p[1:, 3], c[:-1]) - np.minimum(p[1:, 4], c[:-1])
            rets = np.diff(np.log(A[i - 21:i, 5]))
            info[s][day] = dict(atr=float(tr.mean()), adv=float(p[1:, 6].mean()), prev_close=float(A[i - 1, 5]),
                                vol=max(IV_FLOOR, float(rets.std(ddof=1) * math.sqrt(252) * IV_MULT)))
    return info

_ORC, _HIT, _LST = {}, {}, {}
def or_cands(G, day, orm):
    """Opening-range facts for every stock on a day (cached): (rel_volume, sym, direction, high, low, gap, info)."""
    key = (day, orm)
    if key in _ORC: return _ORC[key]
    out = []
    for s in STOCKS:
        D1 = G.m1[s].get(day); I = G.info[s].get(day)
        if D1 is None or I is None or len(D1) < 60 or D1[0, 0] != 570: continue
        hist = G.orvol[(s, orm)].get(day)
        if not hist: continue
        orw = D1[D1[:, 0] < 570 + orm]
        o = orw[0, 1]; c = orw[-1, 4]
        if o < 5 or I['adv'] < 1e6 or I['atr'] < 0.5 or c == o: continue
        out.append((orw[:, 5].sum() / hist, s, 1 if c > o else -1, orw[:, 2].max(), orw[:, 3].min(), o / I['prev_close'] - 1, I))
    _ORC[key] = out; return out

def bars_list(G, s, day, res):
    key = (s, day, res)
    if key not in _LST: _LST[key] = (G.m1[s][day] if res == 1 else G.m5[s][day]).tolist()
    return _LST[key]

def first_hit(G, s, day, res, orm, d, level):
    key = (s, day, res, orm, d)
    if key not in _HIT:
        D = G.m1[s][day] if res == 1 else G.m5[s][day]
        ok = (D[:, 0] >= 570 + orm) & (D[:, 0] < 955) & ((D[:, 2] >= level) if d == 1 else (D[:, 3] <= level))
        nz = np.flatnonzero(ok); _HIT[key] = int(nz[0]) if len(nz) else None
    return _HIT[key]

def confirm_hit(G, s, day, orm, d, level):
    """5-minute confirmation: first 5-min bar that CLOSES beyond the level; entry = the next 1-minute bar's open."""
    key = (s, day, 'c5', orm, d)
    if key not in _HIT:
        D5 = G.m5[s][day]; ok = (D5[:, 0] >= 570 + orm) & (D5[:, 0] < 950) & ((D5[:, 4] > level) if d == 1 else (D5[:, 4] < level))
        nz = np.flatnonzero(ok); i1 = None
        if len(nz):
            m_next = D5[nz[0], 0] + 5; D1 = G.m1[s][day]; j = np.flatnonzero(D1[:, 0] >= m_next)
            i1 = int(j[0]) if len(j) else None
        _HIT[key] = i1
    return _HIT[key]

def orb(G, days, res, orm, topn, rvmin, stop_atr, tgt_r, gapmin, universe='all', collect_opt=False):
    T = []
    for day in days:
        cands = [c for c in or_cands(G, day, orm) if c[0] >= rvmin and abs(c[5]) >= gapmin and (not gapmin or (c[5] > 0) == (c[2] > 0))
                 and (universe == 'all' or c[1] not in HOT)]
        picks = sorted(cands, key=lambda c: -c[0])[:topn]
        for rv, s, d, hi, lo, gap, I in picks:
            level = hi if d == 1 else lo
            D = bars_list(G, s, day, 1)                       # fills and stops always on 1-minute bars
            if res == 1:
                i = first_hit(G, s, day, 1, orm, d, level)
                if i is None: continue
                entry = max(level, D[i][1]) if d == 1 else min(level, D[i][1])    # stop order at the level
            else:
                i = confirm_hit(G, s, day, orm, d, level)
                if i is None: continue
                entry = D[i][1]                                                   # next minute's open after the 5-min close
            stop = entry - d * stop_atr * I['atr']; target = entry + d * tgt_r * stop_atr * I['atr'] if tgt_r else None
            if (stop - entry) * d >= 0: continue
            px, m_out, why = walk(D, i, d, entry, stop, target, False)
            t = dict(day=day, sym=s, d=d, ret=share_ret(entry, px, d, stop_atr * I['atr'] / entry, len(picks)), why=why)
            if collect_opt: t.update(s_in=entry, m_in=D[i][0], s_out=px, m_out=m_out, vol=I['vol'], idx=False)
            T.append(t)
    return T

def noise(G, days, sym, freq, use_vwap, collect_opt=False):
    T = []; D_all = G.m1[sym]; dl = sorted(D_all)
    for day in days:
        k = bisect.bisect_left(dl, day)
        if k < 15 or day not in D_all: continue
        D = D_all[day]; I = G.info[sym].get(day)
        if I is None or D[0, 0] != 570: continue
        o = D[0, 1]; pc = I['prev_close']
        # average absolute move from the open at each minute over the last 14 days
        prev = [D_all[x] for x in dl[k - 14:k]]
        sig = {}
        for P in prev:
            mv = np.abs(P[:, 4] / P[0, 1] - 1)
            for mm, x in zip(P[:, 0], mv): sig.setdefault(int(mm), []).append(x)
        up_base, lo_base = max(o, pc), min(o, pc)
        cpv = np.cumsum((D[:, 2] + D[:, 3] + D[:, 4]) / 3 * D[:, 5]); cv = np.cumsum(D[:, 5])
        pos = 0; ent = None; m_in = None
        checks = list(range(600, 960, freq))
        for cm in checks:
            ii = np.flatnonzero(D[:, 0] <= cm - 1)
            if not len(ii): continue
            i = ii[-1]; px = D[i, 4]; s_ = np.mean(sig.get(int(D[i, 0]), [0.003])) if sig.get(int(D[i, 0])) else 0.003
            ub, lb = up_base * (1 + s_), lo_base * (1 - s_); vw = cpv[i] / cv[i] if cv[i] else px
            last = cm >= 955
            if pos == 1 and (px < (max(ub, vw) if use_vwap else ub) or last) or pos == -1 and (px > (min(lb, vw) if use_vwap else lb) or last):
                T.append(_close(ent, px, pos, day, sym, m_in, cm, I, collect_opt)); pos = 0
            if not pos and not last:
                if px > (max(ub, vw) if use_vwap else ub): pos, ent, m_in = 1, px, cm
                elif px < (min(lb, vw) if use_vwap else lb): pos, ent, m_in = -1, px, cm
        if pos: T.append(_close(ent, D[-1, 4], pos, day, sym, m_in, 959, I, collect_opt))
    return T

def _close(ent, px, d, day, sym, m_in, m_out, I, collect_opt):
    t = dict(day=day, sym=sym, d=d, ret=(px - ent) / ent * d - 2 * SLIP - SEC, why='exit')          # 1x equity, no leverage
    if collect_opt: t.update(s_in=ent, m_in=m_in, s_out=px, m_out=m_out, vol=I['vol'], idx=True)
    return t

def lasthr(G, days, sym, entry_min, min_move, collect_opt=False):
    T = []
    for day in days:
        D = G.m1[sym].get(day); I = G.info[sym].get(day)
        if D is None or I is None or D[0, 0] != 570: continue
        a = D[D[:, 0] <= 599]; b = D[D[:, 0] == entry_min]
        if not len(a) or not len(b): continue
        r1 = a[-1, 4] / I['prev_close'] - 1
        if abs(r1) < min_move: continue
        d = 1 if r1 > 0 else -1; ent = b[0, 1]; px = D[-1, 4]
        t = dict(day=day, sym=sym, d=d, ret=(px - ent) / ent * d - 2 * SLIP - SEC, why='close')
        if collect_opt: t.update(s_in=ent, m_in=entry_min, s_out=px, m_out=959, vol=I['vol'], idx=True)
        T.append(t)
    return T

def gapfade(G, days, sym, gmin, gmax, time_exit, collect_opt=False):
    T = []
    for day in days:
        D = G.m1[sym].get(day); I = G.info[sym].get(day)
        if D is None or I is None or D[0, 0] != 570: continue
        o = D[0, 1]; pc = I['prev_close']; g = o / pc - 1
        if not (gmin <= abs(g) <= gmax): continue
        d = -1 if g > 0 else 1; stop = o + (o - pc) * 1.0
        px, m_out, why = walk(D, 0, d, o, stop, pc, False, last_min=time_exit)
        t = dict(day=day, sym=sym, d=d, ret=(px - o) / o * d - 2 * SLIP - SEC, why=why)
        if collect_opt: t.update(s_in=o, m_in=570, s_out=px, m_out=m_out, vol=I['vol'], idx=True)
        T.append(t)
    return T

def vwappb(G, days, sym, trend, stop_pct, collect_opt=False):
    T = []
    for day in days:
        D = G.m1[sym].get(day); I = G.info[sym].get(day)
        if D is None or I is None or D[0, 0] != 570: continue
        o = D[0, 1]; cpv = np.cumsum((D[:, 2] + D[:, 3] + D[:, 4]) / 3 * D[:, 5]); cv = np.cumsum(D[:, 5])
        for i in range(60, len(D) - 5):
            if D[i, 0] > 900: break
            vw = cpv[i - 1] / cv[i - 1]; ch = D[i - 1, 4] / o - 1
            d = 1 if ch >= trend else -1 if ch <= -trend else 0
            if not d: continue
            touched = (D[i, 3] <= vw) if d == 1 else (D[i, 2] >= vw)
            if touched and ((D[i, 4] > vw) if d == 1 else (D[i, 4] < vw)):
                ent = D[i, 4]; stop = vw * (1 - d * stop_pct); hi_so_far = D[:i, 2].max() if d == 1 else D[:i, 3].min()
                tgt = hi_so_far if (hi_so_far - ent) * d > 0 else None
                px, m_out, why = walk(D, i + 1, d, ent, stop, tgt, False)
                t = dict(day=day, sym=sym, d=d, ret=(px - ent) / ent * d - 2 * SLIP - SEC, why=why)
                if collect_opt: t.update(s_in=ent, m_in=D[i, 0], s_out=px, m_out=m_out, vol=I['vol'], idx=True)
                T.append(t); break
    return T

def overnight(G, sym, only_down):
    A = G.daily_long[sym]; T = []
    for i in range(1, len(A) - 1):
        if only_down and A[i, 5] >= A[i - 1, 5]: continue
        T.append(dict(day=int(A[i, 0]), sym=sym, d=1, ret=A[i + 1, 2] / A[i, 5] - 1 - 2 * SLIP, why='open'))
    return T

def rsi2(G, sym, thr):
    A = G.daily_long[sym]; c = A[:, 5]; T = []
    d = np.diff(c); up = np.where(d > 0, d, 0); dn = np.where(d < 0, -d, 0)
    i = 201
    while i < len(A) - 1:
        g = up[i - 2:i].mean(); l = dn[i - 2:i].mean(); r = 100 if l == 0 else 100 - 100 / (1 + g / l)
        if c[i] > c[i - 200:i].mean() and r < thr:
            ent = c[i]; j = i + 1
            while j < len(A) - 1 and c[j] <= c[j - 5:j].mean() and j - i < 10: j += 1
            T.append(dict(day=int(A[i, 0]), sym=sym, d=1, ret=c[j] / ent - 1 - 2 * SLIP, why='exit')); i = j + 1
        else: i += 1
    return T

# ---------------- search ----------------
def split(days):
    cut = int(len(days) * TRAIN_FRAC); return days[:cut], days[cut:]

def family(name, desc, grid, fn, train, test, min_train=40, opt=True):
    """Try every setting on TRAIN, keep the best, judge it on TEST."""
    rows = []
    for params in grid:
        a = stats(fn(train, *params))
        rows.append((params, a))
    ok = [r for r in rows if r[1].get('trades', 0) >= min_train and r[1].get('pf')]
    if not ok: return dict(name=name, desc=desc, best=None, passed=False, note='not enough trades')
    best_p, best_a = max(ok, key=lambda r: r[1]['pf'])
    tb = fn(test, *best_p); b = stats(tb)
    # robustness: how many settings made money on test
    pos = 0; tot = 0
    for params, a in rows:
        if a.get('trades', 0) < min_train: continue
        tt = stats(fn(test, *params)); tot += 1; pos += int((tt.get('pf') or 0) > 1.0)
    passed = bool(best_a['pf'] >= PASS_PF and (b.get('pf') or 0) >= PASS_PF and b.get('trades', 0) >= 20)
    out = dict(name=name, desc=desc, best=[str(x) for x in best_p], train=best_a, test=b, passed=passed,
               robust=f'{pos} of {tot} settings made money on test', top_train=[dict(params=[str(x) for x in p], train=a) for p, a in sorted(ok, key=lambda r: -r[1]['pf'])[:5]])
    if opt:
        def opt_trades(days_):
            per = defaultdict(list)
            for t in fn(days_, *best_p, collect_opt=True):
                r = option_ret(t['idx'], t['day'], t['d'], t['s_in'], t['m_in'], t['s_out'], t['m_out'], t['vol'])
                if r: per[t['day']].append((t['m_in'], max(-1.0, r[0])))
            # like the live bot: at most 2 option trades a day, 15% of the account each
            return [dict(day=k, ret=OPT_RISK * sum(x[1] for x in sorted(v)[:2])) for k, v in sorted(per.items())]
        out['options'] = dict(train=stats(opt_trades(train)), test=stats(opt_trades(test)))
        ot, oT = out['options']['train'], out['options']['test']
        out['options']['passed'] = bool((ot.get('pf') or 0) >= PASS_PF and (oT.get('pf') or 0) >= PASS_PF and oT.get('trades', 0) >= 20)
    print(name, 'best', best_p, 'TRAIN', json.dumps(best_a), 'TEST', json.dumps(b), out.get('robust'), 'PASS' if passed else '', flush=True)
    if 'options' in out: print('   options', json.dumps(out['options']), flush=True)
    return out

def main():
    t0 = time.time()
    end = datetime.now(ET).date() - timedelta(days=1)
    r = req('GET', f'{TRADE}/v2/calendar', params=dict(start=str(end - timedelta(days=int(DAYS * 1.5) + 30)), end=str(end)))
    cal = r.json() if r.ok else []
    days = [date.fromisoformat(c['date']).toordinal() for c in cal if str(c.get('close', '16:00')).startswith('16')][-DAYS:]   # skip half days
    if len(days) < 100: sys.exit('not enough trading days')
    G = Data(); syms = IDX + STOCKS
    s0 = datetime.combine(date.fromordinal(days[0]) - timedelta(days=60), datetime.min.time(), ET); s1 = datetime.combine(end + timedelta(days=1), datetime.min.time(), ET)
    G.daily = fetch(syms, '1Day', s0, s1, False)
    G.daily_long = fetch(IDX, '1Day', datetime(2015, 1, 1, tzinfo=ET), s1, False)
    print('daily ready', round(time.time() - t0), 's', flush=True)
    M = fetch(syms, '1Min', datetime.combine(date.fromordinal(days[0]) - timedelta(days=30), datetime.min.time(), ET), s1, True)
    print('minute bars', {s: len(a) for s, a in M.items()}, FEED['name'], round(time.time() - t0), 's', flush=True)
    G.m1 = {s: by_day(M.get(s)) for s in syms}; del M
    G.m5 = {s: {d: resample5(D) for d, D in G.m1[s].items()} for s in STOCKS}
    G.info = prep_info(G, days)
    for s in syms:                                   # yesterday's official close = last regular-hours minute
        dl = sorted(G.m1[s])
        for a, b in zip(dl, dl[1:]):
            if b in G.info[s] and len(G.m1[s][a]) > 300: G.info[s][b]['prev_close'] = float(G.m1[s][a][-1, 4])
    # opening-window volume averages (previous 14 days) for relative volume
    G.orvol = {}
    for s in STOCKS:
        dl = sorted(G.m1[s])
        for orm in (5, 15, 30):
            h = {}; vols = []
            for d in dl:
                D = G.m1[s][d]
                v = float(D[D[:, 0] < 570 + orm][:, 5].sum()) if D[0, 0] == 570 else None
                if len(vols) >= 14: h[d] = sum(vols[-14:]) / 14
                if v: vols.append(v)
            G.orvol[(s, orm)] = h
    print('prepared', round(time.time() - t0), 's', flush=True)
    train, test = split(days)
    R = []
    grid = list(itertools.product([1, 5], [5, 15, 30], [4, 10], [1.0, 2.0], [0.05, 0.10, 0.25], [None, 3], [0, 0.03]))
    R.append(family('ORB', 'Opening-range breakout on stocks in play', grid, lambda d, *p, collect_opt=False: orb(G, d, *p, collect_opt=collect_opt), train, test))
    R.append(family('ORB (no hindsight names)', 'Same, without PLTR/COIN/MSTR/SMCI/HOOD/ARM/SOFI/RIVN/NIO', grid,
                    lambda d, *p, collect_opt=False: orb(G, d, *p, universe='core', collect_opt=collect_opt), train, test))
    for sym in IDX:
        R.append(family(f'NOISE {sym}', 'Noise-area intraday momentum', list(itertools.product([30, 60], [True, False])),
                        lambda d, *p, collect_opt=False, s=sym: noise(G, d, s, *p, collect_opt=collect_opt), train, test))
        R.append(family(f'LASTHR {sym}', 'First half hour predicts the last half hour', list(itertools.product([930, 900], [0.0, 0.002, 0.005])),
                        lambda d, *p, collect_opt=False, s=sym: lasthr(G, d, s, *p, collect_opt=collect_opt), train, test))
        R.append(family(f'GAPFADE {sym}', 'Small gaps back to yesterday\'s close', list(itertools.product([0.002, 0.004], [0.006, 0.01], [720, 959])),
                        lambda d, *p, collect_opt=False, s=sym: gapfade(G, d, s, *p, collect_opt=collect_opt), train, test))
        R.append(family(f'VWAPPB {sym}', 'Trend-day pullback to VWAP', list(itertools.product([0.003, 0.006], [0.002, 0.004])),
                        lambda d, *p, collect_opt=False, s=sym: vwappb(G, d, s, *p, collect_opt=collect_opt), train, test))
    cut = date(2024, 1, 1).toordinal()
    for sym in IDX:
        if sym not in G.daily_long: continue
        A = G.daily_long[sym]
        def dsplit(T, tr): return [t for t in T if (t['day'] < cut) == tr]
        for name, desc, grid_, fn in ((f'OVERNIGHT {sym}', 'Buy at the close, sell at the next open', [(False,), (True,)], lambda p, s=sym: overnight(G, s, *p)),
                                      (f'RSI2 {sym}', 'Connors RSI(2) dip buying above the 200-day average', [(5,), (10,)], lambda p, s=sym: rsi2(G, s, *p))):
            rows = [(p, stats(dsplit(fn(p), True))) for p in grid_]
            ok = [x for x in rows if x[1].get('trades', 0) >= 30 and x[1].get('pf')]
            if not ok: R.append(dict(name=name, desc=desc, passed=False, note='not enough trades')); continue
            bp, ba = max(ok, key=lambda x: x[1]['pf']); bb = stats(dsplit(fn(bp), False))
            passed = bool(ba['pf'] >= PASS_PF and (bb.get('pf') or 0) >= PASS_PF and bb.get('trades', 0) >= 20)
            R.append(dict(name=name, desc=desc, best=[str(x) for x in bp], train=ba, test=bb, passed=passed, robust='daily data 2015-2023 train / 2024+ test'))
            print(name, bp, 'TRAIN', json.dumps(ba), 'TEST', json.dumps(bb), 'PASS' if passed else '', flush=True)
    out = dict(updated=datetime.now(ET).isoformat(timespec='seconds'), days=len(days), start=date.fromordinal(days[0]).isoformat(), end=date.fromordinal(days[-1]).isoformat(),
               train=f'{date.fromordinal(train[0])} → {date.fromordinal(train[-1])}', test=f'{date.fromordinal(test[0])} → {date.fromordinal(test[-1])}',
               feed=FEED['name'], start_equity=START_EQ, results=R, seconds=round(time.time() - t0),
               passed=[r['name'] + (' (shares)' if r.get('passed') else '') for r in R if r.get('passed')] + [r['name'] + ' (options)' for r in R if (r.get('options') or {}).get('passed')])
    os.makedirs(OUT, exist_ok=True); json.dump(out, open(f'{OUT}/lab2.json', 'w'), separators=(',', ':'), default=str)
    print(json.dumps(dict(event='lab2_done', passed=out['passed'], seconds=out['seconds'])), flush=True)
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', 'live-lab2', OUT], check=True)
    subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', 'lab2'], check=True)
    subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{O.REPO}.git', 'live-lab2'], check=True, timeout=90, capture_output=True)

if __name__ == '__main__':
    main()
