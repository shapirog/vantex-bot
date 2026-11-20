from datetime import date
import city_putspread as P
from city_options_bt import occ

def test_expiry_and_candidates():
    assert P.expiry_for(date(2024, 2, 12), 6, False) == date(2024, 2, 23)
    assert P.expiry_for(date(2024, 2, 12), 30, True) == date(2024, 3, 15)
    c = P.candidates(500.0, 490.0)
    assert 490.0 in c and 485.0 in c and all(x > 0 for x in c)

def test_settle():
    assert P.settle(100, 95, 101) == 0 and P.settle(100, 95, 97) == 3 and P.settle(100, 95, 80) == 5

def ob(rows):
    return {occ('SPY', date(2024, 3, 15), 'P', k): [dict(t=f'{d}T05:00:00Z', vw=v, c=v) for d, v in L] for k, L in rows.items()}

def test_run_trade_hold_and_managed():
    exp = date(2024, 3, 15)
    o = ob({490: [('2024-02-12', 3.0), ('2024-02-20', 0.9)], 485: [('2024-02-12', 2.0), ('2024-02-20', 0.6)]})
    r = P.run_trade(o, 'SPY', exp, 490, 485, '2024-02-12', ['2024-02-20'], 500.0, managed=False)
    credit = 3.0 * 0.97 - 2.0 * 1.03
    assert abs(r['credit'] - credit) < 1e-12 and r['how'] == 'expired' and abs(r['pnl'] - credit) < 1e-12 and abs(r['risk'] - (5 - credit)) < 1e-12
    r = P.run_trade(o, 'SPY', exp, 490, 485, '2024-02-12', ['2024-02-20'], 500.0, managed=True)
    assert r['how'] == 'take profit' and r['exit_day'] == '2024-02-20'
    r = P.run_trade(o, 'SPY', exp, 490, 485, '2024-02-12', [], 480.0, managed=False)
    assert abs(r['pnl'] - (credit - 5)) < 1e-12                              # full loss below the long strike

def test_account_sim_respects_capital():
    T = [dict(entry='2024-02-12', exit_day='2024-03-15', root='SPY', risk=4.0, pnl=1.0),
         dict(entry='2024-02-12', exit_day='2024-03-15', root='QQQ', risk=4.0, pnl=1.0),
         dict(entry='2024-02-20', exit_day='2024-03-15', root='IWM', risk=4.0, pnl=-4.0),
         dict(entry='2024-03-18', exit_day='2024-04-19', root='DIA', risk=4.0, pnl=1.0)]
    a = P.account_sim(T, start=1000.0)
    assert a['trades'] == 3 and a['end'] == 1000 + 100 + 100 + 100 and a['max_dd_pct'] == 0.0     # IWM skipped: no room
