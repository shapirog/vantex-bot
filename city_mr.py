"""
VANTEX City research batch 3: is the RSI(2) pullback edge real, or one lucky setting? Research only: places NO orders.

Batch 2 found one family that made money after costs in every year: buying very liquid stocks ($50M+ a day) in an uptrend
after a sharp 2-day dip (RSI(2) very low), while SPY is above its 200-day line, and selling into the bounce.
A real edge should survive nearby settings. This sweeps the neighbours instead of picking the best one:
  entry   RSI(2) under 5 / 10 / 15
  exit    RSI(2) back above 50 / above 70 / close above the 5-day average   (max 10 days)
  stop    3 x ATR below the entry / no stop (10 x ATR, a disaster stop only)
  market  SPY above its 200-day line required / not required
= 36 settings, all reported. Then account sizing for the published setting (RSI2<5, exit >70, 3-ATR stop, market filter):
1% or 2% risk per trade, 5 or 10 positions, $2,500 cash, no margin.

  python city_mr.py dev    -> 2023-06 .. 2025-12  -> live-replay/mr_dev.md / .json
  python city_mr.py test   -> 2026 (untouched: run once, only for the setting chosen on dev)
"""
import itertools, json, math, os, re, sys, time
from collections import defaultdict
from datetime import date, datetime, timedelta

import requests

from city_engine import Data, NAME_EXCLUDE
from city_replay import ET, TRADE, log, publish
from city_swing import SPLITS, WARMUP_DAYS, cost_pct, indicators, per_trade_stats, portfolio
from city_research import market_ok, sim

ENTRY = (5, 10, 15)
EXIT = ('rsi>50', 'rsi>70', 'sma5')
STOP = (3, 10)
MKT = (True, False)
CHOSEN = (5, 'rsi>70', 3, True)                                     # the published Connors setting, fixed before looking at results
SIZING = [dict(risk_pct=1.0, max_pos=5, max_pos_pct=25.0), dict(risk_pct=2.0, max_pos=5, max_pos_pct=25.0),
          dict(risk_pct=1.0, max_pos=10, max_pos_pct=15.0), dict(risk_pct=2.0, max_pos=10, max_pos_pct=15.0)]

def exit_fn(rule, B, I):
    if rule == 'rsi>50': return lambda j: I[j] is not None and I[j]['rsi2'] is not None and I[j]['rsi2'] > 50
    if rule == 'rsi>70': return lambda j: I[j] is not None and I[j]['rsi2'] is not None and I[j]['rsi2'] > 70
    return lambda j: I[j] is not None and I[j]['sma5'] is not None and B[j][4] > I[j]['sma5']

def stock_trades(sym, B, I, mkt, start, end):
    """every setting's trades for one stock"""
    out = defaultdict(list)
    fns = {r: exit_fn(r, B, I) for r in EXIT}
    for i in range(22, len(B) - 1):
        d = B[i][0]
        if d < start or d > end or I[i] is None: continue
        x = I[i]; px = B[i][4]; r2 = x['rsi2']
        if px < 5 or x['adv'] < 50e6 or r2 is None or r2 >= max(ENTRY): continue
        m200 = x['sma200']()
        if not (m200 and px > m200): continue
        cp = cost_pct(x['adv'])
        for e, ex, st, mk in itertools.product(ENTRY, EXIT, STOP, MKT):
            if r2 >= e or (mk and not mkt.get(d)): continue
            t = sim(B, I, i, B[i + 1][1] - st * x['atr'], fns[ex], 10, cp)
            if t: out[(e, ex, st, mk)].append(dict(t, sym=sym, rank=-r2))
    return out

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
    s1 = min(datetime.combine(b + timedelta(days=30), datetime.min.time(), ET), datetime.now(ET) - timedelta(days=1))
    def load(chunk):
        return {s: [(x['t'][:10], x['o'], x['h'], x['l'], x['c'], x['v']) for x in L] for s, L in D.bars(chunk, '1Day', s0, s1, 'sip', 'all').items()}
    spyB = load(['SPY'])['SPY']; mkt = market_ok(spyB, indicators(spyB))
    T = defaultdict(list); t0 = time.time()
    for k in range(0, len(syms), 100):
        for s, B in load(syms[k:k + 100]).items():
            if len(B) < 60: continue
            for key_, L in stock_trades(s, B, indicators(B), mkt, start, end).items(): T[key_] += L
        if k % 1000 == 0: log(k, 'settings with trades', len(T), round(time.time() - t0), 's')
    spy = [x for x in spyB if start <= x[0] <= end]
    spy_ret = round((spy[-1][4] / spy[0][1] - 1) * 100, 1) if spy else None
    grid = []
    for key_ in itertools.product(ENTRY, EXIT, STOP, MKT):
        P = per_trade_stats(T[key_]); grid.append(dict(entry=key_[0], exit=key_[1], stop_atr=key_[2], market_filter=key_[3], **{k: P.get(k) for k in
                    ('trades', 'win_rate_pct', 'avg_pct', 'expectancy_R', 'expectancy_without_top10_R', 'profit_factor', 'avg_days')},
                    years={y: v['expectancy_R'] for y, v in P.get('by_year', {}).items()}))
    chosen = T[CHOSEN]
    accounts = [dict(sz, **portfolio(chosen, **sz)) for sz in SIZING]
    pos = sum(1 for g in grid if (g['avg_pct'] or 0) > 0); allyears = sum(1 for g in grid if g['years'] and all(v > 0 for y, v in g['years'].items() if y <= end[:4]))
    out = dict(split=split, period=[start, end], spy_buy_hold_pct=spy_ret, chosen=list(CHOSEN), grid=grid, accounts=accounts,
               chosen_stats=per_trade_stats(chosen), chosen_sample=sorted(chosen, key=lambda t: t['entry_day'])[-40:],
               updated=datetime.now(ET).isoformat(timespec='seconds'))
    rows = ['| entry RSI(2) < | exit | stop | SPY filter | trades | win rate | avg return/trade | without top 10 | profit factor | by year (R/trade) |', '|---|---|---|---|---|---|---|---|---|---|']
    for g in grid:
        rows.append(f"| {g['entry']} | {g['exit']} | {g['stop_atr']} ATR | {'yes' if g['market_filter'] else 'no'} | {g['trades']} | {g['win_rate_pct']}% | {g['avg_pct']}% | "
                    f"{g['expectancy_without_top10_R']}R | {g['profit_factor']} | {', '.join(f'{y}: {v}' for y, v in g['years'].items())} |")
    acc = ['| risk per trade | max positions | final | return | max drawdown | trades taken |', '|---|---|---|---|---|---|'] + \
          [f"| {x['risk_pct']}% | {x['max_pos']} | ${x['final_equity']} | {x['return_pct']:+}% | {x['max_drawdown_pct']}% | {x['trades_taken']} |" for x in accounts]
    md = [f"# VANTEX City research batch 3: RSI(2) pullback robustness - {split} - {start} to {end}", '',
          f"Buy-and-hold SPY: {spy_ret:+}%. Liquid stocks only ($50M+ a day), above their 200-day line. Costs 0.05%-0.10% per side plus fees.",
          f"**{pos} of {len(grid)} settings made money per trade after costs; {allyears} were positive in every year.**", ''] + rows + ['',
          f"## $2,500 cash account, published setting (RSI(2) < {CHOSEN[0]}, exit {CHOSEN[1]}, {CHOSEN[2]}-ATR stop, SPY filter)", ''] + acc + ['',
          'Survivorship bias: today\'s stock list only (small for $50M+/day stocks, not zero). A backtest is not proof.']
    publish({})
    publish({f'mr_{split}.json': out, f'mr_{split}.md': '\n'.join(md) + '\n'})

if __name__ == '__main__':
    main()
