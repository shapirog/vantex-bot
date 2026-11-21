"""
VANTEX City research: PUT CREDIT SPREADS, round 2 (improving the one strategy that worked). Research only: NO orders.

Round 1 (putspread.md): monthly $5-wide put spreads on SPY/QQQ/IWM/DIA held to expiry won 92% of trades, +3.5% on risk, but a
$2,500 account that put everything at risk fell 56% from its peak. Round 2 asks what makes it safer / better. All choices fixed
before running; every variant is shown, and the period is split so a choice that only works in one half is visible:
  dev  = entries Feb 2024 - Jun 2025      test = entries Jul 2025 - now (each half has one sharp sell-off: Apr 2025 / 2026)
  strike     3%, 5% or 7% below the price ($5 wide, first monthly >= 30 days)      expiry  30 vs 45+ days (5% below)
  ETFs       all four (SPY, QQQ, IWM, DIA) vs SPY + QQQ only
  filters    (using only the entry day's information)
             none | SPY above its 200-day average | SPY above its 50-day average | SPY's 20-day volatility under 20% a year
             | only after SPY fell 2%+ in the past week (sell insurance when it is expensive)
  sizing     $2,500 account, 1 contract per trade, money at risk capped at 100% or 50% of the account
Held to expiry (round 1: early exits lost). Credits at daily VWAPs minus 3% per leg.

  python city_putspread2.py   -> live-replay/putspread2.md / .json
"""
import json, math, os, sys
from collections import defaultdict
from datetime import date, datetime, timedelta

from city_engine import Data
from city_replay import ET, log, publish
from city_options_bt import occ, opt_bars
from city_putspread import expiry_for, candidates, nearest_traded, run_trade

ETFS = ['SPY', 'QQQ', 'IWM', 'DIA']
WIDTH = 5.0
PLANS = {'3% below, 30d': (0.03, 30), '5% below, 30d': (0.05, 30), '7% below, 30d': (0.07, 30), '5% below, 45d': (0.05, 45)}
SPLIT = '2025-07-01'

def spy_context(spy, cal):
    """entry-day filters from SPY closes up to the day BEFORE entry (the signal Friday)"""
    c = [spy[d]['c'] for d in cal]; out = {}
    for k in range(200, len(cal)):
        r = [math.log(c[j] / c[j - 1]) for j in range(k - 19, k + 1)]
        vol = (sum(x * x for x in r) / 20) ** 0.5 * math.sqrt(252)
        out[cal[k]] = dict(above200=c[k] > sum(c[k - 199:k + 1]) / 200, above50=c[k] > sum(c[k - 49:k + 1]) / 50,
                           calm=vol < 0.20, after_drop=c[k] / c[k - 5] - 1 <= -0.02)
    return out

FILTERS = {'none': lambda x: True, 'SPY > 200-day avg': lambda x: x['above200'], 'SPY > 50-day avg': lambda x: x['above50'],
           'calm (20-day vol < 20%)': lambda x: x['calm'], 'only after SPY -2% week': lambda x: x['after_drop']}

def account(T, cap, start=2500.0):
    """1 contract per trade in entry order while open risk <= cap x equity; P&L at exit. Returns end, %, max drawdown, trades"""
    eq = start; peak = start; dd = 0.0; open_ = []; n = 0
    def close_until(day):
        nonlocal eq, peak, dd
        for o in sorted([o for o in open_ if o['exit_day'] < day], key=lambda x: x['exit_day']):
            eq += 100 * o['pnl']; open_.remove(o); peak = max(peak, eq); dd = max(dd, 1 - eq / peak)
    for t in sorted(T, key=lambda x: (x['entry'], x['root'])):
        close_until(t['entry'])
        if eq > 0 and sum(100 * o['risk'] for o in open_) + 100 * t['risk'] <= cap * eq: open_.append(t); n += 1
    close_until('9999')
    return dict(end=round(eq), pct=round(100 * (eq / start - 1), 1), max_dd=round(100 * dd, 1), trades=n)

def per_trade(T):
    if not T: return dict(n=0)
    r = [t['pnl'] / t['risk'] for t in T]; n = len(r); mu = sum(r) / n; sd = (sum((x - mu) ** 2 for x in r) / max(1, n - 1)) ** 0.5
    return dict(n=n, win=round(100 * sum(x > 0 for x in r) / n, 1), avg=round(100 * mu, 2), t=round(mu / (sd / n ** 0.5), 2) if sd else None,
                lost_all=round(100 * sum(x <= -0.95 for x in r) / n, 1))

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    D = Data(key, sec); s0 = datetime(2023, 1, 1, tzinfo=ET); s1 = datetime.now(ET) - timedelta(minutes=20)
    bars = {s: {x['t'][:10]: x for x in L} for s, L in D.bars(ETFS, '1Day', s0, s1, 'sip', 'raw').items()}
    cal = sorted(bars['SPY']); pos = {d: k for k, d in enumerate(cal)}; ctx = spy_context(bars['SPY'], cal)
    weeks = [d for k, d in enumerate(cal) if d >= '2024-02-09' and k + 1 < len(cal) and date.fromisoformat(cal[k + 1]).isocalendar()[1] != date.fromisoformat(d).isocalendar()[1]]
    trades = []
    for w in weeks:
        d_in = cal[pos[w] + 1]; e_in = date.fromisoformat(d_in); plan = []
        for root in ETFS:
            px = bars[root][w]['c']
            for lab, (otm, days) in PLANS.items():
                exp = expiry_for(e_in, days, True)
                if exp.isoformat() > cal[-1]: continue
                tgt = px * (1 - otm); ks = candidates(px, tgt) + candidates(px, tgt - WIDTH)
                plan.append((root, lab, exp, px, tgt, ks))
        syms = sorted({occ(r, e, 'P', k) for r, _, e, _, _, ks in plan for k in ks})
        ob = opt_bars(D, syms, d_in, max((p[2] for p in plan), default=e_in).isoformat())
        for root, lab, exp, px, tgt, ks in plan:
            sk = nearest_traded(ob, root, exp, ks, tgt, d_in)
            lk = nearest_traded(ob, root, exp, ks, sk - WIDTH, d_in, below=sk) if sk else None
            if not lk: continue
            ce = bars[root].get(exp.isoformat(), {}).get('c')
            if ce is None:
                prior = [d for d in cal if d <= exp.isoformat()]; ce = bars[root][prior[-1]]['c']
            r = run_trade(ob, root, exp, sk, lk, d_in, [], ce, False)
            if r: trades.append(dict(r, root=root, plan=lab, entry=d_in, signal=w, ctx=ctx.get(w)))
        log(w, len(trades))
    rows = ['| strike / expiry | ETFs | filter | trades | win | avg on risk | t | lost all | dev avg | test avg | $2,500 @100% risk: end / worst drop | @50% risk: end / worst drop | @50% dev | @50% test |',
            '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    res = {}
    for lab in PLANS:
        for etf_lab, roots in (('all 4', set(ETFS)), ('SPY+QQQ', {'SPY', 'QQQ'})):
            for fl, f in FILTERS.items():
                T = [t for t in trades if t['plan'] == lab and t['root'] in roots and t['ctx'] and f(t['ctx'])]
                if not T: continue
                A = per_trade(T); dv = per_trade([t for t in T if t['entry'] < SPLIT]); ts = per_trade([t for t in T if t['entry'] >= SPLIT])
                a1, a5 = account(T, 1.0), account(T, 0.5)
                a5d, a5t = account([t for t in T if t['entry'] < SPLIT], 0.5), account([t for t in T if t['entry'] >= SPLIT], 0.5)
                res[f'{lab} | {etf_lab} | {fl}'] = dict(all=A, dev=dv, test=ts, acct100=a1, acct50=a5, acct50_dev=a5d, acct50_test=a5t)
                rows.append(f"| {lab} | {etf_lab} | {fl} | {A['n']} | {A['win']}% | {A['avg']:+}% | {A['t']} | {A['lost_all']}% | {dv.get('avg', 0):+}% | {ts.get('avg', 0):+}% | "
                            f"${a1['end']:,} / {a1['max_dd']}% | ${a5['end']:,} / {a5['max_dd']}% | {a5d['pct']:+}% / dd {a5d['max_dd']}% | {a5t['pct']:+}% / dd {a5t['max_dd']}% |")
    spy = bars['SPY']; a = min(d for d in spy if d >= '2024-02-12'); bh = spy[cal[-1]]['c'] / spy[a]['o'] - 1
    sd = min(d for d in spy if d >= SPLIT)
    md = ['# VANTEX City research: put credit spreads, round 2', '',
          '$5-wide monthly put spreads on ETFs, held to expiry. Every variant is listed (fixed before running). Dev = entries Feb 2024 - Jun 2025, test = Jul 2025 - now. '
          '"@50%" = never more than half the account at risk. Account columns start at $2,500.', ''] + rows + ['',
          f"SPY buy and hold: whole span {bh * 100:+.1f}%; dev half {(spy[sd]['o'] / spy[a]['o'] - 1) * 100:+.1f}%; test half {(spy[cal[-1]]['c'] / spy[sd]['o'] - 1) * 100:+.1f}%.", '',
          'Many variants are compared on only ~2.75 years, so the single best row will look better than it really is. Prefer choices that help in BOTH halves. '
          'Daily VWAP credits; a live order may get less. A backtest is not proof.']
    publish({}); publish({'putspread2.md': '\n'.join(md) + '\n', 'putspread2.json': res})
    log('done', len(trades))

if __name__ == '__main__':
    main()
