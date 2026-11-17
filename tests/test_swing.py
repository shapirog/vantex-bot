"""Swing research: signals use only data up to the signal day, entries are the next open, stops and costs are applied."""
import os, sys, time
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import city_swing as W

def days(n, start=date(2024, 1, 1)):
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]

def flat(n, px=10.0, v=1_000_000):
    return [(d, px, px * 1.01, px * 0.99, px, v) for d in days(n)]

def test_gapper_signal_and_next_open_entry():
    B = flat(40)
    d = B[30][0]; B[30] = (d, 10.2, 11.7, 10.1, 11.6, 5_000_000)                 # +16% on 5x volume, closes near the high
    B[31] = (B[31][0], 11.6, 12.0, 11.5, 11.9, 2_000_000)
    B[32:] = [(x[0], 11.9, 12.1, 11.8, 12.0, 1_000_000) for x in B[32:]]
    I = W.indicators(B)
    sig = W.signals(B, I, B[0][0], B[-1][0])
    assert ('S1', 30) in [(s, i) for s, i, _, _ in sig] and ('S2', 30) in [(s, i) for s, i, _, _ in sig]
    t = W.trade(B, I, 'S1', 30, 10.1)
    assert t['entry_day'] == B[31][0] and abs(t['entry'] - 11.6 * (1 + W.cost_pct(I[30]['adv']))) < 1e-6
    assert t['why'] == 'time' and t['days'] == 5 and t['R'] > 0

def test_volume_baseline_excludes_the_signal_day():
    B = flat(40); B[30] = (B[30][0], 10.2, 11.6, 10.1, 11.5, 5_000_000)
    I = W.indicators(B)
    assert I[30]['avgv'] == 1_000_000                                         # today's huge volume is not in its own average

def test_gap_through_stop_fills_at_open():
    B = flat(40); B[30] = (B[30][0], 10.2, 11.6, 10.1, 11.5, 5_000_000)
    B[31] = (B[31][0], 11.6, 11.7, 11.4, 11.5, 2_000_000); B[32] = (B[32][0], 9.0, 9.2, 8.8, 9.0, 3_000_000)
    I = W.indicators(B); t = W.trade(B, I, 'S1', 30, 10.1)
    assert t['why'] == 'stop-gap' and abs(t['exit'] - 9.0 * (1 - W.cost_pct(I[30]['adv']))) < 1e-6 and t['R'] < -1

def test_rsi2_pullback_exit_above_5_day_average():
    B = [(d, 50 + i * 0.1, 50 + i * 0.1 + 0.5, 50 + i * 0.1 - 0.5, 50 + i * 0.1, 2_000_000) for i, d in enumerate(days(260))]
    for k, px in ((250, 70.0), (251, 69.0), (252, 68.0)): B[k] = (B[k][0], px + 0.5, px + 0.6, px - 0.4, px, 2_000_000)
    B[253] = (B[253][0], 68.2, 74.0, 68.0, 73.5, 2_000_000)
    I = W.indicators(B)
    sig = [(s, i) for s, i, _, _ in W.signals(B, I, B[0][0], B[-1][0]) if s == 'S3']
    assert (('S3', 251) in sig or ('S3', 252) in sig)
    t = W.trade(B, I, 'S3', sig[-1][1], None)
    assert t['why'] in ('rule', 'time', 'stop', 'stop-gap') and t['stop'] < t['entry']

def test_stats_and_account():
    T = [dict(entry_day='2024-02-01', exit_day='2024-02-05', entry=10.0, stop=9.0, exit=12.0, R=2.0, pct=20.0, days=3, why='time', rank=1),
         dict(entry_day='2024-02-02', exit_day='2024-02-06', entry=10.0, stop=9.0, exit=9.0, R=-1.0, pct=-10.0, days=3, why='stop', rank=1)]
    S = W.per_trade_stats(T)
    assert S['expectancy_R'] == 0.5 and S['profit_factor'] == 2.0 and S['win_rate_pct'] == 50.0
    A = W.portfolio(T)
    assert A['trades_taken'] == 2 and A['final_equity'] > 2500

def test_fast_enough_for_thousands_of_stocks():
    B = [(d, 10 + (i % 7) * 0.1, 10.5 + (i % 7) * 0.1, 9.5, 10 + (i % 5) * 0.1, 1_000_000) for i, d in enumerate(days(900))]
    t0 = time.time(); I = W.indicators(B); W.signals(B, I, B[0][0], B[-1][0])
    assert time.time() - t0 < 3
