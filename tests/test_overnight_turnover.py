"""Strategy A (overnight bias) and B (1-month momentum x turnover): no look-ahead, correct regression, costs, placebo."""
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import city_overnight as A
import city_turnover_mom as B
from test_research import trading_days

def stock(n, gap=0.002, day=0.0, vol=5_000_000, px=50.0, seed=1):
    """opens gap up by `gap` every night, intraday drifts by `day` plus noise"""
    rnd = random.Random(seed); ds = trading_days(n); op, cl = [], []
    c = px
    for k in range(n):
        o = c * (1 + gap + rnd.gauss(0, 0.004)); c = o * (1 + day + rnd.gauss(0, 0.01)); op.append(o); cl.append(c)
    return (ds, op, cl, [vol] * n)

def test_regression_finds_positive_overnight_intercept():
    S = stock(300, gap=0.003, day=-0.003)
    t = A.overnight_t(S, 299)
    assert t is not None and t > A.TCRIT
    assert A.overnight_t(stock(300, gap=0.0, day=0.0, seed=2), 299) < A.TCRIT
    assert A.overnight_t(stock(100), 99) is None                                # fewer than 220 observations

def test_overnight_trades_start_after_the_month_end_and_pay_costs():
    S = stock(320, gap=0.003, day=-0.003); stocks = {'AAA': S}; idx = A.index(stocks); cal = S[0]
    sel = A.selections(stocks, idx, cal, cal[260], cal[-1], random.Random(1))
    me = sorted(sel)[0]; assert sel[me][0] == ['AAA']
    rows = []
    rets, expo = A.run_nights(stocks, idx, cal, sel, cal[260], cal[-1], 0, 0.0005, rows)
    assert rows and all(r[0] > me for r in rows)                               # never trades on the month-end close itself
    gross, _ = A.run_nights(stocks, idx, cal, sel, cal[260], cal[-1], 0, 0.0)
    assert sum(r for _, r in gross) > sum(r for _, r in rets)                  # costs reduce returns
    assert max(expo) <= 0.05 + 1e-9                                            # one stock = 5% cap, rest cash

def test_turnover_momentum_picks_hot_winner_and_enters_next_open():
    n = 420; ds = trading_days(n)
    hot = list(stock(n, gap=0.0, day=0.0, seed=3)); hot[3] = [5_000_000] * (n - 25) + [40_000_000] * 25
    hot[2] = [c * (1.5 if k >= n - 22 else 1.0) for k, c in enumerate(hot[2])]
    stocks = {'HOT': tuple(hot)}
    for k in range(30): stocks[f'S{k:02d}'] = stock(n, gap=0.0, day=0.0, seed=10 + k)
    idx = A.index(stocks); cal = ds
    picks = B.picks_for(stocks, idx, cal, cal[300], cal[-1], random.Random(1))
    hot_months = [m for m, v in picks.items() if 'HOT' in v[0]]
    assert hot_months and all(len(v[1]) == len(v[0]) for v in picks.values())   # placebo is the same size
    rows = []; r, e = B.run_months(stocks, idx, cal, picks, cal[300], cal[-1], 0, 0.0005, rows)
    pos = {d: k for k, d in enumerate(cal)}
    for row in rows:
        me = max(m for m in picks if m < row[0])
        assert row[0] == cal[pos[me] + 1]                                       # bought at the next session's open
