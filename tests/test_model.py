import random
import city_model as M

def mk(n=30, gap_at=28):
    d = [f'2026-01-{k + 1:02d}' if k < 31 else f'x{k}' for k in range(n)]
    o = [10.0] * n; c = [10.0 + 0.01 * k for k in range(n)]; h = [x + 0.2 for x in c]; l = [x - 0.2 for x in c]; v = [2e5] * n
    o[gap_at] = c[gap_at - 1] * 1.05; c[gap_at] = o[gap_at] * 1.02; h[gap_at] = c[gap_at] + 0.1
    return dict(d=d, o=o, h=h, l=l, c=c, v=v)

def test_row_feats_only_open_info():
    S = mk(); f = M.row_feats(S, 28)
    assert abs(f['gap'] - 0.05) < 1e-9 and f['px'] == S['c'][27]
    S2 = mk(); S2['c'][28] = 999; S2['h'][28] = 1000                     # today's close/high must not change the features
    assert M.row_feats(S2, 28) == f
    assert M.row_feats(S, 20) is None and M.row_feats(S, 27) is None      # too early / no gap

def test_build_and_picks():
    st = {'AAA': mk(), 'BBB': mk()}
    rows = M.build(st, {S: 0.0 for S in st['AAA']['d']})
    assert len(rows) == 2 and all(abs(r['y'] - 0.02) < 1e-9 for r in rows) and rows[0]['breadth'] > 0
    for k, r in enumerate(rows): r['score'] = k
    assert [r['sym'] for r in M.daily_picks(rows, 'score', 'top')][0] == 'BBB'
    assert len(M.daily_picks(rows, 'score', 'random', random.Random(1))) == 2
    S = M.evaluate(M.daily_picks(rows, 'score', 'top'), st, 'zzz')
    assert S['trades'] == 2 and S['win_pct'] == 100.0 and S['avg_pct'] < 2.0
    assert M.split_of('2024-01-02') == 'learn' and M.split_of('2025-08-01') == 'check' and M.split_of('2026-03-02') == 'test' and M.split_of('2023-01-03') is None
