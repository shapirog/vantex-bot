"""Replay tests: runs a simulated session chronologically, checks that decisions never use later data (look-ahead canary),
that fills are not assumed, and that results include costs."""
import copy, os, sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pytest
import city_replay as CR
import city_engine as CE
from test_engine import Market, Resp, TODAY, NOW, iso, at

class RMarket(Market):
    def get(self, url, headers=None, params=None, timeout=None):
        path = urlparse(url).path; p = params or {}
        if path == '/v2/stocks/quotes':                                     # last quote before 'end', from the bars
            s = p['symbols']; en = datetime.fromisoformat(p['end']).timestamp()
            L = [b for b in self.minute.get(s, []) if datetime.fromisoformat(b['t'].replace('Z', '+00:00')).timestamp() + 60 <= en]
            if not L: return Resp(200, dict(quotes={}))
            c = L[-1]['c']
            return Resp(200, dict(quotes={s: [dict(bp=round(c - 0.01, 2), ap=round(c + 0.01, 2), t=iso(en - 5))]}))
        if path == '/v2/stocks/bars':
            p = dict(p); p['feed'] = 'sip'; self.paid = True
        return super().get(url, headers, p, timeout)

def make(monkeypatch, market):
    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith('/v2/assets'): return Resp(200, market.assets)
        if url.endswith('/v2/calendar'): return Resp(200, [dict(date=TODAY.isoformat(), open='09:30', close='16:00')])
        return Resp(404, {})
    monkeypatch.setattr(CR.requests, 'get', fake_get)
    return CR.Replay(CE.Data('PK1', 'x', http=market), 'PK1', 'x', {})

def test_replay_runs_and_trades_with_costs(monkeypatch):
    M = RMarket(); RP = make(monkeypatch, M)
    res = RP.run_day(TODAY, 16 * 60, frames=True, state=dict(equity=2500.0, daytrades=[], pdt=False))
    assert res['frames'] and res['frames'][0]['m'] < 570                  # premarket frames exist
    ent = [e for e in res['events'] if e['kind'] == 'entry']
    assert ent and ent[0]['sym'] == 'ACME' and ent[0]['side'] == 'long'
    assert not any(e['kind'] == 'entry' and e['side'] == 'short' for e in res['events'])   # shorts off by default
    t = res['trades'][0]
    assert t['fees'] >= 0 and t['why'] in ('stop', 'stop-gap', 'target', 'time', 'last-bar')
    assert t['m_in'] >= 9 * 60 + 35

def test_no_look_ahead_canary(monkeypatch):
    """Replace every bar after 10:00 with absurd prices. Every frame up to 10:00 must be identical."""
    M1 = RMarket(); r1 = make(monkeypatch, M1).run_day(TODAY, 16 * 60, frames=True, state=dict(equity=2500.0, daytrades=[], pdt=False))
    M2 = RMarket()
    cut = at(10, 0)
    for s, L in M2.minute.items():
        for b in L:
            if datetime.fromisoformat(b['t'].replace('Z', '+00:00')).timestamp() >= cut:
                b.update(o=b['o'] * 3, h=b['h'] * 3, l=b['l'] * 3, c=b['c'] * 3, v=b['v'] * 50)
    r2 = make(monkeypatch, M2).run_day(TODAY, 16 * 60, frames=True, state=dict(equity=2500.0, daytrades=[], pdt=False))
    f1 = [f for f in r1['frames'] if f['m'] <= 600]; f2 = [f for f in r2['frames'] if f['m'] <= 600]
    assert f1 and f1 == f2

def test_failed_fill_when_price_runs_away(monkeypatch):
    import vantex_core as V
    from vantex_core import Bar
    nb = [Bar(0, 600, 10.5, 10.6, 10.45, 10.55, 1000)]
    assert V.sim_limit_fill(1, 10.30, nb)[0] == 0

def test_summary_reports_required_metrics():
    days = [dict(day='2026-01-02', pnl=-10.0, trades=[dict(pnl=-10.0, fees=0.01, R=-1.0, setup='or_high:long', why='stop', m_in=600, m_out=610, exposure=500)],
                 signals={'long:confirmed': 1}, blocks={'spread too wide at decision': 2}),
            dict(day='2026-01-05', pnl=20.0, trades=[dict(pnl=20.0, fees=0.02, R=2.0, setup='or_high:long', why='target', m_in=600, m_out=640, exposure=500)],
                 signals={'long:confirmed': 1}, blocks={})]
    S = CR.summarize(days, 't')
    for k in ('trades', 'net_pnl', 'max_drawdown', 'worst_day', 'avg_exposure', 'R_distribution', 'by_setup', 'rejected_or_blocked', 'losing_days', 'warning'):
        assert k in S, k
    assert S['net_pnl'] == 10.0 and S['max_drawdown'] == 10.0 and S['worst_day'] == ('2026-01-02', -10.0)

def test_parse_day_accepts_phone_formats():
    from datetime import date
    for x in ('2026-11-13', ' 2026-11-13 ', '2026\u201311\u201313', '2026/11/13', '11/13/2026', '11-13-2026'):
        assert CR.parse_day(x) == date(2026, 11, 13), x

def test_publish_first_call_without_files_does_not_commit(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(CR, 'OUT', str(tmp_path / 'out'))
    monkeypatch.setenv('GH_TOKEN', 'x'); monkeypatch.setenv('GITHUB_REPOSITORY', 'a/b')
    class R: returncode = 1
    monkeypatch.setattr(CR.subprocess, 'run', lambda cmd, **k: (calls.append(cmd), R())[1])
    CR.publish({})
    assert not any('commit' in c for c in calls)

def test_compare_variants_share_data(monkeypatch):
    M = RMarket(); RP = make(monkeypatch, M)
    data = RP.load_day(TODAY, 16 * 60)
    out = {k: RP.run_day(TODAY, 16 * 60, state=dict(equity=2500.0, daytrades=[], pdt=False), data=data, cfg=c) for k, c in CR.variant_configs(RP.cfg).items()}
    assert len(out['A_original']['trades']) >= 1                                # ACME breakout (+2% only)
    assert len(out['C_strong_volume']['trades']) == 0                          # +2% is not a strong mover
    assert RP.cfg['signals']['strong_only'] is False                           # the base config is untouched

def test_movers_get_their_own_news_and_are_reported(monkeypatch):
    M = RMarket(); RP = make(monkeypatch, M)
    asked = []
    orig = M.get
    def spy(url, headers=None, params=None, timeout=None):
        if urlparse(url).path == '/v1beta1/news' and (params or {}).get('symbols'): asked.append(params['symbols'])
        return orig(url, headers, params, timeout)
    M.get = spy
    res = RP.run_day(TODAY, 16 * 60, state=dict(equity=2500.0, daytrades=[], pdt=False))
    assert 'GAPR' in asked                                                     # a strong mover gets a news lookup by symbol
    g = [x for x in res['strong_seen'] if x['sym'] == 'GAPR']
    assert g and g[0]['chg'] >= 10 and g[0]['verified'] is False
    f = dict(chg_pct=40.0, rvol=8.0)
    c = RP.catalyst_at('GAPR', f, NOW.timestamp(), TODAY, datetime.combine(TODAY, datetime.min.time(), CR.ET).timestamp(), [])
    assert c['n'] >= 1 and c['verified'] is False and c['latest'].startswith('If You Invested')   # promo article is seen but is not a catalyst
