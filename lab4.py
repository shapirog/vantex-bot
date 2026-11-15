"""Vantex lab 4: "could we have caught the big movers?"  Whole US market, small caps, news + unusual volume.
READ-ONLY: places no orders.

Part A - MOVER CENSUS (what moved them, and was it catchable?)
  Every stock-day in the last N sessions that traded at least 10% above the previous close (price $1-$20 the day
  before, $250K+ traded the day before). That set includes the big winners AND every stock that looked like it
  was starting to run and then didn't - so there is no hindsight in the counts.
  For each one: gap at the open, pre-market volume, news before the open / before the move (Alpaca news), the
  catalyst type (FDA, deal, contract, offering...), when it first hit +10%, and what was left after that.

Part B - PRE-REGISTERED STRATEGIES (long only, shares, 1-minute bars, written down before seeing any result)
  A  CHASE10   buy the first time it trades 10% above yesterday's close (9:30-15:00), stop -8%, out at 15:55
  B  GAP-ORB5  gap 10%+ at the open, buy a break of the first 5-minute high, stop at the 5-minute low
               (skip if that is more than 15% away), out at 15:55   (Zarattini/Barbon/Aziz style, small caps)
  C  PM-HIGH   gap 10%+, 100K+ pre-market shares, buy a break of the pre-market high 9:30-11:00, stop -8%,
               half off at +20% then a 10% trailing stop, out at 15:50
  D  LIVE-MOM  the live momentum bot's long rules exactly (15-min range, 9:45-14:30, break held 3 one-minute
               closes, breakout minute 2x average volume, above VWAP, not 6% past the level, not up 40%+,
               failed-break exit in 15 min, stop -8%, +20% half, 10% trail, out 15:50)
  Each also with "+NEWS": only if a real catalyst headline (not a movers round-up) came out before the entry.
  Costs: 0.5% slippage per side (small caps are wide), also shown at 0.25% and 1%. Stop-and-target in the same
  minute = stop. Trading halts are not modeled (they usually make real results worse).
  Account: $2,500 cash account, one trade a day per strategy (the earliest signal), 50% of equity.
Results: 'live-lab4' branch (lab4.json + lab4_report.md).
"""
import os, sys, re, json, math, time, subprocess
from collections import defaultdict, Counter
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
import numpy as np
import requests

ET = ZoneInfo('America/New_York')
DATA, TRADE = 'https://data.alpaca.markets', 'https://paper-api.alpaca.markets'
OUT = os.environ.get('VANTEX_LAB4_DIR', '/tmp/vantex-lab4')
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
SESSIONS = int(sys.argv[1]) if len(sys.argv) > 1 else 300
H = {'APCA-API-KEY-ID': os.environ.get('APCA_API_KEY_ID', ''), 'APCA-API-SECRET-KEY': os.environ.get('APCA_API_SECRET_KEY', '')}
PMIN, PMAX, MIN_DVOL, FLAG = 1.0, 20.0, 250_000, 0.10
SLIPS, BASE_SLIP, SEC = (0.0025, 0.005, 0.01), 0.005, 27.8e-6
START_EQ, ALLOC, TRAIN_FRAC = 2500.0, 0.5, 0.7
EXCH = {'NASDAQ', 'NYSE', 'AMEX', 'ARCA', 'BATS'}

GOOD = [('FDA', r'\bfda\b|approv|clearance|breakthrough designation|orphan drug'), ('TRIAL', r'phase [123i]|trial|topline|data readout'),
        ('DEAL', r'merger|acquisi|acquire|buyout|takeover|definitive agreement'), ('CONTRACT', r'contract|award|order|purchase order|government'),
        ('PARTNER', r'partner|collaborat|alliance|joint venture|licens'), ('EARNINGS', r'earnings|revenue|results|guidance|profit|record quarter'),
        ('AI', r'\bai\b|artificial intelligence|quantum|nvidia'), ('CRYPTO', r'bitcoin|crypto|blockchain|treasury'), ('UPLIST', r'uplist|nasdaq listing|regains compliance')]
ROUNDUP = r'stocks moving|movers|top gainers|top losers|biggest movers|stocks to watch|stocks trading|mid-day|midday update|market update|session\b|shares are trading|why .* (shares|stock) (is|are)'
BAD = [('OFFERING', r'offering|dilut|registered direct|at-the-market|warrant'), ('SPLIT', r'reverse (stock )?split'),
       ('DELIST', r'delist|non-compliance|deficiency'), ('BANKRUPT', r'bankrupt|chapter 11|going concern')]

GOOD_NAMES = {x for x, _ in GOOD}

def log(*a): print(' '.join(str(x) for x in a), flush=True)

def get(url, params=None):
    for k in range(6):
        try: r = requests.get(url, headers=H, params=params, timeout=60)
        except Exception as e: log('network', type(e).__name__); time.sleep(2 * (k + 1)); continue
        if r.status_code == 429: time.sleep(3 * (k + 1)); continue
        return r
    return None

def tags(headline):
    h = headline.lower()
    if re.search(ROUNDUP, h): return ['ROUNDUP']
    t = [n for n, rx in GOOD if re.search(rx, h)] + [n for n, rx in BAD if re.search(rx, h)]
    return t or ['OTHER']

# ---------------- data ----------------
def universe():
    r = get(f'{TRADE}/v2/assets', dict(status='all', asset_class='us_equity'))
    A = r.json() if r is not None and r.ok else []
    return sorted({a['symbol'] for a in A if a.get('exchange') in EXCH and re.fullmatch(r'[A-Z]{1,5}', a['symbol'] or '')})

def daily_multi(syms, start, end, adjustment):
    out = defaultdict(list)
    for i in range(0, len(syms), 200):
        chunk = syms[i:i + 200]; tok = None
        while True:
            p = dict(symbols=','.join(chunk), timeframe='1Day', start=start.isoformat(), end=end.isoformat(), limit=10000, feed='sip', adjustment=adjustment)
            if tok: p['page_token'] = tok
            r = get(f'{DATA}/v2/stocks/bars', p)
            if r is None or not r.ok: log('daily error', getattr(r, 'status_code', None), getattr(r, 'text', '')[:120]); break
            j = r.json()
            for s, bars in (j.get('bars') or {}).items():
                for b in bars:
                    d = datetime.fromisoformat(b['t'].replace('Z', '+00:00')).astimezone(ET).date().toordinal()
                    out[s].append((d, b['o'], b['h'], b['l'], b['c'], b['v']))
            tok = j.get('next_page_token')
            if not tok: break
        if (i // 200) % 10 == 0: log('  daily', adjustment, i, '/', len(syms))
    return {s: np.array(sorted(v), dtype=float) for s, v in out.items()}

def minutes_day(syms, day):
    """{sym: array[[minute, o, h, l, c, v]]} 4:00-16:00 ET, raw prices"""
    d0 = datetime.combine(date.fromordinal(day), datetime.min.time(), ET)
    out = defaultdict(list)
    for i in range(0, len(syms), 50):
        tok = None
        while True:
            p = dict(symbols=','.join(syms[i:i + 50]), timeframe='1Min', start=(d0 + timedelta(hours=4)).isoformat(), end=(d0 + timedelta(hours=16)).isoformat(),
                     limit=10000, feed='sip', adjustment='raw')
            if tok: p['page_token'] = tok
            r = get(f'{DATA}/v2/stocks/bars', p)
            if r is None or not r.ok: log('minute error', getattr(r, 'status_code', None)); break
            j = r.json()
            for s, bars in (j.get('bars') or {}).items():
                for b in bars:
                    t = datetime.fromisoformat(b['t'].replace('Z', '+00:00')).astimezone(ET)
                    out[s].append((t.hour * 60 + t.minute, b['o'], b['h'], b['l'], b['c'], b['v']))
            tok = j.get('next_page_token')
            if not tok: break
    return {s: np.array(v, dtype=float) for s, v in out.items()}

def news_day(syms, day):
    """{sym: [(minute_of_day relative to this day (negative = day before), headline, tags)]} from 16:00 the day before to 16:00"""
    d0 = datetime.combine(date.fromordinal(day), datetime.min.time(), ET)
    start, end = d0 - timedelta(hours=8), d0 + timedelta(hours=16)
    out = defaultdict(list)
    for i in range(0, len(syms), 40):
        tok = None
        for _ in range(20):
            p = dict(symbols=','.join(syms[i:i + 40]), start=start.isoformat(), end=end.isoformat(), limit=50, sort='asc', include_content='false')
            if tok: p['page_token'] = tok
            r = get(f'{DATA}/v1beta1/news', p)
            if r is None or not r.ok: log('news error', getattr(r, 'status_code', None)); break
            j = r.json()
            for n in j.get('news', []):
                t = datetime.fromisoformat(n['created_at'].replace('Z', '+00:00')).astimezone(ET)
                m = int((t - d0).total_seconds() // 60)
                for s in n.get('symbols', []):
                    if s in syms: out[s].append((m, n.get('headline', ''), tags(n.get('headline', '')), len(n.get('symbols', []))))
            tok = j.get('next_page_token')
            if not tok: break
    return out

# ---------------- strategy engine ----------------
def manage(B, i, entry, stop, flat, partial=None, trail=None, fail=None):
    """walk 1-min RTH bars from index i (the entry bar). returns (exit_price_before_slip, minute, why).
    partial: (gain, fraction) then trailing stop `trail` (fraction from the high). fail: (level, minutes)"""
    hi = entry; half_done = False; got = 0.0; m0 = B[i, 0]
    for k in range(i, len(B)):
        m, o, h, l, c, v = B[k]
        first = k == i
        if not first and m >= flat: return _mix(got, half_done, o, partial), m, 'time'
        cur_stop = stop
        if half_done and trail: cur_stop = max(stop, hi * (1 - trail))
        if (not first) and l <= cur_stop:                         # stop first (conservative)
            return _mix(got, half_done, min(cur_stop, o), partial), m, 'stop'
        if first and c <= cur_stop:
            return _mix(got, half_done, c, partial), m, 'stop'
        if partial and not half_done and h >= entry * (1 + partial[0]) and not first:
            half_done = True; got = max(entry * (1 + partial[0]), o)
        hi = max(hi, h)
        if fail and not half_done and m - m0 <= fail[1] and c < fail[0] and not first:
            return _mix(got, half_done, c, partial), m, 'failed break'
        if m >= 959: return _mix(got, half_done, c, partial), m, 'close'
    c = B[-1, 4]; return _mix(got, half_done, c, partial), B[-1, 0], 'last bar'

def _mix(got, half_done, px, partial):
    return (partial[1] * got + (1 - partial[1]) * px) if (half_done and partial) else px

def first_cross(B, level, m_from, m_to):
    for k in range(len(B)):
        m = B[k, 0]
        if m < m_from: continue
        if m > m_to: return None
        if B[k, 2] >= level: return k, max(level, B[k, 1])
    return None

def run_strats(X):
    """X: dict for one stock-day. returns {strategy: trade or None}"""
    B = X['rth']; pc = X['pc']; out = {}
    if len(B) < 30: return out
    # A CHASE10
    hit = first_cross(B, pc * (1 + FLAG), 570, 900)
    if hit:
        k, px = hit; ex, m, why = manage(B, k, px, px * 0.92, 955)
        out['A CHASE10'] = dict(k=k, m=B[k, 0], entry=px, exit=ex, why=why)
    gap = X['gap']
    if gap >= 0.10:
        # B GAP-ORB5
        orb = B[B[:, 0] < 575]
        if len(orb):
            oh, ol = orb[:, 2].max(), orb[:, 3].min()
            hit = first_cross(B, oh + 0.01, 575, 955)
            if hit and (oh - ol) / oh <= 0.15:
                k, px = hit; ex, m, why = manage(B, k, px, ol, 955)
                out['B GAP-ORB5'] = dict(k=k, m=B[k, 0], entry=px, exit=ex, why=why)
        # C PM-HIGH
        if X['pm_vol'] >= 100_000 and X['pm_high']:
            hit = first_cross(B, X['pm_high'] + 0.01, 570, 660)
            if hit:
                k, px = hit; ex, m, why = manage(B, k, px, px * 0.92, 950, partial=(0.20, 0.5), trail=0.10)
                out['C PM-HIGH'] = dict(k=k, m=B[k, 0], entry=px, exit=ex, why=why)
    # D LIVE-MOM (long side of momentum.py)
    orb = B[B[:, 0] < 585]
    if len(orb) >= 12:
        oh = orb[:, 2].max(); pv = vv = 0.0
        for k in range(len(B)):
            m, o, h, l, c, v = B[k]
            tp = (h + l + c) / 3; pv += tp * v; vv += v
            if m < 585 + 2 or m > 870: continue
            last3 = B[k - 2:k + 1, 4]
            if not (last3 > oh).all(): continue
            avg_v = vv / (k + 1); brk = B[max(0, k - 5):k + 1, 5].max()
            vwap = pv / vv if vv else c
            if brk < 2 * avg_v or c < vwap or c > oh * 1.06 or c / pc - 1 >= 0.40: continue
            if k + 1 >= len(B): break
            px = B[k + 1, 1]                                   # market order fills at the next minute's open
            ex, mm, why = manage(B, k + 1, px, px * 0.92, 950, partial=(0.20, 0.5), trail=0.10, fail=(oh, 15))
            out['D LIVE-MOM'] = dict(k=k + 1, m=B[k + 1, 0], entry=px, exit=ex, why=why)
            break
    # +NEWS variants: a real catalyst headline before the entry minute
    for name in list(out):
        t = out[name]
        if any(n[0] <= t['m'] and n[3] <= 4 and any(g in GOOD_NAMES for g in n[2]) for n in X['news']):
            out[name + ' +NEWS'] = dict(t)
    return out

def ret(t, slip):
    return (t['exit'] * (1 - slip)) / (t['entry'] * (1 + slip)) - 1 - SEC

def pf(r):
    w = r[r > 0].sum(); l = -r[r <= 0].sum(); return round(float(w / l), 2) if l > 0 else None

def boot(r, n=2000, seed=3):
    if len(r) < 10: return None
    g = np.random.default_rng(seed); m = [r[g.integers(0, len(r), len(r))].mean() for _ in range(n)]
    return [round(float(np.percentile(m, 2.5)) * 100, 2), round(float(np.percentile(m, 97.5)) * 100, 2)]

def trade_stats(T, slip):
    if not T: return dict(trades=0)
    r = np.array([ret(t, slip) for t in T])
    return dict(trades=len(r), win_pct=round(float((r > 0).mean()) * 100, 1), mean_pct=round(float(r.mean()) * 100, 2),
                median_pct=round(float(np.median(r)) * 100, 2), pf=pf(r), mean_ci95_pct=boot(r), best_pct=round(float(r.max()) * 100, 1), worst_pct=round(float(r.min()) * 100, 1))

def account(T, days, slip):
    """one trade a day (earliest entry), 50% of equity, cash account"""
    by = {}
    for t in T:
        if t['day'] not in by or t['m'] < by[t['day']]['m']: by[t['day']] = t
    eq = START_EQ; curve = []; pk = eq; dd = 0
    for d in days:
        if d in by: eq *= 1 + ALLOC * ret(by[d], slip)
        pk = max(pk, eq); dd = max(dd, 1 - eq / pk); curve.append(eq)
    return dict(end_equity=round(eq, 2), total_ret_pct=round((eq / START_EQ - 1) * 100, 1), max_dd_pct=round(dd * 100, 1), trade_days=len(by))

# ---------------- main ----------------
def main():
    t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    end = datetime.now(ET).date()
    r = get(f'{TRADE}/v2/calendar', dict(start=str(end - timedelta(days=int(SESSIONS * 1.6) + 20)), end=str(end - timedelta(days=1))))
    cal = [(date.fromisoformat(c['date']).toordinal(), c['close']) for c in (r.json() if r is not None and r.ok else [])]
    cal = [c for c in cal if c[0] < end.toordinal()][-(SESSIONS + 1):]
    days = [d for d, cl in cal[1:] if cl.startswith('16')]
    syms = universe(); log('universe', len(syms), 'symbols;', len(days), 'full sessions', round(time.time() - t0), 's')
    s0 = datetime.combine(date.fromordinal(cal[0][0]) - timedelta(days=7), datetime.min.time(), ET); s1 = datetime.combine(end, datetime.min.time(), ET)
    RAW = daily_multi(syms, s0, s1, 'raw'); ADJ = daily_multi(syms, s0, s1, 'split')
    log('daily done', len(RAW), round(time.time() - t0), 's')
    # candidate stock-days
    cands = defaultdict(list); n_split = 0
    for s, A in RAW.items():
        Aj = ADJ.get(s)
        if Aj is None or len(A) != len(Aj): continue
        d = A[:, 0].astype(int)
        for i in range(1, len(A)):
            day = d[i]
            if day not in DAYSET(days): continue
            pc, pv = A[i - 1, 4], A[i - 1, 5]
            if not (PMIN <= pc <= PMAX) or pc * pv < MIN_DVOL: continue
            if A[i, 2] / pc - 1 < FLAG: continue
            if abs(A[i, 4] / pc - Aj[i, 4] / Aj[i - 1, 4]) > 0.01: n_split += 1; continue      # split day: fake move
            cands[day].append((s, pc, A[i, 1], A[i, 2], A[i, 4], A[i, 5]))
    total = sum(len(v) for v in cands.values()); log('stock-days that hit +10%:', total, 'split days skipped:', n_split)
    del ADJ
    ROWS = []; TR = defaultdict(list); last_day = max(days)
    for di, day in enumerate(days):
        C = cands.get(day, [])
        if not C: continue
        names = [c[0] for c in C]
        M = minutes_day(names, day); N = news_day(names, day)
        for s, pc, o, h, c, v in C:
            Bm = M.get(s)
            if Bm is None or not len(Bm): continue
            pm = Bm[Bm[:, 0] < 570]; rth = Bm[(Bm[:, 0] >= 570) & (Bm[:, 0] < 960)]
            if len(rth) < 30: continue
            news = sorted(N.get(s, []))
            hit = first_cross(rth, pc * (1 + FLAG), 570, 959)
            flag_m = rth[hit[0], 0] if hit else None; flag_px = hit[1] if hit else None
            real = [n for n in news if n[2][0] != 'ROUNDUP' and n[3] <= 4]
            X = dict(sym=s, day=day, pc=pc, o=o, h=h, c=c, v=v, gap=o / pc - 1, pm_vol=float(pm[:, 5].sum()) if len(pm) else 0.0,
                     pm_high=float(pm[:, 2].max()) if len(pm) else None, rth=rth, news=news)
            row = dict(sym=s, day=str(date.fromordinal(day)), pc=round(pc, 3), gap_pct=round(X['gap'] * 100, 1), day_pct=round((c / pc - 1) * 100, 1),
                       high_pct=round((h / pc - 1) * 100, 1), pm_vol=int(X['pm_vol']), flag_min=int(flag_m) if flag_m is not None else None,
                       after_flag_to_close_pct=round((c / flag_px - 1) * 100, 1) if flag_px else None,
                       after_flag_to_high_pct=round((h / flag_px - 1) * 100, 1) if flag_px else None,
                       news_before_open=[n[1][:110] for n in real if n[0] < 570][:2],
                       tags_before_open=sorted({t for n in real if n[0] < 570 for t in n[2]}),
                       news_before_flag=bool(flag_m is not None and any(n[0] <= flag_m for n in real)),
                       tags_any=sorted({t for n in real for t in n[2]}), dvol=round(c * v))
            ROWS.append(row)
            for name, t in run_strats(X).items():
                t.update(day=day, sym=s); TR[name].append(t)
        if di % 20 == 0: log('day', di, '/', len(days), date.fromordinal(day), 'cands', len(C), 'rows', len(ROWS), round(time.time() - t0), 's')
    # ---------------- Part A census ----------------
    big = [r for r in ROWS if r['day_pct'] >= 20]; huge = [r for r in ROWS if r['day_pct'] >= 50]
    def share(rows, f): return round(100 * sum(1 for r in rows if f(r)) / len(rows), 1) if rows else None
    census = dict(stock_days_hit_10pct=len(ROWS), closed_up_20pct=len(big), closed_up_50pct=len(huge),
                  base_rate_hit10_closes_20pct=share(ROWS, lambda r: r['day_pct'] >= 20),
                  base_rate_hit10_closes_below_10pct=share(ROWS, lambda r: r['day_pct'] < 10),
                  base_rate_hit10_closes_red=share(ROWS, lambda r: r['day_pct'] < 0),
                  movers20_gapped_10pct=share(big, lambda r: r['gap_pct'] >= 10), movers20_news_before_open=share(big, lambda r: bool(r['news_before_open'])),
                  movers20_news_before_flag=share(big, lambda r: r['news_before_flag']), movers20_no_news_all_day=share(big, lambda r: not r['tags_any']),
                  all_hit10_news_before_flag=share(ROWS, lambda r: r['news_before_flag']),
                  movers20_tag_counts=Counter(t for r in big for t in r['tags_any']).most_common(),
                  hit10_tag_counts=Counter(t for r in ROWS for t in r['tags_any']).most_common())
    af = np.array([r['after_flag_to_close_pct'] for r in ROWS if r['after_flag_to_close_pct'] is not None])
    if len(af): census['after_first_+10%_to_close'] = dict(n=len(af), median_pct=round(float(np.median(af)), 1), mean_pct=round(float(af.mean()), 2),
                                                          pct_positive=round(float((af > 0).mean()) * 100, 1), p10=round(float(np.percentile(af, 10)), 1), p90=round(float(np.percentile(af, 90)), 1))
    # with vs without news before the flag
    for lab, f in (('news_before_flag', lambda r: r['news_before_flag']), ('no_news_before_flag', lambda r: not r['news_before_flag'])):
        x = np.array([r['after_flag_to_close_pct'] for r in ROWS if r['after_flag_to_close_pct'] is not None and f(r)])
        if len(x): census[f'after_flag_to_close_{lab}'] = dict(n=len(x), median_pct=round(float(np.median(x)), 1), mean_pct=round(float(x.mean()), 2), pct_positive=round(float((x > 0).mean()) * 100, 1))
    by_tag = {}
    for tg in [x for x, _ in GOOD] + [x for x, _ in BAD] + ['OTHER']:
        x = np.array([r['after_flag_to_close_pct'] for r in ROWS if r['after_flag_to_close_pct'] is not None and tg in r['tags_before_open']])
        if len(x) >= 10: by_tag[tg] = dict(n=len(x), median_pct=round(float(np.median(x)), 1), mean_pct=round(float(x.mean()), 2), pct_positive=round(float((x > 0).mean()) * 100, 1))
    census['after_flag_to_close_by_tag_before_open'] = by_tag
    # ---------------- Part B strategies ----------------
    cut = days[int(len(days) * TRAIN_FRAC)]
    S = {}
    for name, T in sorted(TR.items()):
        a = [t for t in T if t['day'] < cut]; b = [t for t in T if t['day'] >= cut]
        S[name] = dict(all={f'slip {x * 100:.2f}%': trade_stats(T, x) for x in SLIPS}, first70=trade_stats(a, BASE_SLIP), last30=trade_stats(b, BASE_SLIP),
                       account_all=account(T, days, BASE_SLIP), account_last30=account(b, [d for d in days if d >= cut], BASE_SLIP),
                       exits=Counter(t['why'] for t in T).most_common())
    last = sorted([r for r in ROWS if r['day'] == str(date.fromordinal(last_day))], key=lambda r: -r['day_pct'])[:40]
    for r in last:
        r['strategies'] = {n: round(float(ret(t, BASE_SLIP)) * 100, 1) for n, T in TR.items() for t in T if t['sym'] == r['sym'] and str(date.fromordinal(t['day'])) == r['day']}
    top = sorted(ROWS, key=lambda r: -r['day_pct'])[:60]
    R = dict(updated=datetime.now(ET).isoformat(timespec='seconds'), sessions=len(days), first=str(date.fromordinal(days[0])), last=str(date.fromordinal(days[-1])),
             split_at=str(date.fromordinal(cut)), universe=len(syms), filters=dict(prev_close=f'${PMIN}-${PMAX}', prev_dollar_volume=MIN_DVOL, flag='+10% vs prev close'),
             census=census, strategies=S, last_session_movers=last, top_movers=top, seconds=round(time.time() - t0))
    json.dump(R, open(f'{OUT}/lab4.json', 'w'), separators=(',', ':'), default=str)
    with open(f'{OUT}/lab4_rows.jsonl', 'w') as f:
        for r in ROWS: f.write(json.dumps(r, default=str) + '\n')
    open(f'{OUT}/lab4_report.md', 'w').write(report(R))
    log(json.dumps(dict(event='lab4_done', seconds=R['seconds'], rows=len(ROWS))))
    publish()

_DS = {}
def DAYSET(days):
    k = id(days)
    if k not in _DS: _DS[k] = set(days)
    return _DS[k]

def report(R):
    L = [f"# Vantex lab 4 — {R['updated']}", f"{R['sessions']} sessions {R['first']} → {R['last']}, universe {R['universe']} symbols, split {R['split_at']}", '', '## Census', '```', json.dumps(R['census'], indent=1, default=str), '```', '## Strategies (per trade, all days)',
         '| strategy | slip | trades | win | mean | median | PF | mean CI95 |', '|---|---|---|---|---|---|---|---|']
    for n, v in R['strategies'].items():
        for sl, m in v['all'].items():
            L.append(f"| {n} | {sl} | {m.get('trades')} | {m.get('win_pct')}% | {m.get('mean_pct')}% | {m.get('median_pct')}% | {m.get('pf')} | {m.get('mean_ci95_pct')} |")
    L += ['', '## First 70% vs last 30% (0.5% slip) and $2,500 account', '| strategy | first70 PF | first70 mean | last30 PF | last30 mean | account all | maxDD | account last30 |', '|---|---|---|---|---|---|---|---|']
    for n, v in R['strategies'].items():
        a, b, c, d = v['first70'], v['last30'], v['account_all'], v['account_last30']
        L.append(f"| {n} | {a.get('pf')} | {a.get('mean_pct')}% | {b.get('pf')} | {b.get('mean_pct')}% | ${c['end_equity']} ({c['total_ret_pct']}%) | {c['max_dd_pct']}% | {d['total_ret_pct']}% |")
    L += ['', '## Last session movers', '| sym | day % | gap % | flag min | after flag→close | news before open | strategies |', '|---|---|---|---|---|---|---|']
    for r in R['last_session_movers']:
        L.append(f"| {r['sym']} | {r['day_pct']} | {r['gap_pct']} | {r['flag_min']} | {r['after_flag_to_close_pct']} | {'; '.join(r['news_before_open'])[:120]} | {r.get('strategies')} |")
    return '\n'.join(L) + '\n'

def publish():
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', 'live-lab4', OUT], check=True)
    subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', 'lab4'], check=True)
    subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{REPO}.git', 'live-lab4'], check=True, timeout=120, capture_output=True)

if __name__ == '__main__':
    main()
