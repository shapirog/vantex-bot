"""
VANTEX City research batch 4: slow, well-documented portfolio rotations. Research only: places NO orders.

Batches 1-3 traded single setups for days and the small edges did not survive costs or the untouched 2026 test.
These rebalance monthly (or weekly), hold many names, and are among the most studied ideas in finance:
  L1  large-cap momentum      top 20 of the 500 most-traded stocks by 12-month return, skipping the last month; monthly
  L2  L1 + trend filter       same, but sit in cash when SPY is under its 200-day line
  L3  ETF dual momentum       monthly: hold whichever of SPY / EFA (international) had the best 12-month return, if it beat
                              short-term Treasuries (SHY); otherwise hold bonds (AGG)
  L4  weekly reversal         each week buy the 20 biggest 5-day losers among the 500 most-traded stocks, hold one week
  L5  low volatility          top 20 of the 500 most-traded stocks with the calmest 60-day price moves; monthly
Prices: buy and sell at the open of the rebalance day, costs by liquidity on both sides, decisions use the prior close only.
Reported against buy-and-hold SPY on return, worst drawdown and risk-adjusted return (Sharpe from period returns).

  python city_rotation.py dev    -> 2023-06 .. 2025-12  -> live-replay/rotation_dev.md / .json
  python city_rotation.py test   -> 2026 (untouched; only for a rotation that earned it)
"""
import json, math, os, re, sys, time
from datetime import date, datetime, timedelta

import requests

from city_engine import Data, NAME_EXCLUDE
from city_replay import ET, TRADE, log, publish
from city_swing import SPLITS, cost_pct, indicators
from city_research import market_ok, compact

WARM = 420
ETFS = ['SPY', 'EFA', 'AGG', 'SHY']
NAMES = {'L1': 'L1. Large-cap momentum (top 20 of 500, monthly)', 'L2': 'L2. Large-cap momentum + SPY trend filter',
         'L3': 'L3. ETF dual momentum (SPY / EFA / bonds)', 'L4': 'L4. Weekly short-term reversal (20 biggest losers of 500)',
         'L5': 'L5. Low volatility (20 calmest of 500, monthly)', 'SPY': 'Buy and hold SPY'}

def rebalance_days(days, freq):
    if freq == 'month': return [d for k, d in enumerate(days) if k == 0 or d[:7] != days[k - 1][:7]]
    out = []
    for k, d in enumerate(days):                                         # first trading day of each ISO week
        if k == 0 or date.fromisoformat(d).isocalendar()[:2] != date.fromisoformat(days[k - 1]).isocalendar()[:2]: out.append(d)
    return out

def rotate(stocks, days, freq, score, top, universe=500, cash_when=None):
    """stocks: {sym: compact()}. score(cl, i) -> number (higher = buy) or None. Returns per-period list of (day, return, picks)."""
    idx = {s: {d: i for i, d in enumerate(S[0])} for s, S in stocks.items()}
    rb = rebalance_days(days, freq); pos = {d: k for k, d in enumerate(days)}; out = []
    for m in range(len(rb) - 1):
        d, nxt = rb[m], rb[m + 1]; prev = days[pos[d] - 1] if pos[d] > 0 else None
        if prev is None: continue
        if cash_when and cash_when(prev): out.append((d, 0.0, 'cash')); continue
        cands = []
        for s, (ds, op, cl, adv) in stocks.items():
            i = idx[s].get(prev); j = idx[s].get(d); k = idx[s].get(nxt)
            if i is None or j is None or k is None or cl[i] < 10: continue
            cands.append((adv[i], s, i, j, k))
        cands.sort(reverse=True); cands = cands[:universe]
        ranked = []
        for adv, s, i, j, k in cands:
            sc = score(stocks[s][2], i)
            if sc is not None: ranked.append((sc, s, j, k, adv))
        ranked.sort(reverse=True); picks = ranked[:top]
        if not picks: out.append((d, 0.0, 'none')); continue
        rets = []
        for sc, s, j, k, adv in picks:
            op = stocks[s][1]; cp = cost_pct(adv)
            rets.append(op[k] * (1 - cp) / (op[j] * (1 + cp)) - 1)
        out.append((d, sum(rets) / len(rets), ','.join(p[1] for p in picks[:5])))
    return out

def dual_momentum(etf, days):
    idx = {s: {d: i for i, d in enumerate(etf[s][0])} for s in etf}; rb = rebalance_days(days, 'month'); pos = {d: k for k, d in enumerate(days)}; out = []
    for m in range(len(rb) - 1):
        d, nxt = rb[m], rb[m + 1]; prev = days[pos[d] - 1] if pos[d] > 0 else None
        if prev is None: continue
        r12 = {}
        for s in ('SPY', 'EFA', 'SHY'):
            i = idx[s].get(prev)
            if i is None or i < 252: break
            r12[s] = etf[s][2][i] / etf[s][2][i - 252] - 1
        if len(r12) < 3: continue
        best = max(('SPY', 'EFA'), key=lambda s: r12[s]); hold = best if r12[best] > r12['SHY'] else 'AGG'
        j, k = idx[hold].get(d), idx[hold].get(nxt)
        if j is None or k is None: continue
        op = etf[hold][1]; cp = cost_pct(1e9)
        out.append((d, op[k] * (1 - cp) / (op[j] * (1 + cp)) - 1, hold))
    return out

def stats(periods, per_year):
    rets = [r for _, r, _ in periods]
    if not rets: return dict(periods=0)
    eq, peak, dd = 1.0, 1.0, 0.0
    for r in rets: eq *= 1 + r; peak = max(peak, eq); dd = max(dd, (peak - eq) / peak * 100)
    mu = sum(rets) / len(rets); sd = (sum((r - mu) ** 2 for r in rets) / max(1, len(rets) - 1)) ** 0.5
    by_year = {}
    for d, r, _ in periods: by_year.setdefault(d[:4], 1.0); by_year[d[:4]] *= 1 + r
    return dict(periods=len(rets), return_pct=round((eq - 1) * 100, 1), max_drawdown_pct=round(dd, 1),
                sharpe=round(mu / sd * per_year ** 0.5, 2) if sd else None, win_periods_pct=round(100 * sum(r > 0 for r in rets) / len(rets), 1),
                by_year={y: round((v - 1) * 100, 1) for y, v in sorted(by_year.items())}, last_picks=[p for _, _, p in periods[-3:]])

def mom_12_1(cl, i): return cl[i - 21] / cl[i - 252] - 1 if i >= 252 else None
def reversal_5(cl, i): return -(cl[i] / cl[i - 5] - 1) if i >= 5 else None
def low_vol_60(cl, i):
    if i < 61: return None
    r = [cl[k] / cl[k - 1] - 1 for k in range(i - 59, i + 1)]; mu = sum(r) / 60
    return -(sum((x - mu) ** 2 for x in r) / 59) ** 0.5

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    split = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else 'dev'
    a, b = SPLITS[split]; b = b or (date.today() - timedelta(days=7))
    start, end = a.isoformat(), b.isoformat()
    D = Data(key, sec); h = {'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': sec}
    r = requests.get(f'{TRADE}/v2/assets', headers=h, params=dict(status='active', asset_class='us_equity'), timeout=60)
    syms = sorted(x['symbol'] for x in (r.json() if r.ok else []) if x.get('exchange') in ('NASDAQ', 'NYSE', 'AMEX') and x.get('tradable')
                  and x['symbol'].isalpha() and not any(re.search(rx, (x.get('name') or '').lower()) for _, rx in NAME_EXCLUDE))
    s0 = datetime.combine(a - timedelta(days=WARM), datetime.min.time(), ET)
    s1 = min(datetime.combine(b + timedelta(days=40), datetime.min.time(), ET), datetime.now(ET) - timedelta(days=1))
    def load(chunk):
        return {s: [(x['t'][:10], x['o'], x['h'], x['l'], x['c'], x['v']) for x in L] for s, L in D.bars(chunk, '1Day', s0, s1, 'sip', 'all').items()}
    eB = load(ETFS); etf = {s: compact(B, indicators(B)) for s, B in eB.items()}
    mkt = market_ok(eB['SPY'], indicators(eB['SPY']))
    days = [d for d in etf['SPY'][0] if start <= d <= end] + [d for d in etf['SPY'][0] if d > end][:25]   # include the next rebalance for the last period
    stocks = {}; t0 = time.time()
    for k in range(0, len(syms), 100):
        for s, B in load(syms[k:k + 100]).items():
            if len(B) < 120: continue
            I = indicators(B)
            if max((x['adv'] for x in I if x), default=0) >= 20e6: stocks[s] = compact(B, I)
        if k % 1000 == 0: log(k, 'liquid stocks kept', len(stocks), round(time.time() - t0), 's')
    keep = lambda P: [p for p in P if p[0] <= end]
    res = {'L1': stats(keep(rotate(stocks, days, 'month', mom_12_1, 20)), 12),
           'L2': stats(keep(rotate(stocks, days, 'month', mom_12_1, 20, cash_when=lambda d: not mkt.get(d))), 12),
           'L3': stats(keep(dual_momentum(etf, days)), 12),
           'L4': stats(keep(rotate(stocks, days, 'week', reversal_5, 20)), 52),
           'L5': stats(keep(rotate(stocks, days, 'month', low_vol_60, 20)), 12)}
    spy_ds, spy_op = etf['SPY'][0], etf['SPY'][1]; rb = rebalance_days(days, 'month'); ix = {d: i for i, d in enumerate(spy_ds)}
    res['SPY'] = stats([(rb[m], spy_op[ix[rb[m + 1]]] / spy_op[ix[rb[m]]] - 1, 'SPY') for m in range(len(rb) - 1) if rb[m] <= end], 12)
    out = dict(split=split, period=[start, end], results={k: dict(name=NAMES[k], **v) for k, v in res.items()}, liquid_stocks=len(stocks),
               updated=datetime.now(ET).isoformat(timespec='seconds'))
    rows = ['| strategy | periods | total return | worst drawdown | Sharpe | % periods up | by year |', '|---|---|---|---|---|---|---|']
    for k, v in out['results'].items():
        if not v.get('periods'): rows.append(f"| {v['name']} | 0 | | | | | |"); continue
        rows.append(f"| {v['name']} | {v['periods']} | {v['return_pct']:+}% | {v['max_drawdown_pct']}% | {v['sharpe']} | {v['win_periods_pct']}% | "
                    f"{', '.join(f'{y}: {x:+}%' for y, x in v['by_year'].items())} |")
    md = [f"# VANTEX City research batch 4: portfolio rotations - {split} - {start} to {end}", '',
          f"{len(stocks)} liquid stocks. Trades at the open of each rebalance day, costs by liquidity on both sides, decisions use the prior close.", ''] + rows + ['',
          'A strategy is only interesting if it beats buy-and-hold SPY on risk-adjusted return (Sharpe) or drawdown, not just on total return in one stretch.',
          'Survivorship bias: today\'s stock list only (small for the 500 most-traded stocks, not zero). A backtest is not proof.']
    publish({})
    publish({f'rotation_{split}.json': out, f'rotation_{split}.md': '\n'.join(md) + '\n'})

if __name__ == '__main__':
    main()
