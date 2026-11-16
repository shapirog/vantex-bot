"""
Vantex lab 11 - "Stocks in Play" 5-minute opening-range breakout (Zarattini, Barbon & Aziz 2024), replicated on NEW data.
Research only, places NO orders. The paper's sample ends 2023; this test runs Sep 2025 -> Nov 13 2026 (after publication).

RULE (as published; fixed before any result was seen, 2026-11-16)
Universe   US common stocks (NASDAQ/NYSE/AMEX, ETFs/funds/warrants/units excluded), opening price > $5,
           14-day average daily volume >= 1,000,000 shares, 14-day ATR > $0.50 (all known before the open).
In play    Relative Volume = volume of the first 5 minutes (9:30-9:34) / average first-5-minute volume of the prior 14
           sessions. Keep RV >= 1.0 and take the 20 highest RV stocks of the day.
Direction  first 5-minute candle up (close > open) -> long only; down -> short only; flat -> no trade.
Entry      stop order from 9:35: long at the 5-minute high, short at the 5-minute low (a gap through fills at the open).
Stop       10% of the 14-day ATR from the entry price. Same-minute entry-and-stop counts as stopped (worst case).
Exit       if not stopped, at the 15:59 close.
Size       risk 1% of equity per trade (shares = 1% of equity / stop distance).
Costs      Alpaca: $0 commission; SEC + FINRA TAF fees on every sale (short entries included); $0.01/share slippage on
           each side (base) and 0.10% per side (stress).

ACCOUNTS (Guillo's plan)
  CASH  $2,500 cash account: LONG trades only (cash accounts cannot short), no leverage, each day's buys <= equity
        (sale proceeds settle T+1, so each dollar is used once per day). No day-trade limit in a cash account.
  -> once equity reaches $25,000 it switches to MARGIN: longs and shorts, buying power up to 4x equity (the paper's cap).
  Also reported: cash-only for the whole period, and margin from $25,000 for the whole period (the paper's setup).
Results    branch 'live-lab11' -> lab11.json, lab11_report.md, lab11_trades.jsonl
"""
import json, math, os, subprocess, sys, time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

import numpy as np

sys.argv = [sys.argv[0], 'history']
import lab8 as L8
L5 = L8.L5
ET, log, get, DATA = L8.ET, L8.log, L8.get, L8.DATA

OUT = os.environ.get('VANTEX_LAB11_DIR', '/tmp/vantex-lab11')
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
FIRST, LAST = date(2025, 9, 4), date(2026, 11, 13)
LOOK = 14
MIN_PX, MIN_ADV, MIN_ATR, MIN_RV, TOP = 5.0, 1_000_000, 0.50, 1.0, 20
STOP_ATR, RISK, LEV = 0.10, 0.01, 4.0
SLIP_CENTS, SLIP_STRESS = 0.01, 0.001
STATS = Counter()

def first5(syms, d):
    """{sym: (open, high, low, close, volume)} of the 9:30-9:34 candle"""
    d0 = datetime.combine(date.fromordinal(d), datetime.min.time(), ET)
    out, P = {}, defaultdict(list)
    for i in range(0, len(syms), 200):
        tok = None
        while True:
            p = dict(symbols=','.join(syms[i:i + 200]), timeframe='1Min', start=(d0 + timedelta(minutes=570)).isoformat(),
                     end=(d0 + timedelta(minutes=575)).isoformat(), limit=10000, feed='sip', adjustment='raw')
            if tok: p['page_token'] = tok
            r = get(f'{DATA}/v2/stocks/bars', p)
            if r is None or not r.ok: STATS['first5_errors'] += 1; break
            j = r.json()
            for s, bars in (j.get('bars') or {}).items():
                for b in bars:
                    t = L5.to_et(b['t'])
                    if 570 <= t.hour * 60 + t.minute < 575: P[s].append((t.hour * 60 + t.minute, b['o'], b['h'], b['l'], b['c'], b['v']))
            tok = j.get('next_page_token')
            if not tok: break
    for s, L in P.items():
        L.sort(); out[s] = (L[0][1], max(x[2] for x in L), min(x[3] for x in L), L[-1][4], sum(x[5] for x in L))
    return out

def simulate(A, d1, o5, atr):
    """one trade on the day's 1-minute bars; returns dict or None"""
    o, h5, l5, c5 = o5
    side = 1 if c5 > o5[0] else -1 if c5 < o5[0] else 0
    if side == 0: return None
    lvl = h5 if side > 0 else l5
    stop_d = STOP_ATR * atr
    rows = A[(A[:, 0] >= 575) & (A[:, 0] <= 959)]
    for k in range(len(rows)):
        m, bo, bh, bl, bc, bv = rows[k]
        hit = bh >= lvl if side > 0 else bl <= lvl
        if not hit: continue
        entry = max(lvl, bo) if side > 0 else min(lvl, bo)
        stop = entry - side * stop_d
        for j in range(k, len(rows)):
            m2, o2, h2, l2, c2, v2 = rows[j]
            if (side > 0 and l2 <= stop) or (side < 0 and h2 >= stop):
                px = stop if j == k else (min(stop, o2) if side > 0 else max(stop, o2))
                return dict(side=side, entry=entry, exit=px, why='stop', t_in=int(m), t_out=int(m2), stop_d=stop_d, vol_in=float(bv))
        return dict(side=side, entry=entry, exit=float(rows[-1, 4]), why='close', t_in=int(m), t_out=int(rows[-1, 0]), stop_d=stop_d, vol_in=float(bv))
    return None

def fees(d, sh, sell_px):
    rate, mx = L8.taf(d)
    return sh * sell_px * L8.sec_fee(d) + min(mx, sh * rate)

def account(trades, days, start, mode_rule, slip='cents'):
    """mode_rule(equity) -> 'cash' or 'margin'. Returns summary, equity curve, per-trade R list"""
    by = defaultdict(list)
    for t in trades: by[t['day']].append(t)
    eq = start; peak = eq; dd = 0.0; curve = []; R = []; worst = 0.0; reached = None; n = Counter()
    for d in days:
        ds = date.fromordinal(d).isoformat(); D = date.fromordinal(d)
        mode = mode_rule(eq)
        if mode == 'margin' and reached is None and start < 25000: reached = ds
        bp = eq * (LEV if mode == 'margin' else 1.0); used = 0.0; pnl = 0.0
        for t in sorted(by.get(ds, []), key=lambda x: (x['t_in'], -x['rv'])):
            if mode == 'cash' and t['side'] < 0: n['skipped_short_cash'] += 1; continue
            s = t['side']; sd = t['stop_d']
            e = t['entry'] + s * (SLIP_CENTS if slip == 'cents' else t['entry'] * SLIP_STRESS)
            x = t['exit'] - s * (SLIP_CENTS if slip == 'cents' else t['exit'] * SLIP_STRESS)
            sh = math.floor(min(RISK * eq / sd, (bp - used) / e))
            if sh < 1: n['skipped_no_buying_power'] += 1; continue
            used += sh * e
            p = s * sh * (x - e) - fees(D, sh, x if s > 0 else e)
            pnl += p; R.append(p / (sh * sd)); n['trades'] += 1; n[f'{"long" if s > 0 else "short"}'] += 1
        worst = min(worst, pnl / eq if eq > 0 else 0); eq += pnl; peak = max(peak, eq); dd = max(dd, 1 - eq / peak)
        curve.append((ds, round(eq, 2)))
        if eq <= 0: break
    r = np.array(R) if R else np.array([0.0])
    w = r[r > 0].sum(); l = -r[r <= 0].sum()
    return dict(start=start, end_equity=round(eq, 2), net_pct=round((eq / start - 1) * 100, 1), max_dd_pct=round(dd * 100, 1),
                worst_day_pct=round(worst * 100, 2), reached_25k_on=reached, trades=n['trades'], longs=n['long'], shorts=n['short'],
                skipped=dict((k, v) for k, v in n.items() if k.startswith('skipped')),
                win_rate_pct=round(float((r > 0).mean()) * 100, 1) if R else None, expectancy_R=round(float(r.mean()), 3) if R else None,
                profit_factor=round(float(w / l), 2) if l > 0 else None), curve

def main():
    t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    sessions, full = L8.sessions_between(FIRST - timedelta(days=60), LAST)
    sidx = {d: i for i, d in enumerate(sessions)}
    test_days = [d for d in sessions if d >= FIRST.toordinal() and d in full]
    need_days = sessions[sidx[test_days[0]] - LOOK:]
    U, dropped = L5.universe(); syms = sorted(U)
    s0 = datetime.combine(date.fromordinal(sessions[0]) - timedelta(days=30), datetime.min.time(), ET)
    s1 = datetime.combine(LAST + timedelta(days=1), datetime.min.time(), ET)
    RAW = L5.daily_multi(syms, s0, s1, 'raw'); ADJ = L5.daily_multi(syms, s0, s1, 'split')
    log('daily bars', len(RAW), round(time.time() - t0), 's')
    # candidates per day from daily data known before the open (split-adjusted history scaled to today's raw prices)
    cand = defaultdict(dict); union = set()
    for s, A in ADJ.items():
        Rw = RAW.get(s)
        if Rw is None or len(A) < LOOK + 2: continue
        rix = {int(x[0]): k for k, x in enumerate(Rw)}
        dd = A[:, 0].astype(int)
        for k in range(LOOK + 1, len(A)):
            d = int(dd[k])
            if d not in full or d < need_days[0]: continue
            prev = A[k - LOOK:k]; pc_adj = A[k - 1, 4]
            kr = rix.get(int(dd[k - 1]))
            if kr is None or pc_adj <= 0: continue
            f = Rw[kr, 4] / pc_adj                                  # adjusted -> today's raw price scale
            tr = np.maximum(prev[:, 2], np.r_[A[k - LOOK - 1, 4], prev[:-1, 4]]) - np.minimum(prev[:, 3], np.r_[A[k - LOOK - 1, 4], prev[:-1, 4]])
            atr = float(tr.mean()) * f; adv = float(prev[:, 5].mean()) / f
            if adv >= MIN_ADV and atr > MIN_ATR and Rw[kr, 4] > 4.0:
                cand[d][s] = dict(atr=atr, adv=adv, pc=float(Rw[kr, 4])); union.add(s)
    del ADJ
    log('candidate stock-days', sum(len(v) for v in cand.values()), 'symbols', len(union), round(time.time() - t0), 's')
    U5 = sorted(union); F5 = {}
    for n, d in enumerate(need_days):
        if d not in full: continue
        F5[d] = first5(U5, d)
        if n % 20 == 0: log('first-5 volumes', n, '/', len(need_days), round(time.time() - t0), 's')
    trades, picks_log = [], Counter()
    hist = defaultdict(list)                                         # sym -> [(day, first5 volume)]
    for d in need_days:
        if d not in full: continue
        today = F5.get(d, {})
        if d in test_days:
            rows = []
            for s, c in cand.get(d, {}).items():
                o5 = today.get(s); H = [v for dd_, v in hist[s] if dd_ < d][-LOOK:]
                if not o5 or len(H) < LOOK or o5[0] <= MIN_PX: continue
                base = float(np.mean(H))
                if base <= 0: continue
                rv = o5[4] / base
                if rv >= MIN_RV: rows.append((rv, s, o5, c))
            rows.sort(reverse=True); pick = rows[:TOP]
            if pick:
                M = L5.minutes_day([s for _, s, _, _ in pick], d)
                for rv, s, o5, c in pick:
                    A = M.get(s)
                    if A is None or not len(A): STATS['no_minutes'] += 1; continue
                    t = simulate(A, d, o5[:4], c['atr'])
                    picks_log['picked'] += 1
                    if t is None: picks_log['no_trigger_or_flat_candle'] += 1; continue
                    t.update(sym=s, day=date.fromordinal(d).isoformat(), rv=round(rv, 2), atr=round(c['atr'], 3), month=date.fromordinal(d).isoformat()[:7],
                             gross_R=round(t['side'] * (t['exit'] - t['entry']) / t['stop_d'], 3))
                    trades.append(t)
            if test_days.index(d) % 20 == 0: log('day', test_days.index(d), '/', len(test_days), 'trades', len(trades), round(time.time() - t0), 's')
        for s in U5: hist[s].append((d, today[s][4] if s in today else 0.0))   # no prints in the first 5 minutes = 0 volume
    plan = lambda e: 'margin' if e >= 25000 else 'cash'
    A_plan, curve_plan = account(trades, test_days, 2500.0, plan)
    A_plan_stress, _ = account(trades, test_days, 2500.0, plan, slip='stress')
    A_cash, _ = account(trades, test_days, 2500.0, lambda e: 'cash')
    A_m25, curve_m25 = account(trades, test_days, 25000.0, lambda e: 'margin')
    A_m25_stress, _ = account(trades, test_days, 25000.0, lambda e: 'margin', slip='stress')
    g = np.array([t['gross_R'] for t in trades]) if trades else np.array([0.0])
    gl = np.array([t['gross_R'] for t in trades if t['side'] > 0]) if trades else np.array([0.0])
    by_month = {}
    for m in sorted({t['month'] for t in trades}):
        x = np.array([t['gross_R'] for t in trades if t['month'] == m]); by_month[m] = dict(trades=len(x), mean_gross_R=round(float(x.mean()), 3))
    R = dict(updated=datetime.now(ET).isoformat(timespec='seconds'), sessions=len(test_days), first=date.fromordinal(test_days[0]).isoformat(),
             last=date.fromordinal(test_days[-1]).isoformat(),
             signals=dict(trades=len(trades), longs=int(sum(t['side'] > 0 for t in trades)), shorts=int(sum(t['side'] < 0 for t in trades)),
                          mean_gross_R_all=round(float(g.mean()), 3), mean_gross_R_longs=round(float(gl.mean()), 3),
                          stopped_pct=round(100 * float(np.mean([t['why'] == 'stop' for t in trades])), 1) if trades else None, picks=dict(picks_log)),
             plan_2500_cash_then_margin_at_25k=A_plan, plan_stress_0_1pct=A_plan_stress, cash_only_2500=A_cash,
             paper_setup_margin_25000=A_m25, paper_setup_stress=A_m25_stress, by_month_gross=by_month, data=dict(STATS), lab5_requests=dict(L5.STATS),
             notes=['Paper period 2016-2023 (+41.6%/yr, Sharpe 2.81 reported). This test uses only data AFTER publication.',
                    'Fills: stop-order entry at the level (gap -> open), stop exits at the stop (gap -> open); same-minute entry+stop = stopped.',
                    'Cash account: longs only; margin account (>= $25K): longs + shorts, borrow assumed available, no borrow fees modeled.',
                    'Survivorship: current Alpaca listing; delisted names missing.'],
             seconds=round(time.time() - t0))
    json.dump(R, open(f'{OUT}/lab11.json', 'w'), indent=1, default=str)
    json.dump(dict(plan=curve_plan, margin25k=curve_m25), open(f'{OUT}/lab11_equity.json', 'w'))
    with open(f'{OUT}/lab11_trades.jsonl', 'w') as f:
        for t in trades: f.write(json.dumps(t, default=str) + '\n')
    j = lambda x: '```\n' + json.dumps(x, indent=1, default=str) + '\n```'
    md = [f"# Vantex lab 11 - Stocks in Play 5-min ORB - {R['updated']}", '', f"{R['sessions']} sessions {R['first']} -> {R['last']}",
          '## Signals', j(R['signals']), '## $2,500 cash account -> margin at $25K (the plan)', j(A_plan), '### same, 0.10% slippage per side', j(A_plan_stress),
          '## $2,500 cash only', j(A_cash), "## The paper's setup: $25,000 margin, longs + shorts, 4x cap", j(A_m25), '### same, 0.10% slippage per side', j(A_m25_stress),
          '## By month (gross R per trade)', j(by_month), '## Notes'] + ['- ' + x for x in R['notes']]
    open(f'{OUT}/lab11_report.md', 'w').write('\n'.join(md) + '\n')
    log('done', round(time.time() - t0), 's'); publish()

def publish():
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', 'live-lab11', OUT], check=True)
    subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', 'lab11'], check=True)
    subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{REPO}.git', 'live-lab11'], check=True, timeout=120, capture_output=True)

if __name__ == '__main__':
    main()
