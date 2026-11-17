"""RSI(2) robustness sweep: every setting is produced, the market filter and entry threshold are respected."""
import os, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import city_mr as MR
import city_swing as W
from test_research import series

def test_sweep_produces_settings_and_respects_filters():
    closes = [100 + i * 0.2 for i in range(260)] + [148.0, 140.0, 133.0, 150.0, 152.0, 153.0, 154.0]
    B = series(closes, v=1_000_000); I = W.indicators(B)
    d = B[260][0]                                                              # the dip starts after this day
    on = MR.stock_trades('AAA', B, I, {x[0]: True for x in B}, B[0][0], B[-1][0])
    off = MR.stock_trades('AAA', B, I, {x[0]: False for x in B}, B[0][0], B[-1][0])
    assert on and any(k[3] is True for k in on) and all(k[3] is False for k in off)
    for L in on.values():
        for t in L: assert t['entry_day'] > d                                 # bought only after the signal day's close
    assert all(k[0] in MR.ENTRY and k[1] in MR.EXIT for k in on)

def test_illiquid_or_downtrend_stocks_are_ignored():
    closes = [200 - i * 0.2 for i in range(260)] + [140.0, 130.0, 120.0, 125.0]
    B = series(closes, v=1_000_000); I = W.indicators(B)
    assert MR.stock_trades('BBB', B, I, {x[0]: True for x in B}, B[0][0], B[-1][0]) == {}
    B2 = series([100 + i * 0.2 for i in range(260)] + [148.0, 140.0, 133.0, 150.0], v=1000); I2 = W.indicators(B2)
    assert MR.stock_trades('CCC', B2, I2, {x[0]: True for x in B2}, B2[0][0], B2[-1][0]) == {}
