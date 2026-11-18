import city_gapdown as G

def mk(n, gap_day=None, base=100.0):
    ds = [f'd{i:04d}' for i in range(n)]; cl = [base * (1.001 ** i) for i in range(n)]; op = list(cl)
    op = [cl[i - 1] if i else cl[0] for i in range(n)]
    if gap_day is not None: op[gap_day] = cl[gap_day - 1] * 0.97; op[gap_day + 1] = cl[gap_day - 1] * 0.99
    return (ds, op, cl, [1e6] * n)

def test_candidates_and_sim():
    st = {'AAA': mk(260, gap_day=250), 'BBB': mk(260)}
    cal = st['AAA'][0]
    c = G.daily_candidates(st, cal)
    d = cal[250]
    row = [x for x in c[d] if x[0] == 'AAA'][0]
    assert abs(row[2] + 0.03) < 1e-9                                     # 3% gap down seen at the open
    rets, trades, wins = G.simulate(st, c, cal, cal[250], cal[250], 0.02, 0.0)
    assert trades == 1 and wins == 1 and abs(rets[0][1] - (0.99 / 0.97 - 1) / 10) < 1e-9
    assert G.daily_candidates(st, cal)[cal[100]] == []                   # needs 200 sessions of history

def test_stats():
    s = G.stats([('2024-01-02', 0.01), ('2024-01-03', -0.005)], 4, 3)
    assert s['win_pct'] == 75.0 and s['days'] == 2
