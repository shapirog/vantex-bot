"""Free-data check: runs end to end on the fake market, uses only IEX prints for decisions, and skips stocks IEX can't see."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import city_iexcheck as IX
import city_replay as CR
import city_engine as CE
from test_engine import Resp, TODAY
from test_replay import RMarket

def make(monkeypatch):
    M = RMarket()
    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith('/v2/assets'): return Resp(200, M.assets)
        if url.endswith('/v2/calendar'): return Resp(200, [dict(date=TODAY.isoformat(), open='09:30', close='16:00')])
        return Resp(404, {})
    monkeypatch.setattr(CR.requests, 'get', fake_get)
    RP = IX.IEXReplay(CE.Data('PK1', 'x', http=M), 'PK1', 'x', {})
    return RP, RP.load_iex(TODAY, RP.load_day(TODAY, 16 * 60))

def test_free_mode_runs_and_reports_coverage(monkeypatch):
    RP, data = make(monkeypatch)
    r = RP.run_free(TODAY, 16 * 60, dict(equity=2500.0, daytrades=[], pdt=False), data, RP.cfg)
    assert r['stats']['looked'] > 0 and r['stats'].get('read', 0) > 0
    for t in r['trades']: assert t['m_in'] >= 9 * 60 + 35 and t['fees'] >= 0

def test_stock_without_iex_prints_is_skipped(monkeypatch):
    RP, data = make(monkeypatch)
    data['IBARS'] = {}                                                        # IEX saw nothing all day
    r = RP.run_free(TODAY, 16 * 60, dict(equity=2500.0, daytrades=[], pdt=False), data, RP.cfg)
    assert r['trades'] == [] and r['stats'].get('read', 0) == 0 and r['stats']['no IEX data'] > 0
