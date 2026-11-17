"""Index-ETF effects: daily summaries from minute bars, overnight/intraday math, 10:00 signal used before the 15:30 entry."""
import os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import city_index as X
from city_engine import ET
from vantex_core import Bar

def day_bars(day, o, c, path=None):
    base = datetime.fromisoformat(day + 'T00:00:00').replace(tzinfo=ET).timestamp()
    L = []
    for m in range(570, 960):
        px = path(m) if path else o + (c - o) * (m - 570) / 389
        L.append(Bar(int(base + m * 60), m, px, px, px, px, 1000))
    return L

def test_daily_summary_and_overnight_intraday():
    M = day_bars('2024-03-04', 100, 101) + day_bars('2024-03-05', 102, 103)
    D = X.daily_from_minutes(M)
    assert set(D) == {'2024-03-04', '2024-03-05'} and abs(D['2024-03-04']['open'] - 100) < 1e-9
    on = X.overnight(D, '2024-03-01', '2024-03-31', 0.0)
    assert len(on) == 1 and abs(on[0][1] - (102 / 101 - 1)) < 1e-9
    assert abs(X.intraday(D, '2024-03-01', '2024-03-31', 0.0)[0][1] - 0.01) < 1e-9

def test_intraday_momentum_uses_morning_sign_only():
    up = day_bars('2024-03-05', 101, 104)                                    # above prior close by 10:00
    dn = day_bars('2024-03-06', 99, 102, path=lambda m: 99 if m < 600 else 102)   # below prior close at 10:00, rallies later
    D = X.daily_from_minutes(day_bars('2024-03-04', 100, 100) + up + dn)
    r = X.intraday_momentum(D, '2024-03-01', '2024-03-31', 0.0)
    assert [d for d, _ in r] == ['2024-03-05']                                # the down-morning day is skipped despite its later rally

def test_pre_fomc_and_vol_managed_run():
    M = day_bars('2024-01-30', 100, 100) + day_bars('2024-01-31', 100, 102)
    D = X.daily_from_minutes(M)
    r = X.pre_fomc(D, '2024-01-01', '2024-12-31', 0.0)
    assert len(r) == 1 and r[0][0] == '2024-01-31' and r[0][1] > 0
