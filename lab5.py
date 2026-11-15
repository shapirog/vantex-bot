"""Vantex lab 5: early-runner detection on low-priced US stocks - ONE locked rule, full market, point-in-time.
READ-ONLY research. Places no orders. Paper/backtest only.

LOCKED RULES (written before any data was examined; do not tune after seeing results)
Universe   US-listed common stocks (NYSE/NASDAQ/AMEX; ETFs, funds, warrants, rights, units, preferreds excluded by
           name/symbol), previous close $0.50-$5.00 (raw, unadjusted), includes inactive/delisted symbols Alpaca still lists.
WATCH      first minute (4:00-16:00 ET) where the minute CLOSE is >= +3% vs the previous close AND cumulative volume so
           far >= 3x the stock's normal cumulative volume at the same time of day.
           normal(t) = average of the prior 20 sessions' cumulative volume up to t (30-minute grid, linear inside a slot,
           at least 10 prior sessions required), floored at 2% of the 20-session average daily volume.
ENTRY      a completed regular-session 5-minute candle (9:30-15:00 start) after WATCH that
             - closes above session VWAP (from 9:30), and
             - is the first close above the pre-market high (4:00-9:29), or above a consolidation high
               (prior six 5-min candles spanning <= 6% high-to-low; level = their highest high), and
             - has volume >= 2x the median of the prior five 5-minute candles (empty intervals count as 0).
           Fill: next minute, at the ASK from historical SIP quotes (+0.2% slippage); estimated spread if no quote.
           Too extended: fill price > VWAP x 1.10 -> recorded as a missed entry, keep watching for a later candle.
           Max one entry per stock per day.
STOP       lower of the breakout candle low and VWAP at the signal. Gaps/halts fill at the next bar's open, not the stop.
SIZE       planned loss <= 0.5% of equity (also run at 1% and 2%), position value <= $500, <= 10% of the fill minute's
           volume, whole shares. Cash account: total buys per day <= settled cash. No averaging down.
EXITS      half at +2R (limit), rest trails 1 cent under the prior completed 5-minute low (only after 2R);
           before 2R the initial stop; everything closes at 15:45. Sells pay bid-side spread, 0.2% slippage, SEC + TAF fees.
Results: 'live-lab5' branch.
"""
import os, sys, re, json, math, time, subprocess, bisect
from collections import defaultdict, Counter
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
import numpy as np
import requests

ET = ZoneInfo('America/New_York')
DATA, TRADE = 'https://data.alpaca.markets', 'https://paper-api.alpaca.markets'
OUT = os.environ.get('VANTEX_LAB5_DIR', '/tmp/vantex-lab5')
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
SESSIONS = int(sys.argv[1]) if len(sys.argv) > 1 else 300
H = {'APCA-API-KEY-ID': os.environ.get('APCA_API_KEY_ID', ''), 'APCA-API-SECRET-KEY': os.environ.get('APCA_API_SECRET_KEY', '')}
SEC_UA = os.environ.get('SEC_UA') or 'Vantex research bot (github.com/shapirog/vantex-bot)'   # SEC asks for a contact; set the SEC_UA secret to add one

# ---- locked parameters ----
PMIN, PMAX = 0.50, 5.00
UP_MIN, RVOL_MIN = 0.03, 3.0
BASE_DAYS, BASE_MIN_DAYS, BASE_FLOOR = 20, 10, 0.02
CONS_N, CONS_RANGE = 6, 0.06
VOL_MULT, MAX_EXT = 2.0, 0.10
FIRST_CANDLE, LAST_CANDLE, FLAT = 570, 900, 945
EQUITY, MAX_POS, PART = 2500.0, 500.0, 0.10
RISKS, BASE_RISK = (0.005, 0.01, 0.02), 0.005
SLIP, SEC_FEE, TAF = 0.002, 27.8e-6, 0.000166
SLOT0, SLOT_MIN, NSLOT = 240, 30, 24            # 30-minute grid 4:00..16:00
CASE = ['AKAN', 'ONFO', 'GIPR', 'FCUV', 'VTSI', 'SLSN', 'WWB', 'RAIN', 'SLND', 'SHIM', 'POLA', 'SBC', 'BZFD', 'AEI', 'BKHA', 'NMAX',
        'LFMD', 'LFTO', 'BGIN', 'MOD', 'KPTCY', 'BIRD', 'FRMI', 'TGHL', 'XCH', 'CLRO', 'HAWK', 'QUCY', 'PAVM', 'MODD', 'CNVS', 'SSII',
        'NXB', 'CNSY', 'OBIO', 'TREO', 'CDXS', 'GYRO']
CASE_DAY = date(2026, 11, 13)
EXCH = {'NASDAQ', 'NYSE', 'AMEX'}
NAME_EXCL = r'\b(etf|etn|fund|trust units?|warrants?|rights?|units?|preferred|pfd|notes?|debentures?|depositary shares? (?:each )?representing|ishares|proshares|direxion|spdr|invesco|vanguard)\b|%'
GOOD = [('FDA', r'\bfda\b|approv|clearance|breakthrough designation|orphan drug'), ('TRIAL', r'phase [123i]|trial|topline|data readout'),
        ('DEAL', r'merger|acquisi|acquire|buyout|takeover|definitive agreement'), ('CONTRACT', r'contract|award|order|purchase order|government'),
        ('PARTNER', r'partner|collaborat|alliance|joint venture|licens'), ('EARNINGS', r'earnings|revenue|results|guidance|profit|record quarter'),
        ('AI', r'\bai\b|artificial intelligence|quantum|nvidia'), ('CRYPTO', r'bitcoin|crypto|blockchain|treasury'), ('UPLIST', r'uplist|nasdaq listing|regains compliance')]
BAD = [('OFFERING', r'offering|dilut|registered direct|at-the-market|warrant|private placement|pricing of'), ('SPLIT', r'reverse (stock )?split'),
       ('DELIST', r'delist|non-compliance|deficiency'), ('BANKRUPT', r'bankrupt|chapter 11|going concern')]
ROUNDUP = r'stocks moving|movers|top gainers|top losers|biggest movers|stocks to watch|stocks trading|mid-day|midday update|market update|session\b|shares are trading|why .* (shares|stock) (is|are)'
DILUTION_FORMS = {'S-1', 'S-1/A', 'F-1', 'F-1/A', 'S-3', 'S-3/A', 'F-3', 'F-3/A', '424B1', '424B2', '424B3', '424B4', '424B5', '424B7', 'EFFECT', 'S-1MEF', 'F-1MEF', 'S-3MEF'}
STATS = Counter()

def log(*a): print(' '.join(str(x) for x in a), flush=True)

def get(url, params=None, headers=None, timeout=60):
    for k in range(6):
        try: r = requests.get(url, headers=headers or H, params=params, timeout=timeout)
        except Exception as e: log('network', type(e).__name__, url[-50:]); time.sleep(2 * (k + 1)); continue
        if r.status_code == 429: time.sleep(3 * (k + 1)); continue
        STATS['requests'] += 1
        return r
    STATS['request_failures'] += 1
    return None

def mins(t): return t.hour * 60 + t.minute
def to_et(s): return datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(ET)
def tag_headline(h):
    h = h.lower()
    if re.search(ROUNDUP, h): return ['ROUNDUP']
    t = [n for n, rx in GOOD if re.search(rx, h)] + [n for n, rx in BAD if re.search(rx, h)]
    return t or ['OTHER']

# ------------------------------------------------------------------ universe + daily data
def universe():
    r = get(f'{TRADE}/v2/assets', dict(status='all', asset_class='us_equity'))
    A = r.json() if r is not None and r.ok else []
    keep, dropped = {}, Counter()
    for a in A:
        s, nm = a.get('symbol') or '', (a.get('name') or '')
        if a.get('exchange') not in EXCH: dropped['exchange (OTC/ARCA/BATS/other)'] += 1; continue
        if not re.fullmatch(r'[A-Z]{1,5}', s): dropped['symbol format (class/when-issued/odd)'] += 1; continue
        if len(s) == 5 and s[-1] in 'WRUZ': dropped['5-letter warrant/right/unit suffix'] += 1; continue
        if re.search(NAME_EXCL, nm.lower()): dropped['name says ETF/fund/warrant/right/unit/preferred/note'] += 1; continue
        keep[s] = dict(name=nm[:60], status=a.get('status'), exchange=a.get('exchange'))
    return keep, dropped

def daily_multi(syms, start, end, adjustment):
    out = defaultdict(list)
    for i in range(0, len(syms), 200):
        tok = None
        while True:
            p = dict(symbols=','.join(syms[i:i + 200]), timeframe='1Day', start=start.isoformat(), end=end.isoformat(), limit=10000, feed='sip', adjustment=adjustment)
            if tok: p['page_token'] = tok
            r = get(f'{DATA}/v2/stocks/bars', p)
            if r is None or not r.ok: STATS['daily_errors'] += 1; break
            j = r.json()
            for s, bars in (j.get('bars') or {}).items():
                for b in bars: out[s].append((to_et(b['t']).date().toordinal(), b['o'], b['h'], b['l'], b['c'], b['v']))
            tok = j.get('next_page_token')
            if not tok: break
        if (i // 200) % 10 == 0: log('  daily', adjustment, i, '/', len(syms))
    return {s: np.array(sorted(v), dtype=float) for s, v in out.items()}

# ------------------------------------------------------------------ 30-minute baselines (point-in-time relative volume)
def slot_profile(bars, sessions_set):
    """bars: list of (t_et, h, v). -> {day: (vol[24], high[24])} on the 4:00-16:00 grid"""
    D = {}
    for t, h, v in bars:
        d = t.date().toordinal()
        if d not in sessions_set: continue
        m = mins(t)
        if m < SLOT0 or m >= SLOT0 + SLOT_MIN * NSLOT: continue
        k = (m - SLOT0) // SLOT_MIN
        if d not in D: D[d] = (np.zeros(NSLOT), np.zeros(NSLOT))
        D[d][0][k] += v; D[d][1][k] = max(D[d][1][k], h)
    return D

def baseline(prof, daily_raw, daily_adj, sessions, sidx, day, band=True):
    """point-in-time baseline for one stock-day, in RAW share units -> dict or a reason string"""
    raw_i = {int(d): k for k, d in enumerate(daily_raw[:, 0])}
    adj_i = {int(d): k for k, d in enumerate(daily_adj[:, 0])} if daily_adj is not None else {}
    k = raw_i.get(day); ka = adj_i.get(day)
    if k is None or k == 0 or ka is None or ka == 0: return 'no bar'
    pc_raw, pc_adj = daily_raw[k - 1, 4], daily_adj[ka - 1, 4]
    if band and not (PMIN <= pc_raw <= PMAX): return 'outside price band'
    if abs(daily_raw[k, 4] / pc_raw - daily_adj[ka, 4] / pc_adj) > 0.01: return 'split day'
    prior = [sessions[j] for j in range(max(0, sidx[day] - BASE_DAYS), sidx[day])]
    listed = [d for d in prior if d in adj_i]
    if len(listed) < BASE_MIN_DAYS: return 'too little history'
    vols = np.array([np.cumsum(prof[d][0]) if d in prof else np.zeros(NSLOT) for d in listed])
    f = pc_adj / pc_raw                                      # raw volume = adjusted volume * pc_adj / pc_raw
    adv = float(np.mean([daily_adj[adj_i[d], 5] for d in listed]))
    return dict(pc=float(pc_raw), pc_adj=float(pc_adj), base_adj=vols.mean(axis=0), floor_adj=BASE_FLOOR * adv, f=f,
                day_open=float(daily_raw[k, 1]), day_high=float(daily_raw[k, 2]), day_close=float(daily_raw[k, 4]))

def prefilter(sym, prof, daily_raw, daily_adj, sessions, sidx, test_days, out):
    """Keep a test day only if WATCH was POSSIBLE: a necessary condition checked on 30-min bars (some slot reached
    +3% and its end-of-slot volume >= 3x the baseline at the slot START). It never drops a day the minute-level rule
    could trigger on, so it adds no hindsight."""
    for day in test_days:
        b = baseline(prof, daily_raw, daily_adj, sessions, sidx, day)
        if isinstance(b, str):
            if b != 'no bar' and b != 'outside price band': STATS['skipped: ' + b] += 1
            continue
        STATS['eligible_stock_days'] += 1
        today = prof.get(day)
        if today is None: STATS['eligible_without_intraday_bars'] += 1; continue
        cum = np.cumsum(today[0]); hi = today[1]
        base_start = np.concatenate([[0.0], b['base_adj'][:-1]])
        ok = (hi >= b['pc_adj'] * (1 + UP_MIN)) & (cum >= RVOL_MIN * np.maximum(base_start, b['floor_adj']))
        if ok.any():
            out[day].append(dict(sym=sym, pc=b['pc'], base=(b['base_adj'] * b['f']).tolist(), floor=b['floor_adj'] * b['f'],
                                 day_high=b['day_high'], day_close=b['day_close']))

def fetch_profiles(syms, start, end, sessions_set):
    """yield (sym, profile) using split-adjusted 30-minute bars, extended hours"""
    for i in range(0, len(syms), 100):
        chunk = syms[i:i + 100]; acc = defaultdict(list); tok = None
        while True:
            p = dict(symbols=','.join(chunk), timeframe='30Min', start=start.isoformat(), end=end.isoformat(), limit=10000, feed='sip', adjustment='split')
            if tok: p['page_token'] = tok
            r = get(f'{DATA}/v2/stocks/bars', p)
            if r is None or not r.ok: STATS['profile_errors'] += 1; break
            j = r.json()
            for s, bars in (j.get('bars') or {}).items():
                for b in bars: acc[s].append((to_et(b['t']), b['h'], b['v']))
            tok = j.get('next_page_token')
            if not tok: break
        for s in chunk: yield s, slot_profile(acc.get(s, []), sessions_set)
        if (i // 100) % 5 == 0: log('  30-min profiles', i, '/', len(syms))

# ------------------------------------------------------------------ minute data, quotes, news, SEC
def minutes_day(syms, day):
    d0 = datetime.combine(date.fromordinal(day), datetime.min.time(), ET)
    out = defaultdict(list)
    for i in range(0, len(syms), 50):
        tok = None
        while True:
            p = dict(symbols=','.join(syms[i:i + 50]), timeframe='1Min', start=(d0 + timedelta(hours=4)).isoformat(), end=(d0 + timedelta(hours=16)).isoformat(),
                     limit=10000, feed='sip', adjustment='raw')
            if tok: p['page_token'] = tok
            r = get(f'{DATA}/v2/stocks/bars', p)
            if r is None or not r.ok: STATS['minute_errors'] += 1; break
            j = r.json()
            for s, bars in (j.get('bars') or {}).items():
                for b in bars: out[s].append((mins(to_et(b['t'])), b['o'], b['h'], b['l'], b['c'], b['v']))
            tok = j.get('next_page_token')
            if not tok: break
    return {s: np.array(v, dtype=float) for s, v in out.items()}

def quote_at(sym, day, minute):
    """first valid SIP quote at/after the minute (within 2 minutes) -> (bid, ask) or None"""
    t0 = datetime.combine(date.fromordinal(day), datetime.min.time(), ET) + timedelta(minutes=minute)
    r = get(f'{DATA}/v2/stocks/quotes', dict(symbols=sym, start=t0.isoformat(), end=(t0 + timedelta(minutes=2)).isoformat(), limit=50, feed='sip'))
    if r is None or not r.ok: STATS['quote_errors'] += 1; return None
    for q in ((r.json().get('quotes') or {}).get(sym) or []):
        bp, ap = q.get('bp') or 0, q.get('ap') or 0
        if bp > 0 and ap >= bp and (ap - bp) / ap < 0.25: STATS['quotes_found'] += 1; return bp, ap
    STATS['quotes_missing'] += 1
    return None

def news_day(syms, day):
    d0 = datetime.combine(date.fromordinal(day), datetime.min.time(), ET)
    out = defaultdict(list)
    for i in range(0, len(syms), 40):
        tok = None
        for _ in range(20):
            p = dict(symbols=','.join(syms[i:i + 40]), start=(d0 - timedelta(hours=8)).isoformat(), end=(d0 + timedelta(hours=16)).isoformat(),
                     limit=50, sort='asc', include_content='false')
            if tok: p['page_token'] = tok
            r = get(f'{DATA}/v1beta1/news', p)
            if r is None or not r.ok: STATS['news_errors'] += 1; break
            j = r.json()
            for n in j.get('news', []):
                m = int((to_et(n['created_at']) - d0).total_seconds() // 60)
                for s in n.get('symbols', []):
                    if s in syms: out[s].append(dict(m=m, h=n.get('headline', '')[:160], src=n.get('source', ''), url=n.get('url', ''),
                                                     tags=tag_headline(n.get('headline', '')), nsym=len(n.get('symbols', []))))
            tok = j.get('next_page_token')
            if not tok: break
    return out

SEC = {'map': None, 'subs': {}, 'ok': None}
def sec_filings(sym):
    """[(acceptance datetime ET, form, items, url)] from SEC EDGAR, or None if unavailable"""
    hdr = {'User-Agent': SEC_UA, 'Accept-Encoding': 'gzip, deflate'}
    if SEC['map'] is None:
        r = get('https://www.sec.gov/files/company_tickers.json', headers=hdr, timeout=30)
        SEC['ok'] = bool(r is not None and r.ok)
        SEC['map'] = {v['ticker'].upper(): int(v['cik_str']) for v in r.json().values()} if SEC['ok'] else {}
        if not SEC['ok']: log('SEC EDGAR not reachable:', getattr(r, 'status_code', None))
    cik = SEC['map'].get(sym)
    if not cik: STATS['sec_no_cik'] += 1; return None
    if cik in SEC['subs']: return SEC['subs'][cik]
    time.sleep(0.12)
    r = get(f'https://data.sec.gov/submissions/CIK{cik:010d}.json', headers=hdr, timeout=30)
    if r is None or not r.ok: STATS['sec_errors'] += 1; SEC['subs'][cik] = None; return None
    f = r.json().get('filings', {}).get('recent', {})
    L = []
    for i in range(len(f.get('form', []))):
        try: acc = datetime.fromisoformat(f['acceptanceDateTime'][i].replace('Z', '+00:00')).astimezone(ET)
        except Exception: continue
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{f['accessionNumber'][i].replace('-', '')}/{f['primaryDocument'][i]}"
        L.append((acc, f['form'][i], f.get('items', [''] * 99999)[i] if i < len(f.get('items', [])) else '', url))
    SEC['subs'][cik] = L
    return L

# ------------------------------------------------------------------ the locked rule on one stock-day
def five_min(M):
    """minute rows -> {bucket_start: [o,h,l,c,v]} on the 5-minute grid"""
    C = {}
    for m, o, h, l, c, v in M:
        b = int(m) // 5 * 5
        if b not in C: C[b] = [o, h, l, c, v]
        else:
            x = C[b]; x[1] = max(x[1], h); x[2] = min(x[2], l); x[3] = c; x[4] += v
    return C

def evaluate(M, pc, base_end, floor):
    """returns dict with watch info and (maybe) an entry signal. All decisions use only data up to that time."""
    out = dict(watch=None)
    if M is None or not len(M): return out
    m = M[:, 0]; c = M[:, 4]; v = M[:, 5]
    cum = np.cumsum(v)
    grid_t = SLOT0 + SLOT_MIN * np.arange(NSLOT + 1)
    base_pts = np.concatenate([[0.0], np.asarray(base_end)])
    t_end = m + 1                                                   # a minute bar is known at its end
    base_t = np.maximum(np.interp(t_end, grid_t, base_pts), floor)
    cond = (c >= pc * (1 + UP_MIN)) & (cum >= RVOL_MIN * base_t)
    if not cond.any(): return out
    k = int(np.argmax(cond))
    out['watch'] = dict(min=int(t_end[k]), px=float(c[k]), rvol=round(float(cum[k] / base_t[k]), 1), chg_pct=round(float(c[k] / pc - 1) * 100, 1),
                        dvol=round(float((M[:k + 1, 4] * M[:k + 1, 5]).sum())))
    after = M[k + 1:]
    out['max_after_watch'] = float(after[:, 2].max()) if len(after) else float(c[k])
    out['day_high'] = float(M[:, 2].max())
    pm = M[m < 570]
    pmh = float(pm[:, 2].max()) if len(pm) else None
    out['pm_high'] = pmh
    C = five_min(M); keys = sorted(C)
    # session VWAP from 9:30, known at each minute end
    rth = M[m >= 570]
    vw_t, vw = [], []
    pv = vv = 0.0
    for row in rth:
        tp = (row[2] + row[3] + row[4]) / 3; pv += tp * row[5]; vv += row[5]
        vw_t.append(int(row[0]) + 1); vw.append(pv / vv if vv else row[4])
    def vwap_at(t):
        i = bisect.bisect_right(vw_t, t) - 1
        return vw[i] if i >= 0 else None
    missed = []
    for b in range(FIRST_CANDLE, LAST_CANDLE + 1, 5):
        end = b + 5
        if end < out['watch']['min'] or b not in C: continue
        o_, h_, l_, c_, v_ = C[b]
        vwap = vwap_at(end)                                          # VWAP through the candle's last minute
        if vwap is None or c_ <= vwap: continue
        prev = C.get(b - 5)
        level, kind = None, None
        if pmh and c_ > pmh and (prev is None or prev[3] <= pmh): level, kind = pmh, 'premarket high'
        else:
            prior = [C.get(b - 5 * j) for j in range(1, CONS_N + 1)]
            if all(p is not None for p in prior):
                hh = max(p[1] for p in prior); ll = min(p[2] for p in prior)
                if ll > 0 and (hh - ll) / ll <= CONS_RANGE and c_ > hh: level, kind = hh, 'consolidation high'
        if level is None: continue
        pv5 = [C[b - 5 * j][4] if (b - 5 * j) in C else 0.0 for j in range(1, 6)]
        if v_ < VOL_MULT * float(np.median(pv5)): continue
        # fill: the first minute bar at/after the candle's end
        idx = np.searchsorted(m, end)
        if idx >= len(M) or M[idx, 0] > end + 5: missed.append(dict(min=end, why='no trade in the next 5 minutes')); continue
        out_sig = dict(candle=b, level=round(level, 4), kind=kind, candle_low=l_, vwap=round(vwap, 4), fill_idx=int(idx), fill_min=int(M[idx, 0]),
                       candle_vol=v_, med5=float(np.median(pv5)))
        out_sig['fill_est'] = float(M[idx, 1])
        if out_sig['fill_est'] > vwap * (1 + MAX_EXT): missed.append(dict(min=end, why=f'too extended: {out_sig["fill_est"] / vwap - 1:.0%} above VWAP')); continue
        out['signal'] = out_sig; break
    out['missed'] = missed
    return out

def simulate_exit(M, sig, entry, stop, spread_half):
    """walk minutes from the fill. returns per-share outcome pieces (prices before slippage/spread on exits)."""
    m = M[:, 0]; i0 = sig['fill_idx']; risk = entry - stop
    target = entry + 2 * risk
    C = {}; half = None; trail = stop; mfe = 0.0; mae = 0.0; last_bucket = None
    for i in range(i0, len(M)):
        mm, o, h, l, c, v = M[i]
        if mm >= FLAT:
            px = o; return dict(half=half, rest=px * (1 - SLIP) - spread_half, rest_why='15:45 close', rest_min=int(mm), mfe=mfe, mae=mae)
        b = int(mm) // 5 * 5
        if last_bucket is not None and b != last_bucket and half is not None:     # a 5-min candle just completed
            pl = C[last_bucket][2]; trail = max(trail, pl - 0.01)
        if b not in C: C[b] = [o, h, l, c]
        else: C[b][1] = max(C[b][1], h); C[b][2] = min(C[b][2], l); C[b][3] = c
        last_bucket = b
        cur = trail if half is not None else stop
        mfe = max(mfe, h / entry - 1); mae = min(mae, l / entry - 1)
        if l <= cur:                                                 # stop first (conservative); gaps fill at the open
            px = min(cur, o) if i > i0 else min(cur, c)
            return dict(half=half, rest=px * (1 - SLIP) - spread_half, rest_why='trail' if half is not None else 'stop', rest_min=int(mm), mfe=mfe, mae=mae)
        if half is None and h >= target and i > i0:
            half = max(target, o)
    px = M[-1, 4]
    return dict(half=half, rest=px * (1 - SLIP) - spread_half, rest_why='last bar', rest_min=int(M[-1, 0]), mfe=mfe, mae=mae)

def trade_pnl(T, shares):
    """dollar P&L for a given share count, incl. fees"""
    if shares <= 0: return 0.0
    h = shares // 2 if T['half'] is not None else 0
    rest = shares - h
    proceeds = h * (T['half'] or 0) + rest * T['rest']
    fees = proceeds * SEC_FEE + min(8.3, shares * TAF)
    return proceeds - fees - shares * T['entry']

def make_trade(row, M):
    """executable fill with a real SIP quote, stop, exits. Returns the trade dict or None (and records why)."""
    sig = row['signal']; q = quote_at(row['sym'], row['day'], sig['fill_min'])
    o = sig['fill_est']
    if q: bid, ask = q
    else:
        est = 0.01 if o < 1 else max(0.01, o * 0.004)
        bid, ask = o - est / 2, o + est / 2
    entry = ask * (1 + SLIP)
    sig['entry'] = entry; sig['quote'] = bool(q); sig['spread_pct'] = round((ask - bid) / ask * 100, 2)
    if entry > sig['vwap'] * (1 + MAX_EXT): row['missed'] = (row.get('missed') or []) + [dict(min=sig['fill_min'], why='too extended at the ask')]; row['signal'] = None; return None
    stop = min(sig['candle_low'], sig['vwap'])
    if entry <= stop: row['missed'] = (row.get('missed') or []) + [dict(min=sig['fill_min'], why='entry at/below stop')]; row['signal'] = None; return None
    ex = simulate_exit(M, sig, entry, stop, (ask - bid) / 2)
    part_cap = int(PART * M[sig['fill_idx'], 5])
    T = dict(sym=row['sym'], day=row['day'], fill_min=sig['fill_min'], entry=entry, stop=stop, part_cap=part_cap, half=ex['half'], rest=ex['rest'],
             rest_why=ex['rest_why'], mfe_pct=round(ex['mfe'] * 100, 2), mae_pct=round(ex['mae'] * 100, 2),
             hit_50=bool(M[sig['fill_idx']:, 2].max() >= 1.5 * entry), premarket_watch=row['watch']['min'] < 570, kind=sig['kind'],
             news=bool(row.get('news_tags')), dilution=bool((row.get('sec') or {}).get('dilution')))
    T['r_mult'] = (trade_pnl(T, 100) / (100 * (entry - stop)))
    sh = math.floor(min(BASE_RISK * EQUITY / (entry - stop), MAX_POS / entry, part_cap))
    T['pnl_usd_at_rule_size'] = round(trade_pnl(T, sh), 2) if sh >= 1 else None; T['shares_at_rule_size'] = sh
    sig['trade'] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in T.items()}
    return T

# ------------------------------------------------------------------ account simulation
def account(trades, days, risk, cap=None):
    cap = MAX_POS if cap is None else cap
    eq = EQUITY; peak = eq; dd = 0.0; daily = []; by_day = defaultdict(list); taken = 0; skipped = Counter()
    for t in trades: by_day[t['day']].append(t)
    worst_trade = 0.0; per_year = defaultdict(float); rmults = []
    for d in days:
        cash = eq; day_pnl = 0.0
        for t in sorted(by_day.get(d, []), key=lambda x: x['fill_min']):
            risk_ps = t['entry'] - t['stop']
            sh = math.floor(min(risk * eq / risk_ps, cap / t['entry'], t['part_cap'], cash / t['entry']))
            if sh < 1: skipped['size < 1 share or no settled cash'] += 1; continue
            cash -= sh * t['entry']
            p = trade_pnl(t, sh); day_pnl += p; taken += 1
            worst_trade = min(worst_trade, p); rmults.append(p / (sh * risk_ps))
        eq += day_pnl; peak = max(peak, eq); dd = max(dd, 1 - eq / peak); daily.append(day_pnl / (eq - day_pnl) if eq - day_pnl > 0 else 0)
        per_year[date.fromordinal(d).year] += float(day_pnl)
    r = np.array(rmults) if rmults else np.array([0.0])
    wins = r[r > 0].sum(); losses = -r[r <= 0].sum()
    return dict(planned_risk_pct=risk * 100, end_equity=round(eq, 2), net_return_pct=round((eq / EQUITY - 1) * 100, 2), max_dd_pct=round(dd * 100, 2),
                trades_taken=taken, skipped=dict(skipped), win_rate_pct=round(float((r > 0).mean()) * 100, 1) if len(rmults) else None,
                profit_factor=round(float(wins / losses), 2) if losses > 0 else None, expectancy_R=round(float(r.mean()), 3) if len(rmults) else None,
                worst_trade_usd=round(worst_trade, 2), worst_day_pct=round(min(daily) * 100, 2) if daily else None,
                by_year_usd={str(k): round(v, 2) for k, v in sorted(per_year.items())}), np.array(daily)

def ruin(daily, horizons=(21, 63), paths=5000, mult=1.0, seed=11):
    g = np.random.default_rng(seed); out = {}
    if len(daily) < 20: return None
    for hz in horizons:
        hit25 = hit50 = hit100 = x32 = 0; ends = []
        for _ in range(paths):
            seq = np.maximum(daily[g.integers(0, len(daily), hz)] * mult, -1.0); eq = np.cumprod(1 + seq)
            hit25 += eq.min() <= 0.75; hit50 += eq.min() <= 0.5; hit100 += eq.min() <= 0.01; x32 += eq[-1] >= 32; ends.append(eq[-1] * EQUITY)
        e = np.array(ends)
        out[f'{hz}_sessions'] = dict(p_down25=round(hit25 / paths * 100, 2), p_down50=round(hit50 / paths * 100, 2), p_ruin=round(hit100 / paths * 100, 2),
                                     p_reach_80k=round(x32 / paths * 100, 3), end_p5=round(float(np.percentile(e, 5))), end_median=round(float(np.median(e))),
                                     end_p95=round(float(np.percentile(e, 95))))
    return out

# ------------------------------------------------------------------ main
def main():
    t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    today = datetime.now(ET).date()
    r = get(f'{TRADE}/v2/calendar', dict(start=str(today - timedelta(days=int((SESSIONS + BASE_DAYS + 5) * 1.6) + 30)), end=str(today - timedelta(days=1))))
    cal = [(date.fromisoformat(c['date']).toordinal(), c['close']) for c in (r.json() if r is not None and r.ok else [])]
    sessions = [d for d, cl in cal if cl.startswith('16') and d < today.toordinal()]       # half days excluded everywhere
    test_days = sessions[-SESSIONS:]
    sessions_set = set(sessions); SIDX = {d: k for k, d in enumerate(sessions)}
    U, dropped = universe(); syms = sorted(U)
    log('universe', len(syms), 'common-stock symbols; excluded', dict(dropped), round(time.time() - t0), 's')
    s0 = datetime.combine(date.fromordinal(sessions[-(SESSIONS + BASE_DAYS + 3)]), datetime.min.time(), ET); s1 = datetime.combine(today, datetime.min.time(), ET)
    RAW = daily_multi(syms, s0 - timedelta(days=7), s1, 'raw')
    ADJ = daily_multi(syms, s0 - timedelta(days=7), s1, 'split')
    log('daily done', len(RAW), round(time.time() - t0), 's')
    test_set = set(test_days)
    cand_syms = [s for s, A in RAW.items() if ((A[:, 4] >= PMIN * 0.8) & (A[:, 4] <= PMAX * 1.2)).any()]
    coverage = dict(universe_symbols=len(syms), with_daily_bars=len(RAW), without_any_bars=len(set(syms) - set(RAW)),
                    in_price_band_at_some_point=len(cand_syms), inactive_symbols_in_universe=sum(1 for s in syms if U[s]['status'] != 'active'),
                    examples_without_bars=sorted(set(syms) - set(RAW))[:30])
    # runners from daily data (for the missed-runner count)
    runners = {}
    for s in cand_syms:
        A = RAW[s]
        for i in range(1, len(A)):
            d = int(A[i, 0])
            if d in test_set and PMIN <= A[i - 1, 4] <= PMAX and A[i, 2] / A[i - 1, 4] >= 1.5:
                Aj = ADJ.get(s); ja = None if Aj is None else np.searchsorted(Aj[:, 0], d)
                if Aj is None or ja is None or ja == 0 or ja >= len(Aj) or Aj[ja, 0] != d: continue
                if abs(A[i, 4] / A[i - 1, 4] - Aj[ja, 4] / Aj[ja - 1, 4]) > 0.01: continue          # split day, not a run
                runners[(s, d)] = float(A[i, 2] / A[i - 1, 4] - 1)
    # 30-minute profiles -> point-in-time baselines -> necessary-condition prefilter
    CANDS = defaultdict(list)
    for s, prof in fetch_profiles(cand_syms, s0, s1, sessions_set):
        if s in RAW: prefilter(s, prof, RAW[s], ADJ.get(s), sessions, SIDX, test_days, CANDS)
    log('prefilter done:', sum(len(v) for v in CANDS.values()), 'stock-days could have triggered WATCH', dict(STATS), round(time.time() - t0), 's')
    del ADJ
    # minute-level replay
    ROWS, SIGS = [], []
    for di, day in enumerate(test_days):
        C = CANDS.get(day, [])
        if not C: continue
        M = minutes_day([c['sym'] for c in C], day)
        for cd in C:
            ev = evaluate(M.get(cd['sym']), cd['pc'], cd['base'], cd['floor'])
            if not ev['watch']: continue
            row = dict(sym=cd['sym'], day=day, pc=cd['pc'], **ev)
            ROWS.append(row)
            if ev.get('signal'): SIGS.append((row, M[cd['sym']]))
        if di % 20 == 0: log('replay day', di, '/', len(test_days), date.fromordinal(day), 'watch', len(ROWS), 'signals', len(SIGS), round(time.time() - t0), 's')
    # catalysts for WATCH rows (news before WATCH; SEC filings before WATCH; dilution flags)
    by_day = defaultdict(list)
    for row in ROWS: by_day[row['day']].append(row)
    for day, rows in by_day.items():
        N = news_day([r_['sym'] for r_ in rows], day)
        for row in rows:
            real = [n for n in N.get(row['sym'], []) if n['tags'][0] != 'ROUNDUP' and n['nsym'] <= 4]
            pre = [n for n in real if n['m'] <= row['watch']['min']]
            row['news_before_watch'] = [dict(min=n['m'], h=n['h'], src=n['src'], url=n['url'], tags=n['tags']) for n in pre[-3:]]
            row['news_tags'] = sorted({t for n in pre for t in n['tags']})
    log('news done', round(time.time() - t0), 's')
    sec_rows = [r_ for r_ in ROWS if r_.get('signal')] + [r_ for r_ in ROWS if not r_.get('signal')][:3000]
    for row in sec_rows:
        F = sec_filings(row['sym'])
        if F is None: row['sec'] = None; continue
        wt = datetime.combine(date.fromordinal(row['day']), datetime.min.time(), ET) + timedelta(minutes=row['watch']['min'])
        recent = [f for f in F if wt - timedelta(days=90) <= f[0] <= wt]
        row['sec'] = dict(catalyst=[dict(t=f[0].isoformat(), form=f[1], items=f[2], url=f[3]) for f in recent if f[0] >= wt - timedelta(hours=20) and f[1] in ('8-K', '6-K', '8-K/A', '425', 'SC TO-T')][:3],
                          dilution=[dict(t=f[0].isoformat()[:10], form=f[1], url=f[3]) for f in recent if f[1] in DILUTION_FORMS or (f[1] == '8-K' and '3.02' in (f[2] or ''))][:5],
                          reverse_split_hint=[dict(t=f[0].isoformat()[:10], form=f[1]) for f in recent if f[1] == '8-K' and '5.03' in (f[2] or '')][:2])
    log('SEC done', SEC['ok'], round(time.time() - t0), 's')
    # executable fills with real quotes
    TR = []
    for row, M in SIGS:
        T = make_trade(row, M)
        if T: TR.append(T)
    log('fills done', len(TR), 'trades', dict(STATS), round(time.time() - t0), 's')
    # ---------------- metrics ----------------
    W = ROWS
    pre = [r_ for r_ in W if r_['watch']['min'] < 570]; reg = [r_ for r_ in W if r_['watch']['min'] >= 570]
    def alert_stats(rows):
        if not rows: return dict(n=0)
        before10 = [r_ for r_ in rows if r_['watch']['px'] < r_['pc'] * 1.10]
        false_ = [r_ for r_ in rows if r_['max_after_watch'] < r_['watch']['px'] * 1.10]
        return dict(n=len(rows), alerts_before_plus10=len(before10),
                    before10_then_reached_plus20_pct=round(100 * sum(1 for r_ in before10 if r_['day_high'] >= r_['pc'] * 1.2) / len(before10), 1) if before10 else None,
                    before10_then_reached_plus50_pct=round(100 * sum(1 for r_ in before10 if r_['day_high'] >= r_['pc'] * 1.5) / len(before10), 1) if before10 else None,
                    false_alerts_pct=round(100 * len(false_) / len(rows), 1),
                    reached_plus10_after_watch_pct=round(100 - 100 * len(false_) / len(rows), 1),
                    with_signal=sum(1 for r_ in rows if r_.get('signal')), median_watch_rvol=float(np.median([r_['watch']['rvol'] for r_ in rows])))
    watched = {(r_['sym'], r_['day']): r_ for r_ in W}
    miss_never = [k for k in runners if k not in watched]
    miss_late = [k for k in runners if k in watched and watched[k]['watch']['px'] >= watched[k]['pc'] * 1.25]
    runner_stats = dict(runner_days_plus50=len(runners), never_watched=len(miss_never), watched_only_after_plus25=len(miss_late),
                        watched_before_plus25=len(runners) - len(miss_never) - len(miss_late),
                        runner_days_with_entry=sum(1 for k in runners if k in watched and watched[k].get('signal')),
                        never_watched_examples=[(s, str(date.fromordinal(d)), round(runners[(s, d)] * 100)) for s, d in sorted(miss_never, key=lambda k: -runners[k])[:15]])
    def tstats(T):
        if not T: return dict(trades=0)
        r_ = np.array([t['r_mult'] for t in T]); w = r_[r_ > 0].sum(); l = -r_[r_ <= 0].sum()
        return dict(trades=len(T), win_rate_pct=round(float((r_ > 0).mean()) * 100, 1), expectancy_R=round(float(r_.mean()), 3),
                    profit_factor=round(float(w / l), 2) if l > 0 else None, hit_plus50_from_entry=sum(t['hit_50'] for t in T),
                    median_mfe_pct=round(float(np.median([t['mfe_pct'] for t in T])), 2), median_mae_pct=round(float(np.median([t['mae_pct'] for t in T])), 2),
                    exits=dict(Counter(t['rest_why'] for t in T)), half_at_2R_pct=round(100 * sum(1 for t in T if t['half'] is not None) / len(T), 1))
    breakdown = dict(all=tstats(TR), premarket_gappers=tstats([t for t in TR if t['premarket_watch']]), regular_session=tstats([t for t in TR if not t['premarket_watch']]),
                     premarket_high_break=tstats([t for t in TR if t['kind'] == 'premarket high']), consolidation_break=tstats([t for t in TR if t['kind'] != 'premarket high']),
                     with_news_before_watch=tstats([t for t in TR if t['news']]), no_news=tstats([t for t in TR if not t['news']]),
                     sec_dilution_flag=tstats([t for t in TR if t['dilution']]), no_dilution_flag=tstats([t for t in TR if not t['dilution']]))
    for y in sorted({date.fromordinal(t['day']).year for t in TR}): breakdown[f'year_{y}'] = tstats([t for t in TR if date.fromordinal(t['day']).year == y])
    ACC, RUIN = {}, {}
    for rk in RISKS:
        a, daily = account(TR, test_days, rk); ACC[f'{rk * 100:.1f}% ($500 cap - the rule)'] = a; RUIN[f'{rk * 100:.1f}% ($500 cap)'] = ruin(daily)
        a, daily = account(TR, test_days, rk, cap=1e12); ACC[f'{rk * 100:.1f}% (no $500 cap, cash only)'] = a; RUIN[f'{rk * 100:.1f}% (no cap)'] = ruin(daily)
    # lottery illustration: 10% of equity risked per trade, no position cap (NOT a recommendation)
    a, daily = account(TR, test_days, 0.10, cap=1e12)
    lottery = dict(account=a, ruin=ruin(daily))
    target = dict(goal='$2,500 -> $80,000 = 32x', per_session_needed_21=round((32 ** (1 / 21) - 1) * 100, 2), per_session_needed_63=round((32 ** (1 / 63) - 1) * 100, 2),
                  note='Shown as risk math only. The strategy is not tuned toward this target.')
    # case study: Nov 13 screenshot symbols, same locked rules, regardless of the price band (eligibility shown)
    case = []
    cd = CASE_DAY.toordinal()
    if cd in sessions_set:
        Mc = minutes_day(CASE, cd); Nc = news_day(CASE, cd)
        prevd = sessions[sessions.index(cd) - 1]
        c0 = datetime.combine(date.fromordinal(sessions[sessions.index(cd) - BASE_DAYS - 2]), datetime.min.time(), ET); c1 = datetime.combine(CASE_DAY + timedelta(days=1), datetime.min.time(), ET)
        dr = daily_multi(CASE, c0 - timedelta(days=5), c1, 'raw'); CADJ = daily_multi(CASE, c0 - timedelta(days=5), c1, 'split')
        CPROF = dict(fetch_profiles(CASE, c0, c1, sessions_set))
        for s in CASE:
            A = dr.get(s); row = dict(sym=s)
            if A is None or not len(A): row['note'] = 'no daily bars from Alpaca (not covered)'; case.append(row); continue
            ii = {int(d): k for k, d in enumerate(A[:, 0])}
            if cd not in ii or ii[cd] == 0: row['note'] = 'no bar for 2026-11-13'; case.append(row); continue
            k = ii[cd]; pc = A[k - 1, 4]
            row.update(prev_close=pc, close=A[k, 4], day_change_pct=round((A[k, 4] / pc - 1) * 100, 2), high_pct=round((A[k, 2] / pc - 1) * 100, 1),
                       in_price_band=bool(PMIN <= pc <= PMAX), in_universe=s in U)
            b = baseline(CPROF.get(s, {}), A, CADJ.get(s), sessions, SIDX, cd, band=False) if s in CADJ else 'no split-adjusted bars'
            if isinstance(b, str): ev = dict(watch=None); row['baseline'] = b
            else: ev = evaluate(Mc.get(s), pc, (b['base_adj'] * b['f']).tolist(), b['floor_adj'] * b['f'])
            row['in_backtest_candidates'] = any(c_['sym'] == s for c_ in CANDS.get(cd, []))
            row['watch'] = ev.get('watch'); row['missed'] = ev.get('missed')
            if ev.get('signal'):
                srow = next((x for x, _ in SIGS if x['sym'] == s and x['day'] == cd), None)
                if srow is not None: row['signal'] = srow.get('signal'); row['missed'] = srow.get('missed')
                else:
                    tmp = dict(sym=s, day=cd, watch=ev['watch'], signal=ev['signal'], missed=ev.get('missed'))
                    make_trade(tmp, Mc[s]); row['signal'] = tmp.get('signal'); row['missed'] = tmp.get('missed')
            row['news_before_open'] = [dict(min=n['m'], h=n['h'], src=n['src']) for n in Nc.get(s, []) if n['m'] < 570 and n['tags'][0] != 'ROUNDUP'][:2]
            case.append(row)
    R = dict(updated=datetime.now(ET).isoformat(timespec='seconds'), sessions=len(test_days), first=str(date.fromordinal(test_days[0])), last=str(date.fromordinal(test_days[-1])),
             locked_rules=__doc__, coverage=coverage, universe_excluded=dict(dropped), stats=dict(STATS), sec_available=SEC['ok'],
             alerts=dict(all=alert_stats(W), premarket=alert_stats(pre), regular_session=alert_stats(reg)), runners=runner_stats,
             trades=breakdown, accounts=ACC, risk_of_ruin=RUIN, lottery_10pct_risk_no_cap=lottery, target_math=target, case_study_2026_11_13=case,
             limitations=['Alpaca asset list is today\'s list (incl. inactive symbols it still carries), not a point-in-time listing history; '
                          'delisted names Alpaca dropped are missing (survivorship bias remains).',
                          'Common-stock filter is by exchange, symbol suffix and name keywords; some ETFs/units may slip through or real stocks be excluded.',
                          'No historical trading-halt (LULD) feed: halts are approximated by filling at the next available bar.',
                          'Quotes: one SIP quote snapshot at the fill minute; exits use the entry spread. Queue position/partial fills beyond the 10% participation cap are not modeled.',
                          'News = Alpaca/Benzinga headlines; not every press release, exchange notice or SEC filing appears there.',
                          'SEC: only tickers in today\'s SEC ticker map; renamed/delisted companies are missed; 3000 non-signal WATCH rows checked at most.',
                          'Historical results are exploratory: ~650 prior trials, and recent months were viewed during development.'],
             seconds=round(time.time() - t0))
    json.dump(R, open(f'{OUT}/lab5.json', 'w'), separators=(',', ':'), default=str)
    with open(f'{OUT}/lab5_trades.jsonl', 'w') as f:
        for t in TR: f.write(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in dict(t, day=str(date.fromordinal(t['day']))).items()}) + '\n')
    with open(f'{OUT}/lab5_watch.jsonl', 'w') as f:
        for r_ in W: f.write(json.dumps(dict(r_, day=str(date.fromordinal(r_['day']))), default=str) + '\n')
    open(f'{OUT}/lab5_report.md', 'w').write(report(R))
    log(json.dumps(dict(event='lab5_done', seconds=R['seconds'], watch=len(W), trades=len(TR))))
    publish()

def report(R):
    L = [f"# Vantex lab 5 — {R['updated']}", f"{R['sessions']} sessions {R['first']} → {R['last']}", '', '## Coverage', '```', json.dumps(R['coverage'], indent=1), json.dumps(R['universe_excluded'], indent=1), json.dumps(R['stats'], indent=1), '```',
         '## Alerts', '```', json.dumps(R['alerts'], indent=1), json.dumps(R['runners'], indent=1), '```', '## Trades (R multiples, per trade)', '```', json.dumps(R['trades'], indent=1), '```',
         '## $2,500 account', '| planned risk | end equity | net | max DD | trades | win | PF | expectancy R | worst trade | worst day | by year |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for k, a in R['accounts'].items():
        L.append(f"| {k} | ${a['end_equity']} | {a['net_return_pct']}% | {a['max_dd_pct']}% | {a['trades_taken']} | {a['win_rate_pct']}% | {a['profit_factor']} | {a['expectancy_R']} | ${a['worst_trade_usd']} | {a['worst_day_pct']}% | {a['by_year_usd']} |")
    L += ['', '## Risk of ruin (bootstrap of daily account returns)', '```', json.dumps(R['risk_of_ruin'], indent=1), '```', '## $80K math', '```', json.dumps(R['target_math'], indent=1), json.dumps(R['lottery_10pct_risk_no_cap'], indent=1), '```',
          '## Case study 2026-11-13', '| sym | prev close | day % | in band | WATCH | entry | result |', '|---|---|---|---|---|---|---|']
    for c in R['case_study_2026_11_13']:
        w = c.get('watch'); s = c.get('signal') or {}; t = s.get('trade') or {}
        hm = lambda x: '%02d:%02d' % divmod(int(x), 60)
        wtxt = f"{hm(w['min'])} ({w['chg_pct']}%, {w['rvol']}x)" if w else (c.get('note') or c.get('baseline') or 'never met WATCH')
        etxt = f"{hm(s['fill_min'])} @ {round(s.get('entry', s.get('fill_est', 0)), 4)}" if s else str(c.get('missed') or '-')[:120]
        rtxt = f"R={round(t['r_mult'], 2)} (${t.get('pnl_usd_at_rule_size')}) MFE {t['mfe_pct']}% MAE {t['mae_pct']}% {t['rest_why']}" if t else '-'
        L.append(f"| {c['sym']} | {c.get('prev_close')} | {c.get('day_change_pct')} | {c.get('in_price_band')} | {wtxt} | {etxt} | {rtxt} |")
    L += ['', '## Limitations'] + ['- ' + x for x in R['limitations']]
    return '\n'.join(L) + '\n'

def publish():
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', 'live-lab5', OUT], check=True)
    subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', 'lab5'], check=True)
    subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{REPO}.git', 'live-lab5'], check=True, timeout=120, capture_output=True)

if __name__ == '__main__':
    main()
