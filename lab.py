"""Vantex strategy lab: tests many day-trading strategies on ~2 years of real market data. Read-only: places no trades.

Every strategy is judged the honest way:
  - TRAIN = the older 70% of days, TEST = the newest 30% the strategy never "saw"
  - it PASSES only if it makes money in BOTH halves (profit factor 1.2+ in each, and 20+ test trades)
  - costs are charged on every trade (stock slippage + fees; options bid/ask spread)

Strategies tested
  OVN  "Where the market opens tells you which level it hunts" (the NQ reel): if QQQ/SPY open in the upper half of the
       overnight range, aim for the overnight HIGH; lower half -> the overnight LOW. Also measures the raw hit rates.
  ORB5 The 5-minute opening-range breakout on "stocks in play" (Zarattini, Barbon & Aziz 2024): each day take the stocks
       with the highest relative opening volume, trade the break of the first 5-minute candle in its direction,
       stop at 10% of the 14-day ATR, exit at the close.
  ORB15 the same with a 15-minute opening range.
  IDX  QQQ/SPY break of the 9:30-10:00 range that holds (the live options bot's index setup), stop at the range middle.
Each is tested with SHARES and with OPTIONS (same-day for QQQ/SPY, this week's for stocks; modeled prices),
and options with three exit styles: follow the stock's stop/target only, add -50% option stop, add +100% take-profit.
Results go to the 'live-lab' branch for the Portfolio page.
"""
import os, sys, json, math, time, subprocess, bisect
from collections import defaultdict
from datetime import datetime, timedelta, timezone, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import options as O

ET, req, TRADE, DATA = O.ET, O.req, O.TRADE, O.DATA
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 500
OUT = os.environ.get('VANTEX_LAB_DIR', '/tmp/vantex-lab')
START_EQ = 2500.0
INDEXES = ['QQQ', 'SPY']
STOCKS = list(dict.fromkeys(O.LIQUID + ['SMCI', 'ARM', 'SHOP', 'CRWD', 'SNOW', 'HOOD', 'SOFI', 'RIVN', 'NIO', 'INTC', 'DIS', 'JPM', 'XOM', 'LLY', 'WMT', 'COST']))
SLIP = 0.0002                  # stock slippage per side (0.02%)
SPREAD_IDX, SPREAD_STK, IV_MULT, IV_FLOOR = 0.03, 0.04, 1.1, 0.12
OPT_RISK = 0.15                # options: share of equity paid per trade
LEV = 2.0                      # shares: most a small account can hold at once (2x buying power)
TRAIN_FRAC, PASS_PF, MIN_TEST = 0.70, 1.2, 20
O_SEC = 27.8e-6               # SEC fee on stock sales

def ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
def bs(S, K, T, vol, call):
    if T <= 1e-9 or vol <= 0: return max(0.0, (S - K) if call else (K - S))
    v = vol * math.sqrt(T); d1 = (math.log(S / K) + 0.5 * v * v) / v; d2 = d1 - v
    return S * ncdf(d1) - K * ncdf(d2) if call else K * ncdf(-d2) - S * ncdf(-d1)

# ---------------- data ----------------
FEED = {'name': 'sip'}
def bars(syms, tf, start, end):
    """{sym: [(t_et, o, h, l, c, v)]} oldest first. Tries the full-market SIP feed (free for history), falls back to IEX."""
    out = defaultdict(list)
    for i in range(0, len(syms), 3):
        group, tok = syms[i:i + 3], None
        for _ in range(400):
            p = dict(symbols=','.join(group), timeframe=tf, start=start.isoformat(), end=end.isoformat(), limit=10000, feed=FEED['name'], adjustment='split')
            if tok: p['page_token'] = tok
            r = req('GET', f'{DATA}/v2/stocks/bars', params=p)
            if r.status_code in (401, 403, 422) and FEED['name'] == 'sip':
                print('SIP history not allowed, using IEX:', r.text[:120], flush=True); FEED['name'] = 'iex'; continue
            if not r.ok: print('bars error', r.status_code, r.text[:160], flush=True); break
            j = r.json()
            for s, B in (j.get('bars') or {}).items():
                for b in B: out[s].append((datetime.fromisoformat(b['t'].replace('Z', '+00:00')).astimezone(ET), b['o'], b['h'], b['l'], b['c'], b['v']))
            tok = j.get('next_page_token')
            if not tok: break
    for s in out: out[s].sort(key=lambda x: x[0])
    return out

def trading_days():
    end = datetime.now(ET).date() - timedelta(days=1)
    r = req('GET', f'{TRADE}/v2/calendar', params=dict(start=str(end - timedelta(days=int(DAYS * 1.5) + 20)), end=str(end)))
    return [date.fromisoformat(c['date']) for c in (r.json() if r.ok else [])][-DAYS:]

def mins(t): return t.hour * 60 + t.minute

def prepare(days):
    t0 = datetime.combine(days[0] - timedelta(days=40), datetime.min.time(), ET); t1 = datetime.combine(days[-1] + timedelta(days=1), datetime.min.time(), ET)
    syms = INDEXES + STOCKS
    D = bars(syms, '1Day', t0, t1)
    M = bars(syms, '5Min', datetime.combine(days[0] - timedelta(days=5), datetime.min.time(), ET), t1)
    rth, ext = defaultdict(dict), defaultdict(dict)
    for s, L in M.items():
        for b in L:
            d = b[0].date(); m = mins(b[0])
            if 570 <= m < 960: rth[s].setdefault(d, []).append(b)
            else: ext[s].setdefault(d, []).append(b)
    info = defaultdict(dict)          # (sym) -> day -> dict(atr, adv, vol20, or_vol_avg)
    for s, L in D.items():
        ds = [b[0].date() for b in L]
        for day in days:
            i = bisect.bisect_left(ds, day)
            if i < 15: continue
            prev = L[i - 15:i]
            trs = [max(prev[k][2], prev[k - 1][4]) - min(prev[k][3], prev[k - 1][4]) for k in range(1, 15)]
            rets = [math.log(prev[k][4] / prev[k - 1][4]) for k in range(1, 15) if prev[k - 1][4] > 0]
            sd = (sum((x - sum(rets) / len(rets)) ** 2 for x in rets) / (len(rets) - 1)) ** 0.5 if len(rets) > 2 else 0.02
            info[s][day] = dict(atr=sum(trs) / len(trs), adv=sum(b[5] for b in prev[1:]) / 14, vol=max(IV_FLOOR, sd * math.sqrt(252) * IV_MULT))
    # opening 5-minute volume history for relative volume
    for s in syms:
        hist = []
        for day in sorted(rth[s]):
            B = rth[s][day]
            v5 = B[0][5] if B and mins(B[0][0]) == 570 else None
            if day in info[s] and len(hist) >= 14: info[s][day]['rv5'] = (v5 / (sum(hist[-14:]) / 14)) if v5 and sum(hist[-14:]) > 0 else 0
            if v5: hist.append(v5)
    return rth, ext, info, FEED['name']

# ---------------- trade simulation ----------------
def years_left(idx, day, m):
    left = max(0, 16 * 60 - m) / 390
    if idx: return left / 252
    k = (4 - day.weekday()) % 7
    if k < 2: k += 7
    return (sum(1 for i in range(1, k + 1) if (day + timedelta(days=i)).weekday() < 5) + left) / 252

def walk(B, i0, d, entry, stop, target):
    """Follow 5-minute bars after entry. Returns (exit_price, exit_bar_index, why). Stop is checked before target (conservative).
    On the entry bar of a breakout, the part of the bar BEFORE the break doesn't count: only its close can stop it out."""
    mid = abs(entry - B[i0][1]) > 1e-9
    for i in range(i0, len(B)):
        t, o, h, l, c, v = B[i]
        if i == i0 and mid: l, h = (min(c, entry), max(h, entry)) if d == 1 else (min(l, entry), max(c, entry))
        if d == 1:
            if l <= stop: return min(stop, o) if i > i0 else stop, i, 'stop'
            if target and h >= target: return max(target, o) if i > i0 else target, i, 'target'
        else:
            if h >= stop: return max(stop, o) if i > i0 else stop, i, 'stop'
            if target and l <= target: return min(target, o) if i > i0 else target, i, 'target'
        if mins(t) >= 955: return c, i, 'close'
    return B[-1][4], len(B) - 1, 'close'

def sim_option(B, i0, d, entry_px, stop, target, idx, day, vol, exit_style):
    """Buy an at-the-money option when the stock signal fires; value it every 5 minutes with Black-Scholes."""
    spr = SPREAD_IDX if idx else SPREAD_STK
    step = 1 if idx else (1 if entry_px < 50 else 2.5 if entry_px < 200 else 5)
    K = round(entry_px / step) * step; m0 = mins(B[i0][0])
    prem = bs(entry_px, K, years_left(idx, day, m0), vol, d == 1) * (1 + spr / 2)
    if prem < 0.05: return None
    flat = 900 if idx else 945; mid = abs(entry_px - B[i0][1]) > 1e-9
    for i in range(i0, len(B)):
        t, o, h, l, c, v = B[i]; m = mins(t) + 5
        if i == i0 and mid: l, h = (min(c, entry_px), max(h, entry_px)) if d == 1 else (min(l, entry_px), max(c, entry_px))
        tl = years_left(idx, day, min(m, 960))
        worst = l if d == 1 else h
        hit_stop = (l <= stop) if d == 1 else (h >= stop)
        hit_tgt = target and ((h >= target) if d == 1 else (l <= target))
        val_close = bs(c, K, tl, vol, d == 1) * (1 - spr / 2)
        val_worst = bs(worst, K, tl, vol, d == 1) * (1 - spr / 2)
        if hit_stop: return prem, bs(stop, K, tl, vol, d == 1) * (1 - spr / 2), 'stock stop'
        if exit_style >= 2 and val_worst <= prem * 0.5: return prem, prem * 0.5, 'option -50%'
        if hit_tgt: return prem, bs(target, K, tl, vol, d == 1) * (1 - spr / 2), 'stock target'
        best = h if d == 1 else l
        if exit_style >= 3 and bs(best, K, tl, vol, d == 1) * (1 - spr / 2) >= prem * 2: return prem, prem * 2, 'option +100%'
        if m >= flat: return prem, val_close, 'time'
    return prem, bs(B[-1][4], K, 1e-6, vol, d == 1) * (1 - spr / 2), 'time'

# ---------------- signal families ----------------
def sig_ovn(day, rth, ext, info, prev_day):
    """The reel: open in the upper half of the overnight range -> target the overnight high; lower half -> low."""
    out, stats = [], []
    for s in INDEXES:
        B = rth[s].get(day)
        if not B or mins(B[0][0]) != 570: continue
        on = [b for b in ext[s].get(prev_day, []) if mins(b[0]) >= 960] + [b for b in ext[s].get(day, []) if mins(b[0]) < 570]
        if len(on) < 10: continue
        hi, lo = max(b[2] for b in on), min(b[3] for b in on); mid = (hi + lo) / 2; o = B[0][1]
        if hi - lo <= 0: continue
        hi_hit = max(b[2] for b in B) >= hi; lo_hit = min(b[3] for b in B) <= lo
        where = 'above' if o > hi else 'below' if o < lo else ('upper' if o >= mid else 'lower')
        stats.append(dict(sym=s, where=where, hi_hit=hi_hit, lo_hit=lo_hit))
        if where not in ('upper', 'lower'): continue
        d = 1 if where == 'upper' else -1; tgt = hi if d == 1 else lo; dist = abs(tgt - o)
        if dist <= o * 0.0005: continue
        out.append(dict(sym=s, idx=True, d=d, i0=0, entry=o, target=tgt, stops={'mid': mid, '1R': o - d * dist}))
    return out, stats

def sig_orb(day, rth, info, n_bars, top_n):
    """Opening-range breakout on stocks in play (highest relative opening volume)."""
    cands = []
    for s in STOCKS:
        B = rth[s].get(day); I = info[s].get(day)
        if not B or not I or len(B) < n_bars + 2 or mins(B[0][0]) != 570: continue
        if B[0][1] < 5 or I['adv'] < 1_000_000 or I['atr'] < 0.5 or I.get('rv5', 0) < 1.0: continue
        o, c = B[0][1], B[n_bars - 1][4]
        if c == o: continue
        cands.append((I['rv5'], s, 1 if c > o else -1, max(b[2] for b in B[:n_bars]), min(b[3] for b in B[:n_bars]), I))
    out = []
    for rv, s, d, hi, lo, I in sorted(cands, reverse=True)[:top_n]:
        B = rth[s][day]; level = hi if d == 1 else lo
        for i in range(n_bars, len(B)):
            if mins(B[i][0]) >= 955: break
            if (B[i][2] >= level) if d == 1 else (B[i][3] <= level):
                entry = max(level, B[i][1]) if d == 1 else min(level, B[i][1])
                out.append(dict(sym=s, idx=False, d=d, i0=i, entry=entry, target=None, stops={'10%ATR': entry - d * 0.10 * I['atr']}))
                break
    return out

def sig_idx(day, rth, info):
    """QQQ/SPY: first 5-minute close outside the 9:30-10:00 range (10:00-1:30), on the right side of VWAP."""
    out = []
    for s in INDEXES:
        B = rth[s].get(day)
        if not B or len(B) < 12 or mins(B[0][0]) != 570: continue
        hi, lo = max(b[2] for b in B[:6]), min(b[3] for b in B[:6]); pv = vv = 0.0
        for i, b in enumerate(B):
            pv += (b[2] + b[3] + b[4]) / 3 * b[5]; vv += b[5]
            if i < 6: continue
            if mins(b[0]) > 810 or i + 1 >= len(B): break
            vw = pv / vv if vv else b[4]
            d = 1 if (b[4] > hi and b[4] > vw) else -1 if (b[4] < lo and b[4] < vw) else 0
            if d:
                out.append(dict(sym=s, idx=True, d=d, i0=i + 1, entry=B[i + 1][1], target=None, stops={'mid': (hi + lo) / 2}))
                break
    return out

# ---------------- run ----------------
def evaluate(name, signals_by_day, rth, info, days, mode, stop_key, exit_style=1, max_per_day=4):
    eq = START_EQ; T = []; curve = []
    for day in days:
        sigs = [s for s in signals_by_day.get(day, []) if stop_key in s['stops']][:(max_per_day if mode == 'shares' else 2)]
        if not sigs: curve.append(eq); continue
        day_pnl = 0.0
        for g in sigs:
            B = rth[g['sym']][day]; I = info[g['sym']].get(day, {}); stop = g['stops'][stop_key]
            if (stop - g['entry']) * g['d'] >= 0: continue
            if mode == 'shares':
                risk = abs(g['entry'] - stop)
                qty = min(eq * 0.01 / risk, eq * LEV / max(1, len(sigs)) / g['entry'])
                px, _, why = walk(B, g['i0'], g['d'], g['entry'], stop, g['target'])
                gross = (px - g['entry']) * g['d'] * qty
                cost = qty * (g['entry'] + px) * SLIP + qty * px * O_SEC
                pnl = gross - cost; base = qty * g['entry']
            else:
                r = sim_option(B, g['i0'], g['d'], g['entry'], stop, g['target'], g['idx'], day, I.get('vol', 0.3), exit_style)
                if not r: continue
                prem, out_px, why = r; budget = eq * OPT_RISK              # same as the live options bot: 15% per trade, 2 at most
                n = int(budget // (prem * 100))
                if n < 1: continue
                pnl = n * (out_px - prem) * 100 - n * 0.10; base = n * prem * 100
            day_pnl += pnl
            T.append(dict(day=day.isoformat(), sym=g['sym'], d=g['d'], pnl=round(pnl, 2), ret=round(pnl / base * 100, 2) if base else 0, why=why))
        eq += day_pnl; curve.append(eq)
        if eq <= 50: break
    return T, curve

def stats(T, curve, start_eq):
    if not T: return dict(trades=0)
    p = [t['pnl'] for t in T]; w = [x for x in p if x > 0]; gl = -sum(x for x in p if x <= 0)
    pk, dd = start_eq, 0.0
    for e in curve: pk = max(pk, e); dd = max(dd, (pk - e) / pk * 100 if pk > 0 else 0)
    return dict(trades=len(T), win_rate=round(len(w) / len(T) * 100, 1), pf=round(sum(w) / gl, 2) if gl > 0 else None,
                net=round(sum(p), 2), ret_pct=round((curve[-1] / start_eq - 1) * 100, 1) if curve else 0, max_dd_pct=round(dd, 1),
                avg_ret=round(sum(t['ret'] for t in T) / len(T), 2))

def main():
    t0 = time.time(); days = trading_days()
    if len(days) < 60: sys.exit('not enough trading days')
    print(f'lab {days[0]} -> {days[-1]} ({len(days)} days)', flush=True)
    rth, ext, info, feed = prepare(days)
    print('data ready', feed, round(time.time() - t0), 's', flush=True)
    cut = int(len(days) * TRAIN_FRAC); train, test = days[:cut], days[cut:]
    sig = {'OVN': {}, 'ORB5': {}, 'ORB15': {}, 'IDX': {}}; ovn_stats = []
    for k, day in enumerate(days):
        prev = days[k - 1] if k else day - timedelta(days=1)
        a, st = sig_ovn(day, rth, ext, info, prev); sig['OVN'][day] = a; ovn_stats += st
        sig['ORB5'][day] = sig_orb(day, rth, info, 1, 4)
        sig['ORB15'][day] = sig_orb(day, rth, info, 3, 4)
        sig['IDX'][day] = sig_idx(day, rth, info)
    # the reel's claim, checked
    def rate(where, key):
        L = [s for s in ovn_stats if s['where'] == where]
        return dict(n=len(L), pct=round(sum(s[key] for s in L) / len(L) * 100, 1) if L else None)
    claim = dict(upper_hits_high=rate('upper', 'hi_hit'), upper_hits_low=rate('upper', 'lo_hit'),
                 lower_hits_low=rate('lower', 'lo_hit'), lower_hits_high=rate('lower', 'hi_hit'),
                 opens_outside=sum(1 for s in ovn_stats if s['where'] in ('above', 'below')), sessions=len(ovn_stats))
    print('reel claim check', json.dumps(claim), flush=True)
    tests = [('OVN', 'shares', 'mid', 1), ('OVN', 'shares', '1R', 1), ('OVN', 'options', 'mid', 1), ('OVN', 'options', 'mid', 3), ('OVN', 'options', '1R', 2),
             ('ORB5', 'shares', '10%ATR', 1), ('ORB5', 'options', '10%ATR', 1), ('ORB5', 'options', '10%ATR', 2), ('ORB5', 'options', '10%ATR', 3),
             ('ORB15', 'shares', '10%ATR', 1), ('ORB15', 'options', '10%ATR', 1), ('ORB15', 'options', '10%ATR', 3),
             ('IDX', 'shares', 'mid', 1), ('IDX', 'options', 'mid', 1), ('IDX', 'options', 'mid', 2), ('IDX', 'options', 'mid', 3)]
    EXIT = {1: 'stock stop/target', 2: '+ option stop -50%', 3: '+ option take profit +100%'}
    results = []
    for fam, mode, sk, ex in tests:
        Ttr, Ctr = evaluate(fam, sig[fam], rth, info, train, mode, sk, ex)
        Tte, Cte = evaluate(fam, sig[fam], rth, info, test, mode, sk, ex)
        a, b = stats(Ttr, Ctr, START_EQ), stats(Tte, Cte, START_EQ)
        ok = bool(a.get('pf') and b.get('pf') and a['pf'] >= PASS_PF and b['pf'] >= PASS_PF and b['trades'] >= MIN_TEST)
        results.append(dict(family=fam, mode=mode, stop=sk, exits=EXIT[ex] if mode == 'options' else 'stop / target / close', train=a, test=b, passed=ok,
                            last_trades=(Tte[-8:])[::-1]))
        print(fam, mode, sk, ex, 'TRAIN', json.dumps(a), 'TEST', json.dumps(b), 'PASS' if ok else '', flush=True)
    out = dict(updated=datetime.now(ET).isoformat(timespec='seconds'), start=days[0].isoformat(), end=days[-1].isoformat(), days=len(days),
               train=f'{train[0]} → {train[-1]}', test=f'{test[0]} → {test[-1]}', feed=feed, start_equity=START_EQ, claim=claim, results=results,
               passed=[f"{r['family']} · {r['mode']} · {r['exits']}" for r in results if r['passed']], seconds=round(time.time() - t0),
               rules=dict(pass_pf=PASS_PF, min_test_trades=MIN_TEST, train_frac=TRAIN_FRAC, opt_risk=OPT_RISK, share_risk='1% of equity per trade, 2x max buying power',
                          universe_stocks=STOCKS))
    os.makedirs(OUT, exist_ok=True); json.dump(out, open(f'{OUT}/lab.json', 'w'), separators=(',', ':'))
    print(json.dumps(dict(event='lab_done', passed=out['passed'], seconds=out['seconds'])), flush=True)
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', 'live-lab', OUT], check=True)
    subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', 'lab'], check=True)
    subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{O.REPO}.git', 'live-lab'], check=True, timeout=90, capture_output=True)

if __name__ == '__main__':
    main()
