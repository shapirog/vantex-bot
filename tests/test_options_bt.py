from datetime import date
import city_options_bt as O

def test_occ_and_expiries():
    assert O.occ('AAPL', date(2024, 2, 16), 'C', 190) == 'AAPL240216C00190000'
    assert O.occ('F', date(2024, 3, 15), 'C', 12.5) == 'F240315C00012500'
    e = dict(O.expiries(date(2024, 2, 12)))                                  # a Monday
    assert e['~1 week'] == date(2024, 2, 23) and e['~1 month'] == date(2024, 3, 15) and e['~2 months'] == date(2024, 4, 19)
    assert O.third_friday(2024, 3) == date(2024, 3, 15)

def test_strikes_and_pick():
    g = O.strike_grid(187.3, 187.3)
    assert 187.5 in g and 185.0 in g and 190.0 in g
    bars = {'X1': [dict(t='2024-02-12T05:00:00Z', vw=2.0, c=2.1)], 'X2': [dict(t='2024-02-13T05:00:00Z', vw=1.0, c=1.0)]}
    assert O.pick_contract(bars, [('X1', 185.0), ('X2', 187.5)], 187.3, '2024-02-12') == ('X1', 185.0)   # X2 did not trade that day
    assert O.vwap_on(bars, 'X1', '2024-02-12') == 2.0 and O.vwap_on(bars, 'X1', '2024-02-13') is None

def test_stats():
    s = O.stats([-1.0, 0.5, 0.2])
    assert s['lost_90pct_plus'] == 33.3 and s['win_pct'] == 66.7
