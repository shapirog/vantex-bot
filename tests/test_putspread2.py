import city_putspread2 as P

def test_account_caps_risk():
    T = [dict(entry='2024-03-01', exit_day='2024-04-19', root=r, risk=4.0, pnl=1.0) for r in ('SPY', 'QQQ', 'IWM', 'DIA')]
    assert P.account(T, 1.0)['trades'] == 4 and P.account(T, 0.5)['trades'] == 3     # $2,500 x 50% = $1,250 -> 3 x $400
    assert P.account(T, 0.5)['end'] == 2800

def test_spy_context_uses_past_only():
    cal = [f'd{k:04d}' for k in range(260)]
    spy = {d: dict(c=100 + k * 0.1) for k, d in enumerate(cal)}
    c = P.spy_context(spy, cal)
    assert c[cal[-1]]['above200'] and c[cal[-1]]['above50'] and c[cal[-1]]['calm'] and not c[cal[-1]]['after_drop']
    assert cal[100] not in c

def test_per_trade():
    s = P.per_trade([dict(pnl=1.0, risk=4.0), dict(pnl=-4.0, risk=4.0)])
    assert s['n'] == 2 and s['win'] == 50.0 and s['lost_all'] == 50.0
