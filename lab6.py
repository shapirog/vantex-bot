"""
Vantex lab 6 - does LOW FLOAT turn the early-runner rule into a winner?  (research only, places no orders)

PRE-REGISTERED before any result was seen (2026-11-15):
  Population : the lab 5 locked-rule trades where the WATCH alert fired premarket (before 9:30 ET).
  Filter     : shares outstanding <= 10,000,000, point-in-time (last SEC cover-page count filed BEFORE
               the trade day, adjusted for any split between that count and the trade day).
  Train      : trades before 2026-05-01.   Test: trades from 2026-05-01 on.
  PASS only if ALL hold:
     1. expectancy > 0 R in train
     2. expectancy > 0 R in test, with the bootstrap 95% lower bound > 0
     3. profit factor >= 1.2 in test
     4. >= 100 test trades (fewer = INCONCLUSIVE, not a pass)
     5. the $2,500 account at 1% risk (rule $500 cap) ends the test period above $2,500
  Everything else in the report (other float buckets, regular-session alerts) is descriptive only
  and can NOT be used to declare a winner.

Inputs : lab5_trades.jsonl + lab5_watch.jsonl from the 'live-lab5' branch (same entries, fills, exits, fees).
Data   : SEC EDGAR companyfacts (dei:EntityCommonStockSharesOutstanding), Alpaca corporate actions (splits).
Results: 'live-lab6' branch -> lab6.json, lab6_report.md, lab6_trades.jsonl
"""
import json, math, os, subprocess, sys, time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

import numpy as np
import requests

OUT = os.environ.get('VANTEX_LAB6_DIR', '/tmp/vantex-lab6')
IN = os.environ.get('VANTEX_LAB5_IN', '/tmp/vantex-lab5-in')
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
H = {'APCA-API-KEY-ID': os.environ.get('APCA_API_KEY_ID', ''), 'APCA-API-SECRET-KEY': os.environ.get('APCA_API_SECRET_KEY', '')}
SEC_UA = os.environ.get('SEC_UA') or 'Vantex research bot (github.com/shapirog/vantex-bot)'
SECH = {'User-Agent': SEC_UA, 'Accept-Encoding': 'gzip, deflate'}
DATA = 'https://data.alpaca.markets'

# ---- pre-registered ----
FLOAT_MAX = 10_000_000
SPLIT_DATE = '2026-05-01'
MIN_TEST_TRADES, MIN_PF = 100, 1.2
MAX_AGE_DAYS = 400                     # a share count older than this is treated as unknown
EQUITY, MAX_POS = 2500.0, 500.0
SEC_FEE, TAF = 27.8e-6, 0.000166
BUCKETS = [('<5M', 0, 5e6), ('5-10M', 5e6, 10e6), ('10-20M', 10e6, 20e6), ('20-50M', 20e6, 50e6), ('>50M', 50e6, 1e18)]
STATS = Counter()

def log(*a): print(' '.join(str(x) for x in a), flush=True)

def get(url, params=None, headers=None, timeout=60):
    for k in range(6):
        try: r = requests.get(url, headers=headers or H, params=params, timeout=timeout)
        except Exception as e: log('network', type(e).__name__, url[-60:]); time.sleep(2 * (k + 1)); continue
        if r.status_code in (429, 503): time.sleep(3 * (k + 1)); continue
        STATS['requests'] += 1
        return r
    STATS['request_failures'] += 1
    return None

# ------------------------------------------------------------------ inputs
def load_lab5():
    os.makedirs(IN, exist_ok=True)
    for f in ('lab5_trades.jsonl', 'lab5_watch.jsonl', 'lab5.json'):
        p = f'{IN}/{f}'
        if not os.path.exists(p):
            subprocess.run(f'git fetch -q --depth 1 origin live-lab5 && git show FETCH_HEAD:{f} > {p}', shell=True, check=True)
    T = [json.loads(l) for l in open(f'{IN}/lab5_trades.jsonl')]
    W = [json.loads(l) for l in open(f'{IN}/lab5_watch.jsonl')]
    return T, W

# ------------------------------------------------------------------ share counts (point in time)
def sec_shares(syms):
    """sym -> [(filed date iso, as-of end date iso, shares)] sorted by filed"""
    r = get('https://www.sec.gov/files/company_tickers.json', headers=SECH, timeout=30)
    if r is None or not r.ok: log('SEC not reachable', getattr(r, 'status_code', None)); return {}
    cmap = {v['ticker'].upper(): int(v['cik_str']) for v in r.json().values()}
    out, cache = {}, {}
    for k, s in enumerate(syms):
        cik = cmap.get(s)
        if not cik: STATS['no_cik'] += 1; continue
        if cik not in cache:
            time.sleep(0.11)
            rr = get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json', headers=SECH, timeout=60)
            if rr is None or not rr.ok: STATS['facts_missing'] += 1; cache[cik] = []
            else:
                f = rr.json().get('facts', {}); L = []
                for ns, tag in (('dei', 'EntityCommonStockSharesOutstanding'), ('us-gaap', 'CommonStockSharesOutstanding')):
                    for u in (f.get(ns, {}).get(tag, {}).get('units', {}).get('shares') or []):
                        if u.get('filed') and u.get('end') and u.get('val'):
                            L.append((u['filed'], u['end'], float(u['val']), 0 if ns == 'dei' else 1))
                # dei cover-page count preferred; if several classes share a filing, add them up
                agg = defaultdict(float); pri = {}
                for fl, en, v, p in L:
                    key = (fl, en)
                    if key in pri and pri[key] < p: continue
                    if key in pri and pri[key] > p: agg[key] = 0.0
                    pri[key] = p; agg[key] += v
                cache[cik] = sorted((fl, en, v) for (fl, en), v in agg.items())
        if cache[cik]: out[s] = cache[cik]
        if k % 200 == 0: log('sec', k, '/', len(syms))
    return out

def splits(syms, start, end):
    """sym -> [(ex_date iso, factor new/old)]"""
    out = defaultdict(list); ok = False
    for base in ('/v1/corporate-actions', '/v1beta1/corporate-actions'):
        for i in range(0, len(syms), 100):
            d0 = start
            while d0 < end:
                d1 = min(d0 + timedelta(days=89), end); tok = None
                while True:
                    p = dict(symbols=','.join(syms[i:i + 100]), types='forward_split,reverse_split', start=d0.isoformat(), end=d1.isoformat(), limit=1000)
                    if tok: p['page_token'] = tok
                    r = get(DATA + base, p)
                    if r is None or not r.ok: STATS[f'splits_http_{getattr(r, "status_code", None)}'] += 1; break
                    ok = True; j = r.json(); ca = j.get('corporate_actions', j)
                    for kind in ('forward_splits', 'reverse_splits'):
                        for x in (ca.get(kind) or []):
                            try: out[x['symbol']].append((x['ex_date'], float(x['new_rate']) / float(x['old_rate'])))
                            except Exception: STATS['split_parse'] += 1
                    tok = j.get('next_page_token')
                    if not tok: break
                d0 = d1 + timedelta(days=1)
        if ok: break
    STATS['splits_found'] = sum(len(v) for v in out.values())
    return {k: sorted(set(v)) for k, v in out.items()}, ok

def shares_on(sym, day, SH, SP):
    """point-in-time shares outstanding for sym before the open of `day` (ISO), or None"""
    L = SH.get(sym)
    if not L: return None, 'no SEC count'
    prior = [x for x in L if x[0] < day]
    if not prior: return None, 'no count filed yet'
    fl, en, v = prior[-1]
    if (date.fromisoformat(day) - date.fromisoformat(fl)).days > MAX_AGE_DAYS: return None, 'count too old'
    for ex, fac in SP.get(sym, []):
        if en < ex <= day: v *= fac
    return v, None

# ------------------------------------------------------------------ stats
def trade_pnl(T, shares):
    if shares <= 0: return 0.0
    h = shares // 2 if T['half'] is not None else 0
    proceeds = h * (T['half'] or 0) + (shares - h) * T['rest']
    return proceeds - proceeds * SEC_FEE - min(8.3, shares * TAF) - shares * T['entry']

def summ(L, seed=5):
    if not L: return dict(trades=0)
    r = np.array([t['r_mult'] for t in L]); w = r[r > 0].sum(); l = -r[r <= 0].sum()
    g = np.random.default_rng(seed); bs = [r[g.integers(0, len(r), len(r))].mean() for _ in range(2000)] if len(r) >= 10 else [np.nan]
    return dict(trades=len(L), win_rate_pct=round(float((r > 0).mean()) * 100, 1), expectancy_R=round(float(r.mean()), 3),
                ci95_R=[round(float(np.nanpercentile(bs, 2.5)), 3), round(float(np.nanpercentile(bs, 97.5)), 3)],
                profit_factor=round(float(w / l), 2) if l > 0 else None, median_mfe_pct=round(float(np.median([t['mfe_pct'] for t in L])), 2),
                hit_plus50_from_entry=sum(bool(t['hit_50']) for t in L), median_R=round(float(np.median(r)), 3))

def account(L, days, risk):
    eq = EQUITY; peak = eq; dd = 0.0; daily = []; by = defaultdict(list)
    for t in L: by[t['day']].append(t)
    for d in days:
        cash = eq; p = 0.0
        for t in sorted(by.get(d, []), key=lambda x: x['fill_min']):
            rps = t['entry'] - t['stop']
            sh = math.floor(min(risk * eq / rps, MAX_POS / t['entry'], t['part_cap'], cash / t['entry']))
            if sh < 1: continue
            cash -= sh * t['entry']; p += trade_pnl(t, sh)
        daily.append(p / eq if eq > 0 else 0.0); eq += p; peak = max(peak, eq); dd = max(dd, 1 - eq / peak)
    return dict(risk_pct=risk * 100, end_equity=round(eq, 2), net_pct=round((eq / EQUITY - 1) * 100, 1), max_dd_pct=round(dd * 100, 1)), np.array(daily)

def odds(daily, hz=42, paths=20000, seed=7):
    if len(daily) < 20: return None
    g = np.random.default_rng(seed); ends = []; d50 = 0
    for _ in range(paths):
        e = np.cumprod(1 + np.maximum(daily[g.integers(0, len(daily), hz)], -1.0)); ends.append(e[-1] * EQUITY); d50 += e.min() <= 0.5
    e = np.array(ends)
    return dict(sessions=hz, p_reach_40k=round(float((e >= 40000).mean()) * 100, 3), p_double=round(float((e >= 5000).mean()) * 100, 2),
                p_down50=round(d50 / paths * 100, 2), median=round(float(np.median(e))), p5=round(float(np.percentile(e, 5))), p95=round(float(np.percentile(e, 95))))

def bucket(v):
    if v is None: return 'unknown'
    for n, a, b in BUCKETS:
        if a <= v < b: return n
    return 'unknown'

# ------------------------------------------------------------------ main
def main():
    t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    T, W = load_lab5()
    days = sorted({w['day'] for w in W}); syms = sorted({w['sym'] for w in W})
    log('lab5 inputs:', len(T), 'trades', len(W), 'alerts', len(syms), 'symbols', len(days), 'sessions')
    SH = sec_shares(syms); log('SEC share counts for', len(SH), 'symbols', round(time.time() - t0), 's')
    SP, sp_ok = splits(syms, date.fromisoformat(days[0]) - timedelta(days=400), date.fromisoformat(days[-1])); log('splits ok', sp_ok, STATS['splits_found'])

    why = Counter()
    for t in T:
        v, w = shares_on(t['sym'], t['day'], SH, SP); t['shares_out'] = v; t['float_bucket'] = bucket(v)
        if w: why[w] += 1
    for w in W:
        v, _ = shares_on(w['sym'], w['day'], SH, SP); w['float_bucket'] = bucket(v)

    pm = [t for t in T if t['premarket_watch']]
    prim = [t for t in pm if t['shares_out'] is not None and t['shares_out'] <= FLOAT_MAX]
    tr = [t for t in prim if t['day'] < SPLIT_DATE]; te = [t for t in prim if t['day'] >= SPLIT_DATE]
    te_days = [d for d in days if d >= SPLIT_DATE]
    A_te, _ = account(te, te_days, 0.01)
    A_all = {r: account(prim, days, r) for r in (0.005, 0.01, 0.02, 0.05)}
    S_tr, S_te = summ(tr), summ(te)
    checks = {
        '1 train expectancy > 0': bool(S_tr.get('expectancy_R') is not None and S_tr['expectancy_R'] > 0),
        '2 test expectancy > 0 and CI low > 0': bool(S_te.get('expectancy_R') is not None and S_te['expectancy_R'] > 0 and S_te['ci95_R'][0] > 0),
        f'3 test profit factor >= {MIN_PF}': bool((S_te.get('profit_factor') or 0) >= MIN_PF),
        f'4 test trades >= {MIN_TEST_TRADES}': bool(S_te['trades'] >= MIN_TEST_TRADES),
        '5 $2,500 at 1% risk ends test above $2,500': bool(A_te['end_equity'] > EQUITY),
    }
    verdict = 'PASS' if all(checks.values()) else ('INCONCLUSIVE (too few test trades)' if not checks[f'4 test trades >= {MIN_TEST_TRADES}'] and all(v for k, v in checks.items() if not k.startswith('4')) else 'FAIL')

    # descriptive tables
    desc_pm = {b: summ([t for t in pm if t['float_bucket'] == b]) for b in [n for n, _, _ in BUCKETS] + ['unknown']}
    desc_all = {b: summ([t for t in T if t['float_bucket'] == b]) for b in [n for n, _, _ in BUCKETS] + ['unknown']}
    alerts = {}
    for b in [n for n, _, _ in BUCKETS] + ['unknown']:
        X = [w for w in W if w['float_bucket'] == b and w['watch']['min'] < 570]
        ok = [w for w in X if w.get('max_after_watch') and w['max_after_watch'] >= 1.10 * w['watch']['px']]
        big = [w for w in X if w.get('day_high') and w['day_high'] >= 1.5 * w['pc']]
        alerts[b] = dict(premarket_alerts=len(X), rose_10pct_more_after_alert_pct=round(len(ok) / len(X) * 100, 1) if X else None,
                         day_high_plus50_pct=round(len(big) / len(X) * 100, 1) if X else None)

    R = dict(updated=datetime.now().isoformat(timespec='seconds'), preregistered=dict(population='lab 5 trades, WATCH before 9:30', float_max=FLOAT_MAX,
             train=f'< {SPLIT_DATE}', test=f'>= {SPLIT_DATE}', pass_rules=list(checks)),
             coverage=dict(trades=len(T), premarket_trades=len(pm), primary_trades=len(prim), share_count_missing=dict(why), splits_feed_ok=sp_ok,
                           symbols_with_sec_count=len(SH), symbols=len(syms), stats=dict(STATS)),
             verdict=verdict, checks=checks, train=S_tr, test=S_te, test_account_1pct=A_te,
             primary_all_period_accounts={f'{r*100:g}%': a for r, (a, _) in A_all.items()},
             odds_2_months={f'{r*100:g}%': odds(dl) for r, (_, dl) in A_all.items()},
             descriptive_premarket_by_float=desc_pm, descriptive_all_by_float=desc_all, premarket_alert_quality_by_float=alerts,
             limitations=['Shares outstanding (SEC cover page) is used for float; true float is smaller (insider/locked shares excluded), so "<=10M shares out" is a stricter test than "<=10M float".',
                          'Companies missing from today\'s SEC ticker map (renamed, delisted, some foreign filers) have unknown share counts and are left out of the primary test.',
                          'Share counts update only when a company files (usually quarterly); offerings between filings are not seen until the next filing.',
                          'Entries, exits, fills and fees are lab 5\'s; lab 5 limitations (no halt feed, one quote snapshot, survivorship) carry over.',
                          'This is trial ~651+; only the pre-registered primary test can count.'],
             seconds=round(time.time() - t0))
    json.dump(R, open(f'{OUT}/lab6.json', 'w'), indent=1, default=str)
    with open(f'{OUT}/lab6_trades.jsonl', 'w') as f:
        for t in prim: f.write(json.dumps(t, default=str) + '\n')
    open(f'{OUT}/lab6_report.md', 'w').write(report(R))
    log('verdict', verdict, checks); publish()

def report(R):
    j = lambda x: '```\n' + json.dumps(x, indent=1, default=str) + '\n```'
    L = [f"# Vantex lab 6 - low float, premarket alerts - {R['updated']}", '', f"## VERDICT: {R['verdict']}", j(R['checks']),
         '## Pre-registered test', j(R['preregistered']), '## Train', j(R['train']), '## Test', j(R['test']), '## Test account at 1% risk', j(R['test_account_1pct']),
         '## Whole period, $2,500 account', j(R['primary_all_period_accounts']), '## Odds over 2 months (42 sessions)', j(R['odds_2_months']),
         '## Descriptive only: premarket trades by shares outstanding', j(R['descriptive_premarket_by_float']),
         '## Descriptive only: all trades by shares outstanding', j(R['descriptive_all_by_float']),
         '## Descriptive only: premarket alert quality by shares outstanding', j(R['premarket_alert_quality_by_float']),
         '## Coverage', j(R['coverage']), '## Limitations'] + ['- ' + x for x in R['limitations']]
    return '\n'.join(L) + '\n'

def publish():
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', 'live-lab6', OUT], check=True)
    subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', 'lab6'], check=True)
    subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{REPO}.git', 'live-lab6'], check=True, timeout=120, capture_output=True)

if __name__ == '__main__':
    main()
