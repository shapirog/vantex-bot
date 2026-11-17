"""
VANTEX City swing-strategy research. Research only: places NO orders.

Holds for days, decides on end-of-day prices, so it works on the free data plan and never makes a day trade.
Each strategy is tested on its own, on every US common stock Alpaca lists, with daily bars:
  signal at the CLOSE of day t (using only data up to t)  ->  buy at the OPEN of day t+1  ->  exit by its own rule.
Costs on every trade: an estimated half-spread + slippage per side by liquidity (0.05% to 0.50%), plus SEC/FINRA fees.
Stops are checked on each day's low; a gap below the stop fills at the open (worse), never at the stop.

Strategies (simple, published ideas, no tuning to the data):
  S1  gapper follow-through  up 10%+ on 3x volume, closes in the top quarter of its range  -> hold 5 days, stop = that day's low
  S2  big-catalyst hold      up 15%+ on 5x volume, closes in the top quarter              -> hold 20 days, stop = that day's low
  S3  RSI(2) pullback        above its 200-day average, 2-day RSI under 10, liquid          -> sell when it closes above its 5-day average (max 10 days), 3-ATR disaster stop
  S4  52-week-high breakout  new 52-week closing high on 2x volume                         -> sell on a close under the 20-day average (max 40 days), 2-ATR stop
Two views of each: every signal (per-trade edge, in R and %), and a $2,500 cash account (max 5 positions, 1% risk each, no margin).
Known limits: today's stock list (delisted stocks are missing = survivorship bias, flatters buy strategies); costs are estimates.

  python city_swing.py dev     -> 2023-06 .. 2025-12   -> live-replay/swing_dev.md / .json
  python city_swing.py test    -> 2026-01 .. last week (untouched until a strategy earns it, run once)
"""
import json, math, os, re, sys, time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

import requests

import vantex_core as V
from city_engine import Data, NAME_EXCLUDE
from city_replay import ET, TRADE, log, publish

SPLITS = {'dev': (date(2023, 6, 1), date(2025, 12, 31)), 'test': (date(2026, 1, 1), None)}
WARMUP_DAYS = 400                                                   # calendar days of history before the period, for the 200-day / 52-week lines

STRATS = {
    'S1': dict(name='S1. Gapper follow-through (up 10%+ on 3x volume, hold 5 days)'),
    'S2': dict(name='S2. Big-catalyst hold (up 15%+ on 5x volume, hold 20 days)'),
    'S3': dict(name='S3. RSI(2) pullback in an uptrend (exit above 5-day average)'),
    'S4': dict(name='S4. 52-week-high breakout on volume (exit under 20-day average)'),
}

def cost_pct(avg_dollar_vol):
    """estimated half-spread + slippage per side, by liquidity"""
    if avg_dollar_vol >= 50e6: return 0.0005
    if avg_dollar_vol >= 10e6: return 0.0010
    if avg_dollar_vol >= 2e6: return 0.0025
    return 0.0050

def indicators(B):
    """B: list of (day, o, h, l, c, v). Per-day values that only use data up to that day (prefix sums, so it stays fast)."""
    n = len(B); c = [x[4] for x in B]; v = [x[5] for x in B]
    pc, pv, pdv, ptr = [0.0], [0.0], [0.0], [0.0]
    for i in range(n):
        pc.append(pc[-1] + c[i]); pv.append(pv[-1] + v[i]); pdv.append(pdv[-1] + v[i] * c[i])
        tr = B[i][2] - B[i][3] if i == 0 else max(B[i][2], c[i - 1]) - min(B[i][3], c[i - 1]); ptr.append(ptr[-1] + tr)
    def avg(p, i, k): return (p[i + 1] - p[i + 1 - k]) / k if i + 1 >= k else None    # last k values up to and including i
    rsi2 = [None] * n; ag = al = None
    for i in range(1, n):                                                # Wilder RSI, 2 days
        ch = c[i] - c[i - 1]; g, ls = max(ch, 0.0), max(-ch, 0.0)
        if ag is None: ag, al = g, ls
        else: ag, al = (ag + g) / 2, (al + ls) / 2
        rsi2[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    out = [None] * n
    for i in range(21, n):
        out[i] = dict(atr=avg(ptr, i, 14), avgv=(pv[i] - pv[i - 20]) / 20, adv=(pdv[i] - pdv[i - 20]) / 20,     # volume: the 20 days BEFORE today
                      sma5=avg(pc, i, 5), sma20=avg(pc, i, 20), rsi2=rsi2[i],
                      sma200=lambda i=i: avg(pc, i, 200), hi252=lambda i=i: max(c[i - 252:i]) if i >= 252 else None)
    return out

def signals(B, I, start, end):
    """(strategy, signal index, stop, rank score) for each signal day inside [start, end]"""
    out = []
    for i in range(21, len(B) - 1):
        d = B[i][0]
        if d < start or d > end or I[i] is None: continue
        _, o, h, l, c, v = B[i]; pc = B[i - 1][4]; x = I[i]
        if c < 2 or x['adv'] < 1e6 or pc <= 0: continue
        chg = c / pc - 1; rv = v / x['avgv'] if x['avgv'] else 0; top = (c - l) / (h - l) if h > l else 0
        if chg >= 0.10 and rv >= 3 and top >= 0.75: out.append(('S1', i, l, rv))
        if chg >= 0.15 and rv >= 5 and top >= 0.75: out.append(('S2', i, l, rv))
        if c >= 5 and x['adv'] >= 5e6 and x['rsi2'] is not None and x['rsi2'] < 10:
            m200 = x['sma200']()
            if m200 and c > m200: out.append(('S3', i, None, -x['rsi2']))
        if c >= 5 and rv >= 2:
            hi = x['hi252']()
            if hi and c > hi: out.append(('S4', i, None, rv))
    return out

def trade(B, I, s, i, stop):
    """simulate one signal: enter next open, exit by the strategy's rule. Returns a trade dict or None."""
    j0 = i + 1; x = I[i]; cp = cost_pct(x['adv'])
    entry_raw = B[j0][1]
    if s == 'S3': stop = entry_raw - 3 * x['atr']
    if s == 'S4': stop = entry_raw - 2 * x['atr']
    if stop is None or stop >= entry_raw: return None
    entry = entry_raw * (1 + cp); risk = entry - stop
    hold = {'S1': 5, 'S2': 20, 'S3': 10, 'S4': 40}[s]
    ex, why, jx = None, None, None
    for j in range(j0, min(len(B), j0 + hold + 1)):
        _, o, h, l, c, v = B[j]
        if j > j0 and o <= stop: ex, why, jx = o, 'stop-gap', j; break
        if l <= stop: ex, why, jx = min(stop, o), 'stop', j; break
        Ij = I[j]
        if s == 'S3' and Ij and Ij['sma5'] and c > Ij['sma5']: ex, why, jx = c, 'rule', j; break
        if s == 'S4' and Ij and Ij['sma20'] and c < Ij['sma20']: ex, why, jx = c, 'rule', j; break
        if j - j0 + 1 >= hold: ex, why, jx = c, 'time', j; break
    if ex is None:                                                       # ran out of data: close at the last close
        jx = len(B) - 1; ex, why = B[jx][4], 'open at end'
    exit_ = ex * (1 - cp)
    return dict(entry_day=B[j0][0], exit_day=B[jx][0], entry=round(entry, 4), stop=round(stop, 4), exit=round(exit_, 4), why=why,
                R=round((exit_ - entry) / risk, 3), pct=round((exit_ / entry - 1) * 100, 3), days=jx - j0 + 1, cost_pct=cp * 100)

def per_trade_stats(T):
    if not T: return dict(trades=0)
    R = [t['R'] for t in T]; P = [t['pct'] for t in T]; W = [t for t in T if t['R'] > 0]; Lo = [t for t in T if t['R'] <= 0]
    s = sorted(R, reverse=True); gw = sum(t['R'] for t in W); gl = -sum(t['R'] for t in Lo)
    by_year = defaultdict(list)
    for t in T: by_year[t['entry_day'][:4]].append(t['R'])
    return dict(trades=len(T), win_rate_pct=round(100 * len(W) / len(T), 1), avg_win_R=round(gw / len(W), 2) if W else None,
                avg_loss_R=round(-gl / len(Lo), 2) if Lo else None, expectancy_R=round(sum(R) / len(R), 3),
                expectancy_without_top10_R=round(sum(s[10:]) / max(1, len(s) - 10), 3), avg_pct=round(sum(P) / len(P), 2),
                median_pct=round(sorted(P)[len(P) // 2], 2), profit_factor=round(gw / gl, 2) if gl else None, avg_days=round(sum(t['days'] for t in T) / len(T), 1),
                by_year={y: dict(trades=len(v), expectancy_R=round(sum(v) / len(v), 3)) for y, v in sorted(by_year.items())},
                exits=dict(Counter(t['why'] for t in T)))

def portfolio(T, start_eq=2500.0, max_pos=5, risk_pct=1.0, max_pos_pct=25.0):
    """a cash account: each day the best-ranked new signals buy at the open while slots and cash allow, then that day's exits free cash"""
    by_entry = defaultdict(list)
    for t in T: by_entry[t['entry_day']].append(t)
    days = sorted(set(t['entry_day'] for t in T) | set(t['exit_day'] for t in T))
    cash, eq_real, peak, dd = start_eq, start_eq, start_eq, 0.0; open_ = []; taken = 0; skipped = 0
    for d in days:
        for t in sorted(by_entry.get(d, []), key=lambda t: -t['rank']):     # buys happen at the open, before any exit frees cash
            if len(open_) >= max_pos: skipped += 1; continue
            risk_ps = t['entry'] - t['stop']
            qty = min(math.floor(eq_real * risk_pct / 100 / risk_ps), math.floor(eq_real * max_pos_pct / 100 / t['entry']), math.floor(cash / t['entry']))
            if qty < 1: skipped += 1; continue
            cash -= qty * t['entry']; open_.append(dict(t=t, qty=qty)); taken += 1
        for p in [p for p in open_ if p['t']['exit_day'] <= d]:
            proceeds = p['qty'] * p['t']['exit']; fees = V.sale_fees(date.fromisoformat(d), p['qty'], p['t']['exit'])
            cash += proceeds - fees; eq_real += proceeds - fees - p['qty'] * p['t']['entry']; open_.remove(p)
            peak = max(peak, eq_real); dd = max(dd, (peak - eq_real) / peak * 100)
    for p in open_: eq_real += p['qty'] * (p['t']['exit'] - p['t']['entry'])
    return dict(final_equity=round(eq_real, 2), return_pct=round((eq_real / start_eq - 1) * 100, 1), max_drawdown_pct=round(dd, 1),
                trades_taken=taken, signals_skipped=skipped)

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    split = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else 'dev'
    a, b = SPLITS[split]; b = b or (date.today() - timedelta(days=7))
    D = Data(key, sec); h = {'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': sec}
    r = requests.get(f'{TRADE}/v2/assets', headers=h, params=dict(status='active', asset_class='us_equity'), timeout=60)
    syms = sorted(x['symbol'] for x in (r.json() if r.ok else []) if x.get('exchange') in ('NASDAQ', 'NYSE', 'AMEX') and x.get('tradable')
                  and x['symbol'].isalpha() and not any(re.search(rx, (x.get('name') or '').lower()) for _, rx in NAME_EXCLUDE))
    log('universe', len(syms), 'period', a, b)
    t0 = time.time(); trades = defaultdict(list); start_s, end_s = a.isoformat(), b.isoformat(); nsym = 0
    s0 = datetime.combine(a - timedelta(days=WARMUP_DAYS), datetime.min.time(), ET); s1 = datetime.combine(b + timedelta(days=60), datetime.min.time(), ET)
    s1 = min(s1, datetime.now(ET) - timedelta(days=1))
    for k in range(0, len(syms), 100):
        raw = D.bars(syms[k:k + 100], '1Day', s0, s1, 'sip', 'all')
        for s, L in raw.items():
            B = [(x['t'][:10], x['o'], x['h'], x['l'], x['c'], x['v']) for x in L]
            if len(B) < 60: continue
            nsym += 1; I = indicators(B)
            for st, i, stop, rank in signals(B, I, start_s, end_s):
                t = trade(B, I, st, i, stop)
                if t: trades[st].append(dict(t, sym=s, rank=rank))
        del raw
        if k % 1000 == 0: log(k, 'symbols done', {s_: len(v) for s_, v in trades.items()}, round(time.time() - t0), 's')
    spy = D.bars(['SPY'], '1Day', datetime.combine(a, datetime.min.time(), ET), datetime.combine(b, datetime.min.time(), ET), 'sip', 'all').get('SPY', [])
    spy_ret = round((spy[-1]['c'] / spy[0]['o'] - 1) * 100, 1) if spy else None
    out = dict(split=split, period=[start_s, end_s], symbols_with_data=nsym, spy_buy_hold_pct=spy_ret, updated=datetime.now(ET).isoformat(timespec='seconds'),
               strategies={k: dict(STRATS[k], per_trade=per_trade_stats(trades[k]), account=portfolio(trades[k]),
                                   sample=sorted(trades[k], key=lambda t: t['entry_day'])[-40:]) for k in STRATS})
    rows = ['| strategy | signals | win rate | avg win | avg loss | expectancy | without top 10 | avg return/trade | profit factor | avg days | $2,500 account | max drawdown |',
            '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for k, v in out['strategies'].items():
        P, A = v['per_trade'], v['account']
        if not P.get('trades'): rows.append(f"| {v['name']} | 0 | | | | | | | | | | |"); continue
        rows.append(f"| {v['name']} | {P['trades']} | {P['win_rate_pct']}% | {P['avg_win_R']}R | {P['avg_loss_R']}R | {P['expectancy_R']}R | {P['expectancy_without_top10_R']}R | "
                    f"{P['avg_pct']}% | {P['profit_factor']} | {P['avg_days']} | ${A['final_equity']} ({A['return_pct']:+}%) | {A['max_drawdown_pct']}% |")
    years = ['', '## Expectancy by year (R per trade)', ''] + [f"- {v['name']}: " + ', '.join(f"{y}: {x['expectancy_R']}R ({x['trades']})" for y, x in v['per_trade'].get('by_year', {}).items())
                                                              for v in out['strategies'].values()]
    md = [f"# VANTEX City swing-strategy research - {split} - {start_s} to {end_s}", '',
          f"{nsym} stocks with data. Signal at the close, buy the next open, costs 0.05%-0.50% per side by liquidity plus fees. "
          f"Buy-and-hold SPY over the same period: {spy_ret:+}%." if spy_ret is not None else '', ''] + rows + years + ['',
          'Survivorship bias: today\'s stock list only, so stocks that were delisted (often after collapsing) are missing. That flatters buy strategies.',
          '"Without top 10" removes the 10 best trades, to show whether a few lucky trades carry the result.', 'A backtest is not proof.']
    publish({})
    publish({f'swing_{split}.json': out, f'swing_{split}.md': '\n'.join(md) + '\n'})

if __name__ == '__main__':
    main()
