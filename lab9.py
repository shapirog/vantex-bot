"""
Vantex lab 9 - buy strong tiny-float runners near the close, sell the next day (no day trade). Research/paper only, NO orders.

  python lab9.py history    Sep 2025 -> Nov 13 2026 (pre-registered train/test split at 2026-05-01)
  python lab9.py forward    locked forward paper test: day-1 signals after 2026-11-13, replayed after each close

PRE-REGISTERED 2026-11-15, before any lab 9 result was seen
Universe  US common stocks (same exclusions as labs 5/8), prior raw close $0.50-$20, shares outstanding <= 5,000,000
          (latest SEC filing filed before day 1, split-adjusted; a proxy for float), >= 20 prior daily bars,
          no split on day 1 or day 2, both days full sessions.
Day 1     decided at 15:50 ET with 1-minute bars that have ended:
            price (15:49 bar close) >= prior close x 1.30
            regular-session volume 9:30-15:50 >= 5 x average daily volume of the prior 20 sessions (split-adjusted)
            price in the top 20% of the 9:30-15:50 range: (price - low) / (high - low) >= 0.80
Entry     15:51:00 at the ask + 0.5%: the quote in force at 15:51:00 if it is <= 60 s old, else the first quote within
          60 s after; otherwise skip. Skip if spread > 2% of mid or displayed ask size < order size.
Size      risk 1% of equity at a -15% stop (position = 6.67% of equity), <= $500, whole shares, cash account:
          new buys <= equity minus yesterday's buys (sold today, proceeds settle T+1).
Day 2     no stops in premarket (not supported). From 9:30:00 every SIP quote is walked in time order:
            bid <= entry x 0.85 -> sell all at that bid - 0.5% (gap-downs fill at the real opening bid)
            bid >= entry x 1.20 -> sell half at that bid - 0.5% (first time only)
            15:45 -> sell the rest at the first bid after 15:45:00 - 0.5%
          Date-correct SEC + FINRA TAF fees on sells.
PASS (all required): train mean return > 0; test mean > 0 with day-clustered 95% CI low > 0; test profit factor >= 1.2;
          >= 100 test trades; $2,500 account ends the test period above $2,500. Otherwise FAIL (or INCONCLUSIVE if the
          only failure is too few trades). Descriptive tables (what ALL day-1 runners did on day 2) cannot declare a winner.
Results   history -> branch 'live-lab9'; forward -> 'live-lab9-forward'.
"""
import json, math, os, subprocess, sys, time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

import numpy as np

MODE = sys.argv[1] if len(sys.argv) > 1 else 'history'
sys.argv = [sys.argv[0], 'history']
import lab8 as L8
L5, L6 = L8.L5, L8.L6
ET, log, get = L8.ET, L8.log, L8.get

OUT = os.environ.get('VANTEX_LAB9_DIR', '/tmp/vantex-lab9')
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
BRANCH = 'live-lab9' if MODE == 'history' else 'live-lab9-forward'
HIST_FIRST, HIST_LAST, FWD_AFTER, SPLIT = date(2025, 9, 4), date(2026, 11, 13), date(2026, 11, 13), '2026-05-01'
PMIN, PMAX, SH_MAX, MIN_HIST = 0.50, 20.0, 5_000_000, 20
UP, VOLX, TOPR, DECIDE = 0.30, 5.0, 0.80, 950            # 15:50
ENTRY_MIN, QUOTE_AGE = 951, 60 * 10**9
STOP, TGT, RISK, CAP, EQUITY, SLIP, MAXSPREAD = 0.15, 0.20, 0.01, 500.0, 2500.0, 0.005, 0.02
BOOT = 5000
STATS = Counter()

def entry_quote(sym, d):
    T = L8.ns_of(d, ENTRY_MIN)
    before = L8.quotes(sym, d, T - QUOTE_AGE, T)
    if before:
        q = before[-1]; src = 'in force at 15:51'
    else:
        after = L8.quotes(sym, d, T, T + QUOTE_AGE)
        if not after: return None, 'no quote within 60 s of 15:51'
        q = after[0]; src = 'first after 15:51'
    return dict(t_ns=q[0], age_ms=round((T - q[0]) / 1e6), src=src, bid=q[1], bid_sz=q[2], ask=q[3], ask_sz=q[4],
                spread_pct=round((q[3] - q[1]) / ((q[3] + q[1]) / 2) * 100, 3)), None

def day2_exit(sym, d2, entry):
    stop, tgt = entry * (1 - STOP), entry * (1 + TGT); legs = []; half = False
    a = L8.ns_of(d2, 570); end = L8.ns_of(d2, 945); first_q = None
    while a < end:
        b = min(a + 15 * 60 * 10**9, end)
        for t, bp, bs, ap, asz in L8.quotes(sym, d2, a, b):
            if first_q is None: first_q = (t, bp)
            if bp <= stop:
                legs.append((0.5 if half else 1.0, bp, t, 'stop' + (' (gap at open)' if first_q[0] == t else ''))); return legs, first_q
            if not half and bp >= tgt:
                legs.append((0.5, bp, t, '+20% half')); half = True
        a = b
    Q = L8.quotes(sym, d2, end, end + 120 * 10**9)
    if Q: legs.append((0.5 if half else 1.0, Q[0][1], Q[0][0], '15:45 exit'))
    else: STATS['no_quote_at_1545'] += 1; legs.append((0.5 if half else 1.0, entry * 0.9, end, '15:45 exit (no quote: -10% placeholder)'))
    return legs, first_q

def cash_pnl(legs, sh, entry_px, d2, slip=SLIP):
    h = sh // 2; rem = sh; p = 0.0
    for i, (frac, bid, t, why) in enumerate(legs):
        n = h if (i == 0 and frac == 0.5 and len(legs) > 1) else rem
        proceeds = n * bid * (1 - slip); rem -= n
        rate, mx = L8.taf(d2); p += proceeds - proceeds * L8.sec_fee(d2) - min(mx, n * rate)
    return p - sh * entry_px

def stats(rets, by_day):
    if not rets: return dict(trades=0)
    r = np.array(rets); w = r[r > 0].sum(); l = -r[r <= 0].sum(); g = np.random.default_rng(23); means = []
    keys = list(by_day)
    if len(keys) >= 2:
        s = np.array([sum(by_day[k]) for k in keys]); n = np.array([len(by_day[k]) for k in keys])
        for _ in range(BOOT):
            ix = g.integers(0, len(keys), len(keys)); means.append(s[ix].sum() / max(1, n[ix].sum()))
    return dict(trades=len(r), win_rate_pct=round(float((r > 0).mean()) * 100, 1), mean_pct=round(float(r.mean()) * 100, 2), median_pct=round(float(np.median(r)) * 100, 2),
                ci95_pct_day_clustered=[round(float(np.percentile(means, 2.5)) * 100, 2), round(float(np.percentile(means, 97.5)) * 100, 2)] if means else None,
                profit_factor=round(float(w / l), 2) if l > 0 else None, best_pct=round(float(r.max()) * 100, 1), worst_pct=round(float(r.min()) * 100, 1))

def account(trades, days, slip=SLIP):
    eq = EQUITY; peak = eq; dd = 0.0; curve = []; open_val = 0.0; pend = 0.0; prev_cost = 0.0; by1 = defaultdict(list)
    for t in trades: by1[t['day1']].append(t)
    worst = 0.0
    for d in days:
        ds = date.fromordinal(d).isoformat()
        eq += pend; worst = min(worst, pend / (eq - pend) if eq - pend > 0 else 0); pend = 0.0
        open_val = prev_cost; prev_cost = 0.0          # cash account: yesterday's buys are sold today but settle tomorrow
        peak = max(peak, eq); dd = max(dd, 1 - eq / peak); curve.append((ds, round(eq, 2)))
        for t in by1.get(ds, []):
            e = t['quote']['ask'] * (1 + slip)
            sh = math.floor(min(RISK * eq / STOP, CAP, eq - open_val) / e)
            if sh < 1 or t['quote']['ask_sz'] < sh: continue
            open_val += sh * e; prev_cost += sh * e; pend += cash_pnl(t['_legs'], sh, e, date.fromisoformat(t['day2']), slip)
    eq += pend; peak = max(peak, eq); dd = max(dd, 1 - eq / peak)
    return dict(end_equity=round(eq, 2), net_pct=round((eq / EQUITY - 1) * 100, 2), max_dd_pct=round(dd * 100, 2), worst_day_pct=round(worst * 100, 2)), curve

def main():
    t0 = time.time(); os.makedirs(OUT, exist_ok=True); now = datetime.now(ET)
    if MODE == 'history':
        sessions, full = L8.sessions_between(HIST_FIRST - timedelta(days=60), HIST_LAST)
        lo, hi = HIST_FIRST.toordinal(), HIST_LAST.toordinal()
    else:
        last = now.date() if now.hour * 60 + now.minute >= 16 * 60 + 30 else now.date() - timedelta(days=1)
        sessions, full = L8.sessions_between(FWD_AFTER - timedelta(days=60), last)
        lo, hi = FWD_AFTER.toordinal() + 1, sessions[-1]
    sidx = {d: i for i, d in enumerate(sessions)}
    pairs = [(d, sessions[sidx[d] + 1]) for d in sessions[:-1] if lo <= d <= hi and d in full and sessions[sidx[d] + 1] in full and sidx[d] > MIN_HIST]
    if not pairs: log('no complete day-1/day-2 pairs yet'); return
    L8.calibrate_lots(); log('quote sizes', L8.LOT_MULT)
    U, dropped = L5.universe(); syms = sorted(U)
    RAW = L5.daily_multi(syms, datetime.combine(date.fromordinal(sessions[0]) - timedelta(days=45), datetime.min.time(), ET),
                         datetime.combine(date.fromordinal(pairs[-1][1]) + timedelta(days=1), datetime.min.time(), ET), 'raw')
    band = [s for s, A in RAW.items() if ((A[:, 4] >= PMIN) & (A[:, 4] <= PMAX)).any()]
    SH = L6.sec_shares(band)
    if not SH: raise SystemExit('SEC share counts unavailable - check SEC_UA')
    SP, ok = L6.splits(band, date.fromordinal(sessions[0]) - timedelta(days=400), date.fromordinal(pairs[-1][1]))
    if not ok: raise SystemExit('split feed unavailable')
    cov = Counter(); cand = defaultdict(list)
    for s in band:
        A = RAW[s]; dd = A[:, 0].astype(int); ix = {d: k for k, d in enumerate(dd)}
        spl = {date.fromisoformat(ex).toordinal(): f for ex, f in SP.get(s, [])}
        for d1, d2 in pairs:
            k = ix.get(d1)
            if k is None or k < MIN_HIST or dd[k - 1] != sessions[sidx[d1] - 1]: continue
            pc = float(A[k - 1, 4])
            if not (PMIN <= pc <= PMAX): continue
            if A[k, 2] < pc * (1 + UP): continue                                    # necessary: day high >= +30%
            vols = []
            for j in range(k - 20, k):
                f = 1.0
                for ex, fac in spl.items():
                    if dd[j] < ex <= d1: f *= fac
                vols.append(A[j, 5] * f)
            avgv = float(np.mean(vols))
            if A[k, 5] < VOLX * avgv: continue                                      # necessary: full-day volume >= 5x
            cov['daily_prefilter_pass'] += 1
            if d1 in spl or d2 in spl: cov['excluded_split'] += 1; continue
            v, why = L6.shares_on(s, date.fromordinal(d1).isoformat(), SH, SP)
            if v is None: cov[f'excluded_shares_unknown: {why}'] += 1; continue
            if v > SH_MAX: continue
            cand[(d1, d2)].append(dict(sym=s, pc=pc, avgv=avgv, shares_out=v))
    del RAW
    log('candidates', sum(len(v) for v in cand.values()), round(time.time() - t0), 's')
    runners, trades, skips = [], [], []
    for n, ((d1, d2), L) in enumerate(sorted(cand.items())):
        D1 = date.fromordinal(d1); D2 = date.fromordinal(d2)
        M1 = L5.minutes_day([c['sym'] for c in L], d1); M2 = L5.minutes_day([c['sym'] for c in L], d2)
        for c in L:
            A = M1.get(c['sym'])
            if A is None: continue
            rth = A[(A[:, 0] >= 570) & (A[:, 0] < DECIDE)]
            if not len(rth): continue
            px = float(rth[-1, 4]); hi_, lo_ = float(rth[:, 2].max()), float(rth[:, 3].min()); vol = float(rth[:, 5].sum())
            pos = (px - lo_) / (hi_ - lo_) if hi_ > lo_ else 0.0
            if not (px >= c['pc'] * (1 + UP) and vol >= VOLX * c['avgv'] and pos >= TOPR): continue
            row = dict(sym=c['sym'], day1=D1.isoformat(), day2=D2.isoformat(), month=D1.isoformat()[:7], pc=c['pc'], px_1550=px, gain_pct=round((px / c['pc'] - 1) * 100, 1),
                       range_pos=round(pos, 3), vol_x=round(vol / c['avgv'], 1), shares_out=c['shares_out'])
            B = M2.get(c['sym'])
            if B is not None and len(B):
                reg = B[(B[:, 0] >= 570) & (B[:, 0] < 960)]
                if len(reg):
                    row.update(d2_open_pct=round((reg[0, 1] / px - 1) * 100, 1), d2_high_pct=round((reg[:, 2].max() / px - 1) * 100, 1),
                               d2_low_pct=round((reg[:, 3].min() / px - 1) * 100, 1), d2_close_pct=round((reg[-1, 4] / px - 1) * 100, 1))
            runners.append(row)
            q, why = entry_quote(c['sym'], D1)
            if q is None: skips.append(dict(row, why=why)); continue
            if q['spread_pct'] > MAXSPREAD * 100: skips.append(dict(row, why='spread > 2%', quote=q)); continue
            entry = q['ask'] * (1 + SLIP)
            legs, fq = day2_exit(c['sym'], D2, entry)
            gross = sum(fr * bid for fr, bid, t, w in legs) / q['ask'] - 1
            net = cash_pnl(legs, 1000, entry, D2) / (1000 * entry)
            trades.append(dict(row, quote=q, entry=round(entry, 4), legs=[dict(frac=f, bid=b, time=L8.hm(t, D2), why=w) for f, b, t, w in legs],
                               ret=round(net, 5), gross_ret=round(gross, 5), _legs=legs))
        if n % 25 == 0: log('pair', n, '/', len(cand), 'runners', len(runners), 'trades', len(trades), round(time.time() - t0), 's')
    days = [d1 for d1, d2 in pairs]
    tr = [t for t in trades if t['day1'] < SPLIT]; te = [t for t in trades if t['day1'] >= SPLIT]
    bd = lambda T: {k: v for k, v in _group(T).items()}
    S_tr, S_te, S_all = stats([t['ret'] for t in tr], bd(tr)), stats([t['ret'] for t in te], bd(te)), stats([t['ret'] for t in trades], bd(trades))
    acc_all, curve = account(trades, days); acc_te, _ = account(te, [d for d in days if date.fromordinal(d).isoformat() >= SPLIT])
    acc_stress, _ = account(trades, days, slip=0.01)
    if MODE == 'history':
        checks = {'train mean > 0': bool(S_tr.get('trades') and S_tr['mean_pct'] > 0),
                  'test mean > 0 and CI low > 0': bool(S_te.get('trades') and S_te['mean_pct'] > 0 and (S_te['ci95_pct_day_clustered'] or [0])[0] > 0),
                  'test profit factor >= 1.2': bool((S_te.get('profit_factor') or 0) >= 1.2),
                  'test trades >= 100': bool(S_te.get('trades', 0) >= 100),
                  '$2,500 ends test period up': bool(acc_te['end_equity'] > EQUITY)}
        only_n = not checks['test trades >= 100'] and all(v for k, v in checks.items() if k != 'test trades >= 100')
        verdict = 'PASS' if all(checks.values()) else ('INCONCLUSIVE (too few test trades)' if only_n else 'FAIL')
    else:
        checks = {}; verdict = f'FORWARD so far: {S_all.get("trades", 0)} trades - far too few to judge; paper only.'
    D2 = [r for r in runners if 'd2_close_pct' in r]
    desc = dict(runners=len(runners), with_day2_data=len(D2))
    for k in ('d2_open_pct', 'd2_high_pct', 'd2_low_pct', 'd2_close_pct'):
        x = np.array([r[k] for r in D2]) if D2 else np.array([0.0])
        desc[k] = dict(median=round(float(np.median(x)), 1), p25=round(float(np.percentile(x, 25)), 1), p75=round(float(np.percentile(x, 75)), 1))
    if D2:
        desc['share_closing_day2_above_1550_price_pct'] = round(100 * float(np.mean([r['d2_close_pct'] > 0 for r in D2])), 1)
        desc['share_opening_below_minus15_pct'] = round(100 * float(np.mean([r['d2_open_pct'] <= -15 for r in D2])), 1)
        desc['share_touching_plus20_pct'] = round(100 * float(np.mean([r['d2_high_pct'] >= 20 for r in D2])), 1)
    R = dict(updated=now.isoformat(timespec='seconds'), mode=MODE, verdict=verdict, checks=checks, train=S_tr, test=S_te, all=S_all,
             account_all=acc_all, account_test=acc_te, account_all_stress_1pct_slip=acc_stress,
             gross_mean_pct=round(float(np.mean([t['gross_ret'] for t in trades])) * 100, 2) if trades else None,
             exits=dict(Counter(l['why'] for t in trades for l in t['legs'])), skips=dict(Counter(s['why'] for s in skips)),
             by_month={m: stats([t['ret'] for t in trades if t['month'] == m], _group([t for t in trades if t['month'] == m])) for m in sorted({t['month'] for t in trades})},
             day2_of_all_runners_descriptive=desc, coverage=dict(cov, pairs=len(pairs), universe_excluded=dict(dropped)),
             data=dict(lab8=dict(L8.STATS), lab5=dict(L5.STATS), lab6=dict(L6.STATS), lab9=dict(STATS), quote_sizes=L8.LOT_MULT),
             limitations=['Shares outstanding is a float proxy.', 'Survivorship: current exchange listing and current SEC ticker map.',
                          'Premarket day-2 moves cannot be stopped (no premarket stops); gap-downs fill at the first regular-session bid.',
                          'One quote at entry; size check uses displayed ask only.', 'Exploratory history: the forward test is the real judge.'],
             seconds=round(time.time() - t0))
    json.dump(R, open(f'{OUT}/lab9.json', 'w'), indent=1, default=str)
    json.dump(curve, open(f'{OUT}/lab9_equity.json', 'w'))
    with open(f'{OUT}/lab9_trades.jsonl', 'w') as f:
        for t in trades: f.write(json.dumps({k: v for k, v in t.items() if not k.startswith('_')}, default=str) + '\n')
    with open(f'{OUT}/lab9_runners.jsonl', 'w') as f:
        for r in runners: f.write(json.dumps(r, default=str) + '\n')
    with open(f'{OUT}/lab9_skips.jsonl', 'w') as f:
        for s in skips: f.write(json.dumps(s, default=str) + '\n')
    j = lambda x: '```\n' + json.dumps(x, indent=1, default=str) + '\n```'
    md = [f'# Vantex lab 9 - day-1 close to day-2 ({MODE}) - {R["updated"]}', '', f'## VERDICT: {verdict}', j(checks), '## Train', j(S_tr), '## Test', j(S_te), '## All',
          j(S_all), '## Accounts ($2,500)', j(dict(all=acc_all, test=acc_te, all_with_1pct_slippage=acc_stress)), f"Gross mean (ask in, bid out, no costs): {R['gross_mean_pct']}%",
          '## Exits', j(R['exits']), '## Skips', j(R['skips']), '## By month', j(R['by_month']), '## What ALL qualifying runners did on day 2 (descriptive)', j(desc),
          '## Coverage', j(R['coverage']), '## Data', j(R['data']), '## Limitations'] + ['- ' + x for x in R['limitations']]
    open(f'{OUT}/lab9_report.md', 'w').write('\n'.join(md) + '\n')
    log('done', verdict, round(time.time() - t0), 's'); publish()

def _group(T):
    g = defaultdict(list)
    for t in T: g[t['day1']].append(t['ret'])
    return g

def publish():
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', BRANCH, OUT], check=True)
    subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', BRANCH], check=True)
    subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{REPO}.git', BRANCH], check=True, timeout=120, capture_output=True)

if __name__ == '__main__':
    main()
