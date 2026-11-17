"""Portfolio rotations: rebalance calendars, scores use only past closes, cash rule, dual momentum and stats."""
import os, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import city_rotation as RT
from test_research import trading_days

def comp(closes, adv=100e6):
    ds = trading_days(len(closes)); return (ds, list(closes), list(closes), [adv] * len(closes))

def test_rebalance_calendars():
    ds = trading_days(60)
    m = RT.rebalance_days(ds, 'month'); w = RT.rebalance_days(ds, 'week')
    assert m[0] == ds[0] and all(a[:7] != b[:7] for a, b in zip(m, m[1:])) and len(w) >= 11

def test_momentum_picks_winner_and_cash_rule():
    n = 320; up = comp([20 + i * 0.1 for i in range(n)]); dn = comp([60 - i * 0.1 for i in range(n)])
    days = up[0]
    P = RT.rotate({'UP': up, 'DN': dn}, days, 'month', RT.mom_12_1, 1)
    picked = [p for p in P if p[2] not in ('none', 'cash')]
    assert picked and all(p[2] == 'UP' for p in picked) and all(p[1] > 0 for p in picked)
    C = RT.rotate({'UP': up}, days, 'month', RT.mom_12_1, 1, cash_when=lambda d: True)
    assert all(p[2] == 'cash' and p[1] == 0.0 for p in C)

def test_scores_only_look_back():
    cl = [10.0] * 300
    assert RT.mom_12_1(cl, 100) is None and RT.mom_12_1(cl, 299) == 0.0
    assert abs(RT.reversal_5([10, 10, 10, 10, 10, 8.0], 5) - 0.2) < 1e-9
    assert RT.low_vol_60(cl, 50) is None and RT.low_vol_60(cl, 200) == 0.0

def test_dual_momentum_goes_to_bonds_when_stocks_lag_cash():
    n = 300
    etf = {'SPY': comp([100 - i * 0.05 for i in range(n)]), 'EFA': comp([50 - i * 0.02 for i in range(n)]),
           'SHY': comp([80 + i * 0.01 for i in range(n)]), 'AGG': comp([90 + i * 0.01 for i in range(n)])}
    P = RT.dual_momentum(etf, etf['SPY'][0])
    assert P and all(p[2] == 'AGG' for p in P)

def test_stats():
    S = RT.stats([('2024-01-02', 0.1, 'x'), ('2024-02-01', -0.1, 'x'), ('2025-01-02', 0.05, 'x')], 12)
    assert S['periods'] == 3 and S['max_drawdown_pct'] == 10.0 and set(S['by_year']) == {'2024', '2025'}
