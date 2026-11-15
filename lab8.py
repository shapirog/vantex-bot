"""
Vantex lab 8 - ONE locked tiny-float pullback rule (ChatGPT spec, 2026-11-15). Research/paper only, places NO orders.

  python lab8.py history    exploratory replay, Sep 2025 -> Nov 13 2026 (already seen while building labs 5-7; NOT a holdout)
  python lab8.py forward    locked forward paper test: every completed session AFTER 2026-11-13, appended day by day

LOCKED RULE (no sweeps, no "best variant")
Universe   US common stocks (NASDAQ/NYSE/AMEX; ETFs, funds, warrants, rights, units, preferreds, OTC excluded),
           prior raw close $0.50-$20, shares outstanding <= 5,000,000 from the latest SEC filing filed BEFORE the
           session (shares-outstanding proxy, NOT true float), >= 20 prior daily bars. Split ex-dates excluded.
Alert      first premarket 1-minute bar ending by 9:25 ET with close >= +3% vs prior close AND cumulative premarket
           volume >= 3x the median of the prior 20 sessions' cumulative premarket volume at the same minute
           (prior sessions with no prints count as 0 volume; split-adjusted). One trade max per symbol per session.
Entry      1-minute bars 9:35-10:29 (ending by 10:30): first a 1-minute CLOSE above the premarket high, then a later
           bar whose LOW touches session VWAP (from 9:30), then the FIRST 1-minute close back above VWAP (can be the
           touching bar). Only that first reclaim counts (one shot). It must have volume >= 2x the median of the
           prior five 1-minute bars (missing minutes = 0) and close <= VWAP x 1.10.
Fill       first valid SIP quote timestamped AFTER the signal bar's end and <= 1 second after it, at ask + 0.5%.
           Skip if spread > 1.5% of mid or displayed ask size < intended shares.
Stop       lower of the pullback low and entry - 1.5 x ATR(14) on completed 5-minute bars (clock-aligned, incl.
           premarket, >= 3 bars). Skip if the stop is > 8% below entry.
Size       risk 0.25% of current paper equity at the stop, notional <= $500, whole shares, cash only.
Exit       +2R: sell half. Remaining shares: initial stop until then; after that, trail at the lowest low of the
           prior two completed 5-minute bars (ratchets up only). Anything left exits at 15:45.
           Exit decisions are made on SIP quotes: a stop/target triggers on the first quote whose BID crosses it;
           the fill is that bid - 0.5% (so gaps/halts fill at the real reopening bid, never at the stop price).
           Time exit: first valid bid after 15:45:00 - 0.5%. Fees: date-correct SEC Section 31 + FINRA TAF on sells.
           If quotes are missing for a minute that may have crossed both levels: stop first (counted as ambiguous).
Comparison Lab 5's locked rule (5-min breakout above VWAP + premarket/consolidation high, stop = min(candle low, VWAP),
           half at 2R, trail prior 5-min low - 1c, flat 15:45) on the SAME alerts, fills, filters, costs and 0.25% sizing.
Stress     (a) slippage 1.0% instead of 0.5% each side; (b) halt/gap stress: exits that came right after a >= 5-minute
           gap in prints (possible halt) or that gapped > 1% through the stop get a further -10%; (c) both.
Stats      day-clustered bootstrap (resample whole sessions with replacement, 5,000 resamples) for mean R.
Results    history -> branch 'live-lab8'; forward -> branch 'live-lab8-forward'.
"""
import json, math, os, subprocess, sys, time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

import numpy as np

MODE = sys.argv[1] if len(sys.argv) > 1 else 'history'
sys.argv = [sys.argv[0], '300']
import lab5 as L5
import lab6 as L6

ET = L5.ET; DATA, TRADE = L5.DATA, L5.TRADE; get, log = L5.get, L5.log
OUT = os.environ.get('VANTEX_LAB8_DIR', '/tmp/vantex-lab8')
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
BRANCH = 'live-lab8' if MODE == 'history' else 'live-lab8-forward'

HIST_FIRST, HIST_LAST, FWD_AFTER = date(2025, 9, 4), date(2026, 11, 13), date(2026, 11, 13)
PMIN, PMAX, SH_MAX, MIN_HIST = 0.50, 20.0, 5_000_000, 20
UP, RVOL, BASE_N, ALERT_END = 0.03, 3.0, 20, 565
WIN0, WIN1 = 575, 630
VOL_MULT, MAX_EXT, MAX_SPREAD, STALE_NS = 2.0, 0.10, 0.015, 1_000_000_000
ATR_N, ATR_K, MAX_STOP = 14, 1.5, 0.08
RISK, CAP, EQUITY = 0.0025, 500.0, 2500.0
SLIP, FLAT = 0.005, 945
SIZE_SHARES_FROM = date(2025, 11, 3)             # SIP quote sizes switched from round lots to shares on this date
BOOT = 5000
STATS = Counter()

def sec_fee(d):
    if d < date(2025, 5, 14): return 27.80e-6
    if d < date(2026, 4, 4): return 0.0
    return 20.60e-6
def taf(d):
    return {2025: (0.000166, 8.30), 2026: (0.000195, 9.79)}.get(d.year, (0.000232, 11.61))

def ns_of(d, minute, sec=0.0):
    return int(datetime.combine(d, datetime.min.time(), ET).timestamp() * 1e9) + int((minute * 60 + sec) * 1e9)
def iso(ns): return datetime.fromtimestamp(ns / 1e9, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'
def parse_ns(s):
    s = s.replace('+00:00', '').rstrip('Z')
    base, frac = (s.split('.') + ['0'])[:2]
    return int(datetime.fromisoformat(base).replace(tzinfo=timezone.utc).timestamp()) * 10**9 + int((frac + '000000000')[:9])
def hm(ns, d):
    return datetime.fromtimestamp(ns / 1e9, timezone.utc).astimezone(ET).strftime('%H:%M:%S.%f')[:-3]

# ------------------------------------------------------------------ data
def quotes(sym, d, a_ns, b_ns):
    """valid SIP quotes with a_ns < t <= b_ns -> list of (t_ns, bid, bid_size_sh, ask, ask_size_sh)"""
    out, tok = [], None
    mult = 100 if d < SIZE_SHARES_FROM else 1
    for _ in range(40):
        p = dict(symbols=sym, start=iso(a_ns), end=iso(b_ns + 1000), limit=10000, feed='sip')
        if tok: p['page_token'] = tok
        r = get(f'{DATA}/v2/stocks/quotes', p)
        if r is None or not r.ok: STATS['quote_errors'] += 1; break
        j = r.json()
        for q in ((j.get('quotes') or {}).get(sym) or []):
            t = parse_ns(q['t'])
            if not (a_ns < t <= b_ns): continue
            bp, ap = q.get('bp') or 0, q.get('ap') or 0
            if bp > 0 and ap > bp: out.append((t, bp, (q.get('bs') or 0) * mult, ap, (q.get('as') or 0) * mult))
            else: STATS['quotes_invalid_locked_crossed_or_zero'] += 1
        tok = j.get('next_page_token')
        if not tok: break
    STATS['quote_requests'] += 1
    return out

def minutes_range(sym, d0, d1):
    """{day ordinal: array[min,o,h,l,c,v]} 4:00-20:00 raw SIP 1-minute bars"""
    out, tok = defaultdict(list), None
    while True:
        p = dict(symbols=sym, timeframe='1Min', start=datetime.combine(d0, datetime.min.time(), ET).isoformat(),
                 end=datetime.combine(d1 + timedelta(days=1), datetime.min.time(), ET).isoformat(), limit=10000, feed='sip', adjustment='raw')
        if tok: p['page_token'] = tok
        r = get(f'{DATA}/v2/stocks/bars', p)
        if r is None or not r.ok: STATS['minute_errors'] += 1; break
        j = r.json()
        for b in ((j.get('bars') or {}).get(sym) or []):
            t = L5.to_et(b['t']); out[t.date().toordinal()].append((t.hour * 60 + t.minute, b['o'], b['h'], b['l'], b['c'], b['v']))
        tok = j.get('next_page_token')
        if not tok: break
    return {k: np.array(v, dtype=float) for k, v in out.items()}

def premarket_cum(A):
    """cumulative premarket volume known at minute ends 241..565 (index t-241)"""
    v = np.zeros(325)
    if A is not None and len(A):
        pm = A[(A[:, 0] >= 240) & (A[:, 0] < 565)]
        np.add.at(v, (pm[:, 0] - 240).astype(int), pm[:, 5])
    return np.cumsum(v)

def five_min(A):
    C = {}
    for m, o, h, l, c, v in A:
        b = int(m) // 5 * 5
        if b not in C: C[b] = [o, h, l, c, v]
        else: x = C[b]; x[1] = max(x[1], h); x[2] = min(x[2], l); x[3] = c; x[4] += v
    return C

def atr_at(C, t):
    ks = [b for b in sorted(C) if b + 5 <= t]
    if len(ks) < 3: return None
    tr = []
    for i in range(1, len(ks)):
        o, h, l, c, v = C[ks[i]]; pc = C[ks[i - 1]][3]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    return float(np.mean(tr[-ATR_N:])) if tr else None

def vwap_series(A):
    """{minute: vwap through that minute} from 9:30"""
    V, pv, vv = {}, 0.0, 0.0
    for m, o, h, l, c, v in A[A[:, 0] >= 570]:
        pv += (h + l + c) / 3 * v; vv += v; V[int(m)] = pv / vv if vv else c
    return V

# ------------------------------------------------------------------ signals (bar data only, decision at the bar's end)
def signal_new(A, pmh):
    V = vwap_series(A); bars = {int(r[0]): r for r in A}
    broke = pulled = False; pull_low = math.inf
    for m in range(WIN0, WIN1):
        r = bars.get(m)
        if r is None: continue
        _, o, h, l, c, v = r; vw = V[m]
        if not broke:
            if c > pmh: broke = True
            continue
        if not pulled and l <= vw: pulled = True
        if pulled:
            pull_low = min(pull_low, l)
            if c > vw:
                prior = [bars[k][5] if k in bars else 0.0 for k in range(m - 5, m)]
                if v < VOL_MULT * float(np.median(prior)): return None, 'reclaim volume < 2x median of prior five 1-min bars', m + 1
                if c > vw * (1 + MAX_EXT): return None, 'signal close > 10% above VWAP', m + 1
                return dict(t=m + 1, vwap=vw, pull_low=pull_low, close=c, vol=v, med5=float(np.median(prior))), None, m + 1
    return None, ('never broke premarket high in window' if not broke else 'no VWAP pullback' if not pulled else 'no close back above VWAP'), None

def signals_lab5(A, pmh):
    """lab 5 candidates in time order (each later one is used only if an earlier one was 'too extended')"""
    V = vwap_series(A); C = five_min(A); out = []
    for b in range(570, 905, 5):
        if b not in C: continue
        o, h, l, c, v = C[b]; vw = V.get(max([k for k in V if k <= b + 4], default=-1))
        if vw is None or c <= vw: continue
        prev = C.get(b - 5); level = None
        if pmh and c > pmh and (prev is None or prev[3] <= pmh): level = pmh
        else:
            pr = [C.get(b - 5 * j) for j in range(1, 7)]
            if all(p is not None for p in pr):
                hh = max(p[1] for p in pr); ll = min(p[2] for p in pr)
                if ll > 0 and (hh - ll) / ll <= 0.06 and c > hh: level = hh
        if level is None: continue
        pv5 = [C[b - 5 * j][4] if (b - 5 * j) in C else 0.0 for j in range(1, 6)]
        if v < 2.0 * float(np.median(pv5)): continue
        out.append(dict(t=b + 5, vwap=vw, stop=min(l, vw)))
    return out

# ------------------------------------------------------------------ execution on quotes
def entry_quote(sym, d, t_min):
    T = ns_of(d, t_min)
    Q = quotes(sym, d, T, T + 2 * STALE_NS)
    if not Q: return None, 'no quote within 2s after signal'
    q = Q[0]
    if q[0] - T > STALE_NS: return None, f'first quote {round((q[0] - T) / 1e6)} ms after signal (> 1 s)'
    return dict(t_ns=q[0], age_ms=round((q[0] - T) / 1e6, 1), bid=q[1], bid_sz=q[2], ask=q[3], ask_sz=q[4], spread_pct=round((q[3] - q[1]) / ((q[3] + q[1]) / 2) * 100, 3)), None

def run_exits(sym, d, A, te_ns, entry, stop, trail_n, trail_off):
    """returns legs [(fraction, raw bid, t_ns, why, flags)], counters"""
    risk = entry - stop; target = entry + 2 * risk; S = stop; half = False; legs = []; cnt = Counter()
    C = five_min(A); rows = A[A[:, 0] >= 0]
    me = int((te_ns - ns_of(d, 0)) // 60_000_000_000)
    prev_end = te_ns; prev_bar_end_min = me
    for r in rows:
        m = int(r[0])
        if m < me: continue
        if m >= FLAT: break
        if half:
            done = [b for b in sorted(C) if b + 5 <= m][-trail_n:]
            if len(done) == trail_n: S = max(S, min(C[b][2] for b in done) - trail_off)
        _, o, h, l, c, v = r
        gap = (m - prev_bar_end_min) >= 5
        end_ns = ns_of(d, m + 1)
        if l <= S * 1.01 or (not half and h >= target * 0.99):
            Q = quotes(sym, d, prev_end, end_ns); cnt['exit_quote_windows'] += 1
            if Q:
                for t, bp, bs, ap, asz in Q:
                    if bp <= S:
                        legs.append((0.5 if half else 1.0, bp, t, 'trail' if half else 'stop', dict(possible_halt=bool(gap), gap_through=bool(bp < S * 0.99))))
                        return legs, cnt
                    if not half and bp >= target:
                        legs.append((0.5, bp, t, '2R half', dict(possible_halt=bool(gap), gap_through=False))); half = True
            else:
                cnt['no_quotes_in_trigger_minute'] += 1
                if l <= S:
                    if not half and h >= target: cnt['ambiguous_bar_stop_first'] += 1
                    legs.append((0.5 if half else 1.0, min(S, o) * 0.99, end_ns, 'stop (bar fallback, -1% spread est.)', dict(possible_halt=bool(gap), gap_through=bool(o < S * 0.99))))
                    return legs, cnt
                if not half and h >= target:
                    legs.append((0.5, target * 0.99, end_ns, '2R half (bar fallback)', dict(possible_halt=bool(gap), gap_through=False))); half = True
        prev_end = end_ns; prev_bar_end_min = m + 1
    T = ns_of(d, FLAT); Q = quotes(sym, d, T, T + 120 * 10**9)
    frac = 0.5 if half else 1.0
    if Q:
        q = Q[0]; age = (q[0] - T) / 1e6
        if age > 1000: cnt['stale_time_exit_quote'] += 1
        legs.append((frac, q[1], q[0], '15:45 exit', dict(possible_halt=False, gap_through=False, age_ms=round(age))))
    else:
        cnt['no_quote_at_1545'] += 1
        last = rows[rows[:, 0] < FLAT]
        legs.append((frac, float(last[-1, 4]) * 0.99 if len(last) else entry * 0.9, T, '15:45 exit (bar fallback)', dict(possible_halt=False, gap_through=False)))
    return legs, cnt

def leg_cash(legs, shares, entry_px, d, slip, halt_stress):
    """net cash P&L for whole shares; half legs use floor(shares/2)"""
    h = shares // 2; rem = shares; pnl = 0.0; proceeds_tot = 0.0
    for i, (frac, bid, t, why, fl) in enumerate(legs):
        n = h if (i == 0 and frac == 0.5 and len(legs) > 1) else rem
        px = bid * (1 - slip)
        if halt_stress and (fl.get('possible_halt') or fl.get('gap_through')): px *= 0.90
        proceeds = n * px; proceeds_tot += proceeds; rem -= n
        rate, mx = taf(d); pnl += proceeds - proceeds * sec_fee(d) - min(mx, n * rate)
    return pnl - shares * entry_px

def leg_gross(legs, shares, ask):
    h = shares // 2; rem = shares; g = 0.0
    for i, (frac, bid, t, why, fl) in enumerate(legs):
        n = h if (i == 0 and frac == 0.5 and len(legs) > 1) else rem
        g += n * bid; rem -= n
    return g - shares * ask

# ------------------------------------------------------------------ pipeline
def build_alerts(days, sessions, U):
    """returns alerts list and coverage counters"""
    cov = Counter()
    sidx = {d: i for i, d in enumerate(sessions)}
    first_needed = sessions[max(0, sidx[days[0]] - BASE_N - 5)]
    syms = sorted(U)
    RAW = L5.daily_multi(syms, datetime.combine(date.fromordinal(first_needed) - timedelta(days=60), datetime.min.time(), ET),
                         datetime.combine(date.fromordinal(days[-1]) + timedelta(days=1), datetime.min.time(), ET), 'raw')
    band = [s for s, A in RAW.items() if ((A[:, 4] >= PMIN) & (A[:, 4] <= PMAX)).any()]
    cov['universe_symbols'] = len(syms); cov['with_daily_bars'] = len(RAW); cov['ever_in_price_band'] = len(band)
    SH = L6.sec_shares(band)
    if not SH: raise SystemExit('SEC share counts unavailable - check SEC_UA secret')
    SP, sp_ok = L6.splits(band, date.fromordinal(first_needed) - timedelta(days=400), date.fromordinal(days[-1]))
    cov['symbols_with_sec_counts'] = len(SH)
    cand = defaultdict(list)                                     # sym -> [(day, prior close, shares)]
    dayset = set(days)
    for s in band:
        A = RAW[s]; dd = A[:, 0].astype(int)
        spl = {date.fromisoformat(ex).toordinal() for ex, f in SP.get(s, [])}
        for d in days:
            k = int(np.searchsorted(dd, d))
            prev_sess = sessions[sidx[d] - 1]
            if k == 0 or dd[k - 1] != prev_sess: continue
            pc = float(A[k - 1, 4])
            if not (PMIN <= pc <= PMAX): continue
            cov['stock_days_in_price_band'] += 1
            if d in spl: cov['excluded_split_day'] += 1; continue
            if k < MIN_HIST: cov['excluded_incomplete_history(<20 daily bars)'] += 1; continue
            v, why = L6.shares_on(s, date.fromordinal(d).isoformat(), SH, SP)
            if v is None: cov[f'excluded_shares_unknown: {why}'] += 1; continue
            if v > SH_MAX: continue
            cov['eligible_stock_days(tiny shares, in band)'] += 1
            cand[s].append((d, pc, v))
    del RAW
    log('eligible stock-days', cov['eligible_stock_days(tiny shares, in band)'], 'symbols', len(cand))
    alerts = []; MIN = {}
    for n, (s, L) in enumerate(sorted(cand.items())):
        d_first = sessions[max(0, sidx[L[0][0]] - BASE_N)]
        M = minutes_range(s, date.fromordinal(d_first), date.fromordinal(L[-1][0]))
        facs = [(date.fromisoformat(ex).toordinal(), f) for ex, f in SP.get(s, [])]
        cum_cache = {}
        for d, pc, shares in L:
            base_days = sessions[sidx[d] - BASE_N:sidx[d]]
            B = []
            for b in base_days:
                if b not in cum_cache: cum_cache[b] = premarket_cum(M.get(b))
                f = 1.0
                for ex, fac in facs:
                    if b < ex <= d: f *= fac
                B.append(cum_cache[b] * f)
            med = np.median(np.array(B), axis=0)
            A = M.get(d)
            if A is None or not len(A): continue
            cum = premarket_cum(A)
            for r in A[(A[:, 0] >= 240) & (A[:, 0] + 1 <= ALERT_END)]:
                t = int(r[0]) + 1; i = t - 241
                if r[4] >= pc * (1 + UP) and cum[i] > 0 and cum[i] >= RVOL * med[i]:
                    alerts.append(dict(sym=s, day=date.fromordinal(d).isoformat(), pc=pc, shares_out=shares, alert_min=t, alert_px=float(r[4]),
                                       cum_vol=float(cum[i]), median_base=float(med[i]), median_was_zero=bool(med[i] == 0)))
                    MIN[(s, d)] = A
                    break
        if n % 50 == 0: log('minutes', n, '/', len(cand), 'alerts', len(alerts))
    cov['alerts'] = len(alerts); cov['alerts_with_zero_median_baseline'] = sum(a['median_was_zero'] for a in alerts)
    return alerts, MIN, cov, sp_ok

def run(days, sessions, equity0=EQUITY):
    U, dropped = L5.universe()
    alerts, MIN, cov, sp_ok = build_alerts(days, sessions, U)
    sigs = []
    for a in alerts:
        d = date.fromisoformat(a['day']); A = MIN[(a['sym'], d.toordinal())]
        pm = A[A[:, 0] < 570]; pmh = float(pm[:, 2].max()) if len(pm) else None
        a['pm_high'] = pmh
        if pmh is None: a['new_rule'] = 'skip: no premarket high'; continue
        s, why, tt = signal_new(A, pmh)
        if s: sigs.append(('NEW', a, s['t'], s))
        else: a['new_rule'] = f'no signal: {why}'
        for s5 in signals_lab5(A, pmh):
            sigs.append(('LAB5', a, s5['t'], s5))
    sigs.sort(key=lambda x: (x[1]['day'], x[2]))
    eq = {'NEW': equity0, 'LAB5': equity0}; pend = {'NEW': 0.0, 'LAB5': 0.0}; day_open = {}; used = set(); trades = []; skips = []
    cnt = Counter()
    def skip(rule, a, t, cat, detail='', quote=None):
        skips.append(dict(rule=rule, sym=a['sym'], day=a['day'], t=t, cat=cat, why=detail or cat, quote=quote)); cnt[f'{rule} skip: {cat}'] += 1
    for rule, a, t, s in sigs:
        key = (rule, a['sym'], a['day'])
        if key in used: continue
        d = date.fromisoformat(a['day']); A = MIN[(a['sym'], d.toordinal())]
        dk = (rule, a['day'])
        if dk not in day_open:
            eq[rule] += pend[rule]; pend[rule] = 0.0
            day_open[dk] = dict(eq=eq[rule], cash=eq[rule])
        q, why = entry_quote(a['sym'], d, t)
        if q is None: skip(rule, a, t, 'no fresh quote within 1 s', why); continue
        entry = q['ask'] * (1 + SLIP)
        if rule == 'NEW':
            atr = atr_at(five_min(A), t)
            if atr is None: skip(rule, a, t, 'ATR: < 3 completed 5-min bars'); used.add(key); continue
            stop = min(s['pull_low'], entry - ATR_K * atr)
            if stop < entry * (1 - MAX_STOP): skip(rule, a, t, 'stop > 8% below entry', f'stop {round((1 - stop / entry) * 100, 1)}% below entry', q); used.add(key); continue
        else:
            if q['ask'] > s['vwap'] * 1.10: cnt['LAB5 too extended, keep watching'] += 1; continue
            stop = s['stop']
        if stop >= entry: skip(rule, a, t, 'stop at/above entry', quote=q); used.add(key); continue
        used.add(key)
        if q['spread_pct'] > MAX_SPREAD * 100: skip(rule, a, t, 'spread > 1.5%', f"spread {q['spread_pct']}%", q); continue
        rps = entry - stop; st = day_open[dk]
        sh = math.floor(min(RISK * st['eq'] / rps, CAP / entry, st['cash'] / entry))
        if sh < 1: skip(rule, a, t, 'size < 1 share', quote=q); continue
        if q['ask_sz'] < sh: skip(rule, a, t, 'displayed ask size < order size', f"ask size {q['ask_sz']} < {sh} shares", q); continue
        st['cash'] -= sh * entry
        legs, c2 = run_exits(a['sym'], d, A, q['t_ns'], entry, stop, 2 if rule == 'NEW' else 1, 0.0 if rule == 'NEW' else 0.01)
        cnt.update({f'{rule} {k}': v for k, v in c2.items()})
        net = leg_cash(legs, sh, entry, d, SLIP, False)
        tr = dict(rule=rule, sym=a['sym'], day=a['day'], month=a['day'][:7], shares_out=a['shares_out'], signal_min=t, entry_quote=q,
                  entry_quote_time=hm(q['t_ns'], d), entry=round(entry, 4), stop=round(stop, 4), risk_ps=round(rps, 4), shares=sh,
                  legs=[dict(frac=f, bid=b, time=hm(tt_, d), why=w, **fl) for f, b, tt_, w, fl in legs],
                  net_usd=round(net, 2), gross_usd=round(leg_gross(legs, sh, q['ask']), 2))
        tr['net_R'] = round(net / (sh * rps), 3); tr['gross_R'] = round(tr['gross_usd'] / (sh * rps), 3)
        tr['_legs'] = legs; tr['_q'] = q
        trades.append(tr); pend[rule] += net
    return alerts, sigs, trades, skips, cnt, cov, sp_ok, dropped

def account_case(trades, days, slip, halt, equity0=EQUITY):
    """re-size every trade on its own equity path for a cost case (trade set and quote filters fixed by the base case)"""
    eq = equity0; peak = eq; dd = 0.0; curve = []; worst = 0.0; by_day = defaultdict(list); R = []; per_day_R = defaultdict(list)
    for tr in trades: by_day[tr['day']].append(tr)
    for d in days:
        ds = date.fromordinal(d).isoformat(); p = 0.0; cash = eq
        for tr in sorted(by_day.get(ds, []), key=lambda x: x['signal_min']):
            entry = tr['_q']['ask'] * (1 + slip); rps = entry - tr['stop']
            if rps <= 0: continue
            sh = math.floor(min(RISK * eq / rps, CAP / entry, cash / entry))
            if sh < 1: continue
            cash -= sh * entry
            pn = leg_cash(tr['_legs'], sh, entry, date.fromisoformat(ds), slip, halt); p += pn
            R.append(pn / (sh * rps)); per_day_R[ds].append(pn / (sh * rps))
        worst = min(worst, p / eq if eq > 0 else 0); eq += p; peak = max(peak, eq); dd = max(dd, 1 - eq / peak)
        curve.append((ds, round(eq, 2)))
    return dict(end_equity=round(eq, 2), net_pct=round((eq / equity0 - 1) * 100, 2), max_dd_pct=round(dd * 100, 2), worst_day_pct=round(worst * 100, 2)), R, per_day_R, curve

def rstats(R, per_day):
    if not R: return dict(trades=0)
    r = np.array(R); w = r[r > 0].sum(); l = -r[r <= 0].sum()
    keys = list(per_day); g = np.random.default_rng(17); means = []
    if len(keys) >= 2:
        sums = np.array([sum(per_day[k]) for k in keys]); ns = np.array([len(per_day[k]) for k in keys])
        for _ in range(BOOT):
            ix = g.integers(0, len(keys), len(keys)); means.append(sums[ix].sum() / max(1, ns[ix].sum()))
    return dict(trades=len(r), sessions_with_trades=len(keys), win_rate_pct=round(float((r > 0).mean()) * 100, 1), expectancy_R=round(float(r.mean()), 3),
                ci95_R_day_clustered=[round(float(np.percentile(means, 2.5)), 3), round(float(np.percentile(means, 97.5)), 3)] if means else None,
                profit_factor=round(float(w / l), 2) if l > 0 else None, median_R=round(float(np.median(r)), 3))

def grp(T):
    pd = defaultdict(list)
    for t in T: pd[t['day']].append(t['net_R'])
    return rstats([t['net_R'] for t in T], pd)

def bucket(v):
    return '<1M' if v < 1e6 else '1-2M' if v < 2e6 else '2-3.5M' if v < 3.5e6 else '3.5-5M'

def summarize(trades, skips, alerts, days, cnt, cov, equity0=EQUITY):
    S = {}
    for rule in ('NEW', 'LAB5'):
        T = [t for t in trades if t['rule'] == rule]
        cases = {}
        for name, slip, halt in (('base (0.5% slip)', SLIP, False), ('stress: 1.0% slip', 0.01, False), ('stress: halt/gap -10%', SLIP, True), ('stress: both', 0.01, True)):
            acc, R, pdR, curve = account_case(T, days, slip, halt, equity0)
            cases[name] = dict(account=acc, net=rstats(R, pdR))
            if name.startswith('base'): base_curve = curve
        G = [t['gross_R'] for t in T]
        S[rule] = dict(cases=cases, gross_expectancy_R=round(float(np.mean(G)), 3) if G else None,
                       by_month={m: grp([t for t in T if t['month'] == m]) for m in sorted({t['month'] for t in T})},
                       by_shares_out={b: grp([t for t in T if bucket(t['shares_out']) == b]) for b in ('<1M', '1-2M', '2-3.5M', '3.5-5M')},
                       exits=dict(Counter(l['why'] for t in T for l in t['legs'])),
                       entry_quote_age_ms=dict(median=float(np.median([t['entry_quote']['age_ms'] for t in T])) if T else None,
                                               max=float(max([t['entry_quote']['age_ms'] for t in T])) if T else None),
                       entry_spread_pct_median=float(np.median([t['entry_quote']['spread_pct'] for t in T])) if T else None,
                       skips=dict(Counter(s_['cat'] for s_ in skips if s_['rule'] == rule)),
                       equity_curve=base_curve)
    nr = Counter(a.get('new_rule', 'signal') for a in alerts)
    return dict(new_rule_alert_outcomes=dict(nr), per_rule=S, counters=dict(cnt), coverage=dict(cov))

def report(R, title):
    j = lambda x: '```\n' + json.dumps(x, indent=1, default=str) + '\n```'
    L = [f'# {title} - {R["updated"]}', '', R['note'], '', '## Verdict', R['verdict'], '', '## Data / implementation checks', *['- ' + x for x in R['checks']], '']
    for rule in ('NEW', 'LAB5'):
        P = R['summary']['per_rule'][rule]
        L += [f'## {rule} rule', '| case | trades | win % | expectancy R | 95% CI (day-clustered) | PF | end equity | max DD % | worst day % |', '|---|---|---|---|---|---|---|---|---|']
        for k, v in P['cases'].items():
            n, a = v['net'], v['account']
            L.append(f"| {k} | {n.get('trades')} | {n.get('win_rate_pct')} | {n.get('expectancy_R')} | {n.get('ci95_R_day_clustered')} | {n.get('profit_factor')} | ${a['end_equity']} | {a['max_dd_pct']} | {a['worst_day_pct']} |")
        L += ['', f"Gross expectancy (ask/bid, no slippage or fees): {P['gross_expectancy_R']} R", '', '### By month', j(P['by_month']), '### By shares outstanding (proxy)', j(P['by_shares_out']),
              '### Exits', j(P['exits']), '### Skips', j(P['skips']), f"Entry quote age ms: {P['entry_quote_age_ms']}, median spread %: {P['entry_spread_pct_median']}", '']
    L += ['## Alert outcomes (NEW rule)', j(R['summary']['new_rule_alert_outcomes']), '## Counters', j(R['summary']['counters']), '## Coverage', j(R['summary']['coverage']),
          '## Files', '- lab8_alerts.jsonl: every eligible alert', '- lab8_trades.jsonl: every fill with quote time/age/spread/size and exit legs',
          '- lab8_skips.jsonl: every skipped signal and why', '- lab8_equity.json: daily equity curves', '', '## Rerun', f"`python lab8.py {MODE}` (GitHub Actions: lab8.yml / lab8-forward.yml)"]
    return '\n'.join(L) + '\n'

CHECKS = [
    'Signals use only bars that have ended (a 1-minute bar is known at its end; 5-minute ATR uses completed bars only; VWAP through the signal bar; premarket high fixed at 9:30).',
    'Shares outstanding: last SEC count filed strictly before the session, split-adjusted; prior close = previous session raw close.',
    'Entry quote: first valid SIP quote with timestamp strictly after the signal bar end; skipped if it arrives > 1 s later. Quotes before the signal are never used.',
    'Exits: triggered by the first quote whose BID crosses the level, so gaps and halts fill at the real reopening bid; bar fallback (stop first) only when no quotes exist for that minute.',
    'Quote sizes: SIP reported round lots before 2025-11-03 and shares after (Alpaca changelog); pre-switch sizes are multiplied by 100.',
    'Fees: SEC Section 31 $27.80/M until 2025-05-13, $0 from 2025-05-14, $20.60/M from 2026-04-04; FINRA TAF $0.000166/sh (max $8.30) in 2025, $0.000195 (max $9.79) in 2026. Labs 5-7 charged $27.80/M throughout (slightly too high).',
    'Known limitation: candidate exit minutes are found from trade-based 1-minute bars (low within 1% of the stop or high within 1% of the target); a bid that crossed without nearby trades could be missed.',
    'Known limitation: no historical halt feed; "possible halt" = a gap of >= 5 minutes with no prints before the exit.',
    'Known limitation: the rule says median baseline; for thin premarket names the 20-session median is often 0, which makes the 3x test pass on any volume. Kept as written (locked); counted in coverage.',
    'Known limitation: survivorship - Alpaca asset list and SEC current ticker map; delisted/renamed names may be missing.',
    'Earlier labs (flagged): lab 5 filled at the first quote up to 2 minutes after the signal and exited on bars with the entry spread; lab 5 SEC dilution flag silently failed; labs 5-7 used per-trade (not day-clustered) bootstraps; lab 7 E3 assumed premarket stops that Alpaca does not support.']

def publish(files):
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', BRANCH, OUT], check=True)
    subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', BRANCH], check=True)
    subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{REPO}.git', BRANCH], check=True, timeout=120, capture_output=True)

def sessions_between(a, b):
    r = get(f'{TRADE}/v2/calendar', dict(start=str(a), end=str(b)))
    return [date.fromisoformat(c['date']).toordinal() for c in (r.json() if r is not None and r.ok else []) if c['close'].startswith('16')]

def main():
    t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    now = datetime.now(ET)
    if MODE == 'history':
        sessions = sessions_between(HIST_FIRST - timedelta(days=60), HIST_LAST)
        days = [d for d in sessions if d >= HIST_FIRST.toordinal()]
        note = ('EXPLORATORY ONLY. These dates were used while building labs 5-7, so this is not an independent test. '
                'Only the forward paper test (sessions after 2026-11-13) can confirm or reject the rule.')
    else:
        last = now.date() if now.hour * 60 + now.minute >= 16 * 60 + 30 else now.date() - timedelta(days=1)
        sessions = sessions_between(FWD_AFTER - timedelta(days=60), last)
        days = [d for d in sessions if d > FWD_AFTER.toordinal()]
        note = 'LOCKED FORWARD PAPER TEST. Rule frozen 2026-11-15; every completed session after 2026-11-13 is replayed with the identical code. No orders are sent.'
        if not days: log('no forward sessions yet'); return
    alerts, sigs, trades, skips, cnt, cov, sp_ok, dropped = run(days, sessions)
    cov['universe_excluded'] = dict(dropped); cov['splits_feed_ok'] = sp_ok
    summ = summarize(trades, skips, alerts, days, cnt, cov)
    nb = summ['per_rule']['NEW']['cases']['base (0.5% slip)']['net']
    if MODE == 'history':
        verdict = (f"Exploratory replay, NEW rule base case: {nb.get('trades', 0)} trades, expectancy {nb.get('expectancy_R')} R, day-clustered 95% CI {nb.get('ci95_R_day_clustered')}. "
                   'Whatever this shows, it is not independent confirmation; the strategy stays paper-only until the forward test decides.')
    else:
        verdict = (f"Forward paper test so far ({len(days)} sessions): {nb.get('trades', 0)} trades, expectancy {nb.get('expectancy_R')} R, CI {nb.get('ci95_R_day_clustered')}. "
                   'A small forward sample cannot show profitability; paper-only.')
    R = dict(updated=now.isoformat(timespec='seconds'), mode=MODE, sessions=len(days), first=date.fromordinal(days[0]).isoformat(), last=date.fromordinal(days[-1]).isoformat(),
             note=note, verdict=verdict, checks=CHECKS, summary=summ, seconds=round(time.time() - t0))
    with open(f'{OUT}/lab8.json', 'w') as f: json.dump({k: v for k, v in R.items()}, f, indent=1, default=str)
    with open(f'{OUT}/lab8_alerts.jsonl', 'w') as f:
        for a in alerts: f.write(json.dumps(a, default=str) + '\n')
    with open(f'{OUT}/lab8_trades.jsonl', 'w') as f:
        for t in trades: f.write(json.dumps({k: v for k, v in t.items() if not k.startswith('_')}, default=str) + '\n')
    with open(f'{OUT}/lab8_skips.jsonl', 'w') as f:
        for s in skips: f.write(json.dumps(s, default=str) + '\n')
    json.dump({r: summ['per_rule'][r]['equity_curve'] for r in ('NEW', 'LAB5')}, open(f'{OUT}/lab8_equity.json', 'w'))
    open(f'{OUT}/lab8_report.md', 'w').write(report(R, 'Vantex lab 8 - locked tiny-float pullback rule' + (' (exploratory history)' if MODE == 'history' else ' (FORWARD paper test)')))
    log('done', verdict, round(time.time() - t0), 's'); publish(None)

if __name__ == '__main__':
    main()
