"""
VANTEX City research: RANGE TRADING (buy near the bottom of a repeating range, sell near the top). Research only: no orders.

Guillo's idea (2026-11-19): some stocks bounce between a high and a low again and again (e.g. 140 <-> 150). Find them, buy near
the low, sell near the high. Rules fixed before running:
  universe  US stocks (active + delisted) with price >= $5 and 20-day average dollar volume >= $20M
  range     the last 20 sessions (about a month, ending YESTERDAY): top H = highest high, bottom L = lowest low.
            Counts as a range when: the range is 6%-25% wide, price came within 2% of the top on >= 2 days AND within 2% of
            the bottom on >= 2 days (it really bounced), and the stock is not trending (net move over the 20 days is less
            than half the range).
  buy       a limit order at L + 1% placed before the open. Filled if today's low reaches it (at the open if it opens
            below, unless it opens under the stop). One trade per stock at a time.
  sell      target H - 2% (near the top), stop L - 3% (the range broke). Three holding limits, reported separately:
              DAY    sell at today's close at the latest (day trade; a same-day target is not counted, daily bars can't
                     show which came first, so only the stop is checked: conservative)
              WEEK   up to 5 sessions          MONTH  up to 21 sessions
  control   same stocks and range days, but buying at the OPEN on any range day, wherever the price is (is buying at
            the bottom what makes the money?)
  costs     0.05%-0.10% per side by liquidity.
Dev = 2019-2024, test = 2025-now. Results per trade, per week and per month ($250 per trade, like a $2,500 account in 10 slots).
Also lists the stocks in a range right now.

  python city_range.py   -> live-replay/range.md / .json / range_now.json
"""
import json, os, random, sys
from collections import defaultdict
from datetime import date, datetime, timedelta

from city_engine import Data
from city_replay import ET, log, publish
from city_overnight import universe
from city_news_study import load_ohlcv
from city_swing import cost_pct

N, MIN_W, MAX_W, TOUCH, BUY_UP, TGT_DN, STOP_DN = 20, 0.06, 0.25, 0.02, 0.01, 0.02, 0.03
HOLD = {'DAY': 1, 'WEEK': 5, 'MONTH': 21}
STAKE = 250.0

def range_at(S, i):
    """range state for day i from the 20 sessions BEFORE day i (no look-ahead). dict or None."""
    if i < N + 1: return None
    h, l, c, v = S['h'][i - N:i], S['l'][i - N:i], S['c'][i - N:i], S['v'][i - N:i]
    H, L = max(h), min(l)
    if L <= 0 or c[-1] < 5: return None
    adv = sum(x * y for x, y in zip(c, v)) / N
    if adv < 20e6: return None
    w = H / L - 1
    if not (MIN_W <= w <= MAX_W): return None
    top = sum(1 for x in h if x >= H * (1 - TOUCH)); bot = sum(1 for x in l if x <= L * (1 + TOUCH))
    if top < 2 or bot < 2: return None
    if abs(c[-1] - S['c'][i - N - 1]) > 0.5 * (H - L): return None
    return dict(H=H, L=L, width=w, adv=adv, top_touches=top, bottom_touches=bot, last=c[-1])

def trade(S, i, R, hold, at_open=False):
    """returns (entry, exit, exit index, how) or None if not filled / not finished"""
    o, h, l, c = S['o'], S['h'], S['l'], S['c']
    buy = R['L'] * (1 + BUY_UP); stop = R['L'] * (1 - STOP_DN); tgt = R['H'] * (1 - TGT_DN)
    if at_open: ent = o[i]
    else:
        if o[i] <= stop or l[i] > buy: return None
        ent = min(o[i], buy)
    if ent >= tgt: return None
    last = min(i + hold, len(c)) - 1
    if last < i + hold - 1: return None                                         # not enough data yet
    for j in range(i, last + 1):
        if j > i and o[j] <= stop: return ent, o[j], j, 'stop (gap)'
        if l[j] <= stop and (j > i or at_open or ent > stop): return ent, stop, j, 'stop'
        if j > i and o[j] >= tgt: return ent, o[j], j, 'target (gap)'
        if j > i and h[j] >= tgt: return ent, tgt, j, 'target'
        if at_open and j == i and h[j] >= tgt and l[j] > stop: return ent, tgt, j, 'target'
    return ent, c[last], last, 'time'

def stats(rs):
    if not rs: return dict(n=0)
    n = len(rs); mu = sum(rs) / n; sd = (sum((x - mu) ** 2 for x in rs) / max(1, n - 1)) ** 0.5; srt = sorted(rs)
    g = sum(x for x in rs if x > 0); lo = -sum(x for x in rs if x < 0)
    return dict(n=n, win_pct=round(100 * sum(x > 0 for x in rs) / n, 1), avg_pct=round(100 * mu, 3), median_pct=round(100 * srt[n // 2], 3),
                pf=round(g / lo, 2) if lo else None, t=round(mu / (sd / n ** 0.5), 2) if sd else None)

def periods(trades, key):
    """dollar P&L per calendar week / month at $250 per trade, on exit date"""
    by = defaultdict(float)
    for t in trades:
        d = date.fromisoformat(t['exit_day'])
        k = f'{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}' if key == 'week' else t['exit_day'][:7]
        by[k] += STAKE * t['net']
    xs = list(by.values())
    if not xs: return dict(n=0)
    return dict(n=len(xs), avg_usd=round(sum(xs) / len(xs), 2), up_pct=round(100 * sum(x > 0 for x in xs) / len(xs), 1),
                worst_usd=round(min(xs), 2), best_usd=round(max(xs), 2))

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    D = Data(key, sec); uni = universe(key, sec)
    s0 = datetime(2018, 10, 1, tzinfo=ET); s1 = datetime.now(ET) - timedelta(minutes=20)
    stocks = load_ohlcv(D, sorted(uni), s0, s1); log('stocks', len(stocks))
    rng = random.Random(3); trades = []; now_list = []
    for s, S in stocks.items():
        busy = {lab: -1 for lab in list(HOLD) + ['CONTROL ' + x for x in HOLD]}
        for i in range(N + 1, len(S['d'])):
            if S['d'][i] < '2019-01-01': continue
            R = range_at(S, i)
            if not R: continue
            sp = 'dev' if S['d'][i] < '2025-01-01' else 'test'; c = cost_pct(R['adv'])
            for lab, hold in HOLD.items():
                if i > busy[lab]:
                    r = trade(S, i, R, hold)
                    if r:
                        ent, ext, j, how = r; busy[lab] = j
                        trades.append(dict(rule=lab, sym=s, day=S['d'][i], exit_day=S['d'][j], net=ext * (1 - c) / (ent * (1 + c)) - 1, how=how, split=sp, width=R['width']))
                cl = 'CONTROL ' + lab
                if i > busy[cl] and rng.random() < 0.15:
                    r = trade(S, i, R, hold, at_open=True)
                    if r:
                        ent, ext, j, how = r; busy[cl] = j
                        trades.append(dict(rule=cl, sym=s, day=S['d'][i], exit_day=S['d'][j], net=ext * (1 - c) / (ent * (1 + c)) - 1, how=how, split=sp, width=R['width']))
        R = range_at(dict(S, h=S['h'] + [0], l=S['l'] + [1e9], c=S['c'] + [0], v=S['v'] + [0]), len(S['d']))   # range as of the last close
        if R and S['d'][-1] >= (datetime.now(ET).date() - timedelta(days=5)).isoformat():
            now_list.append(dict(sym=s, low=round(R['L'], 2), high=round(R['H'], 2), width_pct=round(100 * R['width'], 1), last=round(R['last'], 2),
                                 buy_at=round(R['L'] * (1 + BUY_UP), 2), target=round(R['H'] * (1 - TGT_DN), 2), stop=round(R['L'] * (1 - STOP_DN), 2),
                                 pos_in_range_pct=round(100 * (R['last'] - R['L']) / (R['H'] - R['L']), 0)))
    res = {}; rows = ['| rule | period | trades | win rate | avg per trade | median | profit factor | t-stat | avg week ($250/trade) | weeks up | avg month | months up | worst month |',
                      '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for lab in list(HOLD) + ['CONTROL ' + x for x in HOLD]:
        for sp in ('dev', 'test'):
            T = [t for t in trades if t['rule'] == lab and t['split'] == sp]
            if not T: continue
            S1 = stats([t['net'] for t in T]); W = periods(T, 'week'); M = periods(T, 'month')
            res[f'{lab} | {sp}'] = dict(S1, week=W, month=M, how={h: sum(1 for t in T if t['how'] == h) for h in {t['how'] for t in T}})
            rows.append(f"| {lab} | {sp} | {S1['n']} | {S1['win_pct']}% | {S1['avg_pct']:+}% | {S1['median_pct']:+}% | {S1['pf']} | {S1['t']} | ${W['avg_usd']:+,.0f} | {W['up_pct']}% | "
                        f"${M['avg_usd']:+,.0f} | {M['up_pct']}% | ${M['worst_usd']:+,.0f} |")
    now_list.sort(key=lambda x: x['pos_in_range_pct'])
    md = ['# VANTEX City research: range trading (buy the bottom of a repeating range, sell the top)', '',
          'Range = last 20 sessions, 6-25% wide, at least 2 touches of the top and of the bottom, not trending. Buy limit at bottom + 1%, target top - 2%, stop bottom - 3%. '
          'Dollar columns assume $250 per trade (every signal taken, so busy weeks have many trades). CONTROL = buy at the open on a random range day instead of at the bottom. '
          'Dev = 2019-2024, test = 2025-now.', ''] + rows + ['', f'Stocks in a range right now: {len(now_list)} (see range_now.json, nearest the bottom first).', '',
          'Daily bars: a day-trade target cannot be checked against the entry inside one day, so the DAY rule only exits at the stop or the close. A backtest is not proof.']
    publish({}); publish({'range.md': '\n'.join(md) + '\n', 'range.json': res, 'range_now.json': now_list[:200]})
    log('done', len(trades))

if __name__ == '__main__':
    main()
