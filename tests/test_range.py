import city_range as R

def mk(rows):
    return dict(d=[f'2024-01-{k + 1:02d}' if k < 31 else f'2024-02-{k - 30:02d}' for k in range(len(rows))],
                o=[r[0] for r in rows], h=[r[1] for r in rows], l=[r[2] for r in rows], c=[r[3] for r in rows], v=[1e6] * len(rows))

def bouncing(n=22):
    rows = []
    for k in range(n):                                                    # 140 <-> 150 range, flat, $20M+/day
        up = k % 4 < 2
        rows.append((145, 150 if up else 146, 144 if up else 140, 148 if up else 142))
    return rows

def test_range_detected_without_lookahead():
    S = mk(bouncing())
    r = R.range_at(S, 21)
    assert r and r['H'] == 150 and r['L'] == 140 and r['top_touches'] >= 2 and r['bottom_touches'] >= 2
    S2 = mk(bouncing()); S2['h'][21] = 999                                 # today's bar must not matter
    assert R.range_at(S2, 21) == r

def test_trending_stock_is_not_a_range():
    rows = [(100 + k, 101 + k, 99 + k, 100.5 + k) for k in range(22)]
    assert R.range_at(mk(rows), 21) is None

def test_trade_fills_and_exits():
    rows = bouncing(21) + [(143, 144, 141, 142), (143, 149, 142, 148)] + [(148, 148, 147, 147)] * 4
    S = mk(rows); rr = R.range_at(S, 21)
    ent, ext, j, how = R.trade(S, 21, rr, 5)
    assert ent == 141.4 and how == 'target' and j == 22 and ext == 150 * 0.98
    ent, ext, j, how = R.trade(S, 21, rr, 1)
    assert how == 'time' and ext == 142                                    # DAY: sold at the close
    rows2 = bouncing(21) + [(141, 142, 135, 136), (136, 137, 135, 136)]
    S2 = mk(rows2); assert R.trade(S2, 21, R.range_at(S2, 21), 1)[3] == 'stop'
    rows3 = bouncing(21) + [(135, 136, 134, 135)]                          # opens below the stop: no trade
    S3 = mk(rows3); assert R.trade(S3, 21, R.range_at(S3, 21), 1) is None

def test_periods():
    T = [dict(exit_day='2024-01-02', net=0.04), dict(exit_day='2024-01-03', net=-0.02), dict(exit_day='2024-02-05', net=0.01)]
    m = R.periods(T, 'month'); assert m['n'] == 2 and m['avg_usd'] == round((5.0 + 2.5) / 2, 2)
