"""
Vantex lab 7 - how do you TRADE tiny-float premarket movers?  (research only, places no orders)

Lab 6 showed tiny-float premarket alerts run far more often (26% hit +50% on the day vs 9% for big floats),
but lab 5's 5-minute breakout entry with a tight stop lost money on them. Lab 7 tests 16 entry/exit
combinations built for wild swings, with an honest selection step.

PRE-REGISTERED before any result was seen (2026-11-15):
  Population : lab 5 WATCH alerts that fired premarket (before 9:30 ET) on stocks with < 5,000,000 shares
               outstanding (point-in-time SEC count, split-adjusted - same method as lab 6).
  Entries    : E1 buy the 9:30 open
               E2 first 1-minute close above the premarket high, 9:30-10:30
               E3 buy right after the premarket alert (premarket order at the ask)
               E4 VWAP reclaim: 9:35-11:00, a 1-minute bar dips to/below session VWAP and closes back above it
               All fills: next minute, at the historical SIP ask + 0.5% slippage (no quote -> bar open + 1.5%).
  Exits      : X1 hold to 15:55, emergency stop -25%
               X2 target +20%, stop -15%, else 15:55
               X3 target +10%, stop -10%, else 15:55
               X4 trailing stop 15% under the highest high since entry, else 15:55
               Stops gapped through fill at the bar open. Sells pay half the entry spread + 0.5% slippage + fees.
               Stop is checked before target inside a bar (worst case).
  Selection  : on TRAIN (before 2026-05-01) pick the ONE combo with the best mean net return per trade among
               combos with >= 100 train trades. It must have train mean > 0 and t-stat >= 2, else FAIL.
  TEST       : only that combo, May-Nov 2026. PASS needs ALL of:
               mean > 0 with bootstrap 95% lower bound > 0, profit factor >= 1.2, >= 100 trades,
               and the $2,500 account at 1% risk per trade (position = 1% / stop distance, <= 10% of the
               fill minute's volume, cash only) ends the test period above $2,500.
  The other 15 combos' test numbers are printed for transparency only and cannot be declared winners.
Results: 'live-lab7' branch -> lab7.json, lab7_report.md, lab7_trades.jsonl
"""
import json, math, os, subprocess, sys, time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

import numpy as np

sys.argv = [sys.argv[0], '300']          # lab5 reads a session count from argv at import
import lab5 as L5                         # minute bars + SIP quotes helpers (read-only)
import lab6 as L6                         # SEC share counts + splits helpers (read-only)

OUT = os.environ.get('VANTEX_LAB7_DIR', '/tmp/vantex-lab7')
IN = os.environ.get('VANTEX_LAB5_IN', '/tmp/vantex-lab5-in')
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')

FLOAT_MAX = 5_000_000
SPLIT_DATE = '2026-05-01'
SLIP, NOQ_PEN = 0.005, 0.015
OPEN, CLOSE = 570, 955
EQUITY = 2500.0
PART = 0.10
SEC_FEE, TAF = 27.8e-6, 0.000166
ENTRIES = ['E1 open', 'E2 PM-high break', 'E3 at alert', 'E4 VWAP reclaim']
EXITS = {'X1 hold, -25% stop': (None, 0.25, None), 'X2 +20%/-15%': (0.20, 0.15, None), 'X3 +10%/-10%': (0.10, 0.10, None), 'X4 trail 15%': (None, 0.15, 0.15)}
STATS = Counter()
log = L5.log

def entry_signals(M, watch_min):
    """returns {entry name: fill bar index} using only data available at decision time"""
    mins = M[:, 0]; out = {}
    pm = M[mins < OPEN]; pmh = float(pm[:, 2].max()) if len(pm) else None
    reg = np.where(mins >= OPEN)[0]
    if len(reg) == 0: return out, pmh
    i0 = reg[0]
    if mins[i0] <= OPEN + 5: out['E1 open'] = i0
    if pmh:
        for i in reg:
            if mins[i] > 630: break
            if M[i, 4] > pmh and i + 1 < len(M): out['E2 PM-high break'] = i + 1; break
    after = np.where((mins > watch_min) & (mins < OPEN))[0]
    if len(after): out['E3 at alert'] = after[0]
    pv = 0.0; vv = 0.0
    for i in reg:
        tp = (M[i, 2] + M[i, 3] + M[i, 4]) / 3; pv += tp * M[i, 5]; vv += M[i, 5]
        vw = pv / vv if vv else None
        if mins[i] > 660: break
        if vw and mins[i] >= 575 and M[i, 3] <= vw < M[i, 4] and i + 1 < len(M):
            out['E4 VWAP reclaim'] = i + 1; break
    return out, pmh

def simulate(M, k, entry, half_spread, target, stop_pct, trail):
    """walk bars from fill bar k; returns (exit price, why)"""
    stop = entry * (1 - stop_pct); hh = entry; tgt = entry * (1 + target) if target else None
    for i in range(k, len(M)):
        m, o, h, l, c = M[i, 0], M[i, 1], M[i, 2], M[i, 3], M[i, 4]
        if m > CLOSE: break
        st = max(stop, hh * (1 - trail)) if trail else stop
        if l <= st:
            px = min(st, o) if i > k else st
            return px * (1 - SLIP) * (1 - half_spread), 'stop'
        if tgt and h >= tgt: return (max(tgt, o) if i > k else tgt), 'target'
        hh = max(hh, h)
        if m == CLOSE: return c * (1 - SLIP) * (1 - half_spread), 'close'
    j = min(len(M) - 1, max(k, int(np.searchsorted(M[:, 0], CLOSE, 'right')) - 1))
    return M[j, 4] * (1 - SLIP) * (1 - half_spread), 'last bar'

def summ(R, seed=3):
    if len(R) == 0: return dict(trades=0)
    r = np.array(R); w = r[r > 0].sum(); l = -r[r <= 0].sum()
    g = np.random.default_rng(seed); bs = [r[g.integers(0, len(r), len(r))].mean() for _ in range(2000)]
    t = float(r.mean() / (r.std(ddof=1) / math.sqrt(len(r)))) if len(r) > 2 and r.std() > 0 else 0.0
    return dict(trades=len(r), mean_pct=round(float(r.mean()) * 100, 2), median_pct=round(float(np.median(r)) * 100, 2), win_rate_pct=round(float((r > 0).mean()) * 100, 1),
                profit_factor=round(float(w / l), 2) if l > 0 else None, t_stat=round(t, 2),
                ci95_pct=[round(float(np.percentile(bs, 2.5)) * 100, 2), round(float(np.percentile(bs, 97.5)) * 100, 2)],
                best_pct=round(float(r.max()) * 100, 1), worst_pct=round(float(r.min()) * 100, 1))

def account(T, days, risk):
    eq = EQUITY; peak = eq; dd = 0.0; daily = []; by = defaultdict(list)
    for t in T: by[t['day']].append(t)
    for d in days:
        cash = eq; p = 0.0
        for t in sorted(by.get(d, []), key=lambda x: x['fill_min']):
            pos = min(risk * eq / t['stop_pct'], PART * t['fill_vol'] * t['entry'], cash)
            sh = math.floor(pos / t['entry'])
            if sh < 1: continue
            cash -= sh * t['entry']; proceeds = sh * t['exit']
            p += proceeds - sh * t['entry'] - proceeds * SEC_FEE - min(8.3, sh * TAF)
        daily.append(p / eq if eq > 0 else 0.0); eq += p; peak = max(peak, eq); dd = max(dd, 1 - eq / peak)
    return dict(risk_pct=risk * 100, end_equity=round(eq, 2), net_pct=round((eq / EQUITY - 1) * 100, 1), max_dd_pct=round(dd * 100, 1)), np.array(daily)

def main():
    t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    os.makedirs(IN, exist_ok=True)
    for f in ('lab5_watch.jsonl', 'lab5_trades.jsonl'):
        if not os.path.exists(f'{IN}/{f}'):
            subprocess.run(f'git fetch -q --depth 1 origin live-lab5 && git show FETCH_HEAD:{f} > {IN}/{f}', shell=True, check=True)
    W = [json.loads(l) for l in open(f'{IN}/lab5_watch.jsonl')]
    days = sorted({w['day'] for w in W})
    pmw = [w for w in W if w['watch']['min'] < OPEN]
    syms = sorted({w['sym'] for w in pmw})
    SH = L6.sec_shares(syms)
    if not SH: raise SystemExit('SEC share counts unavailable - check the SEC_UA secret (needs a contact email)')
    SP, sp_ok = L6.splits(syms, date.fromisoformat(days[0]) - timedelta(days=400), date.fromisoformat(days[-1]))
    pop = []
    for w in pmw:
        v, _ = L6.shares_on(w['sym'], w['day'], SH, SP)
        if v is not None and v < FLOAT_MAX: w['shares_out'] = v; pop.append(w)
    log('population', len(pop), 'tiny-float premarket alerts', round(time.time() - t0), 's')

    byday = defaultdict(list)
    for w in pop: byday[w['day']].append(w)
    T = []
    for n, (d, rows) in enumerate(sorted(byday.items())):
        dord = date.fromisoformat(d).toordinal()
        M = L5.minutes_day(sorted({r['sym'] for r in rows}), dord)
        for r in rows:
            A = M.get(r['sym'])
            if A is None or len(A) < 10: STATS['no_minute_bars'] += 1; continue
            sig, pmh = entry_signals(A, r['watch']['min'])
            for en, k in sig.items():
                fm = int(A[k, 0])
                if fm > 900: continue
                q = L5.quote_at(r['sym'], dord, fm)
                if q: bid, ask = q; entry = ask * (1 + SLIP); hs = (ask - bid) / 2 / ask; STATS['quote'] += 1
                else: entry = A[k, 1] * (1 + NOQ_PEN); hs = 0.01; STATS['no_quote'] += 1
                for xn, (tg, sp, tr) in EXITS.items():
                    px, why = simulate(A, k, entry, hs, tg, sp, tr)
                    ret = px / entry - 1 - SEC_FEE
                    T.append(dict(sym=r['sym'], day=d, entry_rule=en, exit_rule=xn, fill_min=fm, entry=round(entry, 4), exit=round(px, 4), why=why,
                                  ret=round(ret, 5), stop_pct=sp, fill_vol=float(A[k, 5]), shares_out=r['shares_out'], quote=bool(q)))
        if n % 20 == 0: log('day', n, '/', len(byday), d, 'trades so far', len(T), round(time.time() - t0), 's')

    combos = [(e, x) for e in ENTRIES for x in EXITS]
    grid = {}
    for e, x in combos:
        S = [t for t in T if t['entry_rule'] == e and t['exit_rule'] == x]
        grid[f'{e} | {x}'] = dict(train=summ([t['ret'] for t in S if t['day'] < SPLIT_DATE]), test=summ([t['ret'] for t in S if t['day'] >= SPLIT_DATE]))
    cand = [(k, v['train']) for k, v in grid.items() if v['train'].get('trades', 0) >= 100]
    chosen = max(cand, key=lambda kv: kv[1]['mean_pct'])[0] if cand else None
    trS = grid[chosen]['train'] if chosen else {}
    train_ok = bool(chosen and trS['mean_pct'] > 0 and trS['t_stat'] >= 2)
    checks, A_te, A_all, odds = {}, None, {}, {}
    if chosen:
        e, x = chosen.split(' | ')
        CT = [t for t in T if t['entry_rule'] == e and t['exit_rule'] == x]
        te = [t for t in CT if t['day'] >= SPLIT_DATE]; teS = grid[chosen]['test']
        A_te, _ = account(te, [d for d in days if d >= SPLIT_DATE], 0.01)
        for rk in (0.01, 0.02, 0.05):
            a, dl = account(CT, days, rk); A_all[f'{rk*100:g}%'] = a
            g = np.random.default_rng(9); ends = np.array([np.prod(1 + np.maximum(dl[g.integers(0, len(dl), 42)], -1)) * EQUITY for _ in range(20000)])
            odds[f'{rk*100:g}%'] = dict(p_reach_40k=round(float((ends >= 40000).mean()) * 100, 3), p_double=round(float((ends >= 5000).mean()) * 100, 2),
                                        p_half=round(float((ends <= 1250).mean()) * 100, 2), median=round(float(np.median(ends))))
        checks = {'0 train: best combo mean > 0 and t >= 2': train_ok,
                  '1 test mean > 0 and CI low > 0': bool(teS.get('trades') and teS['mean_pct'] > 0 and teS['ci95_pct'][0] > 0),
                  '2 test profit factor >= 1.2': bool((teS.get('profit_factor') or 0) >= 1.2),
                  '3 test trades >= 100': bool(teS.get('trades', 0) >= 100),
                  '4 $2,500 at 1% risk ends test above $2,500': bool(A_te and A_te['end_equity'] > EQUITY)}
    verdict = 'PASS' if checks and all(checks.values()) else 'FAIL'
    R = dict(updated=datetime.now().isoformat(timespec='seconds'), verdict=verdict, chosen_on_train=chosen, checks=checks,
             chosen_train=trS, chosen_test=grid[chosen]['test'] if chosen else None, test_account_1pct=A_te, whole_period_accounts=A_all, odds_40k_in_42_sessions=odds,
             all_combos_transparency_only=grid,
             coverage=dict(premarket_alerts=len(pmw), tiny_float_alerts=len(pop), simulated_trades=len(T), stats=dict(STATS), lab5_stats=dict(L5.STATS), splits_ok=sp_ok),
             limitations=['Shares outstanding stands in for float (true float is smaller).', 'No historical halt feed: halts fill at the next bar.',
                          'One SIP quote at entry; exits pay half the entry spread. Premarket stops are simulated (real premarket stop orders are not supported at Alpaca).',
                          'Survivorship: Alpaca\'s asset list plus SEC\'s current ticker map.', 'This is trial ~670 overall; only the single train-chosen combo can count.'],
             seconds=round(time.time() - t0))
    json.dump(R, open(f'{OUT}/lab7.json', 'w'), indent=1, default=str)
    with open(f'{OUT}/lab7_trades.jsonl', 'w') as f:
        for t in T: f.write(json.dumps(t) + '\n')
    j = lambda x: '```\n' + json.dumps(x, indent=1, default=str) + '\n```'
    rows = ['| combo | train n | train mean % | train t | test n | test mean % | test PF |', '|---|---|---|---|---|---|---|']
    for k, v in grid.items():
        a, b = v['train'], v['test']
        rows.append(f"| {k} | {a.get('trades')} | {a.get('mean_pct')} | {a.get('t_stat')} | {b.get('trades')} | {b.get('mean_pct')} | {b.get('profit_factor')} |")
    md = [f"# Vantex lab 7 - trading tiny-float premarket movers - {R['updated']}", '', f"## VERDICT: {verdict}", f"Chosen on train: **{chosen}**", j(checks),
          '## Chosen combo - train', j(trS), '## Chosen combo - test', j(R['chosen_test']), '## Test account at 1% risk', j(A_te),
          '## Whole period accounts', j(A_all), '## $40K in 42 sessions', j(odds), '## All 16 combos (transparency only)'] + rows + \
         ['', '## Coverage', j(R['coverage']), '## Limitations'] + ['- ' + x for x in R['limitations']]
    open(f'{OUT}/lab7_report.md', 'w').write('\n'.join(md) + '\n')
    log('verdict', verdict, chosen, checks); publish()

def publish():
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', 'live-lab7', OUT], check=True)
    subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', 'lab7'], check=True)
    subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{REPO}.git', 'live-lab7'], check=True, timeout=120, capture_output=True)

if __name__ == '__main__':
    main()
