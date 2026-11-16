"""
VANTEX City replay + evaluation. Research only: places NO orders.

  python city_replay.py replay 2026-11-13        -> one session, minute by minute, for the City's Replay player
  python city_replay.py eval dev 20              -> 20 sessions sampled from the development period
  python city_replay.py eval test 20             -> 20 sessions from the untouched out-of-sample period (run once, at the end)
  python city_replay.py compare dev 20           -> original rules vs "strong stocks only" rule sets on the same sessions

No look-ahead: at each minute the engine logic (vantex_core, the same code the live engine runs) only sees
  - daily history up to the prior session, 1-minute bars that had CLOSED before that minute,
  - news whose publish time is before that minute, the last quote before the decision.
Fills: marketable limit at the ask (+0.05%) must trade within the next minute or the order fails; size is capped at 10% of
that minute's volume (partial fills); stops fill at the stop or, through a gap or a halt, at the next available open; exits
pay half the quoted spread plus fees. Assumes the real-time SIP plan (what entries require live).
Known limits: the stock list is today's (delisted stocks are missing = survivorship); halts are inferred from missing
minutes; news headlines are as stored now (later edits can't be undone); the spread for unconfirmed signals is not fetched.
Results -> branch 'live-replay': replay/<day>.json, index.json, eval_<split>.json, eval_<split>.md
"""
import json, math, os, random, re, shutil, subprocess, sys, time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

import vantex_core as V
from vantex_core import Bar
from city_engine import Data, to_bar, epoch, NAME_EXCLUDE, CONTEXT_ETFS
ET = ZoneInfo('America/New_York')
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
OUT = os.environ.get('VANTEX_REPLAY_DIR', '/tmp/vantex-replay')
TRADE = 'https://paper-api.alpaca.markets'                    # read-only here: assets and calendar
DEV = (date(2025, 9, 2), date(2026, 4, 30)); TEST = (date(2026, 5, 1), None)
EXTRA_SLIP = 0.0002
def log(*a): print(datetime.now(ET).strftime('%H:%M:%S'), *a, flush=True)

class Replay:
    def __init__(self, D, key, sec, cfg=None):
        self.D = D; self.h = {'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': sec}
        self.cfg = V.merge(V.DEFAULTS, cfg or {})
        r = requests.get(f'{TRADE}/v2/assets', headers=self.h, params=dict(status='active', asset_class='us_equity'), timeout=60)
        U = self.cfg['universe']; self.assets = r.json() if r.ok else []
        self.common = sorted(a['symbol'] for a in self.assets if a.get('exchange') in U['exchanges'] and a.get('tradable') and a['symbol'].isalpha()
                             and not any(re.search(rx, (a.get('name') or '').lower()) for _, rx in NAME_EXCLUDE))
        self.names = {a['symbol']: (a.get('name') or '')[:60] for a in self.assets}

    def sessions(self, a, b):
        r = requests.get(f'{TRADE}/v2/calendar', headers=self.h, params=dict(start=a.isoformat(), end=b.isoformat()), timeout=30)
        return [(date.fromisoformat(x['date']), int(x['close'][:2]) * 60 + int(x['close'][3:5])) for x in r.json()]

    def setup_day(self, d):
        """universe, daily levels and the volume curve, all from data before d"""
        U = self.cfg['universe']
        D = self.D.bars(self.common, '1Day', datetime.combine(d - timedelta(days=45), datetime.min.time(), ET), datetime.combine(d, datetime.min.time(), ET), 'sip', 'split')
        daily, uni, cov = {}, [], Counter()
        for s in self.common:
            L = D.get(s, [])
            if len(L) < 15: cov['less than 15 days of history'] += 1; continue
            last = L[-1]
            trs = [max(b['h'], p['c']) - min(b['l'], p['c']) for p, b in zip(L[-15:-1], L[-14:])]
            dd = dict(prior_close=last['c'], prior_high=last['h'], prior_low=last['l'], high20=max(b['h'] for b in L[-20:]), low20=min(b['l'] for b in L[-20:]),
                      atr14=sum(trs) / len(trs), adv=sum(b['v'] for b in L[-14:]) / 14, adv_dollars=sum(b['v'] * b['c'] for b in L[-14:]) / 14)
            if dd['prior_close'] < U['min_price']: cov['price filter'] += 1; continue
            if U['max_price'] and dd['prior_close'] > U['max_price']: cov['price filter'] += 1; continue
            if dd['adv_dollars'] < U['min_avg_dollar_volume']: cov['avg dollar volume filter'] += 1; continue
            daily[s] = dd; uni.append(s)
        S = self.D.bars(['SPY'], '1Min', datetime.combine(d - timedelta(days=16), datetime.min.time(), ET), datetime.combine(d, datetime.min.time(), ET), 'sip').get('SPY', [])
        prof = defaultdict(list)
        for b in S: x = to_bar(b); prof[x.m].append(x.v)
        curve = V.curve_from_profile({m: sum(v) / len(v) for m, v in prof.items()})
        return uni, daily, curve, dict(cov)

    def quote_at(self, sym, ts):
        qc = getattr(self, '_qcache', None)
        if qc is not None and (sym, ts) in qc: return qc[(sym, ts)]
        q = self._quote_at(sym, ts)
        if qc is not None: qc[(sym, ts)] = q
        return q

    def _quote_at(self, sym, ts):
        r = self.D.get('/v2/stocks/quotes', dict(symbols=sym, start=datetime.fromtimestamp(ts - 120, timezone.utc).isoformat(),
                                                 end=datetime.fromtimestamp(ts, timezone.utc).isoformat(), limit=1, sort='desc', feed='sip'), 'hist_quote')
        if r is None or not r.ok: return None
        q = (r.json().get('quotes') or {}).get(sym) or []
        if not q: return None
        q = q[0]
        if not q.get('bp') or not q.get('ap') or q['ap'] < q['bp']: return None
        return dict(bid=q['bp'], ask=q['ap'], t=epoch(q['t']))

    def load_day(self, d, close_m=960):
        """everything a session replay needs, fetched once (so several rule sets can be compared on identical data)"""
        t0 = time.time()
        uni, daily, curve, cov = self.setup_day(d)
        start = datetime.combine(d, datetime.min.time(), ET) + timedelta(hours=4); end = datetime.combine(d, datetime.min.time(), ET) + timedelta(minutes=close_m)
        raw = self.D.bars(uni + [s for s in CONTEXT_ETFS if s not in uni], '1Min', start, end, 'sip')
        BARS = {s: [to_bar(b) for b in L] for s, L in raw.items()}; del raw
        news_raw = self.D.news_range(start - timedelta(hours=24), end)
        news = [dict(id=n.get('id'), t=epoch(n.get('created_at')), received=epoch(n.get('created_at')), h=(n.get('headline') or '')[:240], s=n.get('source') or '',
                     u=n.get('url') or '', sy=[x for x in (n.get('symbols') or []) if x.isalpha()][:12], sm=(n.get('summary') or '')[:300]) for n in news_raw]
        news.sort(key=lambda x: x['t'] or 0)
        log(d, 'universe', len(uni), 'symbols with bars', len(BARS), 'news', len(news), round(time.time() - t0), 's')
        self._qcache = {}
        return dict(uni=uni, daily=daily, curve=curve, cov=cov, BARS=BARS, news=news)

    def run_day(self, d, close_m=960, frames=False, state=None, data=None, cfg=None):
        t0 = time.time()
        data = data or self.load_day(d, close_m)
        uni, daily, curve, cov, BARS, news = data['uni'], data['daily'], data['curve'], data['cov'], data['BARS'], data['news']
        saved_cfg = self.cfg
        if cfg is not None: self.cfg = cfg
        try: return self._run(d, close_m, frames, state, uni, daily, curve, cov, BARS, news, t0)
        finally: self.cfg = saved_cfg

    def _run(self, d, close_m, frames, state, uni, daily, curve, cov, BARS, news, t0):
        R = self.cfg['risk']; S = self.cfg['signals']
        flat_m = min(V.hhmm(R['flat_at']), close_m - 10); until_m = min(V.hhmm(R['entries_until']), close_m - 30)
        cfg = V.merge(self.cfg, {'risk': {'entries_until': f'{until_m // 60:02d}:{until_m % 60:02d}'}})
        ptr = {s: 0 for s in BARS}; agg = {s: dict(v=0, dv=0.0, hi=None, lo=None, px=None) for s in BARS}
        st = state or dict(equity=2500.0, daytrades=[])
        eq0 = st['equity']; eq = eq0
        open_pos = {}; traded = set(); trades = []; signals = Counter(); blocks = Counter(); failed_fills = 0; partial_fills = 0
        frames_out = []; prev = {}; chart_syms = set(); events = []
        day_ts = datetime.combine(d, datetime.min.time(), ET).timestamp()
        minutes = list(range(V.PM_START + 1, close_m + 1))
        for m in minutes:
            ts = day_ts + m * 60                                                # this minute's start: bars before it are closed
            for s, L in BARS.items():
                i = ptr[s]; a = agg[s]
                while i < len(L) and L[i].m < m:
                    b = L[i]; a['v'] += b.v; a['dv'] += b.v * (b.h + b.l + b.c) / 3; a['px'] = b.c
                    a['hi'] = b.h if a['hi'] is None else max(a['hi'], b.h); a['lo'] = b.l if a['lo'] is None else min(a['lo'], b.l)
                    i += 1
                ptr[s] = i
            # manage open positions on the bar that just closed
            for s in list(open_pos):
                p = open_pos[s]; L = BARS[s]; i = ptr[s]
                newb = [b for b in L[p['k']:i]]
                if newb:
                    px, b, why = V.sim_exit(p['side'], p['stop'], p['target'], newb, flat_m, p['slip'])
                    if b is not None and why not in ('last-bar', 'no-data'):
                        self.close(p, px, b, why, d, trades, events); eq += trades[-1]['pnl']; del open_pos[s]; continue
                    p['k'] = i
                if m >= flat_m + 1 and s in open_pos:
                    L2 = [b for b in L if b.m >= flat_m]
                    if L2: self.close(p, L2[0].o * (1 - p['side'] * p['slip']), L2[0], 'time', d, trades, events); eq += trades[-1]['pnl']; del open_pos[s]
            sess = V.session(m - 1)
            scan_now = sess == 'regular' or (frames and m % 5 == 0)
            if not scan_now or m >= close_m: continue
            rows, breadth = {}, Counter()
            for s in uni:
                a = agg.get(s)
                if not a or a['px'] is None: continue
                dd = daily[s]; chg = (a['px'] / dd['prior_close'] - 1) * 100
                breadth['up' if chg > 0.05 else 'down' if chg < -0.05 else 'flat'] += 1
                vol_rth = a['v']
                rv = vol_rth / (dd['adv'] * (curve(m) if m >= V.RTH_OPEN else V.default_curve(m))) if dd['adv'] and vol_rth else None
                rows[s] = dict(px=a['px'], chg=chg, v=a['v'], dv=a['dv'], rv=rv, hi=a['hi'], lo=a['lo'])
            lists = V.candidate_lists(rows, daily, m, cfg)
            cand = set().union(*lists.values())
            deep = list(dict.fromkeys(list(open_pos) + V.prerank(cand, rows)[:cfg['candidates']['deep_scan']]))
            vis = [n for n in news if n['t'] and n['t'] < ts]
            groups = V.group_news(vis[-600:], ts, day_ts - 8 * 3600) if vis else []
            out = []
            for s in deep:
                B = BARS[s][:ptr[s]]
                if not B: continue
                dd = daily[s]
                f = V.features(s, B, m - 1, dd['prior_close'], dd['adv'], curve, None, dd, cfg)
                if not f: continue
                cat = V.catalyst_for(s, groups)
                eL = V.evaluate(f, B, 1, cfg, cat); eS = V.evaluate(f, B, -1, cfg, cat)
                # the spread is the only thing bars can't show: fetch the quote at that moment when it is all a setup waits on
                if sess == 'regular' and any(only_spread_pending(e) for e in (eL, eS)):
                    q = self.quote_at(s, ts)
                    if q:
                        f = V.features(s, B, m - 1, dd['prior_close'], dd['adv'], curve, dict(bid=q['bid'], ask=q['ask']), dd, cfg)
                        eL = V.evaluate(f, B, 1, cfg, cat); eS = V.evaluate(f, B, -1, cfg, cat)
                for side, e in ((1, eL), (-1, eS)):
                    k = (s, side)
                    if prev.get(k) != e['status']:
                        signals[('long' if side > 0 else 'bearish', e['status'])] += 1
                        if e['status'] in ('confirmed', 'rejected', 'extended'): events.append(dict(m=m, kind='signal', sym=s, side='long' if side > 0 else 'bearish', status=e['status'], reasons=e['reasons'][:2], level=e['level_name']))
                    prev[k] = e['status']
                    if e['status'] == 'confirmed' and sess == 'regular' and s not in open_pos:
                        self.try_entry(s, side, e, f, B, BARS[s], ptr[s], m, ts, eq, eq0, open_pos, traded, st, cfg, blocks, events, d)
                sc, why, best = V.rank_score(f, eL, eS, cat)
                out.append((sc, s, f, eL, eS, cat, why, best))
            out.sort(key=lambda x: -x[0])
            if frames:
                for x in out[:6]: chart_syms.add(x[1])
                frames_out.append(dict(m=m, breadth=dict(breadth), lists={k: len(v) for k, v in lists.items()},
                                       top=[dict(sym=s, px=round(f['price'], 4), chg=round(f['chg_pct'], 2), rv=round(f['rvol'], 2) if f['rvol'] else None,
                                                 vw=f['vwap_pos'], st=best['status'], side=best['side'], sc=sc, why=why[:3], cat=(cat['types'][:1] or [None])[0] if cat['verified'] else None,
                                                 neg=cat['negative'][:2], warn=len(best['warnings'])) for sc, s, f, eL, eS, cat, why, best in out[:20]],
                                       pos=[dict(sym=s, side=p['side'], qty=p['qty'], entry=round(p['entry'], 4), stop=p['stop']) for s, p in open_pos.items()],
                                       pnl=round(eq - eq0, 2), news=[dict(t=g['t'], h=g['h'], sy=g['sy'][:4], types=g['types'], neg=g['negative'], conf=g['confidence']) for g in groups[:5]]))
        for s, p in list(open_pos.items()):                                    # safety: anything still open closes at the last bar
            L = BARS[s]
            if L: self.close(p, L[-1].c * (1 - p['side'] * p['slip']), L[-1], 'last-bar', d, trades, events); eq += trades[-1]['pnl']
        st['equity'] = eq
        res = dict(day=d.isoformat(), trades=trades, pnl=round(eq - eq0, 2), equity_end=round(eq, 2), signals={f'{a}:{b}': v for (a, b), v in signals.items()},
                   blocks=dict(blocks), coverage=dict(cov, eligible=len(uni)), seconds=round(time.time() - t0))
        if frames:
            res['frames'] = frames_out; res['events'] = events
            res['charts'] = {s: [[b.t, round(b.o, 4), round(b.h, 4), round(b.l, 4), round(b.c, 4), int(b.v)] for b in BARS[s]] for s in sorted(chart_syms)[:40]}
            res['names'] = {s: self.names.get(s, '') for s in chart_syms}
        log(d, 'trades', len(trades), 'pnl', res['pnl'], round(time.time() - t0), 's')
        return res

    def try_entry(self, s, side, e, f, B, L, i, m, ts, eq, eq0, open_pos, traded, st, cfg, blocks, events, d):
        q = self.quote_at(s, ts)
        f = dict(f); qa = (ts - q['t']) if q else None
        if q: mid = (q['bid'] + q['ask']) / 2; f['spread_pct'] = (q['ask'] - q['bid']) / mid * 100
        recent = [x for x in st['daytrades'] if (d - x).days < 7][-5:]
        ctx = dict(paper_verified=True, market_open=True, feed_realtime=True, feed_complete=True, quote_age_s=qa, bar_age_s=0, control='on', now_m=m - 1,
                   city_pnl_today=eq - eq0, account_pnl_today=eq - eq0, start_equity=eq0, equity=eq, open_positions=len(open_pos),
                   exposure=sum(p['qty'] * p['entry'] for p in open_pos.values()), daytrade_count=len(recent) if st.get('pdt', True) else 0, side=side,
                   sym_open=s in open_pos, sym_traded_today=s in traded)
        bl = V.entry_blocks(ctx, cfg)
        if f['spread_pct'] is not None and f['spread_pct'] > cfg['signals']['max_spread_pct']: bl.append('spread too wide at decision')
        if not q: bl.append('no quote')
        if bl:
            for b in bl: blocks[re.sub(r'\(.*?\)|\d[\d.,]*', '', b).strip()] += 1
            return
        lim = V.limit_price(side, q['bid'], q['ask'], cfg)
        sz = V.size_position(lim, e['stop'], eq, eq0, ctx['exposure'], eq * 4, side, cfg)
        if not sz['shares']: blocks[sz['reason']] += 1; return
        cap, px, fb = V.sim_limit_fill(side, lim, L[i:i + 1])
        traded.add(s)
        if not cap: blocks['failed fill (price ran away)'] += 1; events.append(dict(m=m, kind='failed_fill', sym=s)); return
        qty = min(sz['shares'], cap)
        if qty < sz['shares']: blocks['partial fill'] += 1
        px = min(lim, max(px, q['ask'])) if side > 0 else max(lim, min(px, q['bid']))
        slip = (q['ask'] - q['bid']) / 2 / px + EXTRA_SLIP
        open_pos[s] = dict(sym=s, side=side, qty=qty, entry=px, stop=e['stop'], target=e['target'], k=L.index(fb), slip=slip, m_in=fb.m, level=e['level_name'],
                           risk=abs(px - e['stop']) * qty, want=sz['shares'])
        events.append(dict(m=m, kind='entry', sym=s, side='long' if side > 0 else 'short', qty=qty, px=round(px, 4), stop=e['stop'], target=e['target']))

    def close(self, p, px, b, why, d, trades, events):
        gross = p['side'] * (px - p['entry']) * p['qty']
        fees = V.sale_fees(d, p['qty'], px if p['side'] > 0 else p['entry'])
        pnl = gross - fees
        trades.append(dict(sym=p['sym'], side='long' if p['side'] > 0 else 'short', setup=f"{p['level']}:{'long' if p['side'] > 0 else 'short'}", qty=p['qty'], wanted=p['want'],
                           entry=round(p['entry'], 4), exit=round(px, 4), m_in=p['m_in'], m_out=b.m, why=why, pnl=round(pnl, 2), fees=round(fees, 4),
                           R=round(pnl / p['risk'], 3) if p['risk'] else None, exposure=round(p['qty'] * p['entry'], 2)))
        events.append(dict(m=b.m, kind='exit', sym=p['sym'], why=why, px=round(px, 4), pnl=round(pnl, 2)))

def parse_day(txt):
    """accepts 2026-11-13, 2026/11/13, 11/13/2026, 11-13-2026 and phone-keyboard dashes or stray spaces"""
    t = re.sub(r'[\u2010-\u2015\u2212/.\s]+', '-', txt.strip()).strip('-')
    p = [x for x in t.split('-') if x]
    if len(p) == 3 and len(p[0]) == 4: return date(int(p[0]), int(p[1]), int(p[2]))
    if len(p) == 3 and len(p[2]) == 4: return date(int(p[2]), int(p[0]), int(p[1]))
    raise SystemExit(f'Could not read the date {txt!r}: use YYYY-MM-DD, for example 2026-11-13')

VARIANT_NOTES = {
    'A_original': dict(name='A. Original rules', what='every confirmed breakout or breakdown, any stock in the universe'),
    'B_strong_news': dict(name='B. Strong stocks with real news', what='longs only on stocks already up 10%+ on the day, 5x normal volume, a fresh verified news catalyst, and no dilution news'),
    'C_strong_volume': dict(name='C. Strong stocks, news not required', what='longs only on stocks already up 10%+ on the day with 5x normal volume and no dilution news'),
}

def variant_configs(base):
    s = dict(strong_only=True, strong_min_day_change_pct=10.0, strong_min_rvol=5.0, block_negative_news=True)
    return {'A_original': V.merge(base, {'signals': dict(strong_only=False, block_negative_news=False)}),
            'B_strong_news': V.merge(base, {'signals': dict(s, strong_require_catalyst=True)}),
            'C_strong_volume': V.merge(base, {'signals': dict(s, strong_require_catalyst=False)})}

def only_spread_pending(e):
    return e['status'] == 'developing' and [c['name'] for c in e['checks'] if c['ok'] is not True] == ['spread acceptable']

def news_range(self, start, end, pages=40):
    items, tok = [], None
    for _ in range(pages):
        p = dict(start=start.isoformat(), end=end.isoformat(), limit=50, sort='asc', include_content='false', exclude_contentless='true')
        if tok: p['page_token'] = tok
        r = self.get('/v1beta1/news', p, 'news')
        if r is None or not r.ok: break
        j = r.json(); items += j.get('news') or []
        tok = j.get('next_page_token')
        if not tok: break
    return items
Data.news_range = news_range

def summarize(days, label):
    T = [t for d in days for t in d['trades']]
    pnl_by_day = [(d['day'], d['pnl']) for d in days]
    eq, peak, dd, curve = 0.0, 0.0, 0.0, []
    for day, p in pnl_by_day: eq += p; peak = max(peak, eq); dd = max(dd, peak - eq); curve.append((day, round(eq, 2)))
    R = [t['R'] for t in T if t['R'] is not None]
