from datetime import datetime, date
from zoneinfo import ZoneInfo
import city_model_forward as F

ET = ZoneInfo('America/New_York')

def iso(h, m): return datetime(2026, 11, 18, h, m, tzinfo=ET).isoformat()

class FakeD:
    def bars(self, syms, tf, a, b, feed, adj):
        if tf == '1Min':
            return {'AAA': [dict(t=iso(9, 29), o=9, h=9, l=9, c=9, v=1), dict(t=iso(9, 30), o=10, h=10.5, l=9.9, c=10.2, v=5),
                            dict(t=iso(9, 59), o=10.4, h=10.6, l=10.3, c=10.5, v=5), dict(t=iso(15, 59), o=11, h=11, l=11, c=11, v=5)]}
        return {'AAA': [dict(t=iso(0, 0), o=10.0, h=11, l=9.9, c=11.0, v=100)]}

def test_today_opens_skips_premarket():
    assert F.today_opens(FakeD(), ['AAA', 'BBB'], date(2026, 11, 18)) == {'AAA': 10}

def test_score_day_and_summary():
    p = dict(sym='AAA', score=1.0, gap_pct=5, prev_close=9.5, open=10, adv_m=30)
    rec = dict(day='2026-11-18', top_decile=[dict(p)], top3=[dict(p)], all_liquid=[dict(p)])
    r = F.score_day(FakeD(), rec)
    q = r['top_decile'][0]
    assert q['close'] == 11.0 and 9.7 < q['net_open_pct'] < 10.0 and 4.5 < q['net_1000_pct'] < 4.8
    s = F.summary([r])
    assert s['top_decile | net_open_pct']['n'] == 1 and s['top_decile | net_open_pct']['win_pct'] == 100.0
