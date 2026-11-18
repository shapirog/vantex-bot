"""Overnight-bias audit: same regression as the published module, FDR screen, schedule without look-ahead, whole shares."""
import os, sys, random
import pytest
np = pytest.importorskip('numpy')                                             # the live engine's test run does not need numpy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import city_overnight as A
import city_overnight_audit as AU
from test_overnight_turnover import stock

def test_regression_matches_published_module():
    S = stock(300, gap=0.003, day=-0.003)
    a, se, t, n = AU.regress(S, 299)
    assert abs(t - A.overnight_t(S, 299)) < 1e-9 and n >= A.MIN_OBS

def test_benjamini_hochberg():
    p = [0.001, 0.01, 0.03, 0.2, 0.5]
    assert AU.bh(p, 0.02) == {0} and AU.bh(p, 0.05) == {0, 1, 2} and AU.bh([0.5, 0.9], 0.05) == set()

def test_schedule_uses_only_earlier_month_ends():
    cal = ['2024-01-30', '2024-01-31', '2024-02-01', '2024-02-02']
    s = AU.schedule(cal, ['2024-01-31'], '2024-01-01', '2024-12-31')
    assert 1 not in s and s[2] == '2024-01-31'                                 # nothing trades on the month-end close itself

def test_portfolio_cap_and_net_cost():
    ON = np.array([[0.01, np.nan], [0.02, 0.0]])
    g, e = AU.port_daily(ON, [0, 1], [0, 1])
    assert abs(g[0] - 0.05 * 0.03) < 1e-12 and abs(e[0] - 0.10) < 1e-12 and abs(e[1] - 0.05) < 1e-12
    assert abs(AU.net(g, e, 1.0)[0] - (g[0] - 2e-4 * 0.10)) < 1e-15

def test_whole_shares_and_idle_cash():
    cal = ['2026-05-04', '2026-05-05']
    C = np.array([[700.0, 700.0]]); O = np.array([[700.0, 707.0]]); ON = np.full((1, 2), np.nan); ON[0, 0] = 0.01
    r, info = AU.whole_share_sim(C, O, ON, {0: 'm'}, {'m': ['X']}, {'X': 0}, [0], cal, 25, ('bp', 0.0))
    assert info['avg_orders_per_day'] == 2 and info['avg_idle_cash_pct'] > 0 and r[0] > 0
