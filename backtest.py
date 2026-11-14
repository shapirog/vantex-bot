"""Vantex backtest: replays the options bot's exact rules over past trading days. Read-only: places no trades.

What it does
  - downloads the past N trading days (default 60) of 1-minute bars for QQQ, SPY, VIXY and the options bot's stocks,
    plus every headline Alpaca has for those stocks and Nasdaq's earnings calendar for those days
  - walks through each day minute by minute and asks the SAME setup functions the live bot uses
    (range break, news shock, news check), with the same sizing, stops, half-off, trailing stop and closing times
  - runs it twice: with the new filters (calendar guard + earnings + market mood) and without, so you can see what they add
  - publishes the results to the 'live-backtest' branch; setups that lose over 15+ trades are marked "off",
    and the live options bot skips them

Honest limits (it is a model, not a time machine)
  - free data has no history of option prices that matches every contract, so each option is PRICED with the
    Black-Scholes formula from the stock price, time left and the stock's recent volatility (x1.1), then a
    bid/ask spread is charged on the way in and out (3% index, 4% stocks). Real fills can be better or worse.
  - it can't know which stocks the scanner's Radar would have added on a past day, so it tests the fixed list.
  - volume comes from the IEX feed (a slice of the market), same as the live bot.
"""
import os, sys, json, math, time, subprocess, bisect
from collections import Counter
from datetime import datetime, timedelta, timezone, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import options as O                                   # the live bot's rules (exits if the key isn't a paper key)

ET, req, TRADE, DATA = O.ET, O.req, O.TRADE, O.DATA
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 60
OUT = os.environ.get('VANTEX_BT_DIR', '/tmp/vantex-bt')
START_EQ = 2500.0
SPREAD_IDX, SPREAD_STK, IV_MULT, IV_FLOOR = 0.03, 0.04, 1.1, 0.12
UNIVERSE = O.INDEXES + O.LIQUID + ['VIXY']
MIN_TRADES = 15

# ---------------- option pricing (Black-Scholes, no rates) ----------------
def ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
def bs(S, K, T, vol, call):
    if T <= 1e-9 or vol <= 0: return max(0.0, (S - K) if call else (K - S))
    v = vol * math.sqrt(T); d1 = (math.log(S / K) + 0.5 * v * v) / v; d2 = d1 - v
    return S * ncdf(d1) - K * ncdf(d2) if call else K * ncdf(-d2) - S * ncdf(-d1)

def strike_for(und, p, d):
    step = 1 if und in O.INDEXES else (1 if p < 50 else 2.5 if p < 200 else 5)
    return round(p / step) * step

def years_left(und, day, m):
    """Index: same-day expiry. Stocks: the Friday at least 2 days out (weeklies), counted in trading days."""
    today_left = max(0, 16 * 60 - m) / 390
    if und in O.INDEXES: return today_left / 252, day
    k = (4 - day.weekday()) % 7
    if k < 2: k += 7
    exp = day + timedelta(days=k)
    tdays = sum(1 for i in range(1, k + 1) if (day + timedelta(days=i)).weekday() < 5)
    return (tdays + today_left) / 252, exp

# ---------------- data ----------------
def trading_days():
    end = datetime.now(ET).date() - timedelta(days=1)
    r = req('GET', f'{TRADE}/v2/calendar', params=dict(start=str(end - timedelta(days=int(DAYS * 1.7) + 10)), end=str(end)))
    return [date.fromisoformat(c['date']) for c in (r.json() if r.ok else [])][-DAYS:]

def daily_vol(days):
    """20-day realized volatility (annualized) for each symbol, known at the start of each day."""
    start = datetime.combine(days[0] - timedelta(days=45), datetime.min.time(), ET)
    end = datetime.combine(days[-1] + timedelta(days=1), datetime.min.time(), ET)
    out, tok = {}, None
    for _ in range(40):
        p = dict(symbols=','.join(UNIVERSE), timeframe='1Day', start=start.isoformat(), end=end.isoformat(), limit=10000, feed='iex', adjustment='split')
        if tok: p['page_token'] = tok
        r = req('GET', f'{DATA}/v2/stocks/bars', params=p)
        if not r.ok: break
        j = r.json()
        for s, B in (j.get('bars') or {}).items(): out.setdefault(s, []).extend(B)
        tok = j.get('next_page_token')
        if not tok: break
    vol = {}
    for s, B in out.items():
        B.sort(key=lambda b: b['t']); ds = [datetime.fromisoformat(b['t'].replace('Z', '+00:00')).astimezone(ET).date() for b in B]; cs = [b['c'] for b in B]
        for day in days:
            i = bisect.bisect_left(ds, day)
            rets = [math.log(cs[j] / cs[j - 1]) for j in range(max(1, i - 20), i) if cs[j - 1] > 0]
            if len(rets) >= 5:
                mu = sum(rets) / len(rets); sd = math.sqrt(sum((x - mu) ** 2 for x in rets) / (len(rets) - 1))
                vol[(s, day)] = max(IV_FLOOR, sd * math.sqrt(252) * IV_MULT)
    return vol

def minute_bars(days):
    start = datetime.combine(days[0] - timedelta(days=4), datetime.min.time(), ET)
    end = datetime.combine(days[-1] + timedelta(days=1), datetime.min.time(), ET)
    B = {}
    for i in range(0, len(UNIVERSE), 3):                 # a few symbols per request so no page limit cuts the history short
        B.update(O._bars(dict(timeframe='1Min', start=start.isoformat(), end=end.isoformat(), limit=10000, feed='iex'), UNIVERSE[i:i + 3]))
    by = {}
    for s, L in B.items():
        for b in L: by.setdefault(s, {}).setdefault(b['t'].date(), []).append(b)
    return B, by

def history_news(days):
    """Every headline for the stocks over the period, oldest first: {sym: [(time, headline)]}."""
    start = datetime.combine(days[0] - timedelta(days=1), datetime.min.time(), ET).astimezone(timezone.utc)
    end = datetime.combine(days[-1] + timedelta(days=1), datetime.min.time(), ET).astimezone(timezone.utc)
    by = {}; a = start
    while a < end:                                      # one week at a time so busy weeks aren't cut short
        b = min(end, a + timedelta(days=7)); tok = None
        for _ in range(80):
            p = dict(symbols=','.join(O.LIQUID), start=a.isoformat(), end=b.isoformat(), limit=50, sort='asc')
            if tok: p['page_token'] = tok
            r = req('GET', f'{DATA}/v1beta1/news', params=p)
            if not r.ok: break
            j = r.json()
            for n in j.get('news') or []:
                t = datetime.fromisoformat(n['created_at'].replace('Z', '+00:00'))
                for s in n.get('symbols') or []:
                    if s in O.LIQUID: by.setdefault(s, []).append((t, n.get('headline', '')[:160]))
            tok = j.get('next_page_token')
            if not tok: break
        a = b
    for s in by: by[s] = sorted(set(by[s]))
    return by

def history_earnings(days):
    cache, ok = {}, 0
    for d in sorted({d + timedelta(days=k) for d in days for k in range(0, 4)}):
        e = O.nasdaq_earnings(d); cache[d] = e or {}; ok += e is not None
    by_day = {}
    for day in days:
        by = {}
        for k in range(0, 4):
            for s, when in cache.get(day + timedelta(days=k), {}).items(): by.setdefault(s, []).append((k, when))
        by_day[day] = by
    return by_day, ok > 0

# ---------------- replay ----------------
class Sym:
    """One symbol's day with running VWAP and volume, so each minute is cheap to evaluate."""
    def __init__(self, sym, bars, all_bars):
        self.sym, self.b, self.idx = sym, bars, sym in O.INDEXES
        self.or_min = O.IDX_OR if self.idx else O.STK_OR
        cut = bars[0]['t'].replace(hour=9, minute=30) + timedelta(minutes=self.or_min)
        self.k = sum(1 for x in bars if x['t'] < cut)
        orb = bars[:self.k] or bars[:1]
        self.hi, self.lo, self.open = max(x['h'] for x in orb), min(x['l'] for x in orb), bars[0]['o']
        self.cpv, self.cv = [], []; a = v = 0.0
        for x in bars: a += (x['h'] + x['l'] + x['c']) / 3 * x['v']; v += x['v']; self.cpv.append(a); self.cv.append(v)
        self.ema = {}
        if self.idx:                                    # 50-minute EMA running across days, like the live bot
            prior = [x for x in all_bars if x['t'] < bars[0]['t']][-400:]
            e = None; kk = 2 / (O.EMA_LEN + 1)
            for x in prior + bars:
                e = x['c'] if e is None else x['c'] * kk + e * (1 - kk)
                self.ema[x['t']] = e
    def L(self, i):
        """The same dict the live bot's levels() builds, as of bar i."""
        today = self.b[:i + 1]
        return dict(today=today, orb=self.b[:self.k], after=self.b[self.k:i + 1], or_min=self.or_min, hi=self.hi, lo=self.lo, open=self.open,
                    vwap=self.cpv[i] / self.cv[i] if self.cv[i] else None, ema=self.ema.get(self.b[i]['t']), avg_v=self.cv[i] / (i + 1))

def news_at(news, sym, t):
    L = news.get(sym) or []
    j = bisect.bisect_right(L, (t, '\uffff')); i = bisect.bisect_left(L, (t - timedelta(hours=O.NEWS_HOURS), ''))
    return [dict(h=h) for _, h in reversed(L[i:j])]

def run(days, by_day, all_bars, vol, news, earn, filters):
    eq = START_EQ; trades = []; curve = []; skips = Counter()
    for day in days:
        S = {s: Sym(s, by_day[s][day], all_bars.get(s, [])) for s in UNIVERSE if day in by_day.get(s, {}) and len(by_day[s][day]) >= 60}
        if 'SPY' not in S: continue
        ptr = {s: -1 for s in S}; tries = set(); open_ = []; entries = 0; day_iso = day.isoformat()
        for m in range(10 * 60, O.STK_FLAT + 1):
            t = datetime.combine(day, datetime.min.time(), ET).replace(hour=m // 60, minute=m % 60)
            for s, X in S.items():                     # bars that have CLOSED by minute m
                while ptr[s] + 1 < len(X.b) and X.b[ptr[s] + 1]['t'] + timedelta(minutes=1) <= t: ptr[s] += 1
            L_by = {s: X.L(ptr[s]) for s, X in S.items() if ptr[s] >= 0 and s in ('SPY', 'VIXY')}
            # ---- manage open trades
            for T in list(open_):
                X = S[T['und']]; i = ptr[T['und']]; px = X.b[i]['c']
                tl, _ = years_left(T['und'], day, m)
                val = bs(px, T['k'], tl, T['vol'], T['d'] == 1) * (1 - T['spr'] / 2)
                T['peak'] = max(T['peak'], val); gain = val / T['entry'] - 1; why = None
                flat = O.IDX_FLAT if X.idx else O.STK_FLAT
                if m >= flat: why = 'closing time'
                elif day_iso in O.FOMC and m >= O.FOMC_FLAT and filters: why = 'before the Fed decision'
                elif not T['half'] and i >= 1:
                    c2 = [X.b[i - 1]['c'], X.b[i]['c']]; vw = X.cpv[i] / X.cv[i]
                    back = all((c < vw) if T['d'] == 1 else (c > vw) for c in c2) if T['setup'] == 'news shock' else all((c < T['level']) if T['d'] == 1 else (c > T['level']) for c in c2)
                    if back: why = 'move failed'
                if not why and not T['half'] and gain >= O.PARTIAL_PCT:
                    if T['qty'] >= 2:
                        h = T['qty'] // 2; T['cash'] += h * val * 100; T['qty'] -= h; T['stop'] = T['entry']
                    else: T['stop'] = T['entry'] * (1 + O.LOCK_PCT)
                    T['half'] = True
                if not why:
                    stop = max(T['stop'], T['peak'] * (1 - O.TRAIL_PCT)) if T['half'] else T['entry'] * (1 - O.STOP_PCT)
                    if val <= stop: why = 'trailing stop' if T['half'] else 'stop -30%'
                if why:
                    T['cash'] += T['qty'] * val * 100; pnl = T['cash'] - T['cost']; eq += pnl
                    trades.append(dict(day=day_iso, sym=T['und'], setup=T['setup'], d=T['d'], t_in=T['t_in'], t_out=f'{m // 60}:{m % 60:02d}', cost=round(T['cost'], 2),
                                       pnl=round(pnl, 2), ret=round(pnl / T['cost'] * 100, 1), why=why, note=T['note']))
                    open_.remove(T)
            # ---- look for new entries
            if m > O.SHOCK_TO or len(open_) >= O.MAX_OPEN or entries >= O.MAX_ENTRIES: continue
            md = O.mood(L_by)
            busy = {T['und'] for T in open_}
            for s, X in S.items():
                if s == 'VIXY' or s in busy or ptr[s] < 0: continue
                i = ptr[s]; c = X.b[i]['c']
                if X.idx and m > O.IDX_LAST: continue
                for d in (1, -1):
                    if f'{s}{d}' in tries: continue
                    # cheap pre-checks before the real rules
                    near_break = (c > X.hi) if d == 1 else (c < X.lo)
                    shock = (not X.idx) and i >= O.SHOCK_BARS and ((c / X.b[i - O.SHOCK_BARS]['c'] - 1) * d) >= O.SHOCK_MIN
                    if not (near_break or shock): continue
                    L = X.L(i)
                    if X.idx: ok, info = O.break_setup(d, L, True, O.IDX_VOL)
                    else:
                        ok, info = O.shock_setup(d, L, O.SHOCK_VOL) if shock else (False, '')
                        if not ok and m <= O.ENTRY_TO and near_break: ok, info = O.break_setup(d, L, False, O.STK_VOL)
                    if not ok: continue
                    O.NEWS['by'] = {s: news_at(news, s, t.astimezone(timezone.utc))}
                    good, headline, note = O.why(s, d)
                    if not good: tries.add(f'{s}{d}'); skips['news against the move'] += 1; continue
                    if note == 'no news found' and max(x['v'] for x in L['today'][-O.SHOCK_BARS:]) < O.NONEWS_VOL * L['avg_v']: continue
                    if filters:
                        setup_key = 'index break' if X.idx else info['setup']
                        blk = O.calendar_block(day_iso, m) or (None if X.idx else O.earnings_block(s, earn.get(day, {}))) or O.mood_block(d, info['setup'], note, md)
                        if blk:
                            tries.add(f'{s}{d}'); skips['calendar' if 'Fed' in blk or 'CPI' in blk else 'earnings' if 'earnings' in blk else 'market mood'] += 1; continue
                    tries.add(f'{s}{d}')
                    v = vol.get((s, day), 0.3); tl, _ = years_left(s, day, m)
                    spr = SPREAD_IDX if X.idx else SPREAD_STK
                    budget = min(eq * O.RISK_PCT * (0.5 if (filters and md[2]) else 1), eq)
                    # same choice as the live bot: at the money, then a little out of the money if that's over budget
                    step = 1 if X.idx else (1 if c < 50 else 2.5 if c < 200 else 5); lim = c * (0.006 if X.idx else 0.02)
                    k = strike_for(s, c, d); pick = None
                    while (k - c) * d <= lim:
                        prem = bs(c, k, tl, v, d == 1) * (1 + spr / 2)
                        if prem >= 0.05 and prem * 100 <= budget: pick = (k, prem); break
                        k += step * d
                    if not pick: skips['contract over budget'] += 1; continue
                    k, prem = pick; qty = min(O.MAX_QTY, int(budget // (prem * 100)))
                    open_.append(dict(und=s, d=d, k=k, vol=v, spr=spr, entry=prem, peak=prem, qty=qty, cost=qty * prem * 100, cash=0.0, half=False,
                                      stop=prem * (1 - O.STOP_PCT), level=info['level'], setup='index break' if X.idx else info['setup'], note=note,
                                      t_in=f'{m // 60}:{m % 60:02d}'))
                    entries += 1; busy.add(s); break
                if len(open_) >= O.MAX_OPEN or entries >= O.MAX_ENTRIES: break
        curve.append([day.isoformat(), round(eq, 2)])
    return trades, curve, skips

def summary(T, curve=None):
    if not T: return dict(trades=0)
    p = [t['pnl'] for t in T]; w = [x for x in p if x > 0]; l = [x for x in p if x <= 0]; gl = -sum(l)
    streak = run_ = 0
    for x in p: run_ = run_ + 1 if x <= 0 else 0; streak = max(streak, run_)
    out = dict(trades=len(T), win_rate=round(len(w) / len(T) * 100, 1), pf=round(sum(w) / gl, 2) if gl > 0 else None, net=round(sum(p), 2),
               avg_ret=round(sum(t['ret'] for t in T) / len(T), 1), best=round(max(p), 2), worst=round(min(p), 2), losing_streak=streak)
    if curve:
        pk, dd = START_EQ, 0.0
        for _, e in curve: pk = max(pk, e); dd = max(dd, (pk - e) / pk * 100)
        out.update(end_equity=curve[-1][1], ret_pct=round((curve[-1][1] / START_EQ - 1) * 100, 1), max_dd_pct=round(dd, 1))
    return out

def main():
    t0 = time.time()
    days = trading_days()
    if not days: sys.exit('no trading days returned')
    print(f'backtest {days[0]} -> {days[-1]} ({len(days)} days)', flush=True)
    vol = daily_vol(days); all_bars, by_day = minute_bars(days); news = history_news(days); earn, earn_ok = history_earnings(days)
    print(f'data: {sum(len(v) for v in all_bars.values())} bars, {sum(len(v) for v in news.values())} headlines, earnings calendar {"ok" if earn_ok else "unavailable"}', flush=True)
    res = {}
    for name, f in (('filters', True), ('no_filters', False)):
        T, curve, skips = run(days, by_day, all_bars, vol, news, earn, f)
        setups = {k: summary([t for t in T if t['setup'] == k]) for k in ('index break', 'range break', 'news shock')}
        res[name] = dict(all=summary(T, curve), setups=setups, curve=curve, skips=dict(skips), trades=T[-60:][::-1])
        print(name, json.dumps(res[name]['all']), dict(skips), flush=True)
    verdict = {}
    for k, v in res['filters']['setups'].items():
        n, pf = v.get('trades', 0), v.get('pf')
        if n < MIN_TRADES: st = 'on'; why = f'only {n} trades: not enough to judge yet'
        elif pf is not None and pf < 0.9: st = 'off'; why = f'lost money over {n} trades (profit factor {pf})'
        elif pf is None or pf >= 1.0: st = 'on'; why = f'made money over {n} trades (profit factor {pf if pf is not None else "no losses"})'
        else: st = 'watch'; why = f'about break-even over {n} trades (profit factor {pf})'
        verdict[k] = dict(status=st, why=why)
    out = dict(updated=datetime.now(ET).isoformat(timespec='seconds'), start=days[0].isoformat(), end=days[-1].isoformat(), days=len(days),
               start_equity=START_EQ, earnings_data=earn_ok, results=res, verdict=verdict, seconds=round(time.time() - t0),
               model='Option prices are modeled (Black-Scholes from the stock price, time left and 20-day volatility x1.1) with a 3-4% bid/ask spread charged. Real fills can differ.')
    os.makedirs(OUT, exist_ok=True); json.dump(out, open(f'{OUT}/backtest.json', 'w'), separators=(',', ':'))
    print(json.dumps(dict(event='backtest_done', verdict=verdict, seconds=out['seconds'])), flush=True)
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', 'live-backtest', OUT], check=True)
    subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', 'backtest'], check=True)
    subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{O.REPO}.git', 'live-backtest'], check=True, timeout=90, capture_output=True)

if __name__ == '__main__':
    main()
