"""
VANTEX City engine: market-wide scanner + paper trader. Runs on GitHub Actions 4:00 AM - 8:00 PM ET on market days and
publishes everything the City shows to the 'live-city' branch once a minute.

Data: Alpaca market data only (the provider this project has). What the feed really is gets detected at start and shown:
  real-time SIP (paid plan)  every US exchange, real time            -> paper entries may be allowed
  free plan                  full market 15 minutes delayed (SIP) + real-time quotes from IEX (one exchange, ~2-3% of volume)
                             -> scanning works, but NEW PAPER ENTRIES ARE BLOCKED (delayed or partial data)
Orders: only through city_broker.PaperBroker (paper host only). Shorts only if risk.allow_short_orders is true.
Logs: every signal change, order, fill, cancel, failed fill, rejected trade and the reason for no trade.

Files on 'live-city': city.json (status, market context, candidates, setups, positions, risk, health), charts.json,
news.json, events.json (today), history.json (all days), coverage.json (who was scanned / excluded and why).
"""
import json, math, os, re, subprocess, sys, time, traceback
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

import vantex_core as V
from vantex_core import Bar

ET = ZoneInfo('America/New_York')
DATA = 'https://data.alpaca.markets'
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
OUT = os.environ.get('VANTEX_CITY_DIR', '/tmp/vantex-city')
BRANCH = 'live-city'
MAX_RUN_S = int(os.environ.get('CITY_MAX_RUN_S', 330 * 60))
NTFY = os.environ.get('NTFY_TOPIC')
CONTEXT_ETFS = V.INDEXES + list(V.SECTORS) + ['VIXY']
NAME_EXCLUDE = [('ETF / fund', r'\betf\b|\bfund\b|ishares|spdr|proshares|direxion|invesco|vanguard|\bindex\b|\btrust\b(?!.*(bank|realty))'),
                ('warrant', r'\bwarrants?\b'), ('unit', r'\bunits?\b'), ('rights', r'\brights?\b'), ('preferred', r'preferred|\bpfd\b|depositary shares? each representing'),
                ('note / bond', r'\bnotes? due\b|\bdebentures?\b|\bbonds?\b')]

def now(): return datetime.now(ET)
def log(*a): print(now().strftime('%H:%M:%S'), *a, flush=True)
def epoch(t):
    if not t: return None
    try: return datetime.fromisoformat(re.sub(r'(\.\d{6})\d+', r'\1', t.replace('Z', '+00:00'))).timestamp()
    except Exception: return None

# ------------------------------------------------------------------ market data client
class Data:
    def __init__(self, key, secret, http=None):
        self.h = {'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': secret}
        self.http = http or requests.Session(); self.calls = Counter(); self.errors = Counter(); self.last_ok = {}

    def get(self, path, params, tag):
        r = None
        for i in range(5):
            try:
                r = self.http.get(DATA + path, headers=self.h, params=params, timeout=30)
            except Exception as e:
                self.errors[tag] += 1; time.sleep(1 + i); continue
            self.calls[tag] += 1
            if r.status_code == 429: self.errors['rate_limit'] += 1; time.sleep(3 + 3 * i); continue
            if r.status_code >= 500: self.errors[tag] += 1; time.sleep(1 + i); continue
            break
        if r is not None and r.ok: self.last_ok[tag] = time.time()
        elif r is not None: self.errors[tag] += 1
        return r

    def plan(self):
        """real-time SIP only if the account's data plan allows it"""
        r = self.get('/v2/stocks/quotes/latest', dict(symbols='SPY', feed='sip'), 'plan')
        return bool(r is not None and r.ok)

    def snapshots(self, syms, feed):
        out = {}
        for i in range(0, len(syms), 500):
            r = self.get('/v2/stocks/snapshots', dict(symbols=','.join(syms[i:i + 500]), feed=feed), 'snapshots')
            if r is None or not r.ok: continue
            d = r.json() or {}
            if isinstance(d.get('snapshots'), dict): d = d['snapshots']
            out.update({k: v for k, v in d.items() if isinstance(v, dict)})
        return out

    def bars(self, syms, tf, start, end, feed, adjustment='raw'):
        out = defaultdict(list)
        for i in range(0, len(syms), 100):
            tok = None
            while True:
                p = dict(symbols=','.join(syms[i:i + 100]), timeframe=tf, start=start.isoformat(), end=end.isoformat(), limit=10000, feed=feed, adjustment=adjustment)
                if tok: p['page_token'] = tok
                r = self.get('/v2/stocks/bars', p, 'bars_' + tf)
                if r is None or not r.ok: break
                j = r.json()
                for s, L in (j.get('bars') or {}).items(): out[s].extend(L)
                tok = j.get('next_page_token')
                if not tok: break
        return out

    def quotes(self, syms, feed):
        out = {}
        for i in range(0, len(syms), 200):
            r = self.get('/v2/stocks/quotes/latest', dict(symbols=','.join(syms[i:i + 200]), feed=feed), 'quotes')
            if r is not None and r.ok: out.update(r.json().get('quotes') or {})
        return out

    def news(self, start, pages=10):
        items, tok = [], None
        for _ in range(pages):
            p = dict(start=start.isoformat(), limit=50, sort='desc', include_content='false', exclude_contentless='true')
            if tok: p['page_token'] = tok
            r = self.get('/v1beta1/news', p, 'news')
            if r is None or not r.ok: break
            j = r.json(); items += j.get('news') or []
            tok = j.get('next_page_token')
            if not tok: break
        return items

def to_bar(b):
    t = epoch(b['t']); d = datetime.fromtimestamp(t, ET)
    return Bar(int(t), d.hour * 60 + d.minute, b['o'], b['h'], b['l'], b['c'], b['v'])

# ------------------------------------------------------------------ GitHub: config, control, publishing
def gh_file(path, ref='main'):
    tok = os.environ.get('GH_TOKEN')
    try:
        if tok:
            r = requests.get(f'https://api.github.com/repos/{REPO}/contents/{path}?ref={ref}', headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github.raw'}, timeout=15)
        else:
            r = requests.get(f'https://raw.githubusercontent.com/{REPO}/{ref}/{path}?t={int(time.time())}', timeout=15)
        return r.json() if r.ok else None
    except Exception: return None

def publish(files):
    os.makedirs(OUT, exist_ok=True)
    for name, obj in files.items():
        tmp = f'{OUT}/{name}.tmp'
        with open(tmp, 'w') as f: json.dump(obj, f, separators=(',', ':'), default=str)
        os.replace(tmp, f'{OUT}/{name}')
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return True
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    try:
        subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', BRANCH, OUT], check=True)
        subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', 'city'], check=True)
        subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{REPO}.git', BRANCH], check=True, timeout=90, capture_output=True)
        return True
    except Exception as e:
        log('publish failed', str(e)[:160]); return False

def notify(title, msg):
    if not NTFY: return
    try: requests.post(f'https://ntfy.sh/{NTFY}', data=msg.encode(), headers={'Title': title}, timeout=10)
    except Exception: pass

def relay():
    tok = os.environ.get('GH_TOKEN')
    if not tok: return
    try:
        r = requests.post(f'https://api.github.com/repos/{REPO}/actions/workflows/city.yml/dispatches', headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json'},
                          json={'ref': 'main'}, timeout=20)
        log('relay', r.status_code)
    except Exception as e: log('relay failed', e)

# ------------------------------------------------------------------ the engine
class Engine:
    def __init__(self, data, broker, cfg_over=None, clock=None):
        self.D, self.B = data, broker
        self.cfg = V.merge(V.DEFAULTS, cfg_over or {})
        self.clock = clock or now
        self.day = None; self.events = []; self.history = []; self.news_seen = {}; self.prev_status = {}
        self.bars1 = {}; self.health = {}; self.paper = dict(verified=False, reason='not checked yet'); self.plan_sip = False
        self.coverage = {}; self.charts = {}; self.traded_today = set(); self.pending = {}
        self.control = 'on'; self.cfg_loaded_at = 0; self.curve = V.default_curve; self.mcap = {}

    # ---------------- logging
    def ev(self, kind, **k):
        e = dict(t=self.clock().isoformat(timespec='seconds'), kind=kind, **k); self.events.append(e)
        if len(self.events) > 3000: self.events = self.events[-3000:]
        return e

    # ---------------- once a day
    def load_config(self, force=False):
        if not force and time.time() - self.cfg_loaded_at < 300: return
        c = gh_file('city_config.json') or {}
        self.cfg = V.merge(V.DEFAULTS, c); self.cfg_loaded_at = time.time()
        ctl = gh_file('control.json') or {}
        city = str(ctl.get('city', 'on')).lower(); allb = str(ctl.get('trading', 'on')).lower()
        mode = 'stop' if 'stop' in (city, allb) else 'pause' if 'pause' in (city, allb) else 'on'
        if city not in ('on', 'pause', 'stop'): mode = 'pause'                  # a typo fails safe
        if mode != self.control: self.ev('control', mode=mode, source='control.json')
        self.control = mode

    def daily_setup(self):
        t0 = time.time(); U = self.cfg['universe']
        self.plan_sip = self.D.plan()
        assets = []
        try:
            r = self.B._req('GET', '/v2/assets', params=dict(status='active', asset_class='us_equity'))
            assets = r.json() if r is not None and r.ok else []
        except Exception as e: log('assets failed', e)
        cov, uni, names = {}, [], {}
        for a in assets:
            s, nm = a.get('symbol', ''), (a.get('name') or '')
            if a.get('exchange') not in U['exchanges']: cov[s] = 'exchange not in list (' + str(a.get('exchange')) + ')'; continue
            if not a.get('tradable'): cov[s] = 'not tradable at Alpaca'; continue
            if not s.isalpha(): cov[s] = 'share class / preferred / warrant symbol'; continue
            why = next((w for w, rx in NAME_EXCLUDE if re.search(rx, nm.lower())), None)
            if why: cov[s] = 'not a common stock: ' + why; continue
            uni.append(s); names[s] = nm[:60]
        self.assets = {a['symbol']: a for a in assets}
        self.names = names
        # daily history (complete SIP, known before today) for prior close, levels, ATR and average volume
        today = self.clock().date()
        D = self.D.bars(uni, '1Day', datetime.combine(today - timedelta(days=45), datetime.min.time(), ET),
                        datetime.combine(today, datetime.min.time(), ET), 'sip', 'split')
        self.daily = {}
        for s in uni:
            L = [b for b in D.get(s, []) if datetime.fromisoformat(b['t'].replace('Z', '+00:00')).astimezone(ET).date() < today]
            if len(L) < 15: cov[s] = 'less than 15 days of trading history'; continue
            last = L[-1]; prev = L[-15:-1]
            trs = [max(b['h'], p['c']) - min(b['l'], p['c']) for p, b in zip(L[-15:-1], L[-14:])]
            adv = sum(b['v'] for b in L[-14:]) / 14; advd = sum(b['v'] * b['c'] for b in L[-14:]) / 14
            self.daily[s] = dict(prior_close=last['c'], prior_high=last['h'], prior_low=last['l'], high20=max(b['h'] for b in L[-20:]),
                                 low20=min(b['l'] for b in L[-20:]), atr14=sum(trs) / len(trs), adv=adv, adv_dollars=advd)
        self.universe = []
        for s in uni:
            d = self.daily.get(s)
            if not d: continue
            p = d['prior_close']
            if p < U['min_price']: cov[s] = f"price under ${U['min_price']}"; continue
            if U['max_price'] and p > U['max_price']: cov[s] = f"price over ${U['max_price']}"; continue
            if d['adv_dollars'] < U['min_avg_dollar_volume']: cov[s] = f"avg dollar volume under ${U['min_avg_dollar_volume'] / 1e6:g}M"; continue
            if U['min_atr_pct'] and d['atr14'] / p * 100 < U['min_atr_pct']: cov[s] = f"daily ATR under {U['min_atr_pct']}%"; continue
            self.universe.append(s)
        self.coverage = dict(day=today.isoformat(), listed=len(assets), common_stocks=len(uni), eligible=len(self.universe),
                             excluded_counts=dict(Counter(re.sub(r'\(.*\)', '', v).strip() for v in cov.values())), excluded=cov,
                             filters=U, market_cap_note='market cap filters use SEC share counts and only apply where a count exists')
        # volume curve measured on SPY over the last 10 sessions
        try:
            S = self.D.bars(['SPY'], '1Min', datetime.combine(today - timedelta(days=16), datetime.min.time(), ET),
                            datetime.combine(today, datetime.min.time(), ET), 'sip').get('SPY', [])
            prof = defaultdict(list)
            for b in S: x = to_bar(b); prof[x.m].append(x.v)
            self.curve = V.curve_from_profile({m: sum(v) / len(v) for m, v in prof.items()})
        except Exception as e: log('curve failed', e)
        self.bars1 = {}; self.charts = {}; self.traded_today = set(); self.prev_status = {}
        self.ev('day_start', listed=len(assets), eligible=len(self.universe), feed=self.feed_label(), seconds=round(time.time() - t0))
        log('universe', len(self.universe), 'of', len(assets), round(time.time() - t0), 's')

    def feed_label(self):
        return dict(realtime=True, complete=True, label='Real-time SIP (all US exchanges)') if self.plan_sip else \
               dict(realtime=False, complete=True, label='Full market, 15-min delayed (SIP) + real-time IEX quotes (one exchange)')

    # ---------------- each minute
    def cycle(self):
        t0 = time.time(); nw = self.clock(); m = nw.hour * 60 + nw.minute; today = nw.date()
        self.load_config()
        cal = self.calendar(today)
        sess = V.session(m, nw.weekday(), holiday=cal is None)
        close_m = cal['close_m'] if cal else V.RTH_CLOSE
        if sess == 'regular' and m >= close_m: sess = 'afterhours'
        F = self.feed_label(); snap_feed = 'sip' if self.plan_sip else 'delayed_sip'
        H = dict(session=sess, feed=F, cycle_started=nw.isoformat(timespec='seconds'))
        # account / paper verification
        acct = None
        try: acct = self.B.verify(); self.paper = dict(verified=True, account_suffix=str(acct.get('account_number', ''))[-4:], checked=nw.isoformat(timespec='seconds'))
        except Exception as e: self.paper = dict(verified=False, reason=str(e)[:160])
        # 1. whole-market snapshot
        syms = self.universe + [s for s in CONTEXT_ETFS if s not in self.universe]
        snap = self.D.snapshots(syms, snap_feed)
        H['snapshot'] = dict(requested=len(syms), returned=len(snap), feed=snap_feed)
        rows, breadth, missing = {}, Counter(), 0
        for s in self.universe:
            sn = snap.get(s)
            if not sn: missing += 1; continue
            lt, db, mb = sn.get('latestTrade') or {}, sn.get('dailyBar') or {}, sn.get('minuteBar') or {}
            px = lt.get('p') or mb.get('c') or db.get('c'); d = self.daily[s]
            if not px: missing += 1; continue
            bar_day = datetime.fromisoformat(db['t'].replace('Z', '+00:00')).astimezone(ET).date() if db.get('t') else None
            v = int(db.get('v') or 0) if bar_day == today else 0
            chg = (px / d['prior_close'] - 1) * 100
            breadth['up' if chg > 0.05 else 'down' if chg < -0.05 else 'flat'] += 1
            rv = v / (d['adv'] * (self.curve(m) if m >= V.RTH_OPEN else V.default_curve(m))) if d['adv'] and v else None
            hi = db.get('h') if bar_day == today else None; lo = db.get('l') if bar_day == today else None
            rows[s] = dict(px=px, chg=chg, v=v, dv=v * px, rv=rv, hi=hi, lo=lo, tt=epoch(lt.get('t')))
        H['snapshot']['no_data'] = missing
        newest = max((r['tt'] or 0 for r in rows.values()), default=0)
        H['data_age_s'] = round(nw.timestamp() - newest) if newest else None
        # 2. candidate lists (what was found, and why)
        lists = V.candidate_lists(rows, self.daily, m, self.cfg)
        cand = set().union(*lists.values())
        mine = self.city_book(nw)
        pre = V.prerank(cand, rows)
        deep = list(dict.fromkeys(list(mine['qty']) + pre[:self.cfg['candidates']['deep_scan']]))
        # 3. minute bars for the deep list (SIP: real time on the paid plan, otherwise it ends 16 minutes ago)
        self.update_bars(deep, nw)
        q_feed = 'sip' if self.plan_sip else 'iex'
        quotes = self.D.quotes(deep, q_feed) if deep else {}
        # 4. news
        groups = self.update_news(nw)
        # 5. features, both sides, catalyst, rank
        out = []
        for s in deep:
            B = self.bars1.get(s) or []
            if not B: continue
            d = self.daily.get(s) or {}
            qt = quotes.get(s) or {}
            qa = nw.timestamp() - epoch(qt.get('t')) if qt.get('t') else None
            q = dict(bid=qt.get('bp'), ask=qt.get('ap'), age=qa) if qt else None
            f = V.features(s, B, B[-1].m, d.get('prior_close'), d.get('adv'), self.curve, q, d, self.cfg)
            if not f: continue
            cat = V.catalyst_for(s, groups)
            eL = V.evaluate(f, B, 1, self.cfg, cat); eS = V.evaluate(f, B, -1, self.cfg, cat)
            # data warnings the rules can't see from bars alone
            dw = []
            bar_age = nw.timestamp() - B[-1].t - 60
            if sess == 'regular' and self.plan_sip and bar_age > 300 and (d.get('adv') or 0) > 500_000: dw.append('no trades for 5+ minutes: possible halt')
            if q and f['mid'] and abs(f['mid'] / f['price'] - 1) > (0.03 if self.plan_sip else 0.08): dw.append('quote and last price disagree')
            if not self.plan_sip: dw.append('chart data 15 min delayed; spread from IEX only')
            if cat['negative']: dw.append('negative news: ' + ', '.join(cat['negative']))
            sc, why, best = V.rank_score(f, eL, eS, cat)
            mc = self.market_cap(s, f['price'])
            row = dict(sym=s, name=self.names.get(s, ''), f=slim(f), long=eL, bear=eS, score=sc, why=why, catalyst=cat, data_warnings=dw,
                       lists=[k for k, v in lists.items() if s in v], quote_age_s=None if qa is None else round(qa), bar_age_s=round(bar_age),
                       market_cap=mc, status=best['status'], side=best['side'])
            U = self.cfg['universe']
            if mc and ((U['min_market_cap'] and mc < U['min_market_cap']) or (U['max_market_cap'] and mc > U['max_market_cap'])):
                row['status'] = 'rejected'; row['why'].append('outside market-cap filter')
            out.append(row)
            for side, e in ((1, eL), (-1, eS)):
                key = (s, side); prev = self.prev_status.get(key)
                if prev != e['status'] and (e['status'] in ('confirmed', 'rejected', 'extended') or prev == 'confirmed'):
                    self.ev('signal', sym=s, side='long' if side > 0 else 'bearish', status=e['status'], prev=prev, level=e['level_name'],
                            price=f['price'], reasons=e['reasons'], warnings=e['warnings'], checks=[(c['name'], c['ok']) for c in e['checks']])
                self.prev_status[key] = e['status']
            self.charts[s] = chart_rows(B)
        out.sort(key=lambda r: -r['score'])
        # 6. market context
        etf = {}
        for s in CONTEXT_ETFS:
            sn = snap.get(s) or {}; lt, db, pb = sn.get('latestTrade') or {}, sn.get('dailyBar') or {}, sn.get('prevDailyBar') or {}
            px = lt.get('p') or db.get('c')
            bar_day = datetime.fromisoformat(db['t'].replace('Z', '+00:00')).astimezone(ET).date() if db.get('t') else None
            ref = pb.get('c') if bar_day == today else db.get('c')
            if px and ref: etf[s] = dict(chg_pct=round((px / ref - 1) * 100, 2), price=px, vwap=db.get('vw') if bar_day == today else None,
                                         above_vwap=(px > db['vw']) if bar_day == today and db.get('vw') else None, t=lt.get('t'))
        ctx = V.market_context(etf, dict(breadth))
        # 7. paper trading
        risk = self.trade(out, acct, sess, m, nw, cal, F, mine)
        H.update(calls=dict(self.D.calls), errors=dict(self.D.errors), last_ok={k: datetime.fromtimestamp(v, ET).isoformat(timespec='seconds') for k, v in self.D.last_ok.items()},
                 paper=self.paper, cycle_seconds=round(time.time() - t0, 1), deep_scan=len(deep), candidates=len(cand),
                 stale=self.is_stale(sess, H.get('data_age_s')))
        self.health = H
        top = [r for r in out][:60]
        city = dict(updated=nw.isoformat(timespec='seconds'), day=today.isoformat(), session=sess, early_close=cal and cal['close_m'] < V.RTH_CLOSE,
                    feed=F, health=H, context=ctx, lists={k: sorted(v, key=lambda s: -rows[s]['dv'])[:50] for k, v in lists.items()},
                    list_counts={k: len(v) for k, v in lists.items()}, candidates=top, risk=risk, config=self.cfg,
                    coverage=dict((k, v) for k, v in self.coverage.items() if k != 'excluded'), control=self.control)
        newsj = dict(updated=city['updated'], source='Alpaca news (Benzinga wire)', items=[slim_news(g) for g in groups[:150]])
        files = {'city.json': city, 'charts.json': dict(updated=city['updated'], delayed=not self.plan_sip, ema=self.cfg['signals']['chart_emas'], syms=self.charts),
                 'news.json': newsj, 'events.json': dict(day=today.isoformat(), events=self.events[-1500:]), 'history.json': dict(trades=self.history[-2000:])}
        if not getattr(self, '_cov_pub', None) == today:
            files['coverage.json'] = self.coverage; self._cov_pub = today
        publish(files)
        return city

    def is_stale(self, sess, age):
        if sess not in ('premarket', 'regular') or age is None: return None
        lim = self.cfg['feed']['max_bar_age_s'] if self.plan_sip else 25 * 60
        return age > lim

    def calendar(self, d):
        if getattr(self, '_cal', (None,))[0] == d: return self._cal[1]
        info = None
        try:
            r = self.B._req('GET', '/v2/calendar', params=dict(start=d.isoformat(), end=d.isoformat()))
            j = r.json() if r is not None and r.ok else []
            if j and j[0].get('date') == d.isoformat():
                h, mi = j[0]['close'].split(':'); info = dict(close_m=int(h) * 60 + int(mi))
        except Exception: info = dict(close_m=V.RTH_CLOSE)
        self._cal = (d, info); return info

    def update_bars(self, syms, nw):
        start_day = datetime.combine(nw.date(), datetime.min.time(), ET) + timedelta(hours=4)
        end = nw.astimezone(timezone.utc) - (timedelta(0) if self.plan_sip else timedelta(minutes=16))
        if end <= start_day: return
        need_full = [s for s in syms if s not in self.bars1]
        have = [s for s in syms if s in self.bars1]
        if need_full:
            got = self.D.bars(need_full, '1Min', start_day, end, 'sip')
            for s in need_full: self.bars1[s] = [x for x in map(to_bar, got.get(s, [])) if x.t + 60 <= end.timestamp()]
        if have:
            since = min((self.bars1[s][-1].t if self.bars1[s] else start_day.timestamp()) for s in have)
            since = max(since, end.timestamp() - 30 * 60)                          # late prints older than 30 min are ignored
            got = self.D.bars(have, '1Min', datetime.fromtimestamp(since, timezone.utc), end, 'sip')
            for s in have:
                L = self.bars1[s]
                new = [x for x in map(to_bar, got.get(s, [])) if x.t + 60 <= end.timestamp()]
                L = [b for b in L if b.t < (new[0].t if new else 10 ** 12)] + new if new else L
                self.bars1[s] = L

    def update_news(self, nw):
        first = not self.news_seen
        items = self.D.news(nw - timedelta(hours=36 if first else 2), pages=12 if first else 2)
        rec = nw.timestamp()
        for n in items:
            i = n.get('id')
            if i in self.news_seen: continue
            self.news_seen[i] = dict(id=i, t=epoch(n.get('created_at')), received=rec, received_note='at engine start' if first else 'live',
                                     h=(n.get('headline') or '')[:240], s=n.get('source') or '', u=n.get('url') or '',
                                     sy=[x for x in (n.get('symbols') or []) if x.isalpha()][:12], sm=(n.get('summary') or '')[:300])
        cut = nw.timestamp() - 48 * 3600
        self.news_seen = {k: v for k, v in self.news_seen.items() if (v['t'] or 0) > cut}
        prior_close = datetime.combine(nw.date() - timedelta(days=1), datetime.min.time(), ET).timestamp() + 16 * 3600
        return V.group_news(list(self.news_seen.values()), nw.timestamp(), prior_close)

    def market_cap(self, sym, px):
        if sym in self.mcap: return self.mcap[sym] and round(self.mcap[sym] * px)
        self.mcap[sym] = None
        ua = os.environ.get('SEC_UA')
        if not ua or len(self.mcap) > 400: return None
        try:
            if not hasattr(self, '_cik'):
                r = requests.get('https://www.sec.gov/files/company_tickers.json', headers={'User-Agent': ua}, timeout=20)
                self._cik = {v['ticker']: v['cik_str'] for v in r.json().values()} if r.ok else {}
            cik = self._cik.get(sym)
            if not cik: return None
            r = requests.get(f'https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/dei/EntityCommonStockSharesOutstanding.json', headers={'User-Agent': ua}, timeout=20)
            if r.ok:
                L = sorted(r.json().get('units', {}).get('shares', []), key=lambda x: x.get('end', ''))
                if L and L[-1]['val'] >= 200_000: self.mcap[sym] = L[-1]['val']
            time.sleep(0.15)
        except Exception: pass
        return self.mcap[sym] and round(self.mcap[sym] * px)

    # ---------------- the City's own book, from its orders at the broker (survives restarts)
    def city_book(self, nw):
        qty, cash, fills, opn = Counter(), Counter(), [], []
        if not self.paper.get('verified'): return dict(qty={}, cash={}, fills=[], open=[], orders=[])
        start = datetime.combine(nw.date(), datetime.min.time(), ET).astimezone(timezone.utc).isoformat()
        try: orders = self.B.orders('all', after=start)
        except Exception: orders = []
        flat = []
        for o in orders or []:
            if not str(o.get('client_order_id', '')).startswith('city-'): continue
            flat.append(o); flat += o.get('legs') or []
        for o in flat:
            fq = float(o.get('filled_qty') or 0); fp = float(o.get('filled_avg_price') or 0); sym = o['symbol']
            sgn = 1 if o['side'] == 'buy' else -1
            if fq:
                qty[sym] += sgn * fq; cash[sym] -= sgn * fq * fp
                if sgn < 0: cash[sym] -= V.sale_fees(nw.date(), fq, fp)
                fills.append(dict(sym=sym, side=o['side'], qty=fq, price=fp, t=o.get('filled_at'), id=o['id'], role=o.get('order_type') or o.get('type'), parent=o.get('client_order_id')))
            if o.get('status') in ('new', 'accepted', 'partially_filled', 'pending_new', 'held'): opn.append(o)
            if str(o.get('client_order_id', '')).startswith('city-entry'): self.traded_today.add(sym)
        return dict(qty={k: v for k, v in qty.items() if abs(v) > 1e-9}, cash=dict(cash), fills=fills, open=opn, orders=flat)

    def trade(self, rows, acct, sess, m, nw, cal, F, book):
        R = self.cfg['risk']
        eq = float(acct['equity']) if acct else 0.0; se = float(acct.get('last_equity') or eq) if acct else 0.0
        px = {r['sym']: r['f']['price'] for r in rows}
        try: pos = {p['symbol']: p for p in (self.B.positions() if self.paper.get('verified') else [])}
        except Exception: pos = {}
        for s in book['qty']:
            if s in pos: px[s] = float(pos[s].get('current_price') or px.get(s) or 0)
        city_pnl = sum(book['cash'].get(s, 0) for s in book['cash']) + sum(q * px.get(s, 0) for s, q in book['qty'].items())
        exposure_all = sum(abs(float(p.get('market_value') or 0)) for p in pos.values())
        flat_m = min(V.hhmm(R['flat_at']), (cal or {}).get('close_m', V.RTH_CLOSE) - 10)
        until_m = min(V.hhmm(R['entries_until']), (cal or {}).get('close_m', V.RTH_CLOSE) - 30)
        cfg = V.merge(self.cfg, {'risk': {'entries_until': f'{until_m // 60:02d}:{until_m % 60:02d}'}})
        # cancel entries that didn't fill in time (failed or partial fills are logged, never chased)
        for o in book['open']:
            if not str(o.get('client_order_id', '')).startswith('city-entry'): continue
            age = nw.timestamp() - (epoch(o.get('submitted_at')) or nw.timestamp())
            if age > R['entry_timeout_s']:
                self.B.cancel(o['id'])
                self.ev('order_cancel', sym=o['symbol'], reason='entry not filled in time', filled_qty=o.get('filled_qty'), qty=o.get('qty'),
                        result='partial fill' if float(o.get('filled_qty') or 0) > 0 else 'failed fill (no shares)')
        # time stop / stop switch: close the City's own shares
        if book['qty'] and ((sess == 'regular' and m >= flat_m) or self.control == 'stop'):
            for s, q in book['qty'].items():
                for o in book['open']:
                    if o['symbol'] == s: self.B.cancel(o['id'])
                ok, res, body = self.B.submit_exit(s, abs(q), 'sell' if q > 0 else 'buy', tag='flat')
                self.ev('exit', sym=s, qty=abs(q), why='time stop' if self.control != 'stop' else 'control.json stop', ok=ok, broker=str(res)[:200])
        ctx_base = dict(paper_verified=self.paper.get('verified'), market_open=sess == 'regular', feed_realtime=F['realtime'], feed_complete=F['complete'],
                        control=self.control, now_m=m, city_pnl_today=city_pnl, account_pnl_today=eq - se if acct else 0, start_equity=se, equity=eq,
                        open_positions=len(book['qty']) + sum(1 for o in book['open'] if str(o.get('client_order_id', '')).startswith('city-entry')),
                        exposure=sum(abs(q) * px.get(s, 0) for s, q in book['qty'].items()), daytrade_count=int(acct.get('daytrade_count') or 0) if acct else 0)
        global_blocks = V.entry_blocks(dict(ctx_base, quote_age_s=0, bar_age_s=0, side=1), cfg)
        proposals = []
        for r in rows:
            for side, e in ((1, r['long']), (-1, r['bear'])):
                if e['status'] != 'confirmed': continue
                f = r['f']; q_ok = r['quote_age_s']
                ctx = dict(ctx_base, quote_age_s=q_ok, bar_age_s=r['bar_age_s'], side=side, sym_open=r['sym'] in book['qty'],
                           sym_traded_today=r['sym'] in self.traded_today)
                blocks = V.entry_blocks(ctx, cfg) + [w for w in r['data_warnings'] if 'halt' in w or 'disagree' in w]
                bid = f.get('mid') and f['mid'] * (1 - (f['spread_pct'] or 0) / 200); ask = f.get('mid') and f['mid'] * (1 + (f['spread_pct'] or 0) / 200)
                lim = V.limit_price(side, bid, ask, cfg) if bid and ask else None
                sz = V.size_position(lim or f['price'], e['stop'], eq or se, se, max(ctx_base['exposure'], 0), float(acct.get('buying_power') or 0) if acct else 0, side, cfg)
                if not sz['shares']: blocks.append(sz['reason'])
                P = dict(sym=r['sym'], side='long' if side > 0 else 'bearish', thesis=f"{e['level_name'].replace('_', ' ')} {'breakout' if side > 0 else 'breakdown'} confirmed: " + '; '.join(c['detail'] for c in e['checks'][:3]),
                         trigger=round(e['trigger'], 4), limit=lim, stop=e['stop'], target=e['target'], target_logic=f"{cfg['signals']['target_r']}R (risk x {cfg['signals']['target_r']})",
                         shares=sz.get('shares', 0), risk_dollars=sz.get('risk_dollars'), cost=sz.get('cost'), spread_pct=f['spread_pct'], data_time=datetime.fromtimestamp(f['t'] + 60, ET).isoformat(timespec='seconds'),
                         blocks=blocks, decision='ENTER' if not blocks else 'WAIT / NO TRADE')
                key = (r['sym'], side, tuple(blocks))
                if blocks:
                    if self.prev_status.get(('block',) + key[:2]) != key[2]: self.ev('no_trade', **P)
                    self.prev_status[('block',) + key[:2]] = key[2]
                else:
                    ok, res, body = self.B.submit_bracket(r['sym'], P['shares'], 'buy' if side > 0 else 'sell', lim, e['stop'], e['target'])
                    P['order'] = dict(ok=ok, id=res.get('id'), status=res.get('status'), message=res.get('message'))
                    self.ev('order', **P); self.traded_today.add(r['sym'])
                    if ok:
                        ctx_base['open_positions'] += 1; ctx_base['exposure'] += P['shares'] * lim
                        notify('VANTEX City paper order', f"{P['side']} {P['shares']} {r['sym']} limit {lim} stop {e['stop']} target {e['target']}")
                proposals.append(P)
        # completed City trades today -> history
        self.record_history(book, nw)
        lim_d = se * R['max_daily_loss_pct'] / 100
        return dict(equity=eq, start_equity=se, account_pnl_today=round(eq - se, 2) if acct else None, city_pnl_today=round(city_pnl, 2),
                    daily_loss_limit=round(lim_d, 2), locked=city_pnl <= -lim_d or (eq - se) <= -lim_d, control=self.control,
                    daytrade_count=ctx_base['daytrade_count'], open_positions=[dict(sym=s, qty=q, price=px.get(s), unrealized=round(q * px.get(s, 0) + book['cash'].get(s, 0), 2))
                                                                                for s, q in book['qty'].items()],
                    other_bots_exposure=round(exposure_all - ctx_base['exposure'], 2), open_orders=[dict(sym=o['symbol'], side=o['side'], type=o.get('type'), qty=o.get('qty'),
                    limit=o.get('limit_price'), stop=o.get('stop_price'), status=o['status']) for o in book['open']],
                    fills=book['fills'], proposals=proposals, entry_blocks=global_blocks, limits=R)

    def record_history(self, book, nw):
        by = defaultdict(list)
        for f in book['fills']: by[f['sym']].append(f)
        day = nw.date().isoformat()
        for s, L in by.items():
            if s in book['qty']: continue                                      # still open
            buys = sum(f['qty'] * f['price'] for f in L if f['side'] == 'buy'); sells = sum(f['qty'] * f['price'] for f in L if f['side'] == 'sell')
            q = sum(f['qty'] for f in L if f['side'] == 'buy')
            fees = sum(V.sale_fees(nw.date(), f['qty'], f['price']) for f in L if f['side'] == 'sell')
            key = f'{day}:{s}'
            if any(h['key'] == key for h in self.history): continue
            first = min(L, key=lambda f: f['t'] or '')
            self.history.append(dict(key=key, day=day, sym=s, side='long' if first['side'] == 'buy' else 'short', qty=q, pnl=round(sells - buys - fees, 2), fees=round(fees, 4),
                                     entry=first['price'], exit=max(L, key=lambda f: f['t'] or '')['price'], fills=len(L)))
            self.ev('trade_closed', **self.history[-1])

def slim(f):
    out = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in f.items() if k != 'levels'}
    out['levels'] = {k: round(v, 4) for k, v in f['levels'].items()}
    return out

def slim_news(g):
    return dict(t=datetime.fromtimestamp(g['t'], ET).isoformat(timespec='seconds') if g['t'] else None, received=datetime.fromtimestamp(g['received'], ET).isoformat(timespec='seconds'),
                received_note=g.get('received_note'), h=g['h'], s=g.get('s'), sources=g['sources'], u=g.get('u'), sy=g['sy'], types=g['types'], negative=g['negative'],
                promo=g['promo'], roundup=g['roundup'], rumor=g['rumor'], stale=g['stale'], confidence=g['confidence'], verified=g['verified'], repeats=g['repeats'])

def chart_rows(B):
    return [[b.t, round(b.o, 4), round(b.h, 4), round(b.l, 4), round(b.c, 4), int(b.v)] for b in B[-600:]]

def restore(engine):
    """pick up today's log and the trade history from the last published files"""
    try:
        h = requests.get(f'https://raw.githubusercontent.com/{REPO}/{BRANCH}/history.json?t={int(time.time())}', timeout=15)
        if h.ok: engine.history = h.json().get('trades', [])
        e = requests.get(f'https://raw.githubusercontent.com/{REPO}/{BRANCH}/events.json?t={int(time.time())}', timeout=15)
        if e.ok and e.json().get('day') == now().date().isoformat(): engine.events = e.json().get('events', [])
    except Exception: pass

def main():
    import city_broker as CB
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    try: broker = CB.PaperBroker(key, sec)
    except CB.NotPaper as e: sys.exit(f'Refusing to run: {e}')
    E = Engine(Data(key, sec), broker); restore(E); E.load_config(force=True)
    once = '--once' in sys.argv; t0 = time.time()
    while True:
        nw = now(); m = nw.hour * 60 + nw.minute
        if E.day != nw.date() and 235 <= m < 1200 and nw.weekday() < 5:
            try: E.daily_setup(); E.day = nw.date(); E.events = [e for e in E.events if e['t'][:10] == nw.date().isoformat()]
            except Exception: log('daily setup failed', traceback.format_exc()[-600:]); time.sleep(60); continue
        if E.day == nw.date() and 240 <= m < 1200:
            try: E.cycle()
            except Exception: log('cycle failed', traceback.format_exc()[-800:]); E.ev('engine_error', error=traceback.format_exc()[-300:])
        elif m % 10 == 0:
            publish({'city.json': dict(updated=nw.isoformat(timespec='seconds'), session='closed' if nw.weekday() >= 5 else V.session(m, nw.weekday()),
                                       idle=True, note='The City engine scans 4:00 AM - 8:00 PM ET on market days.', feed=E.feed_label(), health=E.health)})
        if once: break
        if time.time() - t0 > MAX_RUN_S: relay(); break
        time.sleep(max(5, 60 - time.time() % 60))

if __name__ == '__main__':
    main()
