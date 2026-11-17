"""
VANTEX City research batch 2: mean reversion done properly, monthly momentum, and calendar effects. Research only: NO orders.

Batch 1 (city_swing.py) showed the RSI(2) pullback wins 63% of the time but breaks even after costs, and the gapper / breakout
ideas lose. This batch tests the published versions that are known to need cheap, liquid instruments and a healthy market:
  M1  RSI(2) < 10 pullback, only the most liquid stocks ($50M+ a day), only while SPY is above its 200-day line
  M2  Connors RSI(2) < 5, exit when RSI(2) rises above 70, same liquidity and market filter
  M3  RSI(2) < 10 on liquid index and sector ETFs (SPY, QQQ, IWM, DIA, XL*), exit above the 5-day average
  M4  three down days in a row on liquid stocks above their 200-day line, market filter, exit above the 5-day average
  M5  monthly momentum rotation: hold the 5 liquid stocks with the best 6-month return (skipping the last week), rebalance each
      month, go to cash when SPY is under its 200-day line
  M6  turn of the month on SPY: buy the close 4 trading days before month-end, sell the close of the 3rd trading day
Same honesty as before: signal on day t's close, act on day t+1's open (M6 acts at the close, as published), costs by liquidity,
stops on the low, gaps fill at the open. Every result is also shown with the 10 best trades removed and by year.

  python city_research.py dev   -> 2023-06 .. 2025-12  -> live-replay/research_dev.md / .json
  python city_research.py test  -> 2026 (untouched; only for a strategy that has earned it)
"""
import json, math, os, re, sys, time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

import requests

from city_engine import Data, NAME_EXCLUDE
from city_replay import ET, TRADE, log, publish
from city_swing import SPLITS, WARMUP_DAYS, cost_pct, indicators, per_trade_stats, portfolio

ETFS = ['SPY', 'QQQ', 'IWM', 'DIA', 'XLK', 'XLF', 'XLE', 'XLV', 'XLY', 'XLP', 'XLI', 'XLB', 'XLU', 'XLRE', 'XLC']
NAMES = {
    'M1': 'M1. RSI(2) pullback, $50M+/day stocks, SPY uptrend only',
    'M2': 'M2. Connors RSI(2) < 5, exit RSI(2) > 70, $50M+/day, SPY uptrend',
    'M3': 'M3. RSI(2) pullback on index and sector ETFs',
    'M4': 'M4. Three down days in a row, liquid uptrend stocks, SPY uptrend',
    'M5': 'M5. Monthly momentum rotation (top 5 by 6-month return, cash when SPY < 200-day)',
    'M6': 'M6. Turn of the month on SPY',
}

def market_ok(spy_B, spy_I):
    """day -> True when SPY closed above its 200-day average that day"""
    out = {}
    for i, b in enumerate(spy_B):
        x = spy_I[i]; m = x['sma200']() if x else None
        out[b[0]] = bool(m and b[4] > m)
    return out

def sim(B, I, i, stop, exit_rule, hold, cp):
    """enter at the open after signal day i; exit by rule at a close, by stop on the low (gap = open), or after `hold` days"""
    j0 = i + 1
    if j0 >= len(B): return None
    entry_raw = B[j0][1]
    if stop is None or stop >= entry_raw: return None
    entry = entry_raw * (1 + cp); risk = entry - stop; ex = why = jx = None
    for j in range(j0, min(len(B), j0 + hold)):
        _, o, h, l, c, v = B[j]
        if j > j0 and o <= stop: ex, why, jx = o, 'stop-gap', j; break
        if l <= stop: ex, why, jx = min(stop, o), 'stop', j; break
        if exit_rule(j): ex, why, jx = c, 'rule', j; break
    if ex is None:
        jx = min(len(B), j0 + hold) - 1; ex, why = B[jx][4], 'time'
    exit_ = ex * (1 - cp)
    return dict(entry_day=B[j0][0], exit_day=B[jx][0], entry=round(entry, 4), stop=round(stop, 4), exit=round(exit_, 4), why=why,
                R=round((exit_ - entry) / risk, 3), pct=round((exit_ / entry - 1) * 100, 3), days=jx - j0 + 1, cost_pct=cp * 100)

def stock_signals(sym, B, I, mkt, start, end, is_etf):
    out = []
    c = [b[4] for b in B]
    for i in range(22, len(B) - 1):
        d = B[i][0]
        if d < start or d > end or I[i] is None: continue
        x = I[i]; cp = cost_pct(x['adv']); px = c[i]
        if px < 5: continue
        above = (lambda: (lambda m: m is not None and px > m)(x['sma200']()))
        r2 = x['rsi2']
        sma5_exit = lambda j: I[j] is not None and I[j]['sma5'] is not None and B[j][4] > I[j]['sma5']
        if is_etf:
            if r2 is not None and r2 < 10 and above():
                t = sim(B, I, i, B[i + 1][1] - 4 * x['atr'], sma5_exit, 10, cost_pct(max(x['adv'], 50e6)))
                if t: out.append(('M3', dict(t, sym=sym, rank=-r2)))
            continue
        if not mkt.get(d): continue
        if x['adv'] >= 50e6 and r2 is not None and r2 < 10 and above():
            t = sim(B, I, i, B[i + 1][1] - 3 * x['atr'], sma5_exit, 10, cp)
            if t: out.append(('M1', dict(t, sym=sym, rank=-r2)))
        if x['adv'] >= 50e6 and r2 is not None and r2 < 5 and above():
            t = sim(B, I, i, B[i + 1][1] - 3 * x['atr'], lambda j: I[j] is not None and I[j]['rsi2'] is not None and I[j]['rsi2'] > 70, 10, cp)
            if t: out.append(('M2', dict(t, sym=sym, rank=-r2)))
        if x['adv'] >= 20e6 and c[i] < c[i - 1] < c[i - 2] < c[i - 3] and above():
            t = sim(B, I, i, B[i + 1][1] - 3 * x['atr'], sma5_exit, 10, cp)
            if t: out.append(('M4', dict(t, sym=sym, rank=(c[i - 3] / c[i] - 1))))
    return out

def compact(B, I):
    """what the rotation needs, small enough to keep for every liquid stock: days, opens, closes, 20-day dollar volume"""
    return ([b[0] for b in B], [b[1] for b in B], [b[4] for b in B], [x['adv'] if x else 0.0 for x in I])

def momentum(stocks, mkt, start, end, top=5):
    """monthly rotation. stocks: {sym: compact(...)}. Returns trades and the month-by-month account curve."""
    days = sorted({d for S in stocks.values() for d in S[0] if start <= d <= end})
    firsts = [d for k, d in enumerate(days) if k == 0 or d[:7] != days[k - 1][:7]]
    pos = {d: k for k, d in enumerate(days)}
    idx = {s: {d: i for i, d in enumerate(S[0])} for s, S in stocks.items()}
    trades, eq, curve = [], 1.0, []
    for m, d in enumerate(firsts[:-1]):
        nxt = firsts[m + 1]; prev = days[pos[d] - 1] if pos[d] > 0 else None
        if prev is None or not mkt.get(prev): curve.append((d, round(eq, 4), 'cash')); continue
        ranked = []
        for s, (ds, op, cl, adv) in stocks.items():
            i = idx[s].get(prev); j = idx[s].get(d); k = idx[s].get(nxt)
            if i is None or j is None or k is None or i < 130: continue
            if adv[i] < 20e6 or cl[i] < 10: continue
            ranked.append((cl[i - 5] / cl[i - 126] - 1, s, j, k, adv[i]))
        ranked.sort(reverse=True); picks = ranked[:top]
        if not picks: curve.append((d, round(eq, 4), 'none')); continue
        rets = []
        for r, s, j, k, adv in picks:
            ds, op, cl, _ = stocks[s]; cp = cost_pct(adv)
            e = op[j] * (1 + cp); x = op[k] * (1 - cp); rets.append(x / e - 1)
            trades.append(dict(sym=s, entry_day=ds[j], exit_day=ds[k], entry=round(e, 4), exit=round(x, 4), pct=round((x / e - 1) * 100, 3),
                               R=round((x / e - 1) / 0.10, 3), why='rebalance', days=k - j, stop=0, rank=r))
        eq *= 1 + sum(rets) / len(rets); curve.append((d, round(eq, 4), ','.join(p[1] for p in picks)))
    return trades, curve

def turn_of_month(B, start, end):
    days = [b[0] for b in B]; trades = []; cp = cost_pct(1e9)
    by_month = defaultdict(list)
    for i, d in enumerate(days): by_month[d[:7]].append(i)
    months = sorted(by_month)
    for a, b in zip(months, months[1:]):
        if len(by_month[a]) < 5 or len(by_month[b]) < 3: continue
        if days[by_month[a][-4]] < start or days[by_month[b][2]] > end: continue
        i = by_month[a][-4]; k = by_month[b][2]                               # buy the close 4 days before month-end, sell the 3rd day's close
        e = B[i][4] * (1 + cp); x = B[k][4] * (1 - cp)
        trades.append(dict(sym='SPY', entry_day=days[i], exit_day=days[k], entry=round(e, 4), exit=round(x, 4), pct=round((x / e - 1) * 100, 3),
                           R=round((x / e - 1) / 0.02, 3), why='calendar', days=k - i, stop=0, rank=0))
    return trades

def curve_stats(curve):
    eq = [c[1] for c in curve] or [1.0]; peak, dd = 1.0, 0.0
    for e in eq: peak = max(peak, e); dd = max(dd, (peak - e) / peak * 100)
    rets = [eq[0] - 1] + [eq[k] / eq[k - 1] - 1 for k in range(1, len(eq))]
    mu = sum(rets) / len(rets); sd = (sum((r - mu) ** 2 for r in rets) / max(1, len(rets) - 1)) ** 0.5
    return dict(return_pct=round((eq[-1] - 1) * 100, 1), max_drawdown_pct=round(dd, 1), sharpe_monthly_annualized=round(mu / sd * 12 ** 0.5, 2) if sd else None,
                months=len(eq), cash_months=sum(1 for c in curve if c[2] in ('cash', 'none')))

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
    s0 = datetime.combine(a - timedelta(days=WARMUP_DAYS), datetime.min.time(), ET)
    s1 = min(datetime.combine(b + timedelta(days=45), datetime.min.time(), ET), datetime.now(ET) - timedelta(days=1))
    def load(chunk):
        return {s: [(x['t'][:10], x['o'], x['h'], x['l'], x['c'], x['v']) for x in L] for s, L in D.bars(chunk, '1Day', s0, s1, 'sip', 'all').items()}
    etf = load(ETFS); etfI = {s: indicators(B) for s, B in etf.items()}
    mkt = market_ok(etf['SPY'], etfI['SPY'])
    trades = defaultdict(list); liquid = {}; t0 = time.time()
    for s in ETFS:
        for st, t in stock_signals(s, etf[s], etfI[s], mkt, start, end, True): trades[st].append(t)
    for k in range(0, len(syms), 100):
        for s, B in load(syms[k:k + 100]).items():
            if len(B) < 60: continue
            I = indicators(B)
            for st, t in stock_signals(s, B, I, mkt, start, end, False): trades[st].append(t)
            if max((x['adv'] for x in I if x), default=0) >= 20e6: liquid[s] = compact(B, I)
        if k % 1000 == 0: log(k, {s_: len(v) for s_, v in trades.items()}, 'liquid', len(liquid), round(time.time() - t0), 's')
    mom_trades, mom_curve = momentum(liquid, mkt, start, end); trades['M5'] = mom_trades
    trades['M6'] = turn_of_month(etf['SPY'], start, end)
    spy = [x for x in etf['SPY'] if start <= x[0] <= end]
    spy_ret = round((spy[-1][4] / spy[0][1] - 1) * 100, 1) if spy else None
    res = {}
    for k_, name in NAMES.items():
        T = trades[k_]; P = per_trade_stats(T)
        A = curve_stats(mom_curve) if k_ == 'M5' else (dict(return_pct=round((math.prod(1 + t['pct'] / 100 for t in T) - 1) * 100, 1)) if k_ == 'M6' else portfolio(T))
        res[k_] = dict(name=name, per_trade=P, account=A, sample=sorted(T, key=lambda t: t['entry_day'])[-30:])
    out = dict(split=split, period=[start, end], spy_buy_hold_pct=spy_ret, updated=datetime.now(ET).isoformat(timespec='seconds'), strategies=res,
               momentum_curve=mom_curve)
    rows = ['| strategy | trades | win rate | avg return/trade | expectancy | without top 10 | profit factor | account result | max drawdown |', '|---|---|---|---|---|---|---|---|---|']
    for k_, v in res.items():
        P, A = v['per_trade'], v['account']
        if not P.get('trades'): rows.append(f"| {v['name']} | 0 | | | | | | | |"); continue
        acct = f"{A.get('return_pct'):+}%" + (f" (${A['final_equity']})" if 'final_equity' in A else '')
        rows.append(f"| {v['name']} | {P['trades']} | {P['win_rate_pct']}% | {P['avg_pct']}% | {P['expectancy_R']}R | {P['expectancy_without_top10_R']}R | "
                    f"{P['profit_factor']} | {acct} | {A.get('max_drawdown_pct', '')}% |")
    years = ['', '## Average return per trade by year', ''] + [f"- {v['name']}: " + ', '.join(f"{y}: {x['expectancy_R']}R ({x['trades']})" for y, x in v['per_trade'].get('by_year', {}).items())
                                                                for v in res.values()]
    md = [f"# VANTEX City research batch 2 - {split} - {start} to {end}", '',
          f"Buy-and-hold SPY over the same period: {spy_ret:+}%. Costs 0.05%-0.50% per side by liquidity plus fees. Accounts start at $2,500, cash only "
          '(M1-M4: max 5 positions, 1% risk each; M5: 5 equal positions; M6: all-in SPY for the window).', ''] + rows + years + ['',
          'M5/M6 "expectancy" uses a nominal 10% / 2% risk unit, so compare them on average return per trade and account result.',
          'Survivorship bias: today\'s stock list only. A backtest is not proof.']
    publish({})
    publish({f'research_{split}.json': out, f'research_{split}.md': '\n'.join(md) + '\n'})

if __name__ == '__main__':
    main()
