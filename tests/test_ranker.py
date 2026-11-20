import math, random
import numpy as np
import city_ranker as R

def mk(n=320, drift=0.001, seed=1):
    rnd = random.Random(seed); c = [10.0]
    for _ in range(n - 1): c.append(c[-1] * (1 + drift + rnd.gauss(0, 0.01)))
    c = np.array(c); o = np.concatenate([[c[0]], c[:-1]]) * 1.001
    days = []
    from datetime import date, timedelta
    d = date(2020, 1, 6)
    while len(days) < n:
        if d.weekday() < 5: days.append(d.isoformat())
        d += timedelta(days=1)
    return (days, o, c * 1.01, c * 0.99, c, np.full(n, 3e6))

def test_features_no_lookahead():
    S = mk(); f = R.features(S)
    i = 300
    S2 = (S[0], S[1].copy(), S[2].copy(), S[3].copy(), S[4].copy(), S[5].copy())
    S2[4][i + 1:] *= 3; S2[1][i + 1:] *= 3; S2[2][i + 1:] *= 3; S2[3][i + 1:] *= 3      # change the future only
    f2 = R.features(S2)
    for k in R.FEATS[:-2]:
        assert np.isclose(f[k][i], f2[k][i], equal_nan=True), k
    assert abs(f['r21'][i] - math.log(S[4][i] / S[4][i - 21])) < 1e-12
    assert abs(f['r252_21'][i] - math.log(S[4][i - 21] / S[4][i - 252])) < 1e-9

def test_week_ends_and_rows():
    S = mk(); cal = S[0]
    wk = R.week_ends(cal)
    assert wk[0] == '2020-01-10' and all(d in cal for d in wk)
    spy = {d: (S[1][k], S[4][k]) for k, d in enumerate(cal)}
    rows, sma, nxt, pos = R.build_rows({'AAA': S}, cal, spy)
    d = sorted(rows)[0]; r = rows[d][0]
    k_in, k_out = pos[d] + 1, pos[nxt[d]] + 1
    assert abs(r['fwd'] - (S[1][k_out] / S[1][k_in] - 1)) < 1e-12 and len(r['x']) == len(R.FEATS)

def test_rank_and_portfolio():
    L = [dict(fwd=0.05), dict(fwd=None), dict(fwd=-0.02), dict(fwd=0.01)]
    assert R.rank_target(L) == {2: 0.0, 3: 0.5, 0: 1.0}
    rets = R.portfolio(['w1', 'w2'], {'w1': [('A', 0.02), ('B', 0.0)], 'w2': [('A', 0.01), ('C', 0.01)]}, 0.001)
    assert abs(rets[0][1] - (0.01 - 1.0 * 0.001)) < 1e-12                               # full buy in week 1
    assert abs(rets[1][1] - (0.01 - (0.5 + 0.5) * 0.001)) < 1e-12                       # swap B for C
    S = R.stats(rets); assert S['weeks'] == 2
