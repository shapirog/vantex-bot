from vantex_core import Bar
import city_intraday_gap as G

def day(path, vol=1000):
    """path: list of closes per minute from 9:30; open = previous close, high/low +-0.01"""
    out, prev = [], path[0]
    for k, c in enumerate(path):
        out.append(Bar(k * 60, 570 + k, prev, max(prev, c) + 0.01, min(prev, c) - 0.01, c, vol)); prev = c
    return out

def test_g5_short_triggers_and_covers_at_1545():
    path = [10.0] * 15 + [9.9] * 2 + [9.5] * 373                          # breaks the 15-min low at 9:45, drifts lower
    r = G.g5(day(path), 'short')
    assert r and r[2] == 586 and r[4] == 'time 15:45' and r[1] == 9.5
    assert G.ret('short', r[0], r[1], 0.0) > 0

def test_g5_stop_and_no_trigger():
    path = [10.0] * 15 + [9.9] + [10.5] * 374                             # breaks down, then rips above the 15-min high
    r = G.g5(day(path), 'short')
    assert r[4] == 'stop' and G.ret('short', r[0], r[1], 0.0) < 0
    assert G.g5(day([10.0] * 390), 'short') is None

def test_g4_needs_volume_and_break_after_10():
    path = [10.0] * 30 + [10.2] * 360
    assert G.g4(day(path, vol=1000), adv_sh=10_000_000) is None           # first-30 volume far below normal
    r = G.g4(day(path, vol=100000), adv_sh=1_000_000)
    assert r and r[2] == 601 and r[4] == 'time 15:45'

def test_stats():
    assert G.stats([0.01, -0.01, 0.02])['win_pct'] == 66.7
