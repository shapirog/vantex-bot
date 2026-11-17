"""5-minute ORB tester: picks stocks in play from the first 5 minutes only, enters on the range break, exits on stop or close."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vantex_core as V
from vantex_core import Bar
import city_orb as O

def bars(rows, start=570):
    return [Bar(1_800_000_000 + 60 * i, start + i, *r) for i, r in enumerate(rows)]

def day(after):
    """opening range 9:30-9:35 from 20.00 up to a 20.50 high (closes up), then the given bars"""
    return bars([(20.0, 20.2, 19.9, 20.1, 50000), (20.1, 20.3, 20.0, 20.2, 50000), (20.2, 20.4, 20.1, 20.3, 50000),
                 (20.3, 20.5, 20.2, 20.4, 50000), (20.4, 20.5, 20.3, 20.45, 50000)] + after, 570)

DAILY = dict(prior_close=19.5, atr14=1.0, adv=1_000_000, adv_dollars=20_000_000)

def test_selects_in_play_from_first_five_minutes_only():
    B = {'AAA': day([(20.5, 30, 20.4, 29, 9_000_000)] * 10), 'BBB': bars([(20, 20.01, 19.99, 20, 10)] * 15)}
    picks, skip, n = O.select(['AAA', 'BBB'], {'AAA': DAILY, 'BBB': DAILY}, B, lambda m: 0.02)
    assert [p['sym'] for p in picks] == ['AAA'] and picks[0]['side'] == 1 and picks[0]['high'] == 20.5
    assert picks[0]['rvol'] == round(250000 / (1_000_000 * 0.02), 2)          # the huge later bars do not count

def test_cheap_or_quiet_stocks_are_not_in_the_universe():
    picks, _, n = O.select(['AAA'], {'AAA': dict(DAILY, prior_close=4.0)}, {'AAA': day([])}, lambda m: 0.02)
    assert n == 0 and picks == []

def test_long_entry_stop_and_close_exit():
    r = dict(sym='AAA', high=20.5, low=19.9, atr=1.0)
    B = {'AAA': day([(20.45, 20.6, 20.44, 20.55, 1000)] + [(20.55, 20.9, 20.5, 20.8, 1000)] * 20)}
    t = O.simulate(r, 1, B, 0.10, None)
    assert t['entry'] == 20.5 and t['why'] == 'close' and t['exit'] == 20.8 and abs(t['dist'] - 0.1) < 1e-9

def test_stop_and_gap_and_no_break():
    r = dict(sym='AAA', high=20.5, low=19.9, atr=1.0)
    B = {'AAA': day([(20.45, 20.6, 20.44, 20.55, 1000), (20.5, 20.52, 20.3, 20.35, 1000)])}
    assert O.simulate(r, 1, B, 0.10, None)['why'] == 'stop'
    B = {'AAA': day([(20.45, 20.6, 20.44, 20.55, 1000), (20.2, 20.25, 20.1, 20.2, 1000)])}
    t = O.simulate(r, 1, B, 0.10, None); assert t['why'] == 'stop-gap' and t['exit'] == 20.2
    B = {'AAA': day([(20.3, 20.4, 20.2, 20.3, 1000)] * 5)}
    assert O.simulate(r, 1, B, 0.10, None) == 'range never broken'

def test_target_variant_and_stats():
    r = dict(sym='AAA', high=20.5, low=19.9, atr=1.0)
    B = {'AAA': day([(20.45, 20.6, 20.44, 20.55, 1000), (20.6, 20.8, 20.55, 20.75, 1000)])}
    assert O.simulate(r, 1, B, 0.10, 2.0)['why'] == 'target'
    S = O.stats([dict(day='d1', pnl=20.0, R=2.0, why='close'), dict(day='d2', pnl=-10.0, R=-1.0, why='stop')], ['d1', 'd2'])
    assert S['expectancy_R'] == 0.5 and S['profit_factor'] == 2.0 and S['max_drawdown'] == 10.0
