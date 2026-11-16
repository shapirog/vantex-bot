"""End-to-end engine tests against a simulated Alpaca (market data + paper broker). No network.
Covers: universe/exclusion records, candidate lists, confirmed long -> bracket paper order, bearish = watch-only,
delayed feed blocks entries, stale data blocks entries, pause control, daily-loss lockout, catalyst tagging."""
import json, math, os, sys, tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
import city_engine as CE
import city_broker as CB
import vantex_core as V

ET = ZoneInfo('America/New_York')
NOW = datetime(2026, 11, 16, 10, 15, 5, tzinfo=ET)
TODAY = NOW.date()

class Resp:
    def __init__(self, code, j): self.status_code, self._j, self.content = code, j, b'x'
    @property
    def ok(self): return 200 <= self.status_code < 300
    def json(self): return self._j

def iso(t): return datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def at(h, m, d=TODAY): return datetime(d.year, d.month, d.day, h, m, tzinfo=ET).timestamp()

class Market:
    """a small fake market: ACME breaks out of its opening range, BETA breaks down on offering news, GAPR is up 60% and
    extended, THIN is too illiquid, plus filler stocks and the context ETFs"""
    def __init__(self, paid=True, stale=False):
        self.paid, self.stale = paid, stale
        self.syms = ['ACME', 'BETA', 'GAPR', 'THIN'] + [f'FIL{c}' for c in 'ABCDEFGHIJ']
        self.assets = [dict(symbol=s, name=f'{s} Inc. Common Stock', exchange='NASDAQ', tradable=True, status='active') for s in self.syms]
        self.assets += [dict(symbol='XETF', name='Example Growth ETF', exchange='ARCA', tradable=True), dict(symbol='ABC.WS', name='ABC Warrants', exchange='NYSE', tradable=True)]
        self.assets += [dict(symbol=s, name=s + ' fund', exchange='ARCA', tradable=True) for s in V.INDEXES]
        self.prior = dict(ACME=10.0, BETA=20.0, GAPR=5.0, THIN=3.0)
        self.adv = dict(ACME=200_000, BETA=300_000, GAPR=400_000, THIN=2_000)
        self.minute = {s: self.make_minutes(s) for s in self.syms + ['SPY']}

    def make_minutes(self, s):
        B = []
        def add(h, m, o, hi, lo, c, v): B.append(dict(t=iso(at(h, m)), o=o, h=hi, l=lo, c=c, v=v))
        if s == 'ACME':
            for k in range(30): add(9, 0 + k, 10.0, 10.02, 9.98, 10.0, 200)
            for k in range(5): add(9, 30 + k, 10.0, 10.10, 9.95, 10.05, 4000)
            for k in range(33): mm = 35 + k; add(9 + mm // 60, mm % 60, 10.05, 10.08, 10.0, 10.06, 1500)
            add(10, 8, 10.07, 10.20, 10.06, 10.18, 20000)
            for k in range(6): add(10, 9 + k, 10.18, 10.22, 10.15, 10.18 + 0.004 * k, 5000)
        elif s == 'BETA':
            for k in range(5): add(9, 30 + k, 19.0, 19.05, 18.9, 18.95, 6000)
            for k in range(33): mm = 35 + k; add(9 + mm // 60, mm % 60, 18.95, 19.0, 18.92, 18.94, 2500)
            add(10, 8, 18.93, 18.94, 18.82, 18.84, 30000)
            for k in range(6): add(10, 9 + k, 18.84, 18.87, 18.80, 18.83 - 0.004 * k, 7000)
        elif s == 'GAPR':
            for k in range(45): mm = 30 + k; px = 7.0 + 0.03 * k; add(9 + mm // 60, mm % 60, px, px + 0.05, px - 0.02, px + 0.03, 9000)
        elif s == 'SPY':
            for d in range(1, 15):
                day = TODAY - timedelta(days=d)
                if day.weekday() >= 5: continue
                for k in range(390): mm = 570 + k; B.append(dict(t=iso(at(mm // 60, mm % 60, day)), o=600, h=600.1, l=599.9, c=600, v=50000))
            for k in range(45): mm = 570 + k; add(mm // 60, mm % 60, 600, 600.2, 599.8, 600.1, 60000)
        else:
            px = self.prior.get(s, 30.0)
            for k in range(45): mm = 570 + k; add(mm // 60, mm % 60, px, px + 0.02, px - 0.02, px, 300)
        return B

    def daily(self, s):
        p = self.prior.get(s, 30.0 if s not in V.SECTORS and s not in V.INDEXES else 100.0); a = self.adv.get(s, 100_000)
        out = []
        for d in range(40, 0, -1):
            day = TODAY - timedelta(days=d)
            if day.weekday() >= 5: continue
            out.append(dict(t=iso(at(0, 0, day) + 5 * 3600), o=p, h=p * 1.03 if s != 'ACME' else 10.5, l=p * 0.97, c=p, v=a))
        return out

    def last(self, s):
        L = self.minute.get(s)
        return L[-1] if L else None

    def get(self, url, headers=None, params=None, timeout=None):
        path = urlparse(url).path; p = params or {}
        syms = p.get('symbols', '').split(',') if p.get('symbols') else []
        if path == '/v2/stocks/quotes/latest':
            if p.get('feed') == 'sip' and not self.paid: return Resp(403, dict(message='subscription does not permit'))
            qt = {}
            for s in syms:
                b = self.last(s)
                if b: qt[s] = dict(bp=round(b['c'] - 0.01, 2), ap=round(b['c'] + 0.01, 2), t=iso(NOW.timestamp() - (3600 if self.stale else 2)))
            return Resp(200, dict(quotes=qt))
        if path == '/v2/stocks/snapshots':
            out = {}
            for s in syms:
                L = self.minute.get(s)
                if s in V.SECTORS or s in V.INDEXES or s == 'VIXY':
                    out[s] = dict(latestTrade=dict(p=101.0 if s in ('SPY', 'QQQ', 'IWM', 'XLK') else 99.5, t=iso(NOW.timestamp() - 3)), dailyBar=dict(t=iso(at(9, 30)), c=100.5, vw=100.2, v=1),
                                  prevDailyBar=dict(c=100.0)); continue
                if not L: continue
                tt = NOW.timestamp() - (2 * 3600 if self.stale else 3)
                if not self.paid: tt = NOW.timestamp() - 15 * 60
                out[s] = dict(latestTrade=dict(p=L[-1]['c'], t=iso(tt)), minuteBar=L[-1],
                              dailyBar=dict(t=iso(at(9, 30)), o=L[0]['o'], h=max(b['h'] for b in L), l=min(b['l'] for b in L), c=L[-1]['c'], v=sum(b['v'] for b in L)),
                              prevDailyBar=dict(c=self.prior.get(s, 30.0)))
            return Resp(200, out)
        if path == '/v2/stocks/bars':
            st = datetime.fromisoformat(p['start']).timestamp(); en = datetime.fromisoformat(p['end']).timestamp()
            if p.get('feed') == 'sip' and not self.paid and en > NOW.timestamp() - 15 * 60: return Resp(403, dict(message='recent SIP not permitted'))
            out = {}
            for s in syms:
                L = self.daily(s) if p['timeframe'] == '1Day' else self.minute.get(s, [])
                L = [b for b in L if st <= datetime.fromisoformat(b['t'].replace('Z', '+00:00')).timestamp() < en]
                if L: out[s] = L
            return Resp(200, dict(bars=out, next_page_token=None))
        if path == '/v1beta1/news':
            n = [dict(id=1, created_at=iso(NOW.timestamp() - 1200), headline='ACME Wins $40 Million Army Contract', source='benzinga', url='https://x/1', symbols=['ACME'], summary=''),
                 dict(id=2, created_at=iso(NOW.timestamp() - 900), headline='BETA Announces $15 Million Registered Direct Offering', source='benzinga', url='https://x/2', symbols=['BETA'], summary=''),
                 dict(id=3, created_at=iso(NOW.timestamp() - 600), headline='If You Invested $1000 In GAPR 5 Years Ago', source='benzinga', url='https://x/3', symbols=['GAPR'], summary='')]
            return Resp(200, dict(news=n, next_page_token=None))
        return Resp(404, {})

class Broker:
    def __init__(self, market, equity=2500.0, last_equity=2500.0, daytrades=0):
        self.m, self.orders, self.calls = market, [], []
        self.acct = dict(account_number='PA33TEST', status='ACTIVE', trading_blocked=False, account_blocked=False, equity=str(equity),
                         last_equity=str(last_equity), buying_power='5000', daytrade_count=daytrades)
    def request(self, method, url, headers=None, timeout=None, params=None, json=None):
        path = urlparse(url).path; self.calls.append((method, url))
        assert url.startswith('https://paper-api.alpaca.markets/')
        if path == '/v2/account': return Resp(200, self.acct)
        if path == '/v2/assets': return Resp(200, self.m.assets)
        if path == '/v2/calendar': return Resp(200, [dict(date=TODAY.isoformat(), open='09:30', close='16:00')])
        if path == '/v2/positions': return Resp(200, [])
        if path == '/v2/orders' and method == 'GET': return Resp(200, [])
        if path == '/v2/orders' and method == 'POST':
            o = dict(json, id=f'o{len(self.orders)}', status='accepted'); self.orders.append(o); return Resp(200, o)
        return Resp(404, {})

@pytest.fixture
def run(monkeypatch, tmp_path):
    monkeypatch.setattr(CE, 'OUT', str(tmp_path))
    monkeypatch.setattr(CE, 'gh_file', lambda path, ref='main': CTL.get(path))
    monkeypatch.setattr(CE.time, 'sleep', lambda s: None)
    monkeypatch.delenv('GH_TOKEN', raising=False); monkeypatch.delenv('SEC_UA', raising=False)
    def go(paid=True, stale=False, control=None, **bk):
        CTL.clear(); CTL['control.json'] = control or {'trading': 'on'}
        M = Market(paid, stale); BR = Broker(M, **bk)
        E = CE.Engine(CE.Data('PK1', 'x', http=M), CB.PaperBroker('PK1', 'x', session=BR), clock=lambda: NOW)
        E.load_config(force=True); E.daily_setup(); E.day = TODAY
        city = E.cycle()
        return E, BR, city, json.load(open(tmp_path / 'city.json'))
    return go
CTL = {}

def cand(city, s): return next(c for c in city['candidates'] if c['sym'] == s)

def test_universe_exclusions_are_recorded(run):
    E, BR, city, pub = run()
    ex = E.coverage['excluded']
    assert 'THIN' in ex and 'dollar volume' in ex['THIN']
    assert 'not a common stock' in ex['XETF'] and 'share class' in ex['ABC.WS']
    assert 'ACME' in E.universe and city['coverage']['eligible'] == len(E.universe)

def test_lists_and_ranking(run):
    E, BR, city, pub = run()
    assert 'GAPR' in city['lists']['gainers'] and 'BETA' in city['lists']['decliners']
    assert cand(city, 'ACME')['long']['status'] == 'confirmed'
    assert cand(city, 'GAPR')['long']['status'] in ('extended', 'watching', 'developing')
    assert cand(city, 'ACME')['score'] > cand(city, 'GAPR')['score']        # biggest % gainer is not ranked first

def test_confirmed_long_places_bracket_paper_order(run):
    E, BR, city, pub = run()
    assert len(BR.orders) == 1
    o = BR.orders[0]
    assert o['symbol'] == 'ACME' and o['side'] == 'buy' and o['order_class'] == 'bracket' and o['client_order_id'].startswith('city-entry')
    P = next(p for p in city['risk']['proposals'] if p['sym'] == 'ACME')
    assert P['decision'] == 'ENTER' and P['risk_dollars'] <= 2500 * 0.005 + 1e-9
    for k in ('thesis', 'trigger', 'stop', 'target', 'target_logic', 'shares', 'spread_pct', 'data_time'): assert P[k] is not None, k
    assert any(e['kind'] == 'order' for e in E.events)

def test_bearish_setup_is_watch_only(run):
    E, BR, city, pub = run()
    b = cand(city, 'BETA')
    assert b['bear']['status'] == 'confirmed'
    P = next(p for p in city['risk']['proposals'] if p['sym'] == 'BETA')
    assert P['decision'] == 'WAIT / NO TRADE' and any('short orders are off' in x for x in P['blocks'])
    assert all(o['symbol'] != 'BETA' for o in BR.orders)
    assert 'OFFERING' in b['catalyst']['negative']

def test_catalysts(run):
    E, BR, city, pub = run()
    assert cand(city, 'ACME')['catalyst']['verified'] and cand(city, 'ACME')['catalyst']['types'] == ['CONTRACT']
    g = cand(city, 'GAPR')['catalyst']
    assert not g['verified'] and g['text'] == 'no verified catalyst found'

def test_delayed_feed_blocks_entries(run):
    E, BR, city, pub = run(paid=False)
    assert BR.orders == []
    assert city['feed']['realtime'] is False and 'delayed' in city['feed']['label']
    assert any('delayed' in b for b in city['risk']['entry_blocks'])

def test_stale_data_blocks_entries(run):
    E, BR, city, pub = run(stale=True)
    assert BR.orders == []
    assert city['health']['stale'] is True

def test_pause_control(run):
    E, BR, city, pub = run(control={'trading': 'on', 'city': 'pause'})
    assert BR.orders == [] and any('paused' in b for b in city['risk']['entry_blocks'])

def test_daily_loss_lockout(run):
    E, BR, city, pub = run(equity=2450.0, last_equity=2500.0)
    assert BR.orders == [] and city['risk']['locked']

def test_pdt_limit(run):
    E, BR, city, pub = run(daytrades=3)
    assert BR.orders == [] and any('day-trade' in b for b in city['risk']['entry_blocks'])

def test_published_files(run, tmp_path):
    E, BR, city, pub = run()
    for f in ('city.json', 'charts.json', 'news.json', 'events.json', 'history.json', 'coverage.json'): assert (tmp_path / f).exists(), f
    assert pub['candidates'][0]['sym'] and 'ACME' in json.load(open(tmp_path / 'charts.json'))['syms']
