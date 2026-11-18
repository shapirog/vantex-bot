from datetime import datetime
from zoneinfo import ZoneInfo
import city_news_study as N

ET = ZoneInfo('America/New_York')
CAL = ['2026-06-01', '2026-06-02', '2026-06-03', '2026-06-05']

def mk(rows):
    return dict(d=[r[0] for r in rows], o=[r[1] for r in rows], h=[r[2] for r in rows], l=[r[3] for r in rows], c=[r[4] for r in rows], v=[r[5] for r in rows])

def test_session_for():
    assert N.session_for(datetime(2026, 6, 2, 8, 0, tzinfo=ET), CAL) == ('2026-06-02', 'pre')
    assert N.session_for(datetime(2026, 6, 2, 10, 0, tzinfo=ET), CAL) == ('2026-06-02', 'intra')
    assert N.session_for(datetime(2026, 6, 2, 17, 0, tzinfo=ET), CAL) == ('2026-06-03', 'pre')
    assert N.session_for(datetime(2026, 6, 4, 12, 0, tzinfo=ET), CAL) == ('2026-06-05', 'pre')   # holiday -> next session
    assert N.session_for(datetime(2026, 6, 6, 12, 0, tzinfo=ET), CAL) == (None, None)

def test_hold_time_stop_target():
    S = mk([('a', 10, 11, 9.5, 10.5, 1), ('b', 10.5, 12, 10, 11, 1), ('c', 11, 11, 8, 9, 1)])
    assert N.hold(S, 0, 2) == (11, 1, 'time')
    assert N.hold(S, 0, 3, stop=9.0)[2] == 'stop'                       # day c touches 8
    assert N.hold(S, 0, 1, stop=9.0, target=10.8) == (10.8, 0, 'target')
    assert N.hold(S, 0, 1, stop=9.6, target=10.8)[2] == 'stop'          # both touched: stop first
    assert N.hold(S, 1, 2, stop=11.5)[2] == 'stop (gap)'                # opens below the stop
    assert N.hold(S, 1, 5, last_cal='c') is None                        # still running at the end of the data
    assert N.hold(S, 1, 5, last_cal='z')[2].startswith('last close')    # stopped trading

def test_feats_and_good():
    rows = [(f'd{i:02d}', 10, 10.5, 9.5, 10, 1000) for i in range(21)] + [('d21', 11, 12, 10.8, 11.9, 5000)]
    f = N.feats(mk(rows), 21)
    assert abs(f['gap'] - 0.10) < 1e-9 and abs(f['rvol'] - 5) < 1e-9 and f['adv'] == 10000 and f['rng'] > 0.9
    assert N.feats(mk(rows), 5) is None
    n = N.V.classify('Acme receives FDA approval for drug', '', 1)
    assert N.good(n)
    assert not N.good(N.V.classify('Acme announces $5M registered direct offering', '', 1))

def test_newsmap_and_run():
    rows = [(f'2026-05-{i + 1:02d}', 10, 10.2, 9.8, 10, 1e6) for i in range(21)]
    rows += [('2026-06-01', 11, 12.5, 10.9, 12.4, 5e6), ('2026-06-02', 12.5, 13, 12.3, 12.9, 2e6), ('2026-06-03', 13, 13.2, 12.8, 13.1, 1e6)]
    S = mk(rows); cal = [r[0] for r in rows]
    items = [dict(created_at='2026-06-01T11:00:00Z', headline='Acme wins $40M Department of Defense contract', symbols=['ACME'])]
    nm, kept = N.build_newsmap(items, cal, {'ACME'})
    assert ('ACME', '2026-06-01') in nm and nm[('ACME', '2026-06-01')]['pre']
    from datetime import date
    trades, ev, cover = N.run({'ACME': S}, cal, nm, date(2026, 6, 1), cal[-1])
    rules = {t['rule'] for t in trades}
    assert any(r.startswith('N1 ') for r in rules) and any(r.startswith('N2 ') for r in rules)
    assert not any(r.startswith('C1') for r in rules)                    # it had news, so it is not a control trade
    n1 = [t for t in trades if t['rule'].startswith('N1 ')][0]
    assert n1['buy'] == 11 and n1['sell'] == 12.4 and n1['net'] < 12.4 / 11 - 1

def test_stats():
    s = N.stats([0.01, -0.02, 0.03])
    assert s['n'] == 3 and s['win_pct'] == 66.7 and s['median_pct'] == 1.0
