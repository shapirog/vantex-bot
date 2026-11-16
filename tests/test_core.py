"""Tests for vantex_core: scanner math, signal rules, sizing, lockouts, stale-feed gate, news tagging, fill model.
Run: python -m pytest -q tests"""
import math, os, sys
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vantex_core as V
from vantex_core import Bar

T0 = 1_800_000_000

def mk(rows, start_m=570):
    """rows: (o, h, l, c, v) per minute from start_m"""
    return [Bar(T0 + 60 * i, start_m + i, *r) for i, r in enumerate(rows)]

def flat(n, px=10.0, v=1000, start_m=570, wiggle=0.02):
    return mk([(px, px + wiggle, px - wiggle, px, v)] * n, start_m)

CFG = V.merge(V.DEFAULTS, {})
Q = dict(bid=10.49, ask=10.51)

def breakout_bars(hold=True, vol=8000, n_after=3, wick=False):
    """opening range 9:30-9:34 tops at 10.10, quiet until a strong 1-min close above it, then holds (or fails)"""
    b = mk([(10.0, 10.10, 9.95, 10.05, 3000)] * 5)                        # opening range: high 10.10
    b += mk([(10.05, 10.08, 10.0, 10.06, 1000)] * 15, 575)                   # quiet under the level
    hi = 10.80 if wick else 10.32
    b += mk([(10.07, hi, 10.06, 10.30, vol)], 590)                           # break: close 10.30 > 10.10
    if hold: b += mk([(10.30, 10.36, 10.26, 10.31 + 0.01 * i, 4000) for i in range(n_after)], 591)
    else: b += mk([(10.30, 10.31, 9.98, 10.00, 4000)] + [(10.0, 10.02, 9.95, 9.98, 3000)] * (n_after - 1), 591)
    return b

def feat(bars, quote=Q, adv=100_000, daily=None):
    return V.features('TEST', bars, bars[-1].m, 9.5, adv, quote=quote, daily=daily or {}, cfg=CFG)

# ---------------- indicators / scanner math
def test_vwap_typical_price_weighted():
    b = mk([(10, 11, 9, 10, 100), (20, 21, 19, 20, 300)])
    assert abs(V.vwap_series(b)[-1] - (10 * 100 + 20 * 300) / 400) < 1e-9

def test_vwap_resets_at_open():
    b = mk([(5, 5, 5, 5, 1000)], 560) + mk([(10, 10, 10, 10, 10)], 570)
    assert V.vwap_series(b)[-1] == 10

def test_ema_and_resample():
    assert abs(V.ema_series([1, 2, 3], 2)[-1] - (1 + 2 / 3 * (2 - 1) + 2 / 3 * (3 - (1 + 2 / 3)))) < 1e-9
    r = V.resample(mk([(1, 2, 0.5, 1.5, 10)] * 10), 5)
    assert len(r) == 2 and r[0].v == 50 and r[0].m == 570 and r[1].m == 575

def test_change_gap_rvol_dollar_volume():
    b = mk([(10.0, 10.2, 9.9, 10.1, 1000)] * 10)
    f = V.features('X', b, 579, 9.0, 1_000_000, curve=lambda m: 0.05, cfg=CFG)
    assert abs(f['chg_pct'] - (10.1 / 9 - 1) * 100) < 1e-9
    assert abs(f['gap_pct'] - (10.0 / 9 - 1) * 100) < 1e-9
    assert abs(f['rvol'] - 10_000 / (1_000_000 * 0.05)) < 1e-9                  # time-of-day adjusted
    assert abs(f['dollar_volume'] - 10 * 1000 * (10.2 + 9.9 + 10.1) / 3) < 1e-6

def test_opening_range_unknown_before_935():
    b = mk([(10, 10.1, 9.9, 10, 1000)] * 3)
    assert V.features('X', b, 572, 9.5, 1e6, cfg=CFG)['or_high'] is None
    b = mk([(10, 10.1, 9.9, 10, 1000)] * 6)
    assert V.features('X', b, 575, 9.5, 1e6, cfg=CFG)['or_high'] == 10.1

def test_spread_from_quote_and_crossed_quote_ignored():
    b = flat(10)
    assert abs(feat(b, dict(bid=9.99, ask=10.01))['spread_pct'] - 0.2) < 1e-9
    assert feat(b, dict(bid=10.02, ask=10.0))['spread_pct'] is None

def test_curve_monotonic_and_bounded():
    xs = [V.default_curve(m) for m in range(570, 960)]
    assert all(b >= a for a, b in zip(xs, xs[1:])) and 0 < xs[0] < 0.1 and 0.95 < xs[-1] <= 1.0

# ---------------- signal rules
def test_breakout_confirmed_with_volume_and_hold():
    b = breakout_bars()
    e = V.evaluate(feat(b), b, 1, CFG)
    assert e['status'] == 'confirmed', e
    assert e['level_name'] == 'or_high' and e['stop'] < 10.30 < e['target']

def test_breakout_reversal_rejected():
    b = breakout_bars(hold=False)
    e = V.evaluate(feat(b), b, 1, CFG)
    assert e['status'] in ('rejected', 'watching') and e['status'] != 'confirmed'

def test_breakout_waits_for_hold():
    b = breakout_bars(n_after=0)
    e = V.evaluate(feat(b), b, 1, CFG)
    assert e['status'] == 'developing' and any('waiting' in r for r in e['reasons'])

def test_low_volume_break_not_confirmed():
    b = breakout_bars(vol=900)
    e = V.evaluate(feat(b), b, 1, CFG)
    assert e['status'] != 'confirmed'
    assert any(c['name'] == 'volume supports the move' and c['ok'] is False for c in e['checks'])

def test_wick_warning():
    b = breakout_bars(wick=True)
    e = V.evaluate(feat(b), b, 1, CFG)
    assert any('wick' in w for w in e['warnings'])

def test_no_quote_means_no_confirmation():
    b = breakout_bars()
    e = V.evaluate(feat(b, quote=None), b, 1, CFG)
    assert e['status'] != 'confirmed'

def test_wide_spread_blocks_confirmation():
    b = breakout_bars()
    e = V.evaluate(feat(b, quote=dict(bid=10.2, ask=10.5)), b, 1, CFG)
    assert e['status'] != 'confirmed'

def test_bearish_breakdown_symmetric():
    up = breakout_bars()
    # mirror prices around 10.0 so the breakout becomes a breakdown below the opening-range low
    mir = [Bar(x.t, x.m, 20 - x.o, 20 - x.l, 20 - x.h, 20 - x.c, x.v) for x in up]
    f = V.features('TEST', mir, mir[-1].m, 10.5, 100_000, quote=dict(bid=9.49, ask=9.51), cfg=CFG)
    e = V.evaluate(f, mir, -1, CFG)
    assert e['status'] == 'confirmed', e
    assert e['level_name'] == 'or_low' and e['stop'] > f['price'] > e['target']

def test_vwap_cross_alone_is_not_a_signal():
    b = mk([(10, 10.02, 9.98, 10, 1000)] * 20)
    b += mk([(10, 10.05, 9.99, 10.04, 1000)], 590)                           # crosses VWAP, breaks no level
    e = V.evaluate(feat(b), b, 1, CFG)
    assert e['status'] != 'confirmed'

def test_five_minute_confirmation_ignores_open_bar():
    cfg = V.merge(V.DEFAULTS, {'signals': {'confirm_minutes': 5}})
    b = breakout_bars(n_after=1)                                             # last 5-min bucket incomplete
    f = V.features('TEST', b, b[-1].m, 9.5, 100_000, quote=Q, cfg=cfg)
    e = V.evaluate(f, b, 1, cfg)
    assert e['status'] != 'confirmed'

def test_extended_label():
    b = breakout_bars()
    b += mk([(10.4 + 0.15 * i, 10.6 + 0.15 * i, 10.4 + 0.15 * i, 10.55 + 0.15 * i, 9000) for i in range(4)], b[-1].m + 1)
    e = V.evaluate(feat(b, quote=dict(bid=11.0, ask=11.02)), b, 1, CFG)
    assert e['status'] == 'extended', e

def test_rank_prefers_developing_liquid_over_biggest_gainer():
    b = breakout_bars(); f1 = feat(b)
    l1 = V.evaluate(f1, b, 1, CFG); s1 = V.evaluate(f1, b, -1, CFG)
    big = mk([(5, 9, 5, 9, 200)] * 30)                                       # +80%, thin, no setup
    f2 = V.features('BIG', big, big[-1].m, 5.0, 50_000, quote=dict(bid=8.5, ask=9.1), cfg=CFG)
    l2 = V.evaluate(f2, big, 1, CFG); s2 = V.evaluate(f2, big, -1, CFG)
    assert f2['chg_pct'] > f1['chg_pct']
    assert V.rank_score(f1, l1, s1)[0] > V.rank_score(f2, l2, s2)[0]

# ---------------- sizing
def test_size_from_stop_distance():
    s = V.size_position(10.0, 9.8, 2500, 2500, 0, 10000, 1, CFG)
    assert s['shares'] == math.floor(2500 * 0.005 / 0.2) == 62 and s['limited_by'] == 'risk'

def test_size_never_from_buying_power_alone():
    s = V.size_position(10.0, 9.99, 2500, 2500, 0, 1e9, 1, CFG)               # tiny stop: capped by position limit, not BP
    assert s['shares'] == math.floor(2500 * 0.25 / 10) and s['limited_by'] == 'position'
    assert V.size_position(10.0, 10.0, 2500, 2500, 0, 1e9, 1, CFG)['shares'] == 0
    assert V.size_position(10.0, 10.5, 2500, 2500, 0, 1e9, 1, CFG)['shares'] == 0   # stop on the wrong side

def test_no_size_up_after_losses():
    a = V.size_position(10.0, 9.8, 2400, 2500, 0, 1e4, 1, CFG)['shares']
    b = V.size_position(10.0, 9.8, 2600, 2500, 0, 1e4, 1, CFG)['shares']
    assert a <= b == 62

def test_exposure_cap():
    s = V.size_position(10.0, 9.8, 2500, 2500, 1200, 1e4, 1, CFG)
    assert s['shares'] == math.floor((1250 - 1200) / 10)

# ---------------- safety lockouts / stale feed / paper-only
OK = dict(paper_verified=True, market_open=True, feed_realtime=True, feed_complete=True, quote_age_s=5, bar_age_s=30, control='on',
          now_m=600, city_pnl_today=0, account_pnl_today=0, start_equity=2500, equity=2500, open_positions=0, exposure=0,
          daytrade_count=0, side=1, sym_open=False, sym_traded_today=False)

def test_all_clear():
    assert V.entry_blocks(OK, CFG) == []

def blocked(**k): return V.entry_blocks(dict(OK, **k), CFG)

def test_stale_and_partial_feed_block_entries():
    assert any('delayed' in x for x in blocked(feed_realtime=False))
    assert any('partial' in x for x in blocked(feed_complete=False))
    assert any('quote stale' in x for x in blocked(quote_age_s=300))
    assert any('quote stale' in x for x in blocked(quote_age_s=None))
    assert any('bars stale' in x for x in blocked(bar_age_s=900))

def test_lockouts():
    assert any('lockout' in x for x in blocked(city_pnl_today=-37.5))
    assert any('lockout' in x for x in blocked(account_pnl_today=-40))
    assert any('paused' in x for x in blocked(control='pause'))
    assert any('max open' in x for x in blocked(open_positions=2))
    assert any('day-trade' in x for x in blocked(daytrade_count=3))
    assert blocked(daytrade_count=3, equity=30000, start_equity=30000) == []
    assert any('short orders are off' in x for x in blocked(side=-1))
    assert any('averaging' in x for x in blocked(sym_open=True))
    assert any('entry hours' in x for x in blocked(now_m=570))
    assert any('not verified' in x for x in blocked(paper_verified=False))

# ---------------- news
def test_news_classification_and_negative_flags():
    c = V.classify('Acme Announces $5 Million Registered Direct Offering Priced At-The-Market')
    assert 'OFFERING' in c['types'] and 'OFFERING' in c['negative']
    c = V.classify('Acme Receives FDA Approval For Lead Drug')
    assert c['types'][0] == 'REGULATORY' and c['confidence'] == 'high'
    assert V.classify('Acme announces 1-for-20 reverse stock split')['negative'] == ['REVERSE_SPLIT']
    assert V.classify('If You Invested $1000 In Acme 10 Years Ago')['promo']
    assert V.classify('Acme reportedly in talks to be acquired')['rumor']
    assert V.classify('12 Health Care Stocks Moving In Monday\'s Pre-Market Session')['roundup']

def test_news_grouping_stale_and_no_catalyst():
    now = 1_800_000_000
    it = [dict(t=now - 600, h='Acme Wins $40M Army Contract', s='benzinga', u='u1', sy=['ACME']),
          dict(t=now - 300, h='ACME wins $40m army contract!', s='globenewswire', u='u2', sy=['ACME']),
          dict(t=now - 40 * 3600, h='Beta Corp Q3 Earnings Beat', s='benzinga', u='u3', sy=['BETA'])]
    g = V.group_news(it, now, now - 3600 * 18)
    acme = [x for x in g if 'ACME' in x['sy']][0]
    assert acme['repeats'] == 1 and len(acme['sources']) == 2 and acme['verified']
    beta = [x for x in g if 'BETA' in x['sy']][0]
    assert beta['stale'] and not beta['verified']
    assert V.catalyst_for('ACME', g)['verified']
    nc = V.catalyst_for('ZZZZ', g)
    assert not nc['verified'] and nc['text'] == 'no verified catalyst found'

# ---------------- fees / fills
def test_fees_by_date():
    assert V.sec_rate(date(2025, 6, 1)) == 0 and V.sec_rate(date(2026, 5, 1)) == 20.60e-6
    assert V.sale_fees(date(2026, 5, 1), 100, 10.0) == round(1000 * 20.60e-6 + 100 * 0.000195, 4)
    assert V.taf(date(2026, 1, 2))[1] == 9.79

def test_limit_fill_needs_trade_through_and_caps_size():
    nb = mk([(10.2, 10.3, 10.15, 10.25, 1000)], 600)
    sh, px, _ = V.sim_limit_fill(1, 10.10, nb)
    assert sh == 0 and px is None                                           # never traded down to the limit: failed fill
    sh, px, _ = V.sim_limit_fill(1, 10.20, nb)
    assert sh == 100 and px == 10.2                                          # partial: 10% of the bar's volume

def test_gap_through_stop_fills_at_open_not_stop():
    nb = mk([(9.0, 9.1, 8.9, 9.0, 1000)], 600)
    px, _, why = V.sim_exit(1, 9.8, 11, nb, 950, 0.0)
    assert why == 'stop-gap' and px == 9.0

def test_stop_checked_before_target_in_same_bar():
    nb = mk([(10, 11.5, 9.0, 10, 1000)], 600)
    px, _, why = V.sim_exit(1, 9.5, 11, nb, 950, 0.0)
    assert why == 'stop'

# ---------------- strong-stocks filter
def test_strong_filter_rejects_weak_and_falling_stocks():
    b = breakout_bars()
    cfg = V.merge(V.DEFAULTS, {'signals': {'strong_only': True, 'strong_min_day_change_pct': 10, 'strong_min_rvol': 1.0, 'strong_require_catalyst': False}})
    f = V.features('TEST', b, b[-1].m, 9.5, 100_000, quote=Q, cfg=cfg)          # up ~9% on the day: not strong enough
    e = V.evaluate(f, b, 1, cfg)
    assert e['status'] == 'rejected' and any('not a strong stock' in r for r in e['reasons'])
    f = V.features('TEST', b, b[-1].m, 9.0, 100_000, quote=Q, cfg=cfg)          # up ~15%: passes
    assert V.evaluate(f, b, 1, cfg)['status'] == 'confirmed'

def test_strong_filter_requires_real_news():
    b = breakout_bars()
    cfg = V.merge(V.DEFAULTS, {'signals': {'strong_only': True, 'strong_min_day_change_pct': 10, 'strong_min_rvol': 1.0, 'strong_require_catalyst': True}})
    f = V.features('TEST', b, b[-1].m, 9.0, 100_000, quote=Q, cfg=cfg)
    assert V.evaluate(f, b, 1, cfg, dict(verified=False, types=[], negative=[]))['status'] == 'rejected'
    good = dict(verified=True, types=['CONTRACT'], negative=[], headline='Wins contract')
    assert V.evaluate(f, b, 1, cfg, good)['status'] == 'confirmed'
    offering = dict(verified=True, types=['OFFERING'], negative=['OFFERING'], headline='Prices offering')
    assert V.evaluate(f, b, 1, cfg, offering)['status'] == 'rejected'

def test_block_negative_news():
    b = breakout_bars()
    cfg = V.merge(V.DEFAULTS, {'signals': {'block_negative_news': True}})
    f = feat(b)
    assert V.evaluate(f, b, 1, cfg, dict(verified=False, types=[], negative=['OFFERING']))['status'] == 'rejected'
    assert V.evaluate(f, b, 1, cfg, dict(verified=False, types=[], negative=[]))['status'] == 'confirmed'

def test_default_rules_unchanged():
    b = breakout_bars()
    assert not V.strong_checks(feat(b), 1, None, CFG['signals'])
