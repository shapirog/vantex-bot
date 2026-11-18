"""Overnight paper trial: paper-only broker, control switch blocks buys, trial stops after N days, summary math."""
import os, sys
import pytest
pytest.importorskip('numpy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import city_overnight_live as L
import city_broker

def test_refuses_live_keys():
    with pytest.raises(city_broker.NotPaper): city_broker.PaperBroker('AKLIVE', 'x')

def test_control_switch_blocks_new_buys(monkeypatch):
    monkeypatch.setattr(L, 'gh_file', lambda p: {'trading': 'stop'}); assert L.control_blocks()
    monkeypatch.setattr(L, 'gh_file', lambda p: {'trading': 'on', 'overnight': 'off'}); assert L.control_blocks()
    monkeypatch.setattr(L, 'gh_file', lambda p: {'trading': 'on'}); assert L.control_blocks() == []

def test_summary_counts_only_closed_trades():
    led = [dict(sym='A', qty=10, entry_price=10.0, exit_price=10.5), dict(sym='B', qty=5, entry_price=20.0, exit_price=19.0), dict(sym='C', qty=1, entry_price=5.0)]
    S = L.summary(dict(buy_days=['d1'], open=[1]), led)
    assert S['closed_trades'] == 2 and S['net_pnl'] == 0.0 and S['winners'] == 1

class FakeB:
    def __init__(self): self.sent = []
    def clock(self): return {'is_open': True}
    def verify(self, max_age_s=300): return {'buying_power': '5000'}

def test_trial_stops_after_three_days(monkeypatch):
    saved = {}
    monkeypatch.setattr(L, 'load_state', lambda: (dict(buy_days=['a', 'b', 'c'], open=[], events=[]), []))
    monkeypatch.setattr(L, 'save', lambda st, led: saved.update(st=st))
    L.do_buy(FakeB(), None, 'PK', 'x')
    assert saved['st']['events'][-1]['kind'] == 'trial over'
