"""
Vantex lab 10 - the "EMA 9 x VWAP cross on 3-minute candles" strategy from the Instagram reel. Research only, NO orders.

LOCKED RULE (as shown in the reel; written before any result was seen, 2026-11-16)
Chart      3-minute candles, regular session 9:30-16:00 ET (built from SIP 1-minute bars).
Lines      VWAP: session VWAP from 9:30, price source (high + low + close + close) / 4 (the reel's setting).
           EMA 9 of the 3-minute closes (carried across days, like TradingView).
Signal     at a candle's close: EMA crosses ABOVE VWAP -> long ("buy calls"); crosses BELOW -> short ("buy puts").
           No signals on the first two candles of the day (VWAP just reset). No new entries after 15:30.
Exit       the opposite cross (and reverse into the new direction), or flat at 15:57.
Fill       the open of the next 1-minute bar after the signal candle closes, +/- 0.03% slippage each side.
           Stock shares are used as a stand-in for calls/puts: there is no historical option-quote data, and an
           option trade only magnifies the same stock move (minus time decay and spread).
Test       ~300 sessions, Sep 2025 -> Nov 13 2026, on 40 liquid stocks/ETFs.
           TRAIN = before 2026-05-01, TEST = from 2026-05-01. "Best stock" is picked ONLY on TRAIN, then judged on TEST.
Variants   (1) both directions (calls + puts) = primary; (2) long only (calls only), reported for comparison.
Results    branch 'live-lab10' -> lab10.json, lab10_report.md, lab10_trades.jsonl
"""
import json, math, os, subprocess, sys, time
from collections import defaultdict
from datetime import date, datetime, timedelta

import numpy as np

sys.argv = [sys.argv[0], 'history']
import lab8 as L8
ET, log = L8.ET, L8.log

OUT = os.environ.get('VANTEX_LAB10_DIR', '/tmp/vantex-lab10')
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
FIRST, LAST, SPLIT = date(2025, 9, 4), date(2026, 11, 13), '2026-05-01'
SYMS = ['SPY', 'QQQ', 'IWM', 'DIA', 'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AMD', 'NFLX', 'AVGO', 'PLTR',
        'COIN', 'MU', 'MSTR', 'UBER', 'BA', 'JPM', 'XOM', 'SMCI', 'ARM', 'HOOD', 'SOFI', 'INTC', 'BAC', 'F', 'RIVN',
        'SOUN', 'MARA', 'RIOT', 'CVNA', 'SHOP', 'CRWD', 'SNOW', 'DKNG', 'AFRM', 'UPST']
SLIP = 0.0003
EMA_N = 9
EQUITY = 2500.0

def three_min(A):
    """1-minute RTH rows -> 3-minute candles [start_min, o, h, l, c, v] plus the 1-minute opens by minute"""
    rth = A[(A[:, 0] >= 570) & (A[:, 0] < 960)]
    C = {}
    for m, o, h, l, c, v in rth:
        b = 570 + (int(m) - 570) // 3 * 3
        if b not in C: C[b] = [b, o, h, l, c, v]
        else: x = C[b]; x[2] = max(x[2], h); x[3] = min(x[3], l); x[4] = c; x[5] += v
    opens = {int(r[0]): r[1] for r in rth}
    return [C[k] for k in sorted(C)], opens, rth

def fill_px(opens, rth, minute):
    """open of the first 1-minute bar at/after `minute` (None if none before 16:00)"""
    for k in range(minute, 960):
        if k in opens: return opens[k], k
    return None, None

def run_symbol(M):
    """trades for one symbol across days: list of dict(day, side, entry, exit, ret)"""
    T = []; ema = None; alpha = 2 / (EMA_N + 1)
    for d in sorted(M):
        C, opens, rth = three_min(M[d])
        if len(C) < 10: continue
        pv = vv = 0.0; prev = None; pos = None
        for i, (b, o, h, l, c, v) in enumerate(C):
            src = (h + l + 2 * c) / 4; pv += src * v; vv += v
            vwap = pv / vv if vv else c
            ema = c if ema is None else ema + alpha * (c - ema)
            diff = ema - vwap
            end = b + 3                                               # candle known at its close
            if pos and end >= 957:
                px, k = fill_px(opens, rth, 957)
                if px is None: px = C[-1][4]
                T.append(close(pos, px, d)); pos = None
            if i >= 2 and prev is not None and end < 957:
                cross = 1 if (prev <= 0 < diff) else -1 if (prev >= 0 > diff) else 0
                if cross and (pos is None or pos['side'] != cross):
                    px, k = fill_px(opens, rth, end)
                    if px is not None and k < 957:
                        if pos: T.append(close(pos, px, d)); pos = None
                        if end <= 930: pos = dict(side=cross, entry=px * (1 + SLIP * cross), t=k, day=d)
            prev = diff
        if pos:
            px = C[-1][4]; T.append(close(pos, px, d))
    return T

def close(pos, px, d):
    ex = px * (1 - SLIP * pos['side'])
    return dict(day=date.fromordinal(d).isoformat(), side=pos['side'], entry=round(pos['entry'], 4), exit=round(ex, 4),
                minute_in=pos['t'], ret=round(pos['side'] * (ex / pos['entry'] - 1), 6))

def stats(R, by_day=None):
    if not R: return dict(trades=0)
    r = np.array(R); w = r[r > 0].sum(); l = -r[r <= 0].sum()
    out = dict(trades=len(r), win_rate_pct=round(float((r > 0).mean()) * 100, 1), mean_bps=round(float(r.mean()) * 1e4, 2),
               total_pct=round(float(r.sum()) * 100, 1), profit_factor=round(float(w / l), 2) if l > 0 else None)
    if by_day:
        keys = list(by_day); s = np.array([sum(by_day[k]) for k in keys]); n = np.array([len(by_day[k]) for k in keys])
        g = np.random.default_rng(5); means = [s[ix].sum() / n[ix].sum() for ix in (g.integers(0, len(keys), len(keys)) for _ in range(3000))]
        out['ci95_mean_bps_day_clustered'] = [round(float(np.percentile(means, 2.5)) * 1e4, 2), round(float(np.percentile(means, 97.5)) * 1e4, 2)]
    return out

def grp(T):
    g = defaultdict(list)
    for t in T: g[t['day']].append(t['ret'])
    return stats([t['ret'] for t in T], g)

def account(T, start=EQUITY):
    """whole account in every trade of one symbol (upper bound: ignores the day-trade limit under $25K)"""
    eq = start; peak = eq; dd = 0.0
    for t in T: eq *= 1 + t['ret']; peak = max(peak, eq); dd = max(dd, 1 - eq / peak)
    return dict(end_equity=round(eq, 2), max_dd_pct=round(dd * 100, 1))

def main():
    t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    sessions, full = L8.sessions_between(FIRST - timedelta(days=10), LAST)
    days = {d for d in sessions if d >= FIRST.toordinal() and d in full}
    per, allT = {}, []
    for k, s in enumerate(SYMS):
        M = {d: A for d, A in L8.minutes_range(s, FIRST - timedelta(days=5), LAST).items() if d in days}
        if not M: log('no data', s); continue
        T = run_symbol(M)
        for t in T: t['sym'] = s
        allT += T
        tr = [t for t in T if t['day'] < SPLIT]; te = [t for t in T if t['day'] >= SPLIT]
        per[s] = dict(sessions=len(M), train=grp(tr), test=grp(te), train_long=grp([t for t in tr if t['side'] > 0]),
                      test_long=grp([t for t in te if t['side'] > 0]), account_test_both=account(te), account_test_long=account([t for t in te if t['side'] > 0]))
        log(k + 1, '/', len(SYMS), s, len(T), 'trades', per[s]['train'].get('mean_bps'), per[s]['test'].get('mean_bps'), round(time.time() - t0), 's')
    ranked = sorted([s for s in per if per[s]['train'].get('trades', 0) >= 100], key=lambda s: -per[s]['train']['mean_bps'])
    best3 = ranked[:3]
    tr = [t for t in allT if t['day'] < SPLIT]; te = [t for t in allT if t['day'] >= SPLIT]
    best_test = [t for t in te if t['sym'] in best3]
    pooled = dict(train=grp(tr), test=grp(te), train_long=grp([t for t in tr if t['side'] > 0]), test_long=grp([t for t in te if t['side'] > 0]))
    picked = dict(best3_on_train=best3, their_train=grp([t for t in tr if t['sym'] in best3]), their_test=grp(best_test),
                  their_test_long=grp([t for t in best_test if t['side'] > 0]), best1=best3[0] if best3 else None,
                  best1_test=per[best3[0]]['test'] if best3 else None, best1_test_account=per[best3[0]]['account_test_both'] if best3 else None)
    positive_both = [s for s in per if (per[s]['train'].get('mean_bps') or -1) > 0 and (per[s]['test'].get('mean_bps') or -1) > 0]
    R = dict(updated=datetime.now(ET).isoformat(timespec='seconds'), rule='EMA9 x VWAP(hlcc4) cross, 3-min candles, stop-and-reverse, flat 15:57, 0.03% slippage',
             sessions=len(days), pooled=pooled, picked_on_train=picked, positive_in_both_periods=positive_both,
             per_symbol=per, seconds=round(time.time() - t0),
             notes=['Stock moves stand in for calls/puts (no historical option quotes). Options add leverage, time decay and spread.',
                    'Day-trade limit: under $25K only 3 day trades per 5 days in a margin account; accounts here ignore it (upper bound).',
                    'The reel shows a monthly P&L screenshot; it does not show the rules for exits, position size or which tickers.'])
    json.dump(R, open(f'{OUT}/lab10.json', 'w'), indent=1, default=str)
    with open(f'{OUT}/lab10_trades.jsonl', 'w') as f:
        for t in allT: f.write(json.dumps(t) + '\n')
    j = lambda x: '```\n' + json.dumps(x, indent=1, default=str) + '\n```'
    rows = ['| symbol | train trades | train bps/trade | train PF | test trades | test bps/trade | test PF | test long-only bps |', '|---|---|---|---|---|---|---|---|']
    for s in sorted(per, key=lambda s: -(per[s]['test'].get('mean_bps') or -999)):
        a, b, c = per[s]['train'], per[s]['test'], per[s]['test_long']
        rows.append(f"| {s} | {a.get('trades')} | {a.get('mean_bps')} | {a.get('profit_factor')} | {b.get('trades')} | {b.get('mean_bps')} | {b.get('profit_factor')} | {c.get('mean_bps')} |")
    md = [f"# Vantex lab 10 - EMA 9 x VWAP cross (3-minute) - {R['updated']}", '', R['rule'], '', '## All 40 symbols pooled', j(pooled),
          '## "Best stock" picked on TRAIN, judged on TEST', j(picked), f"Positive in BOTH periods: {positive_both}", '', '## Every symbol (sorted by test)'] + rows + \
         ['', '## Notes'] + ['- ' + n for n in R['notes']]
    open(f'{OUT}/lab10_report.md', 'w').write('\n'.join(md) + '\n')
    log('done', round(time.time() - t0), 's'); publish()

def publish():
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', 'live-lab10', OUT], check=True)
    subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', 'lab10'], check=True)
    subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{REPO}.git', 'live-lab10'], check=True, timeout=120, capture_output=True)

if __name__ == '__main__':
    main()
