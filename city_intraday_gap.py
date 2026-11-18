"""
VANTEX City research: ChatGPT's ideas #4 and #5 (2026-11-17), tested on 1-minute bars. Research only: places NO orders.

Both wait for the gap to SHOW its hand after the open instead of buying the open blindly (which loses: news_study.md).
  G4 gap-up survivor (long)   gap 4-15%, price >= $5, $20M+/day. After 10:00 (first 30 min done): first 1-min close above the
                              first-30-minute high AND above VWAP, with first-30-minute volume >= 1.5x normal for that half hour
                              (normal = the stock's 20-day average daily volume x the City's intraday volume curve; ChatGPT asked for
                              the same-interval 20-session median, which needs 20x more minute data: a stated substitution).
                              Buy the next minute's open. Exit 15:45, or the minute after a 1-min close below max(VWAP, 30-min low).
                              No new entries after 15:00.
  G5 failed opening range (short)  gap 4-20%, price >= $5, $50M+/day, shortable + easy to borrow (Alpaca's flag TODAY).
                              From 9:45 to 11:30: first 1-min close below the first-15-minute low AND below VWAP. Short the next
                              minute's open. Cover 15:45, or the minute after a 1-min close above the first-15-minute high.
  G5L mirror check (long)     the same gap list, first 1-min close ABOVE the 15-minute high and above VWAP (9:45-11:30), long,
                              exit 15:45 or a close below the 15-minute low. Shown only for comparison.
Entries/exits fill at the NEXT minute's open + costs by liquidity (0.05-0.10% per side here) + 0.02% extra slippage.
Short results assume ETB borrow is free (Alpaca ETB) and ignore that today's ETB flag may differ from the past.
Dev = Jun 2023 - Dec 2025, test = 2026. Settings above are ChatGPT's, used as given.

  python city_intraday_gap.py   -> live-replay/intraday_gap.md / .json / intraday_gap_trades.csv
"""
import csv, io, json, os, sys, time
from collections import defaultdict
from datetime import date, datetime, timedelta

import vantex_core as V
from city_engine import Data, to_bar
from city_replay import ET, log, publish
from city_overnight import universe
from city_news_study import load_ohlcv
from city_model import short_flags
from city_swing import cost_pct

SLIP = 0.0002
DEV_END = '2025-12-31'

def vwap_path(bars):
    out, pv, vv = [], 0.0, 0.0
    for b in bars:
        pv += (b.h + b.l + b.c) / 3 * b.v; vv += b.v; out.append(pv / vv if vv else b.c)
    return out

def first_window(bars, minutes):
    w = [b for b in bars if b.m < 570 + minutes]
    if not w or w[0].m > 572: return None
    return max(b.h for b in w), min(b.l for b in w), sum(b.v for b in w)

def run_trade(bars, k_sig, side, stop_fn, last_m=945):
    """enter at bars[k_sig+1].o; exit at the open of the minute after a stop close, or at the 15:45 bar close.
    Returns (entry, exit, minute_in, minute_out, how) or None."""
    if k_sig + 1 >= len(bars): return None
    ent = bars[k_sig + 1].o; vw = vwap_path(bars)
    for k in range(k_sig + 1, len(bars)):
        b = bars[k]
        if b.m >= last_m: return ent, b.c, bars[k_sig + 1].m, b.m, 'time 15:45'
        if stop_fn(b, vw[k]):
            if k + 1 < len(bars): return ent, bars[k + 1].o, bars[k_sig + 1].m, bars[k + 1].m, 'stop'
            return ent, b.c, bars[k_sig + 1].m, b.m, 'stop'
    return ent, bars[-1].c, bars[k_sig + 1].m, bars[-1].m, 'last bar'

def g4(bars, adv_sh):
    fw = first_window(bars, 30)
    if not fw: return None
    hi, lo, v30 = fw; expect = (V.default_curve(600) - V.default_curve(570)) * adv_sh
    if expect <= 0 or v30 < 1.5 * expect: return None
    vw = vwap_path(bars)
    for k, b in enumerate(bars):
        if b.m < 600: continue
        if b.m >= 900: return None
        if b.c > hi and b.c > vw[k]:
            return run_trade(bars, k, 'long', lambda x, v: x.c < max(v, lo))
    return None

def g5(bars, side='short'):
    fw = first_window(bars, 15)
    if not fw: return None
    hi, lo, _ = fw; vw = vwap_path(bars)
    for k, b in enumerate(bars):
        if b.m < 585: continue
        if b.m >= 690: return None
        if side == 'short' and b.c < lo and b.c < vw[k]: return run_trade(bars, k, 'short', lambda x, v: x.c > hi)
        if side == 'long' and b.c > hi and b.c > vw[k]: return run_trade(bars, k, 'long', lambda x, v: x.c < lo)
    return None

def ret(side, ent, ext, c):
    if side == 'long': return ext * (1 - c) / (ent * (1 + c)) - 1
    return (ent * (1 - c) - ext * (1 + c)) / ent

def stats(rs):
    if not rs: return dict(n=0)
    n = len(rs); mu = sum(rs) / n; sd = (sum((x - mu) ** 2 for x in rs) / max(1, n - 1)) ** 0.5; srt = sorted(rs)
    g = sum(x for x in rs if x > 0); l = -sum(x for x in rs if x < 0); wo = srt[:-5] if n > 10 else srt
    return dict(n=n, win_pct=round(100 * sum(x > 0 for x in rs) / n, 1), avg_pct=round(100 * mu, 3), median_pct=round(100 * srt[n // 2], 3),
                pf=round(g / l, 2) if l else None, t=round(mu / (sd / n ** 0.5), 2) if sd else None, avg_wo_best5_pct=round(100 * sum(wo) / len(wo), 3))

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    D = Data(key, sec); uni = universe(key, sec); flags = short_flags(key, sec)
    s0 = datetime(2023, 4, 1, tzinfo=ET); s1 = datetime.now(ET) - timedelta(minutes=20)
    stocks = load_ohlcv(D, sorted(uni), s0, s1); log('stocks', len(stocks))
    cands = defaultdict(list)                                              # day -> [(sym, gap, adv$, adv shares)]
    for s, S in stocks.items():
        for i in range(21, len(S['d'])):
            d = S['d'][i]
            if d < '2023-06-01' or S['c'][i - 1] < 5 or S['c'][i - 1] <= 0: continue
            gap = S['o'][i] / S['c'][i - 1] - 1
            if not (0.04 <= gap < 0.20): continue
            adv = sum(S['c'][j] * S['v'][j] for j in range(i - 20, i)) / 20
            if adv < 20e6: continue
            cands[d].append((s, gap, adv, sum(S['v'][i - 20:i]) / 20))
    log('candidate days', len(cands), 'stock-days', sum(len(v) for v in cands.values()))
    trades = []; t0 = time.time()
    for n, (d, L) in enumerate(sorted(cands.items())):
        a = datetime.combine(date.fromisoformat(d), datetime.min.time(), ET) + timedelta(hours=9, minutes=30)
        M = D.bars([x[0] for x in L], '1Min', a, a + timedelta(hours=6, minutes=30), 'sip', 'raw')
        for s, gap, adv, adv_sh in L:
            bars = sorted((b for b in map(to_bar, M.get(s, [])) if 570 <= b.m < 960), key=lambda b: b.t)
            if len(bars) < 300: continue
            c = cost_pct(adv) + SLIP; sp = 'dev' if d <= DEV_END else 'test'
            tests = []
            if gap < 0.15: tests.append(('G4 gap-up survivor (long)', 'long', g4(bars, adv_sh)))
            if adv >= 50e6 and flags.get(s) == (True, True): tests.append(('G5 failed opening range (short, ETB)', 'short', g5(bars, 'short')))
            if adv >= 50e6: tests.append(('G5L mirror: opening range breakout (long)', 'long', g5(bars, 'long')))
            for name, side, r in tests:
                if not r: continue
                ent, ext, mi, mo, how = r
                trades.append(dict(rule=name, split=sp, day=d, sym=s, gap=round(gap * 100, 1), entry=ent, exit=ext, m_in=mi, m_out=mo, how=how,
                                   net=ret(side, ent, ext, c), net2=ret(side, ent, ext, 2 * c)))
        if n % 100 == 0: log(n, 'days', len(trades), 'trades', round(time.time() - t0), 's')
    res = {}; rows = ['| rule | period | trades | win rate | avg net | median | avg w/o best 5 | profit factor | t-stat | avg at 2x costs |', '|---|---|---|---|---|---|---|---|---|---|']
    for name in sorted({t['rule'] for t in trades}):
        for sp in ('dev', 'test'):
            T = [t for t in trades if t['rule'] == name and t['split'] == sp]; S1 = stats([t['net'] for t in T]); S2 = stats([t['net2'] for t in T])
            res[f'{name} | {sp}'] = dict(S1, avg_2x_pct=S2.get('avg_pct'))
            if S1['n']: rows.append(f"| {name} | {sp} | {S1['n']} | {S1['win_pct']}% | {S1['avg_pct']}% | {S1['median_pct']}% | {S1['avg_wo_best5_pct']}% | {S1['pf']} | {S1['t']} | {S2['avg_pct']}% |")
    yr = ['| rule | year | trades | win rate | avg net |', '|---|---|---|---|---|']
    for name in sorted({t['rule'] for t in trades}):
        for y in sorted({t['day'][:4] for t in trades}):
            T = [t['net'] for t in trades if t['rule'] == name and t['day'][:4] == y]
            if T: S1 = stats(T); yr.append(f"| {name} | {y} | {S1['n']} | {S1['win_pct']}% | {S1['avg_pct']}% |")
    md = ['# VANTEX City research: ChatGPT ideas #4 and #5 on 1-minute bars', '',
          'Wait for the gap to prove itself after the open, then trade the next minute. Costs included. Dev = Jun 2023 - Dec 2025, test = 2026.', ''] + rows + [
          '', '## By year', ''] + yr + ['', 'G4 volume check uses the City volume curve x 20-day average volume (substitution, see file header). '
          'Shorts assume Alpaca easy-to-borrow (free) using TODAY\'s flags. Historical SIP minute bars; the live free feed is 15 minutes delayed '
          '(IEX real-time only), so a live version would need the $99/month real-time plan or IEX bars. A backtest is not proof.']
    buf = io.StringIO(); w = csv.writer(buf); cols = ['rule', 'split', 'day', 'sym', 'gap', 'entry', 'exit', 'm_in', 'm_out', 'how', 'net']
    w.writerow(cols)
    for t in trades: w.writerow([round(t[c] * 100, 3) if c == 'net' else t[c] for c in cols])
    publish({}); publish({'intraday_gap.md': '\n'.join(md) + '\n', 'intraday_gap.json': res, 'intraday_gap_trades.csv': buf.getvalue()})
    log('done', len(trades))

if __name__ == '__main__':
    main()
