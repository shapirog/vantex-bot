"""Vantex lab 3: independent audit of lab 2 + canonical RSI(2) replay + pre-registered tests.
READ-ONLY. Places no orders, never touches account settings, never uses live keys.

Every rule below was written down BEFORE this script was run on real data (pre-registration).
Nothing here is tuned. The April-November 2026 intraday period is treated as selection-contaminated.

0  AUDIT       reproduce lab 2's RSI(2) numbers exactly, then fix one thing at a time to show what each flaw was worth
1  CANONICAL   RSI(2) on SPY and on QQQ: signal after the close, fill at the NEXT open (entries and exits),
               Wilder RSI(2) < 10, close > SMA(200), exit on a close > SMA(5) or after 10 sessions held, no stop,
               no adding. 25% / 50% / 100% of equity. Fractional shares and whole shares. Buy-and-hold benchmarks.
2  COMBINED    SPY + QQQ in one account (cap 50% / 100%), plus how correlated the two really are
3  STRESS      0.10% / 0.25% slippage, fills one session late, fills at the next close, 10% / 25% of signals missed
A  ETF UNIVERSE  same rules, no tuning: SPY QQQ IWM DIA XLF XLK XLI XLP XLY XLU XLE XLV XLB.
               Each alone (50%), and pooled: total cap 50% of equity, free capacity split equally among that
               morning's new signals, no pyramiding.
B  LEVERAGED   SPY signal -> trade SSO, QQQ signal -> trade QLD, half the dollars of the unleveraged run
C  INTRADAY    SPY: R = price at 10:00 / prior close - 1. At 15:30 go long if R > 0 (short if R < 0), flat at the close.
               Long-or-cash version too. Entry delays 0-5 minutes. Pre-2024 and 2024+ reported separately.
O  OVERNIGHT   executable version of lab 2's "buy at the close after a down day": decide at 15:50, buy at the close
D  OPTIONS     only with real historical quotes. Probes Alpaca for them; if they don't exist, the test is not run.
R  RISK        block-bootstrap risk of ruin for a $2,500 account over 21 and 252 sessions
Results: 'live-lab3' branch (lab3.json + lab3_report.md).
"""
import os, sys, json, math, time, random, subprocess
from collections import defaultdict
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
import numpy as np
import requests

ET = ZoneInfo('America/New_York')
DATA = 'https://data.alpaca.markets'
TRADE = 'https://paper-api.alpaca.markets'
OUT = os.environ.get('VANTEX_LAB3_DIR', '/tmp/vantex-lab3')
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
START_EQ = 2500.0
SLIP = 0.0005             # 0.05% each side on every ETF fill (lab 2 used 0.02% on SPY/QQQ)
SEC_FEE = 27.8e-6         # SEC fee on sell notional
CUT = date(2024, 1, 1).toordinal()          # daily: train < 2024 <= test
DATA_START = date(2015, 1, 1)
ETFS = ['SPY', 'QQQ', 'IWM', 'DIA', 'XLF', 'XLK', 'XLI', 'XLP', 'XLY', 'XLU', 'XLE', 'XLV', 'XLB']
LEVMAP = {'SPY': 'SSO', 'QQQ': 'QLD'}
MC_PATHS = int(os.environ.get('LAB3_MC', '5000'))
SKIP_MIN = os.environ.get('LAB3_SKIP_MINUTE') == '1'
RNG = np.random.default_rng(7)

# trials already run before this lab (for the multiple-testing note)
PRIOR_TRIALS = {
    'lab2 ORB grid (2 universes x 288)': 576, 'lab2 NOISE (2 x 4)': 8, 'lab2 LASTHR (2 x 6)': 12, 'lab2 GAPFADE (2 x 8)': 16,
    'lab2 VWAPPB (2 x 2-4)': 6, 'lab2 OVERNIGHT (2 x 2)': 4, 'lab2 RSI2 (2 x 2 thresholds)': 4,
    'lab2 options re-runs of every intraday family': 12, 'lab1 (OVN, ORB5, ORB15, IDX + options)': 8,
    'live options bot replay (3 setups)': 3,
}

def log(*a):
    print(' '.join(str(x) for x in a), flush=True)

H = {'APCA-API-KEY-ID': os.environ.get('APCA_API_KEY_ID', ''), 'APCA-API-SECRET-KEY': os.environ.get('APCA_API_SECRET_KEY', '')}

def get(url, params=None):
    for k in range(6):
        try:
            r = requests.get(url, headers=H, params=params, timeout=60)
        except Exception as e:
            log('network', type(e).__name__, url[-60:]); time.sleep(2 * (k + 1)); continue
        if r.status_code == 429: time.sleep(3 * (k + 1)); continue
        return r
    return None

# ------------------------------------------------------------------ data
def fetch_daily(sym, start, end, adjustment='all'):
    rows, tok = [], None
    while True:
        p = dict(symbols=sym, timeframe='1Day', start=start.isoformat(), end=end.isoformat(), limit=10000, feed='sip', adjustment=adjustment)
        if tok: p['page_token'] = tok
        r = get(f'{DATA}/v2/stocks/bars', p)
        if r is None or not r.ok: log('daily error', sym, getattr(r, 'status_code', None), getattr(r, 'text', '')[:120]); break
        j = r.json()
        for b in (j.get('bars') or {}).get(sym, []):
            t = datetime.fromisoformat(b['t'].replace('Z', '+00:00')).astimezone(ET)
            rows.append((t.date().toordinal(), b['o'], b['h'], b['l'], b['c'], b['v']))
        tok = j.get('next_page_token')
        if not tok: break
    if not rows: return None
    A = np.array(rows, dtype=float)
    return dict(d=A[:, 0].astype(int), o=A[:, 1], h=A[:, 2], l=A[:, 3], c=A[:, 4], v=A[:, 5])

def fetch_minutes(sym, start, end):
    """{day_ordinal: array[[minute, o, h, l, c, v]]} regular hours only, split+dividend adjusted"""
    days, tok, n = defaultdict(list), None, 0
    while True:
        p = dict(symbols=sym, timeframe='1Min', start=start.isoformat(), end=end.isoformat(), limit=10000, feed='sip', adjustment='all')
        if tok: p['page_token'] = tok
        r = get(f'{DATA}/v2/stocks/bars', p)
        if r is None or not r.ok: log('minute error', sym, getattr(r, 'status_code', None), getattr(r, 'text', '')[:120]); break
        j = r.json(); n += 1
        for b in (j.get('bars') or {}).get(sym, []):
            t = datetime.fromisoformat(b['t'].replace('Z', '+00:00')).astimezone(ET); m = t.hour * 60 + t.minute
            if 570 <= m < 960: days[t.date().toordinal()].append((m, b['o'], b['h'], b['l'], b['c'], b['v']))
        tok = j.get('next_page_token')
        if n % 50 == 0: log('  minute pages', sym, n)
        if not tok: break
    return {d: np.array(v, dtype=float) for d, v in days.items()}

# ------------------------------------------------------------------ indicators
def sma(c, n):
    out = np.full(len(c), np.nan)
    if len(c) >= n:
        cs = np.cumsum(np.insert(c, 0, 0.0)); out[n - 1:] = (cs[n:] - cs[:-n]) / n
    return out

def rsi_wilder(c, n=2):
    out = np.full(len(c), np.nan); d = np.diff(c)
    if len(d) < n: return out
    up = np.where(d > 0, d, 0.0); dn = np.where(d < 0, -d, 0.0)
    au, ad = up[:n].mean(), dn[:n].mean()
    val = lambda a, b: 50.0 if a == 0 and b == 0 else (100.0 if b == 0 else 100 - 100 / (1 + a / b))
    out[n] = val(au, ad)
    for i in range(n, len(d)):
        au = (au * (n - 1) + up[i]) / n; ad = (ad * (n - 1) + dn[i]) / n; out[i + 1] = val(au, ad)
    return out

def signals(S):
    c = S['c']; s200 = sma(c, 200); s5 = sma(c, 5); r = rsi_wilder(c, 2)
    ent = (c > s200) & (r < 10); ex = c > s5
    return {int(d): (bool(e), bool(x)) for d, e, x in zip(S['d'], ent, ex) if not np.isnan(s200[np.searchsorted(S['d'], d)])}

# ------------------------------------------------------------------ portfolio simulator (daily)
def simulate(D, cal, sleeves, alloc, pooled=False, slip=SLIP, whole=False, delay=0, fill='open', skip=0.0, rng=None, max_hold=10):
    """sleeves: [(signal_sym, traded_sym)]. alloc: fraction of equity per position (single) or total cap (pooled).
    Signal at the close of day t -> order executes at day t+1+delay ('open' or 'close' price)."""
    idx = {s: {int(d): i for i, d in enumerate(D[s]['d'])} for s in {x for sl in sleeves for x in sl}}
    sig = {s: SIG[s] for s, _ in sleeves}
    cash = START_EQ; pos = {}                # sleeve -> dict(sh, px, ent_day, held, alloc_cost)
    pend_in, pend_out = defaultdict(list), defaultdict(list)
    waiting = set()                          # sleeves with an order pending
    E, INV, trades, skipped_small, missed_fill = [], [], [], 0, 0
    def price(sym, day, kind):
        i = idx[sym].get(day)
        return None if i is None else float(D[sym][kind][i])
    prev_E = START_EQ
    for t, day in enumerate(cal):
        # ---- orders at the open (or close when fill='close'): exits first, then entries
        for k in pend_out.pop(t, []):
            sym = sleeves[k][1]; px = price(sym, day, 'o' if fill == 'open' else 'c')
            if px is None: pend_out[t + 1].append(k); missed_fill += 1; continue
            p = pos.pop(k); sell = px * (1 - slip); gross = p['sh'] * sell; fee = gross * SEC_FEE
            cash += gross - fee
            trades.append(dict(sym=sym, sig=sleeves[k][0], ent=p['ent_day'], ex=day, ent_px=p['px'], ex_px=sell, sh=p['sh'],
                               pnl=gross - fee - p['cost'], ret=(gross - fee) / p['cost'] - 1, alloc=p['cost'] / p['eq'], held=p['held']))
            waiting.discard(k)
        new = pend_in.pop(t, [])
        if new:
            if fill == 'close':
                ready = [k for k in new if price(sleeves[k][1], day, 'c') is not None]
            else:
                ready = [k for k in new if price(sleeves[k][1], day, 'o') is not None]
            for k in new:
                if k not in ready: waiting.discard(k); missed_fill += 1
            inv_prev = sum(p['sh'] * (price(sleeves[k][1], cal[t - 1], 'c') or p['px']) for k, p in pos.items()) if t else 0.0
            for k in ready:
                sym = sleeves[k][1]; px = price(sym, day, 'o' if fill == 'open' else 'c'); buy = px * (1 + slip)
                if pooled:
                    room = alloc * prev_E - inv_prev; amt = max(0.0, room) / len(ready)
                else:
                    amt = alloc * prev_E
                amt = min(amt, cash * 0.999)
                sh = math.floor(amt / buy) if whole else amt / buy
                if sh <= 0 or sh * buy < 1.0:
                    skipped_small += 1; waiting.discard(k); continue
                cash -= sh * buy
                pos[k] = dict(sh=sh, px=buy, ent_day=day, held=0, cost=sh * buy, eq=prev_E)
                waiting.discard(k)
        # ---- mark to market at the close
        inv = 0.0
        for k, p in pos.items():
            c = price(sleeves[k][1], day, 'c'); p['last'] = c if c is not None else p.get('last', p['px']); inv += p['sh'] * p['last']
        eq = cash + inv; E.append(eq); INV.append(inv / eq if eq > 0 else 0); prev_E = eq
        # ---- decide after the close
        for k, (ssym, tsym) in enumerate(sleeves):
            s = sig[ssym].get(int(day))
            if s is None: continue
            e_sig, x_sig = s
            if k in pos and k not in waiting:
                pos[k]['held'] += 1
                if x_sig or pos[k]['held'] >= max_hold:
                    pend_out[t + 1 + delay].append(k); waiting.add(k)
            elif k in pos:
                pos[k]['held'] += 1
            elif k not in waiting and e_sig:
                if skip and rng.random() < skip: continue
                pend_in[t + 1 + delay].append(k); waiting.add(k)
    open_pos = [dict(sym=sleeves[k][1], ent=p['ent_day'], unrealized_pct=round((p['last'] / p['px'] - 1) * 100, 2)) for k, p in pos.items()]
    return dict(E=np.array(E), INV=np.array(INV), trades=trades, skipped_small=skipped_small, missed_fill=missed_fill, open=open_pos)

# ------------------------------------------------------------------ metrics
def boot_ci(x, fn, n=2000):
    if len(x) < 5: return None
    x = np.asarray(x); vals = [fn(x[RNG.integers(0, len(x), len(x))]) for _ in range(n)]
    vals = [v for v in vals if v is not None and np.isfinite(v)]
    return [round(float(np.percentile(vals, 2.5)), 4), round(float(np.percentile(vals, 97.5)), 4)] if vals else None

def pf_of(r):
    w = r[r > 0].sum(); l = -r[r <= 0].sum()
    return float(w / l) if l > 0 else None

def metrics(cal, sim, i0, i1, bench=None):
    """slice [i0, i1] of the calendar; equity base = close before i0"""
    E = sim['E']; base = E[i0 - 1] if i0 > 0 else START_EQ
    e = np.concatenate([[base], E[i0:i1 + 1]])
    d0 = date.fromordinal(int(cal[i0 - 1] if i0 > 0 else cal[i0])); d1 = date.fromordinal(int(cal[i1]))
    yrs = max((d1 - d0).days / 365.25, 1e-9)
    r = e[1:] / e[:-1] - 1; pk = np.maximum.accumulate(e); dd = float(((pk - e) / pk).max())
    months = defaultdict(float); last = {}
    for k in range(i0, i1 + 1):
        dd_ = date.fromordinal(int(cal[k])); last[(dd_.year, dd_.month)] = E[k]
    mk = sorted(last); mret = []; prev = base
    for m in mk: mret.append(last[m] / prev - 1); prev = last[m]
    tr = [t for t in sim['trades'] if cal[i0] <= t['ent'] <= cal[i1]]
    rr = np.array([t['ret'] for t in tr]) if tr else np.array([])
    pnl = np.array([t['pnl'] for t in tr]) if tr else np.array([])
    out = dict(start=str(date.fromordinal(int(cal[i0]))), end=str(d1), sessions=int(i1 - i0 + 1),
               total_ret_pct=round(float(e[-1] / base - 1) * 100, 2), cagr_pct=round(float((e[-1] / base) ** (1 / yrs) - 1) * 100, 2),
               max_dd_pct=round(dd * 100, 2), worst_day_pct=round(float(r.min()) * 100, 2) if len(r) else None,
               worst_month_pct=round(float(min(mret)) * 100, 2) if mret else None,
               sharpe=round(float(r.mean() / r.std() * math.sqrt(252)), 2) if len(r) > 2 and r.std() > 0 else None,
               exposure_pct=round(float((sim['INV'][i0:i1 + 1] > 0).mean()) * 100, 1),
               avg_invested_pct=round(float(sim['INV'][i0:i1 + 1].mean()) * 100, 1),
               trades=len(tr), win_rate_pct=round(float((rr > 0).mean()) * 100, 1) if len(rr) else None,
               pf_dollars=round(pf_of(pnl), 2) if len(pnl) and pf_of(pnl) else None,
               avg_win_pct=round(float(rr[rr > 0].mean()) * 100, 2) if (rr > 0).any() else None,
               avg_loss_pct=round(float(rr[rr <= 0].mean()) * 100, 2) if (rr <= 0).any() else None,
               mean_trade_pct=round(float(rr.mean()) * 100, 3) if len(rr) else None,
               mean_trade_ci95_pct=[round(x * 100, 3) for x in boot_ci(rr, lambda x: x.mean())] if len(rr) >= 5 else None,
               pf_ci95=boot_ci(rr, pf_of) if len(rr) >= 5 else None,
               avg_hold_sessions=round(float(np.mean([t['held'] for t in tr])), 1) if tr else None)
    if bench is not None:
        b = bench; bi = {int(d): k for k, d in enumerate(b['d'])}
        k0 = bi.get(int(cal[i0 - 1])) if i0 > 0 else bi.get(int(cal[i0])); k1 = bi.get(int(cal[i1]))
        if k0 is not None and k1 is not None:
            bc = b['c'][k0:k1 + 1]; bpk = np.maximum.accumulate(bc)
            out['bench_total_ret_pct'] = round(float(bc[-1] / bc[0] - 1) * 100, 2)
            out['bench_cagr_pct'] = round(float((bc[-1] / bc[0]) ** (1 / yrs) - 1) * 100, 2)
            out['bench_max_dd_pct'] = round(float(((bpk - bc) / bpk).max()) * 100, 2)
    return out

def periods(cal):
    i_tr1 = int(np.searchsorted(cal, CUT)) - 1
    P = {'full': (0, len(cal) - 1), 'train_<2024': (0, i_tr1), 'test_2024+': (i_tr1 + 1, len(cal) - 1)}
    yrs = sorted({date.fromordinal(int(d)).year for d in cal})
    for y in yrs:
        a = int(np.searchsorted(cal, date(y, 1, 1).toordinal())); b = int(np.searchsorted(cal, date(y + 1, 1, 1).toordinal())) - 1
        if b >= a: P[str(y)] = (a, b)
    return P

def report_sim(cal, sim, bench, years=False):
    out = {}
    for name, (a, b) in periods(cal).items():
        if not years and name[:2] == '20': continue
        out[name] = metrics(cal, sim, a, b, bench)
    out['skipped_too_small'] = sim['skipped_small']; out['missed_fills'] = sim['missed_fill']; out['open_at_end'] = sim['open']
    return out

# ------------------------------------------------------------------ 0. reproduce lab 2 exactly
def lab2_rsi2(S, thr=10, slip=0.0002, next_open=False, wilder=False, std_sma=False):
    c, o = S['c'], S['o']; T = []
    d = np.diff(c); up = np.where(d > 0, d, 0); dn = np.where(d < 0, -d, 0); W = rsi_wilder(c, 2)
    i = 201
    while i < len(c) - 2:
        if wilder: r = W[i]
        else:
            g = up[i - 2:i].mean(); l = dn[i - 2:i].mean(); r = 100 if l == 0 else 100 - 100 / (1 + g / l)
        trend = c[i] > (c[i - 199:i + 1].mean() if std_sma else c[i - 200:i].mean())
        if trend and r < thr:
            ent = o[i + 1] if next_open else c[i]; j = i + 1
            def above5(j): return c[j] > (c[j - 4:j + 1].mean() if std_sma else c[j - 5:j].mean())
            while j < len(c) - 2 and not above5(j) and j - i < 10: j += 1
            ex = o[j + 1] if next_open else c[j]
            T.append(dict(day=int(S['d'][i]), ret=ex / ent - 1 - 2 * slip)); i = (j + 1) if next_open else (j + 1)
        else: i += 1
    return T

def lab2_stats(T):
    if not T: return dict(trades=0)
    r = np.array([t['ret'] for t in T]); eq = START_EQ * np.cumprod(1 + r); pk = np.maximum.accumulate(np.concatenate([[START_EQ], eq]))
    w = r[r > 0].sum(); l = -r[r <= 0].sum()
    return dict(trades=len(r), win_rate=round(float((r > 0).mean() * 100), 1), pf=round(float(w / l), 2) if l > 0 else None,
                ret_pct=round(float(eq[-1] / START_EQ - 1) * 100, 1), max_dd_pct=round(float(((pk[1:] - eq) / pk[1:]).max() * 100), 1),
                first=str(date.fromordinal(T[0]['day'])), last=str(date.fromordinal(T[-1]['day'])))

def audit_steps(S):
    steps = [('as reported by lab 2 (same-close fills, simple RSI, 0.02% slip)', {}),
             ('+ fill at the NEXT OPEN instead of the signal close', dict(next_open=True)),
             ('+ standard Wilder RSI(2)', dict(next_open=True, wilder=True)),
             ('+ SMA200/SMA5 include today (standard)', dict(next_open=True, wilder=True, std_sma=True)),
             ('+ 0.05% slippage per side (canonical)', dict(next_open=True, wilder=True, std_sma=True, slip=SLIP))]
    out = []
    for name, kw in steps:
        T = lab2_rsi2(S, **kw)
        tr = [t for t in T if t['day'] < CUT]; te = [t for t in T if t['day'] >= CUT]
        out.append(dict(step=name, train=lab2_stats(tr), test=lab2_stats(te)))
    return out

# ------------------------------------------------------------------ C. intraday 10:00 -> 15:30
def at(Dm, minute, field, upto=5):
    """value of the first bar at or after `minute` (within `upto` minutes). field: 1=o 2=h 3=l 4=c"""
    k = int(np.searchsorted(Dm[:, 0], minute))
    if k < len(Dm) and Dm[k, 0] <= minute + upto: return float(Dm[k, field])
    return None

def intraday_test(M, full_days):
    days = sorted(M)
    res = {}
    rows = []
    for a, b in zip(days, days[1:]):
        if b not in full_days or b - a > 5: continue      # trade day must be a full day; prior day may be a half day
        A, B = M[a], M[b]
        if len(A) < 300 or len(B) < 300: continue
        pc = float(A[-1, 4]); p10 = None
        k = int(np.searchsorted(B[:, 0], 600)) - 1          # last bar that finished by 10:00 (the 9:59 bar)
        if k >= 0 and B[k, 0] >= 595: p10 = float(B[k, 4])
        if p10 is None: continue
        close = at(B, 959, 4, 0)
        if close is None: continue
        R = p10 / pc - 1
        row = dict(day=b, R=R, close=close)
        for dl in range(6):
            row[f'o{dl}'] = at(B, 930 + dl, 1, 0); row[f'h{dl}'] = at(B, 930 + dl, 2, 0); row[f'l{dl}'] = at(B, 930 + dl, 3, 0)
        rows.append(row)
    half_spread = 0.005           # SPY quotes are a penny wide: pay half a cent each side, plus 0.01% slippage
    def trade_ret(row, dl, mode, worst):
        o = row[f'o{dl}']
        if o is None: return None
        d = 1 if row['R'] > 0 else (-1 if row['R'] < 0 else 0)
        if mode == 'long_only' and d < 0: return 0.0
        if mode == 'always_long': d = 1
        if d == 0: return 0.0
        if worst: ent = row[f'h{dl}'] if d == 1 else row[f'l{dl}']
        else: ent = o
        ent = ent + d * half_spread; ent *= 1 + d * 0.0001
        ex = row['close'] - d * half_spread; ex *= 1 - d * 0.0001
        return (ex - ent) / ent * d - SEC_FEE           # SEC fee on the one sell (exit for longs, entry for shorts)
    for mode in ('long_short', 'long_only', 'always_long'):
        for worst in (False, True):
            for dl in range(6):
                rr = [(row['day'], trade_ret(row, dl, mode, worst)) for row in rows]
                missed = sum(1 for _, r in rr if r is None); rr = [(d, r) for d, r in rr if r is not None]
                key = f'{mode}|{"worst_in_bar" if worst else "bar_open"}|delay{dl}'
                res[key] = dict(missed=missed)
                for pname, f in (('2016-2023', lambda d: d < CUT), ('2024+', lambda d: d >= CUT), ('all', lambda d: True)):
                    x = np.array([r for d, r in rr if f(d)]); nz = x[x != 0]
                    if not len(x): continue
                    eq = np.cumprod(1 + x); pk = np.maximum.accumulate(np.concatenate([[1], eq]))
                    res[key][pname] = dict(days=len(x), trades=int(len(nz)), mean_bp=round(float(nz.mean()) * 1e4, 2) if len(nz) else None,
                                           t_stat=round(float(nz.mean() / nz.std() * math.sqrt(len(nz))), 2) if len(nz) > 2 and nz.std() > 0 else None,
                                           pf=round(pf_of(nz), 2) if len(nz) and pf_of(nz) else None, win_pct=round(float((nz > 0).mean()) * 100, 1) if len(nz) else None,
                                           total_ret_pct=round(float(eq[-1] - 1) * 100, 2), max_dd_pct=round(float(((pk[1:] - eq) / pk[1:]).max()) * 100, 2),
                                           mean_ci95_bp=[round(v * 1e4, 2) for v in boot_ci(nz, lambda z: z.mean())] if len(nz) >= 5 else None)
    by_year = {}
    for row in rows:
        r = trade_ret(row, 0, 'long_short', False)
        if r is None: continue
        y = date.fromordinal(row['day']).year; by_year.setdefault(y, []).append(r)
    res['long_short|bar_open|delay0|by_year'] = {str(y): dict(days=len(v), mean_bp=round(float(np.mean([x for x in v if x] or [0])) * 1e4, 2), total_ret_pct=round(float(np.prod(1 + np.array(v)) - 1) * 100, 2)) for y, v in sorted(by_year.items())}
    res['sample_days'] = len(rows)
    return res

# ------------------------------------------------------------------ O. executable overnight
def overnight_test(M, S, full_days):
    di = {int(d): k for k, d in enumerate(S['d'])}; days = sorted(M)
    out = {}
    for variant in ('lab2_signal_at_close', 'executable_1550_decision'):
        rr = []
        for a, b in zip(days, days[1:]):
            if a not in full_days: continue
            A = M[a]; ka, kb = di.get(a), di.get(b)
            if ka is None or kb is None or ka == 0 or len(A) < 300: continue
            prev = S['c'][ka - 1]; close = S['c'][ka]
            if variant == 'lab2_signal_at_close': down = close < prev
            else:
                p = at(A, 949, 4, 0)
                if p is None: continue
                down = p < prev
            if not down: continue
            ret = S['o'][kb] * (1 - SLIP) / (close * (1 + SLIP)) - 1 - SEC_FEE
            rr.append((a, ret))
        for pname, f in (('2016-2023', lambda d: d < CUT), ('2024+', lambda d: d >= CUT)):
            x = np.array([r for d, r in rr if f(d)])
            if not len(x): continue
            eq = np.cumprod(1 + x); pk = np.maximum.accumulate(np.concatenate([[1], eq]))
            out.setdefault(variant, {})[pname] = dict(trades=len(x), pf=round(pf_of(x), 2) if pf_of(x) else None, mean_bp=round(float(x.mean()) * 1e4, 2),
                                                      total_ret_pct=round(float(eq[-1] - 1) * 100, 2), max_dd_pct=round(float(((pk[1:] - eq) / pk[1:]).max()) * 100, 2))
    return out

# ------------------------------------------------------------------ R. risk of ruin
def ruin(daily_r, horizons=(21, 252), paths=None, block=10, mult=1.0):
    paths = paths or MC_PATHS; r = np.asarray(daily_r) * mult; n = len(r); out = {}
    for h in horizons:
        hit = {25: 0, 50: 0, 100: 0}; ends = []; x32 = 0
        for _ in range(paths):
            seq = []
            while len(seq) < h:
                s = int(RNG.integers(0, n)); seq.extend(r[s:s + block].tolist() if s + block <= n else r[s:].tolist())
            seq = np.maximum(np.array(seq[:h]), -1.0)
            eq = np.cumprod(1 + seq); mn = eq.min()
            if mn <= 0.75: hit[25] += 1
            if mn <= 0.50: hit[50] += 1
            if mn <= 0.01: hit[100] += 1
            if eq[-1] >= 32: x32 += 1
            ends.append(eq[-1])
        ends = np.array(ends)
        out[f'{h}_sessions'] = dict(p_drawdown_25pct=round(hit[25] / paths * 100, 2), p_drawdown_50pct=round(hit[50] / paths * 100, 2),
                                    p_ruin_99pct=round(hit[100] / paths * 100, 2), p_reach_32x=round(x32 / paths * 100, 3),
                                    end_equity_p5=round(float(np.percentile(ends, 5)) * START_EQ, 0), end_equity_median=round(float(np.median(ends)) * START_EQ, 0),
                                    end_equity_p95=round(float(np.percentile(ends, 95)) * START_EQ, 0), paths=paths)
    return out

# ------------------------------------------------------------------ D. options data probe
def probe_options():
    out = {}
    tests = {'historical_quotes': f'{DATA}/v1beta1/options/quotes', 'historical_bars': f'{DATA}/v1beta1/options/bars',
             'historical_trades': f'{DATA}/v1beta1/options/trades'}
    sym = 'SPY250117C00600000'
    for k, url in tests.items():
        p = dict(symbols=sym, start='2024-12-02', end='2024-12-03', limit=5)
        if k == 'historical_bars': p['timeframe'] = '1Day'
        r = get(url, p)
        out[k] = dict(status=getattr(r, 'status_code', None), sample=(r.text[:200] if r is not None else None))
    q = out['historical_quotes']['status']
    out['verdict'] = ('Historical option QUOTES are available - spread test could be run in a later lab.' if q == 200 and '"quotes"' in (out['historical_quotes']['sample'] or '')
                      else 'No historical option quotes (bid/ask) from this data source. Per the rules, the 45-60 DTE call-spread test is NOT run; '
                           'trade-based bars or modeled prices are not executable fills.')
    return out

# ------------------------------------------------------------------ main
SIG = {}

def main():
    t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    end = datetime.now(ET).date()
    r = get(f'{TRADE}/v2/calendar', dict(start=str(DATA_START), end=str(end - timedelta(days=1))))
    calj = r.json() if r is not None and r.ok else []
    tdays = {date.fromisoformat(c['date']).toordinal(): c.get('close', '16:00') for c in calj}
    full_days = {d for d, c in tdays.items() if str(c).startswith('16')}
    log('calendar days', len(tdays), 'half days', len(tdays) - len(full_days))
    s0 = datetime.combine(DATA_START, datetime.min.time(), ET); s1 = datetime.combine(end, datetime.min.time(), ET)
    D = {}
    for s in ETFS + list(LEVMAP.values()):
        x = fetch_daily(s, s0, s1)
        if x is not None: D[s] = x
        log('daily', s, 0 if x is None else len(x['d']))
    # ---- data audit
    dq = {}
    for s, x in D.items():
        dd = x['d']; miss = sorted(set(d for d in tdays if dd[0] <= d <= dd[-1]) - set(dd.tolist()))
        extra = sorted(set(dd.tolist()) - set(tdays))
        jumps = int((np.abs(np.diff(np.log(x['c']))) > 0.15).sum())
        dq[s] = dict(first=str(date.fromordinal(int(dd[0]))), last=str(date.fromordinal(int(dd[-1]))), bars=len(dd),
                     missing_trading_days=len(miss), missing_sample=[str(date.fromordinal(m)) for m in miss[:5]], non_trading_day_bars=len(extra),
                     duplicate_days=int(len(dd) - len(set(dd.tolist()))), bad_prices=int((x['c'] <= 0).sum() + (x['h'] < x['l']).sum()),
                     daily_moves_over_15pct=jumps)
    for s in D: SIG[s] = signals(D[s])
    cal = D['SPY']['d'][D['SPY']['d'] < end.toordinal()]
    first_sig = int(min(SIG['SPY'])); cal = cal[cal >= first_sig]          # start once SMA200 exists
    log('calendar', date.fromordinal(int(cal[0])), '->', date.fromordinal(int(cal[-1])), len(cal), 'sessions')
    R = dict(updated=datetime.now(ET).isoformat(timespec='seconds'), data_quality=dq,
             calendar=dict(first_tradable=str(date.fromordinal(int(cal[0]))), last=str(date.fromordinal(int(cal[-1]))), sessions=len(cal),
                           train=f'{date.fromordinal(int(cal[0]))} -> 2023-12-29', test=f'2024-01-02 -> {date.fromordinal(int(cal[-1]))}'),
             assumptions=dict(slippage_per_side_pct=SLIP * 100, sec_fee_on_sells=SEC_FEE, prices='Alpaca SIP daily bars, adjustment=all (splits + dividends)',
                              cash_return='0% (uninvested cash earns nothing)', equity=START_EQ,
                              returns='total_ret_pct = cumulative return on TOTAL account equity over the period; cagr_pct annualized; '
                                      'mean_trade_pct = per invested dollar'))
    # ---- 0 audit
    R['audit_reproduction'] = {s: audit_steps(D[s]) for s in ('SPY', 'QQQ')}
    log('audit done', round(time.time() - t0))
    # ---- 1 canonical
    C = {}; daily_r = {}
    for s in ('SPY', 'QQQ'):
        for a in (0.25, 0.5, 1.0):
            sim = simulate(D, cal, [(s, s)], a)
            C[f'{s} {int(a * 100)}% fractional'] = report_sim(cal, sim, D[s], years=(a == 1.0))
            if a == 1.0:
                daily_r[s] = sim['E'][1:] / sim['E'][:-1] - 1
                C[f'{s} 100% fractional']['trade_list'] = [dict(sym=t['sym'], entry=str(date.fromordinal(t['ent'])), exit=str(date.fromordinal(t['ex'])),
                                                                 ret_pct=round(t['ret'] * 100, 2), held=t['held']) for t in sim['trades']]
        for a in (0.5, 1.0):
            sim = simulate(D, cal, [(s, s)], a, whole=True)
            C[f'{s} {int(a * 100)}% whole shares ($2,500 start)'] = report_sim(cal, sim, D[s])
    R['canonical'] = C
    log('canonical done', round(time.time() - t0))
    # ---- 2 combined
    Cb = {}
    for cap in (0.5, 1.0):
        sim = simulate(D, cal, [('SPY', 'SPY'), ('QQQ', 'QQQ')], cap, pooled=True)
        Cb[f'SPY+QQQ pooled cap {int(cap * 100)}%'] = report_sim(cal, sim, D['SPY'])
        if cap == 0.5: daily_r['combo50'] = sim['E'][1:] / sim['E'][:-1] - 1
        if cap == 1.0: daily_r['combo100'] = sim['E'][1:] / sim['E'][:-1] - 1
    a, b = daily_r['SPY'], daily_r['QQQ']; m = (a != 0) | (b != 0)
    s1_ = simulate(D, cal, [('SPY', 'SPY')], 1.0); s2_ = simulate(D, cal, [('QQQ', 'QQQ')], 1.0)
    both = float(((s1_['INV'] > 0) & (s2_['INV'] > 0)).sum()); either = float(((s1_['INV'] > 0) | (s2_['INV'] > 0)).sum())
    Cb['correlation'] = dict(daily_strategy_return_corr=round(float(np.corrcoef(a[m], b[m])[0, 1]), 3) if m.sum() > 10 else None,
                             pct_of_invested_days_both_in=round(both / either * 100, 1) if either else None,
                             spy_qqq_price_return_corr=round(float(np.corrcoef(np.diff(np.log(D['SPY']['c'][-2000:])), np.diff(np.log(D['QQQ']['c'][-2000:])))[0, 1]), 3))
    R['combined'] = Cb
    # ---- 3 stress
    St = {}
    for s in ('SPY', 'QQQ'):
        base = metrics(cal, simulate(D, cal, [(s, s)], 1.0), 0, len(cal) - 1, D[s])
        row = {'base (0.05%, next open)': base}
        for sl in (0.001, 0.0025):
            row[f'slippage {sl * 100:.2f}%'] = metrics(cal, simulate(D, cal, [(s, s)], 1.0, slip=sl), 0, len(cal) - 1, D[s])
        row['fills one session late'] = metrics(cal, simulate(D, cal, [(s, s)], 1.0, delay=1), 0, len(cal) - 1, D[s])
        row['fills at next CLOSE'] = metrics(cal, simulate(D, cal, [(s, s)], 1.0, fill='close'), 0, len(cal) - 1, D[s])
        for sk in (0.10, 0.25):
            vals = []
            for k in range(200):
                rng = np.random.default_rng(1000 + k)
                vals.append(metrics(cal, simulate(D, cal, [(s, s)], 1.0, skip=sk, rng=rng), 0, len(cal) - 1)['total_ret_pct'])
            row[f'{int(sk * 100)}% of signals missed (200 runs)'] = dict(total_ret_p5=round(float(np.percentile(vals, 5)), 2),
                                                                        total_ret_median=round(float(np.median(vals)), 2), total_ret_p95=round(float(np.percentile(vals, 95)), 2))
        St[s] = {k: ({kk: v[kk] for kk in ('total_ret_pct', 'cagr_pct', 'max_dd_pct', 'trades', 'pf_dollars')} if 'total_ret_pct' in v else v) for k, v in row.items()}
    R['stress'] = St
    log('stress done', round(time.time() - t0))
    # ---- A ETF universe
    A = {}
    for s in ETFS:
        if s not in D: A[s] = dict(note='no data'); continue
        sim = simulate(D, cal, [(s, s)], 0.5)
        A[s] = report_sim(cal, sim, D[s])
    sl = [(s, s) for s in ETFS if s in D]
    sim = simulate(D, cal, sl, 0.5, pooled=True)
    A['POOLED 13 ETFs, cap 50%'] = report_sim(cal, sim, D['SPY'], years=True)
    daily_r['etf_pool'] = sim['E'][1:] / sim['E'][:-1] - 1
    R['etf_universe'] = A
    # ---- B leveraged
    Bv = {}
    for s, L in LEVMAP.items():
        if L not in D: Bv[L] = dict(note='no data'); continue
        for a in (0.25, 0.5, 1.0):
            sim = simulate(D, cal, [(s, L)], a / 2)
            rep = report_sim(cal, sim, D[L])
            gaps = []; li = {int(d): k for k, d in enumerate(D[L]['d'])}
            for t in sim['trades']:
                k0, k1 = li[t['ent']], li[t['ex']]
                g = [D[L]['o'][k] / D[L]['c'][k - 1] - 1 for k in range(k0 + 1, k1 + 1)]
                if g: gaps.append(min(g))
            rets = np.array([t['ret'] for t in sim['trades']])
            rep['worst_overnight_gap_while_held_pct'] = round(float(min(gaps)) * 100, 2) if gaps else None
            rep['trade_ret_p5_pct'] = round(float(np.percentile(rets, 5)) * 100, 2) if len(rets) else None
            rep['worst_trade_pct'] = round(float(rets.min()) * 100, 2) if len(rets) else None
            r_ = sim['E'][1:] / sim['E'][:-1] - 1
            rep['annual_vol_pct'] = round(float(r_.std() * math.sqrt(252)) * 100, 2)
            Bv[f'{s} signal -> {L} at {a * 50:.1f}% (half of {int(a * 100)}%)'] = rep
            un = simulate(D, cal, [(s, s)], a)
            rets_u = np.array([t['ret'] for t in un['trades']])
            Bv[f'{s} signal -> {L} at {a * 50:.1f}% (half of {int(a * 100)}%)']['same_signal_unleveraged_worst_trade_pct'] = round(float(rets_u.min()) * 100, 2) if len(rets_u) else None
    R['leveraged'] = Bv
    log('leveraged done', round(time.time() - t0))
    # ---- D options probe
    R['options_probe'] = probe_options()
    # ---- C + O need minute data
    if not SKIP_MIN:
        Mn = {}
        for s in ('SPY', 'QQQ'):
            Mn[s] = fetch_minutes(s, datetime.combine(date(2016, 1, 1), datetime.min.time(), ET), s1)
            log('minutes', s, len(Mn[s]), 'days', round(time.time() - t0), 's')
        R['intraday_10am_to_330'] = intraday_test(Mn['SPY'], full_days)
        R['overnight_after_down_day'] = {s: overnight_test(Mn[s], D[s], full_days) for s in ('SPY', 'QQQ')}
        del Mn
    log('intraday done', round(time.time() - t0))
    # ---- R risk of ruin
    Rk = {}
    for name, key in (('SPY RSI2 100% of equity', 'SPY'), ('QQQ RSI2 100% of equity', 'QQQ'), ('SPY+QQQ pooled cap 50%', 'combo50'),
                      ('SPY+QQQ pooled cap 100%', 'combo100'), ('13-ETF pool cap 50%', 'etf_pool')):
        Rk[name] = ruin(daily_r[key])
    Rk['LOTTERY (hypothetical): SPY+QQQ cap 100% daily returns x10, like deep-leverage options'] = ruin(daily_r['combo100'], mult=10.0)
    Rk['note'] = ('Block bootstrap (10-session blocks) of this strategy\'s own historical daily account returns, 2016-2026. '
                  'Assumes the future looks like a reshuffled past; real crashes can be worse. 32x needs ~17.9% per session for 21 sessions.')
    R['risk_of_ruin'] = Rk
    R['trials'] = dict(prior=PRIOR_TRIALS, prior_total=sum(PRIOR_TRIALS.values()),
                       this_lab_pre_registered=['canonical RSI2 SPY', 'canonical RSI2 QQQ', 'ETF universe pooled', 'SSO/QLD', '10:00->15:30 SPY', 'overnight executable'],
                       note='The 2024+ daily test was seen once in lab 2 when choosing threshold 10 over 5 (2 thresholds x 2 symbols). '
                            'April-November 2026 intraday results are selection-contaminated: lab 1 -> lab 2 changes were made after seeing them.')
    R['seconds'] = round(time.time() - t0)
    json.dump(R, open(f'{OUT}/lab3.json', 'w'), separators=(',', ':'), default=str)
    open(f'{OUT}/lab3_report.md', 'w').write(markdown(R))
    log(json.dumps(dict(event='lab3_done', seconds=R['seconds'])))
    publish()

def markdown(R):
    L = [f"# Vantex lab 3 — {R['updated']}", '', f"Calendar: {R['calendar']}", '', '## Audit reproduction (lab 2 RSI2)']
    for s, steps in R['audit_reproduction'].items():
        L.append(f'### {s}'); L.append('| step | train trades | train PF | train ret | test trades | test PF | test ret | test maxDD |'); L.append('|---|---|---|---|---|---|---|---|')
        for x in steps:
            a, b = x['train'], x['test']
            L.append(f"| {x['step']} | {a.get('trades')} | {a.get('pf')} | {a.get('ret_pct')}% | {b.get('trades')} | {b.get('pf')} | {b.get('ret_pct')}% | {b.get('max_dd_pct')}% |")
    def tbl(title, D):
        L.append(f'## {title}'); L.append('| run | period | trades | total ret | CAGR | maxDD | PF $ | win | exposure | bench ret | bench CAGR | bench maxDD |'); L.append('|---|---|---|---|---|---|---|---|---|---|---|---|')
        for k, v in D.items():
            if not isinstance(v, dict): continue
            for p in ('full', 'train_<2024', 'test_2024+'):
                m = v.get(p)
                if not m: continue
                L.append(f"| {k} | {p} {m['start']}→{m['end']} | {m['trades']} | {m['total_ret_pct']}% | {m['cagr_pct']}% | {m['max_dd_pct']}% | {m['pf_dollars']} | {m['win_rate_pct']}% | {m['exposure_pct']}% | {m.get('bench_total_ret_pct')}% | {m.get('bench_cagr_pct')}% | {m.get('bench_max_dd_pct')}% |")
    tbl('Canonical RSI(2)', R['canonical']); tbl('SPY + QQQ combined', R['combined']); tbl('ETF universe', R['etf_universe']); tbl('Leveraged (SSO/QLD)', R['leveraged'])
    L.append('## Stress'); L.append('```'); L.append(json.dumps(R['stress'], indent=1)); L.append('```')
    if 'intraday_10am_to_330' in R:
        L.append('## Intraday 10:00 → 15:30 SPY'); L.append('| version | period | days | trades | mean bp | t | PF | total ret | maxDD |'); L.append('|---|---|---|---|---|---|---|---|---|')
        for k, v in R['intraday_10am_to_330'].items():
            if '|delay' not in k or k.endswith('by_year'): continue
            for p in ('2016-2023', '2024+'):
                m = v.get(p)
                if m: L.append(f"| {k} | {p} | {m['days']} | {m['trades']} | {m['mean_bp']} | {m['t_stat']} | {m['pf']} | {m['total_ret_pct']}% | {m['max_dd_pct']}% |")
        L.append('## Overnight after a down day'); L.append('```'); L.append(json.dumps(R['overnight_after_down_day'], indent=1)); L.append('```')
    L.append('## Options data probe'); L.append(R['options_probe']['verdict'])
    L.append('## Risk of ruin'); L.append('```'); L.append(json.dumps(R['risk_of_ruin'], indent=1)); L.append('```')
    L.append('## Trials'); L.append('```'); L.append(json.dumps(R['trials'], indent=1)); L.append('```')
    L.append('## Data quality'); L.append('```'); L.append(json.dumps(R['data_quality'], indent=1)); L.append('```')
    return '\n'.join(L) + '\n'

def publish():
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', 'live-lab3', OUT], check=True)
    subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', 'lab3'], check=True)
    subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{REPO}.git', 'live-lab3'], check=True, timeout=120, capture_output=True)

if __name__ == '__main__':
    main()
