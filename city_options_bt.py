"""
VANTEX City research: BUYING CALL OPTIONS backtest. Research only: places NO orders.

Question (Guillo, 2026-11-19): pick the right stock, buy options with the right expiration, would it do well?
Alpaca's historical option prices start in February 2024, so this covers Feb 2024 - now (about 90 weeks).
Each week (signal at Friday's close, trade the next session, sell 5 sessions later):
  which stocks     the 100 most-traded US stocks with options (by 20-day dollar volume, price >= $10). Picks:
                   MOMENTUM   the 10 with the best 12-month return excluding the last month (classic, fixed rule)
                   STRONG+DIP the 10 best 12-1 momentum names that fell over the last week (buy strength on a pullback)
                   RANDOM     10 random names from the same 100 (control: is the stock pick worth anything?)
                   SPY, QQQ   the index ETFs
  which options    CALLS, 3 expirations x 2 strikes, all fixed before running:
                   expiry  ~1 week (first Friday >= 7 days out), ~1 month (first monthly >= 28 days), ~2 months (>= 56 days)
                   strike  at the money (closest to the stock price) and 5% out of the money
  prices           the option's daily VWAP on the entry and exit days (real traded prices), minus a spread penalty of
                   3% of the premium per side (and a 6% check); contracts with no trade that day are skipped and counted
  compared with    simply buying the same stocks for the same week
Holding a week keeps the test about picking direction, not about holding to expiry. A backtest is not proof.

  python city_options_bt.py   -> live-replay/options_bt.md / .json / options_bt_trades.csv
"""
import csv, io, json, math, os, random, sys, time
from collections import defaultdict
from datetime import date, datetime, timedelta

from city_engine import Data
from city_replay import ET, log, publish
from city_overnight import universe

SPREAD = (0.03, 0.06)
START = '2024-02-12'

def occ(root, exp, kind, strike):
    """OCC option symbol, e.g. AAPL240216C00190000"""
    return f"{root}{exp.strftime('%y%m%d')}{kind}{int(round(strike * 1000)):08d}"

def third_friday(y, m):
    d = date(y, m, 15)
    while d.weekday() != 4: d += timedelta(days=1)
    return d

def expiries(entry):
    """(label, expiry date) for the three fixed choices"""
    d = entry + timedelta(days=7)
    while d.weekday() != 4: d += timedelta(days=1)
    out = [('~1 week', d)]
    for lab, days in (('~1 month', 28), ('~2 months', 56)):
        t = entry + timedelta(days=days); y, m = t.year, t.month
        f = third_friday(y, m)
        if f < t: y, m = (y + 1, 1) if m == 12 else (y, m + 1); f = third_friday(y, m)
        out.append((lab, f))
    return out

def strike_grid(px, target):
    """candidate strikes around `target` using the usual listed increments"""
    steps = [0.5, 1.0] if px < 25 else [1.0, 2.5, 5.0] if px < 200 else [5.0, 10.0]
    c = set()
    for st in steps:
        base = round(target / st) * st
        for k in range(-2, 3): c.add(round(base + k * st, 2))
    return sorted(x for x in c if x > 0)

def pick_contract(bars, cands, target, entry_day):
    """the listed contract closest to target strike that traded on the entry day: (symbol, strike) or None"""
    best = None
    for sym, k in cands:
        L = bars.get(sym) or []
        if any(b['t'][:10] == entry_day for b in L):
            if best is None or abs(k - target) < abs(best[1] - target): best = (sym, k)
    return best

def vwap_on(bars, sym, day):
    for b in bars.get(sym) or []:
        if b['t'][:10] == day: return b.get('vw') or b['c']
    return None

def opt_bars(D, syms, a, b):
    out = defaultdict(list)
    for i in range(0, len(syms), 100):
        tok = None
        while True:
            p = dict(symbols=','.join(syms[i:i + 100]), timeframe='1Day', start=a, end=b, limit=10000)
            if tok: p['page_token'] = tok
            r = D.get('/v1beta1/options/bars', p, 'opt_bars')
            if r is None or not r.ok:
                if r is not None: log('option bars error', r.status_code, r.text[:200])
                break
            j = r.json()
            for s, L in (j.get('bars') or {}).items(): out[s].extend(L)
            tok = j.get('next_page_token')
            if not tok: break
    return out

def stats(rs):
    if not rs: return dict(n=0)
    n = len(rs); mu = sum(rs) / n; srt = sorted(rs); sd = (sum((x - mu) ** 2 for x in rs) / max(1, n - 1)) ** 0.5
    wo = srt[:-5] if n > 10 else srt
    return dict(n=n, win_pct=round(100 * sum(x > 0 for x in rs) / n, 1), avg_pct=round(100 * mu, 2), median_pct=round(100 * srt[n // 2], 2),
                t=round(mu / (sd / n ** 0.5), 2) if sd else None, avg_wo_best5_pct=round(100 * sum(wo) / len(wo), 2),
                lost_90pct_plus=round(100 * sum(x <= -0.9 for x in rs) / n, 1))

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    D = Data(key, sec)
    # probe: can we read historical option bars on this plan?
    pr = opt_bars(D, [occ('SPY', date(2024, 3, 15), 'C', 510)], '2024-03-01', '2024-03-15')
    log('probe SPY 2024-03-15 510C bars:', len(pr.get(occ('SPY', date(2024, 3, 15), 'C', 510), [])))
    h = {'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': sec}
    import requests
    from city_replay import TRADE
    opt = set()
    r = requests.get(f'{TRADE}/v2/assets', headers=h, params=dict(status='active', asset_class='us_equity', attributes='options_enabled'), timeout=90)
    if r.ok: opt = {x['symbol'] for x in r.json() if x.get('tradable') and x['symbol'].isalpha()}
    if len(opt) < 200: opt = {s for s, v in universe(key, sec).items() if v == 'active'}      # filter not supported: use all active
    log('options-enabled symbols', len(opt))
    s0 = datetime(2022, 12, 1, tzinfo=ET); s1 = datetime.now(ET) - timedelta(minutes=20)
    syms = sorted(opt | {'SPY', 'QQQ'}); bars = {}; adj = {}
    for k in range(0, len(syms), 100):
        for s, L in D.bars(syms[k:k + 100], '1Day', s0, s1, 'sip', 'raw').items():
            if len(L) > 300: bars[s] = L                                        # raw prices: what strikes were listed against
        for s, L in D.bars(syms[k:k + 100], '1Day', s0, s1, 'sip', 'split').items():
            if len(L) > 300: adj[s] = {x['t'][:10]: x['c'] for x in L}          # split-adjusted closes: for momentum
    cal = [x['t'][:10] for x in bars['SPY']]; pos = {d: k for k, d in enumerate(cal)}
    ix = {s: {x['t'][:10]: i for i, x in enumerate(L)} for s, L in bars.items()}
    weeks = [d for k, d in enumerate(cal) if d >= START and (k + 1 == len(cal) or date.fromisoformat(cal[k + 1]).isocalendar()[1] != date.fromisoformat(d).isocalendar()[1])]
    rng = random.Random(4); trades = []
    for w in weeks:
        k = pos[w]
        if k + 6 >= len(cal): break
        d_in, d_out = cal[k + 1], cal[k + 6]
        rows = []
        for s, L in bars.items():
            i = ix[s].get(w)
            if i is None or i < 260 or s in ('SPY', 'QQQ'): continue
            c = L[i]['c']; A = adj.get(s, {}); dd = [L[j]['t'][:10] for j in (i, i - 5, i - 21, i - 252)]
            if c < 10 or any(x not in A for x in dd): continue
            adv = sum(L[j]['c'] * L[j]['v'] for j in range(i - 19, i + 1)) / 20
            rows.append((adv, s, A[dd[2]] / A[dd[3]] - 1, A[dd[0]] / A[dd[1]] - 1))
        rows.sort(reverse=True); top = rows[:100]
        mom = sorted(top, key=lambda r: -r[2])
        groups = {'MOMENTUM (top 10 by 12-1 month return)': [r[1] for r in mom[:10]],
                  'STRONG+DIP (strong, fell last week)': [r[1] for r in mom[:30] if r[3] < 0][:10],
                  'RANDOM 10 (control)': [r[1] for r in rng.sample(top, 10)], 'SPY': ['SPY'], 'QQQ': ['QQQ']}
        plan = []
        for g, L in groups.items():
            for s in L:
                i_in, i_out = ix[s].get(d_in), ix[s].get(d_out)
                if i_in is None or i_out is None: continue
                px = bars[s][ix[s][w]]['c']; e = date.fromisoformat(d_in)
                stock_r = bars[s][i_out]['vw'] / bars[s][i_in]['vw'] - 1 if bars[s][i_in].get('vw') else None
                for lab, ex in expiries(e):
                    for mlab, tgt in (('at the money', px), ('5% out of the money', px * 1.05)):
                        cands = [(occ(s, ex, 'C', k_), k_) for k_ in strike_grid(px, tgt)]
                        plan.append(dict(group=g, sym=s, week=w, d_in=d_in, d_out=d_out, expiry=ex.isoformat(), exp_lab=lab, money=mlab, target=tgt, cands=cands, stock_r=stock_r))
        allsyms = sorted({c for p in plan for c, _ in p['cands']})
        ob = opt_bars(D, allsyms, d_in, d_out)
        for p in plan:
            got = pick_contract(ob, p['cands'], p['target'], p['d_in'])
            if not got: p['skipped'] = 'no contract traded on entry day'; trades.append(p); continue
            b_in = vwap_on(ob, got[0], p['d_in']); b_out = vwap_on(ob, got[0], p['d_out'])
            if b_out is None:                                                    # no trade on exit day: last trade before it
                prior = [b for b in ob.get(got[0], []) if p['d_in'] < b['t'][:10] < p['d_out']]
                b_out = (prior[-1].get('vw') or prior[-1]['c']) if prior else None
            if b_out is None and date.fromisoformat(p['expiry']) <= date.fromisoformat(p['d_out']): b_out = 0.0
            if not b_in or b_out is None: p['skipped'] = 'no exit price'; trades.append(p); continue
            p.update(contract=got[0], strike=got[1], premium=b_in, exit=b_out,
                     net=[b_out * (1 - sp) / (b_in * (1 + sp)) - 1 for sp in SPREAD])
            trades.append(p)
        log(w, 'contracts', len(allsyms), 'priced', sum(1 for p in plan if 'net' in p))
    res = {}; rows_md = ['| stocks | expiry | strike | trades | win rate | avg per trade | median | avg w/o best 5 | lost 90%+ | t-stat | at 6% spread | same stocks, no options |',
                         '|---|---|---|---|---|---|---|---|---|---|---|---|']
    groups = ['MOMENTUM (top 10 by 12-1 month return)', 'STRONG+DIP (strong, fell last week)', 'RANDOM 10 (control)', 'SPY', 'QQQ']
    for g in groups:
        for lab in ('~1 week', '~1 month', '~2 months'):
            for ml in ('at the money', '5% out of the money'):
                T = [t for t in trades if t['group'] == g and t['exp_lab'] == lab and t['money'] == ml and 'net' in t]
                if not T: continue
                S = stats([t['net'][0] for t in T]); S2 = stats([t['net'][1] for t in T]); st = stats([t['stock_r'] for t in T if t['stock_r'] is not None])
                res[f'{g} | {lab} | {ml}'] = dict(S, avg_6pct_spread=S2['avg_pct'], stock_avg_pct=st.get('avg_pct'))
                rows_md.append(f"| {g} | {lab} | {ml} | {S['n']} | {S['win_pct']}% | {S['avg_pct']:+}% | {S['median_pct']:+}% | {S['avg_wo_best5_pct']:+}% | {S['lost_90pct_plus']}% | "
                               f"{S['t']} | {S2['avg_pct']:+}% | {st.get('avg_pct', 0):+}% |")
    skipped = sum(1 for t in trades if 'skipped' in t)
    md = ['# VANTEX City research: buying call options (Feb 2024 - now)', '',
          f'{len(trades)} planned trades, {len(trades) - skipped} priced, {skipped} skipped (no traded contract or price). Buy the call the session after Friday\'s close, '
          'sell 5 sessions later, both at the option\'s daily VWAP, minus 3% of premium per side for the spread. Returns are per trade on the premium paid.', ''] + rows_md + [
          '', '"same stocks, no options" = the stock\'s own VWAP-to-VWAP return over the same days. "lost 90%+" = share of trades that lost almost all of the premium. '
          'Option VWAPs are real trades but a small order can still pay more than the 3% assumed. A backtest is not proof.']
    buf = io.StringIO(); w_ = csv.writer(buf)
    w_.writerow(['group', 'week', 'sym', 'contract', 'expiry', 'money', 'premium', 'exit', 'net_pct', 'stock_pct', 'skipped'])
    for t in trades:
        w_.writerow([t['group'], t['week'], t['sym'], t.get('contract'), t['expiry'], t['money'], t.get('premium'), t.get('exit'),
                     round(100 * t['net'][0], 2) if 'net' in t else None, round(100 * t['stock_r'], 2) if t.get('stock_r') is not None else None, t.get('skipped')])
    publish({}); publish({'options_bt.md': '\n'.join(md) + '\n', 'options_bt.json': res, 'options_bt_trades.csv': buf.getvalue()})
    log('done', len(trades), 'skipped', skipped)

if __name__ == '__main__':
    main()
