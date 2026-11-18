"""
VANTEX City research: NEWS + VOLUME study. Research only: places NO orders.

Question (Guillo, 2026-11-17): catch the stocks that are going up, listen to the news, look for volume, trade accordingly.
What this does, on every US stock (active + delisted, penny stocks included) from June 2026 (first month Alpaca has news):
  1. Pulls every Alpaca news item, files it under the trading session it can first affect:
       published before 9:30 ET  -> "pre-open" news for that day      (tradable at that day's open)
       published 9:30-16:00      -> "intraday" news for that day     (tradable at the next open)
       after 16:00 / weekend     -> "pre-open" news for the next trading day
     Only items tagged with 1-2 symbols (roundups and listicles dropped), classified with the City's own classifier.
  2. Event study: for gap buckets, compares stocks WITH good news vs negative news vs NO news at all (the control).
  3. Fixed trading rules, chosen before running (published / widely used momentum-trader setups), long only:
       N1 news gap-and-go       pre-open good news + gap >= 4%: buy the open, sell the close
       N1s same, with a 7% stop and 15% target (if both are touched the same day we assume the stop: conservative)
       C1 control: gap-and-go   same gap, NO news in the last 3 days (is it the news, or just the gap?)
       N2 day-2 continuation    N1 stocks that closed in the top 25% of the day's range on >= 3x volume: buy next open, sell next close
       N3 episodic pivot        good news + gap >= 10% + volume >= 3x + closed above its open: buy next open, stop at the
                                pivot day's low, sell after 10 sessions (Kullamagi-style "EP", simplified to daily bars)
       N4 post-earnings drift   earnings news + gap >= 3% + closed above its open: buy next open, hold 20 sessions
       N5 intraday news next day  good news during the session + up >= 5% close-to-close on >= 2x volume: buy next open, sell next close
       C2 control: volume spike  up >= 5% on >= 5x volume with NO news: buy next open, sell next close
     Entries at the open of the day the signal is known (only data up to that moment). Day-D volume is only used for
     next-day entries. Costs by liquidity per side (0.05%-0.5%, +1% under $1) and a 2x-cost check.
  Development = Jun-Sep 2026, test = Oct 2026 to now. Both are reported; nothing is tuned between them.
Data limits: Alpaca's news feed covers only some movers (it misses many penny-stock press releases); daily bars only, so
same-day stop/target order is unknown (assumed stop first); open prices are the official open (a real order at 9:30 can
fill worse); delisted names that stop trading exit at their last close.

  python city_news_study.py   -> live-replay/news_study.md / .json / news_study_trades.csv
"""
import bisect, csv, io, json, math, os, random, sys, time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

import vantex_core as V
from city_engine import Data
from city_replay import ET, log, publish            # importing city_replay also adds Data.news_range
from city_overnight import universe
from city_swing import cost_pct

START = date(2026, 6, 1); DEV_END = '2026-09-30'
MIN_PX, MIN_ADV = 0.50, 1e6
GAP_BUCKETS = [(-1, -0.10), (-0.10, -0.04), (-0.04, 0.0), (0.0, 0.04), (0.04, 0.10), (0.10, 0.20), (0.20, 99)]

# ------------------------------------------------------------------ pure helpers (tested)
def cost(adv, px):
    return cost_pct(adv) + (0.01 if px < 1 else 0.0)

def session_for(ts_et, cal):
    """(trading day, 'pre' | 'intra') for a news timestamp; cal = sorted list of ISO trading days"""
    d = ts_et.date().isoformat(); hm = ts_et.hour * 60 + ts_et.minute
    k = bisect.bisect_left(cal, d)
    if k < len(cal) and cal[k] == d:
        if hm < 570: return d, 'pre'
        if hm < 960: return d, 'intra'
        k += 1
    return (cal[k], 'pre') if k < len(cal) else (None, None)

def good(n):
    return bool(n['types']) and not n['negative'] and n['confidence'] != 'low' and not n['roundup']

def feats(S, i):
    """day-i numbers. adv / avg volume use the 20 sessions BEFORE day i (known at the open)."""
    if i < 21: return None
    o, h, l, c, v = S['o'], S['h'], S['l'], S['c'], S['v']
    avgv = sum(v[i - 20:i]) / 20
    if c[i - 1] <= 0 or o[i] <= 0 or avgv <= 0: return None
    return dict(gap=o[i] / c[i - 1] - 1, oc=c[i] / o[i] - 1, cc=c[i] / c[i - 1] - 1, rvol=v[i] / avgv,
                adv=sum(c[j] * v[j] for j in range(i - 20, i)) / 20, px=c[i - 1],
                rng=(c[i] - l[i]) / (h[i] - l[i]) if h[i] > l[i] else 0.5)

def hold(S, i_in, n_days, stop=None, target=None, last_cal=None):
    """buy at the open of day i_in; exit at a stop / target or at the close of day i_in + n_days - 1.
    A gap through the stop (target) fills at the open; if both are touched in one day, the stop wins.
    Returns (exit_price, exit_index, how) or None if the trade is still running at the end of the data."""
    n = len(S['d']); last = None
    for k in range(i_in, min(i_in + n_days, n)):
        o, h, l, c = S['o'][k], S['h'][k], S['l'][k], S['c'][k]
        if stop is not None and o <= stop: return o, k, 'stop (gap)'
        if target is not None and k > i_in and o >= target: return o, k, 'target (gap)'
        if stop is not None and l <= stop: return stop, k, 'stop'
        if target is not None and h >= target: return target, k, 'target'
        last = k
    if last is None: return None
    if last == i_in + n_days - 1: return S['c'][last], last, 'time'
    if last_cal and S['d'][last] >= last_cal: return None                  # still open at the end of the data
    return S['c'][last], last, 'last close (stopped trading)'

def net(buy, sell, c): return sell * (1 - c) / (buy * (1 + c)) - 1

def stats(rs):
    if not rs: return dict(n=0)
    n = len(rs); mu = sum(rs) / n; sd = (sum((x - mu) ** 2 for x in rs) / max(1, n - 1)) ** 0.5
    srt = sorted(rs); med = srt[n // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
    gains = sum(x for x in rs if x > 0); losses = -sum(x for x in rs if x < 0)
    wo = srt[:-5] if n > 10 else srt
    return dict(n=n, avg_pct=round(mu * 100, 3), median_pct=round(med * 100, 3), win_pct=round(100 * sum(x > 0 for x in rs) / n, 1),
                profit_factor=round(gains / losses, 2) if losses else None, t=round(mu / (sd / n ** 0.5), 2) if sd and n > 1 else None,
                avg_without_best5_pct=round(sum(wo) / len(wo) * 100, 3))

def bucket(g):
    for a, b in GAP_BUCKETS:
        if a <= g < b: return f'{a * 100:+.0f}%..{b * 100:+.0f}%' if b < 99 else f'>= {a * 100:+.0f}%'
    return None

# ------------------------------------------------------------------ the study
def run(stocks, cal, newsmap, start, last_cal):
    """newsmap: (sym, day) -> dict(pre=[classified], intra=[classified]). Returns (trades, event rows)."""
    trades = []; ev = defaultdict(list); cover = Counter()
    def add(rule, s, S, d_sig, i_in, n_days, f, stop=None, target=None, note=''):
        if i_in >= len(S['d']): return
        r = hold(S, i_in, n_days, stop, target, last_cal)
        if r is None: return
        px_out, k, how = r; b = S['o'][i_in]; c = cost(f['adv'], f['px'])
        trades.append(dict(rule=rule, sym=s, signal_day=d_sig, buy_day=S['d'][i_in], sell_day=S['d'][k], buy=round(b, 4), sell=round(px_out, 4),
                           net=net(b, px_out, c), net2=net(b, px_out, 2 * c), gross=px_out / b - 1, how=how, price=round(f['px'], 2), gap=round(f['gap'] * 100, 1),
                           rvol=round(f['rvol'], 1), note=note, split='dev' if d_sig <= DEV_END else 'test'))
    for s, S in stocks.items():
        ds = S['d']
        recent = set()                                                     # days with any news for this symbol
        for i, d in enumerate(ds):
            if (s, d) in newsmap: recent.add(i)
        for i in range(21, len(ds)):
            d = ds[i]
            if d < start.isoformat(): continue
            f = feats(S, i)
            if not f or f['px'] < MIN_PX or f['adv'] < MIN_ADV: continue
            nm = newsmap.get((s, d), {}); pre = nm.get('pre', []); intra = nm.get('intra', [])
            pre_good = [n for n in pre if good(n)]; pre_neg = [n for n in pre if n['negative']]
            no_news = not any(j in recent for j in range(i - 3, i + 1))
            split = 'dev' if d <= DEV_END else 'test'
            kind = 'good news' if pre_good else 'negative news' if pre_neg else 'no news' if no_news else None
            bk = bucket(f['gap'])
            if kind and bk: ev[(split, kind, bk)].append((f['oc'], f['cc']))
            if f['gap'] >= 0.10:
                cover[(split, 'gap >= 10%')] += 1
                if pre: cover[(split, 'gap >= 10% with pre-open news')] += 1
            if pre_good:
                typ = pre_good[0]['types'][0]
                five = S['c'][min(i + 4, len(ds) - 1)] / S['o'][i] - 1 if i + 4 < len(ds) else None
                ev[(split, 'type', typ)].append((f['oc'], f['gap'], five))
            # ---- rules
            if pre_good and f['gap'] >= 0.04:
                note = pre_good[0]['types'][0]
                add('N1 news gap-and-go (open->close)', s, S, d, i, 1, f, note=note)
                add('N1s news gap-and-go, 7% stop / 15% target', s, S, d, i, 1, f, stop=S['o'][i] * 0.93, target=S['o'][i] * 1.15, note=note)
                if f['rng'] >= 0.75 and f['rvol'] >= 3: add('N2 day-2 continuation (next open->close)', s, S, d, i + 1, 1, f, note=note)
            if no_news and f['gap'] >= 0.04:
                add('C1 control: gap >= 4%, no news (open->close)', s, S, d, i, 1, f)
            if (pre_good or (s, ds[i - 1]) in newsmap and any(good(n) for n in newsmap[(s, ds[i - 1])].get('intra', []))) and f['gap'] >= 0.10 and f['rvol'] >= 3 and S['c'][i] > S['o'][i] and f['px'] >= 1:
                add('N3 episodic pivot (stop at pivot low, 10 days)', s, S, d, i + 1, 10, f, stop=S['l'][i], note=(pre_good or [{'types': ['prior-day']}])[0]['types'][0])
            if any('EARNINGS' in n['types'] for n in pre) and f['gap'] >= 0.03 and S['c'][i] > S['o'][i]:
                add('N4 post-earnings drift (20 days)', s, S, d, i + 1, 20, f, note='EARNINGS')
            intra_good = [n for n in intra if good(n)]
            if intra_good and f['cc'] >= 0.05 and f['rvol'] >= 2:
                add('N5 intraday news, next day (open->close)', s, S, d, i + 1, 1, f, note=intra_good[0]['types'][0])
            if no_news and not intra and f['cc'] >= 0.05 and f['rvol'] >= 5:
                add('C2 control: volume spike, no news (next open->close)', s, S, d, i + 1, 1, f)
    return trades, ev, cover

def build_newsmap(items, cal, universe_syms):
    nm = defaultdict(lambda: dict(pre=[], intra=[])); kept = Counter()
    for it in items:
        sy = [x for x in (it.get('symbols') or []) if x in universe_syms]
        if not sy or len(it.get('symbols') or []) > 2: kept['dropped: no symbol / 3+ symbols'] += 1; continue
        try: ts = datetime.fromisoformat(it['created_at'].replace('Z', '+00:00')).astimezone(ET)
        except Exception: continue
        d, when = session_for(ts, cal)
        if not d: continue
        c = V.classify(it.get('headline') or '', it.get('summary') or '', len(it.get('symbols') or []))
        c['h'] = (it.get('headline') or '')[:140]
        for s in sy: nm[(s, d)][when].append(c)
        kept['kept ' + when] += 1
    return dict(nm), kept

def load_ohlcv(D, syms, s0, s1):
    out = {}; t0 = time.time()
    for k in range(0, len(syms), 100):
        for s, L in D.bars(syms[k:k + 100], '1Day', s0, s1, 'sip', 'all').items():
            if len(L) >= 25:
                out[s] = dict(d=[x['t'][:10] for x in L], o=[x['o'] for x in L], h=[x['h'] for x in L], l=[x['l'] for x in L], c=[x['c'] for x in L], v=[x['v'] for x in L])
        if k % 1000 == 0: log(k, 'symbols', len(out), round(time.time() - t0), 's')
    return out

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    D = Data(key, sec); uni = universe(key, sec); log('universe', len(uni))
    s0 = datetime(2026, 4, 1, tzinfo=ET); s1 = datetime.now(ET) - timedelta(minutes=20)
    spy = D.bars(['SPY'], '1Day', s0, s1, 'sip', 'all').get('SPY', []); cal = [x['t'][:10] for x in spy]; last_cal = cal[-1]
    stocks = load_ohlcv(D, sorted(uni), s0, s1); log('stocks with bars', len(stocks))
    items = []; day = START; per_day = {}
    while day <= s1.date():
        a = datetime.combine(day, datetime.min.time(), ET); L = D.news_range(a, a + timedelta(days=1), pages=400)
        items += [dict(created_at=x.get('created_at'), headline=x.get('headline'), summary=x.get('summary'), symbols=x.get('symbols')) for x in L]
        per_day[day.isoformat()] = len(L); day += timedelta(days=1)
        if day.day == 1: log('news through', day, len(items))
    newsmap, kept = build_newsmap(items, cal, set(stocks)); log('news items', len(items), dict(kept))
    trades, ev, cover = run(stocks, cal, newsmap, START, last_cal)
    rules = sorted({t['rule'] for t in trades}); res = {}
    rows = ['| rule | period | trades | win rate | avg net | median | avg without best 5 | profit factor | t-stat | avg at 2x costs |', '|---|---|---|---|---|---|---|---|---|---|']
    for r in rules:
        for sp in ('dev', 'test'):
            T = [t for t in trades if t['rule'] == r and t['split'] == sp]; S1 = stats([t['net'] for t in T]); S2 = stats([t['net2'] for t in T])
            res[f'{r} | {sp}'] = dict(S1, avg_2x_cost_pct=S2.get('avg_pct'))
            if S1['n']: rows.append(f"| {r} | {sp} | {S1['n']} | {S1['win_pct']}% | {S1['avg_pct']}% | {S1['median_pct']}% | {S1['avg_without_best5_pct']}% | {S1['profit_factor']} | {S1['t']} | {S2['avg_pct']}% |")
    # price buckets for the main rule, both periods together
    pb = ['| rule | price | trades | win rate | avg net |', '|---|---|---|---|---|']
    for r in rules:
        for lo, hi, lab in ((0, 1, 'under $1'), (1, 5, '$1-5'), (5, 20, '$5-20'), (20, 1e9, '$20+')):
            T = [t['net'] for t in trades if t['rule'] == r and lo <= t['price'] < hi]
            if T: S1 = stats(T); pb.append(f"| {r} | {lab} | {S1['n']} | {S1['win_pct']}% | {S1['avg_pct']}% |")
    evrows = ['| period | news | gap at open | stock-days | open->close avg | open->close up % |', '|---|---|---|---|---|---|']
    evj = {}
    for (sp, kind, bk), L in sorted(ev.items()):
        if kind == 'type': continue
        oc = [x[0] for x in L]; evj[f'{sp} | {kind} | {bk}'] = dict(n=len(L), oc_avg_pct=round(100 * sum(oc) / len(oc), 3), oc_up_pct=round(100 * sum(x > 0 for x in oc) / len(oc), 1))
        evrows.append(f"| {sp} | {kind} | {bk} | {len(L)} | {evj[f'{sp} | {kind} | {bk}']['oc_avg_pct']}% | {evj[f'{sp} | {kind} | {bk}']['oc_up_pct']}% |")
    tyrows = ['| period | news type (pre-open, good) | stock-days | avg gap | open->close avg | up % | open->5-day close avg |', '|---|---|---|---|---|---|---|']
    for (sp, kind, typ), L in sorted(ev.items()):
        if kind != 'type': continue
        oc = [x[0] for x in L]; g = [x[1] for x in L]; fv = [x[2] for x in L if x[2] is not None]
        tyrows.append(f"| {sp} | {typ} | {len(L)} | {100 * sum(g) / len(g):+.2f}% | {100 * sum(oc) / len(oc):+.3f}% | {100 * sum(x > 0 for x in oc) / len(oc):.1f}% | "
                      f"{(100 * sum(fv) / len(fv)) if fv else 0:+.2f}% |")
    covrows = [f"- {sp}: {cover[(sp, 'gap >= 10% with pre-open news')]} of {cover[(sp, 'gap >= 10%')]} stock-days that gapped up 10%+ had pre-open news in Alpaca's feed" for sp in ('dev', 'test')]
    md = ['# VANTEX City research: news + volume study', '',
          f"Jun 2026 to {last_cal}. {len(stocks)} stocks with daily bars, {len(items)} news items ({dict(kept)}). Dev = Jun-Sep, test = Oct-now. "
          'All numbers are per trade, after estimated costs (both sides). Long only.', '', '## Rules', ''] + rows + [
          '', '## By price (both periods)', ''] + pb + ['', '## Event study: does news change what a gap does?', ''] + evrows + [
          '', '## By news type (good pre-open news, any gap)', ''] + tyrows + ['', '## News coverage', ''] + covrows + [
          '', 'Controls C1/C2 use the same entries with no news in the last 3 days. Daily bars only: same-day stop/target order assumed stop-first. '
          'Official opening prices can be better than a real order would get, especially under $5. A backtest is not proof.']
    buf = io.StringIO(); w = csv.writer(buf); cols = ['rule', 'split', 'sym', 'signal_day', 'buy_day', 'sell_day', 'buy', 'sell', 'net', 'how', 'price', 'gap', 'rvol', 'note']
    w.writerow(cols)
    for t in trades: w.writerow([round(t[c] * 100, 3) if c == 'net' else t[c] for c in cols])
    out = dict(results=res, events=evj, coverage={f'{k[0]} | {k[1]}': v for k, v in cover.items()}, news_items=len(items), news_per_day=per_day,
               kept=dict(kept), updated=datetime.now(ET).isoformat(timespec='seconds'))
    publish({})
    publish({'news_study.json': out, 'news_study.md': '\n'.join(md) + '\n', 'news_study_trades.csv': buf.getvalue()})
    log('done', len(trades), 'trades')

if __name__ == '__main__':
    main()
