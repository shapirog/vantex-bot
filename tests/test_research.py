"""Research batch 2: next-open entries, stops, calendar windows and the monthly rotation use only past data."""
import os, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import city_research as RS
import city_swing as W

def trading_days(n, start=date(2024, 1, 2)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5: out.append(d.isoformat())
        d += timedelta(days=1)
    return out

def series(closes, v=5_000_000):
    return [(d, c, c * 1.01, c * 0.99, c, v) for d, c in zip(trading_days(len(closes)), closes)]

def test_sim_enters_next_open_and_exits_on_rule_or_stop():
    B = series([100.0] * 30 + [95.0, 99.0, 102.0, 103.0]); I = W.indicators(B)
    t = RS.sim(B, I, 30, 90.0, lambda j: B[j][4] > 100, 10, 0.001)
    assert t['entry_day'] == B[31][0] and t['exit_day'] == B[32][0] and t['why'] == 'rule'
    B2 = series([100.0] * 30 + [95.0, 99.0, 80.0]); I2 = W.indicators(B2)
    t2 = RS.sim(B2, I2, 30, 90.0, lambda j: False, 10, 0.0)
    assert t2['why'] == 'stop-gap' and t2['exit'] == 80.0

def test_market_filter_and_turn_of_month():
    B = series([100 + i * 0.1 for i in range(300)]); I = W.indicators(B)
    mk = RS.market_ok(B, I)
    assert mk[B[-1][0]] is True and mk[B[10][0]] is False                   # no 200-day line yet = not ok
    T = RS.turn_of_month(B, B[0][0], B[-1][0])
    assert T and all(t['entry_day'] < t['exit_day'] for t in T) and all(t['pct'] > 0 for t in T)

def test_momentum_picks_the_best_past_performer_and_respects_cash_rule():
    n = 200; days = trading_days(n)
    up = [(days[i], 10 + i * 0.2, 0, 0, 10 + i * 0.2, 0) for i in range(n)]
    flat = [(days[i], 20.0, 0, 0, 20.0, 0) for i in range(n)]
    st = {'UP': ([d for d, *_ in up], [x[1] for x in up], [x[4] for x in up], [50e6] * n),
          'FLAT': ([d for d, *_ in flat], [x[1] for x in flat], [x[4] for x in flat], [50e6] * n)}
    T, curve = RS.momentum(st, {d: True for d in days}, days[0], days[-1], top=1)
    assert T and all(t['sym'] == 'UP' for t in T)
    T2, curve2 = RS.momentum(st, {d: False for d in days}, days[0], days[-1], top=1)
    assert T2 == [] and all(c[2] == 'cash' for c in curve2)

def test_curve_stats():
    S = RS.curve_stats([('a', 1.1, 'x'), ('b', 0.99, 'x'), ('c', 1.2, 'x')])
    assert S['return_pct'] == 20.0 and S['max_drawdown_pct'] == 10.0
