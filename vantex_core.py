"""
VANTEX City core: the decision logic shared by the live engine (city_engine.py), the replay (city_replay.py) and the tests.
Pure functions only: no network, no orders, no clock. Every function gets the data it may use passed in, so replay can
only ever see what was known at that minute.

Bars are Bar(t, m, o, h, l, c, v): t = epoch seconds of the bar start, m = minute of the day in New York time (570 = 9:30).
"""
import math, re
from functools import lru_cache
from collections import namedtuple
from datetime import date

Bar = namedtuple('Bar', 't m o h l c v')

PM_START, RTH_OPEN, OR_END, RTH_CLOSE, AH_END = 240, 570, 575, 960, 1200

DEFAULTS = {
    'universe': {
        'exchanges': ['NASDAQ', 'NYSE', 'AMEX', 'ARCA', 'BATS'],
        'min_price': 0.50, 'max_price': 0,                # 0 = no upper limit
        'min_avg_dollar_volume': 1_000_000,               # 14-day average daily dollar volume
        'min_market_cap': 0, 'max_market_cap': 0,         # 0 = off (market cap is only known for some stocks)
        'min_atr_pct': 0,                                 # 14-day ATR as % of price, 0 = off
    },
    'candidates': {
        'deep_scan': 40,                                  # stocks that get full minute-by-minute analysis
        'move_pct': 3.0,                                  # gainers / decliners threshold vs prior close
        'unusual_rvol': 3.0,                              # time-of-day relative volume for "unusual volume"
        'near_level_pct': 0.5,                            # "near a key level" distance
        'min_today_dollar_volume_pre': 50_000,
        'min_today_dollar_volume_rth': 250_000,
    },
    'signals': {
        'confirm_minutes': 1,                             # 1 = 1-minute closes confirm, 5 = 5-minute closes
        'breakout_buffer_pct': 0.10,                      # close must clear the level by this much
        'min_rvol': 2.0,                                  # time-of-day relative volume for the stock
        'min_bar_volume_mult': 1.5,                       # breakout bar volume vs the 10 bars before it
        'hold_bars': 2,                                   # closes that must hold beyond the level after the break
        'retest_tolerance_pct': 0.30,
        'lookback_bars': 6,                               # a break older than this many bars is stale
        'max_spread_pct': 0.50,
        'max_vwap_extension_atr': 3.0,                    # beyond this many 5-minute ATRs from VWAP = extended
        'max_level_extension_atr': 2.0,                   # beyond this far past the level with no retest = extended
        'wick_max': 0.60,                                 # wick share of the breakout bar's range
        'outlier_atr': 4.0,                               # a bar this many ATRs long on little volume = outlier print
        'ema_fast': 9, 'ema_slow': 20,
        'chart_emas': [9, 20],
        'target_r': 2.0,
        # "strong stocks only": the traders' stocks-in-play filter. Off = the original rules.
        'strong_only': False,
        'strong_min_day_change_pct': 10.0,               # longs: already up this much on the day (bearish: down this much)
        'strong_min_rvol': 5.0,                           # time-of-day relative volume
        'strong_require_catalyst': True,                  # a fresh, verified, non-negative news catalyst (bearish: any verified or negative news)
        'block_negative_news': False,                     # longs: never buy a stock with offering / dilution / compliance news
    },
    'risk': {
        'risk_per_trade_pct': 0.50,                       # $12.50 on $2,500
        'max_daily_loss_pct': 1.50,                       # $37.50 on $2,500: no new entries after this
        'max_open_positions': 2,
        'max_exposure_pct': 50.0,
        'max_position_pct': 25.0,
        'allow_short_orders': False,
        'max_day_trades': 3,                              # under $25K: the 4th day trade in 5 days flags the account
        'entries_from': '09:35', 'entries_until': '15:30', 'flat_at': '15:50',
        'limit_offset_pct': 0.05,                         # marketable limit: ask + 0.05% (bid - 0.05% for shorts)
        'entry_timeout_s': 60,
        'one_entry_per_symbol_per_day': True,
    },
    'feed': {
        'require_realtime_sip': True,                     # partial (IEX) or delayed data never opens a position
        'max_quote_age_s': 90,
        'max_bar_age_s': 180,
    },
}

def merge(base, over):
    out = {}
    for k, v in base.items():
        out[k] = merge(v, over.get(k, {})) if isinstance(v, dict) else over.get(k, v)
    for k, v in (over or {}).items():
        if k not in out: out[k] = v
    return out

def hhmm(s):
    h, m = s.split(':'); return int(h) * 60 + int(m)

def session(m, weekday=0, holiday=False):
    if holiday or weekday >= 5: return 'closed'
    if PM_START <= m < RTH_OPEN: return 'premarket'
    if RTH_OPEN <= m < RTH_CLOSE: return 'regular'
    if RTH_CLOSE <= m < AH_END: return 'afterhours'
    return 'overnight'

# ------------------------------------------------------------------ indicators
def ema_series(xs, n):
    out, e, a = [], None, 2 / (n + 1)
    for x in xs:
        e = x if e is None else e + a * (x - e); out.append(e)
    return out

def vwap_series(bars):
    """session VWAP from 9:30 using (h+l+c)/3; premarket bars get a premarket VWAP from 4:00"""
    out, pv, vv, sess = [], 0.0, 0.0, None
    for b in bars:
        s = 'rth' if b.m >= RTH_OPEN else 'pre'
        if s != sess: pv = vv = 0.0; sess = s
        tp = (b.h + b.l + b.c) / 3; pv += tp * b.v; vv += b.v
        out.append(pv / vv if vv else b.c)
    return out

def resample(bars, k):
    """1-minute bars -> k-minute bars aligned to the session clock (only complete buckets are returned as closed)"""
    if k <= 1: return list(bars)
    B = {}
    for b in bars:
        key = b.m // k * k
        x = B.get(key)
        if x is None: B[key] = [b.t, key, b.o, b.h, b.l, b.c, b.v]
        else: x[3] = max(x[3], b.h); x[4] = min(x[4], b.l); x[5] = b.c; x[6] += b.v
    return [Bar(*B[k_]) for k_ in sorted(B)]

def atr(bars, n=14):
    if len(bars) < 2: return (bars[0].h - bars[0].l) if bars else 0.0
    trs = [max(b.h, p.c) - min(b.l, p.c) for p, b in zip(bars[:-1], bars[1:])][-n:]
    return sum(trs) / len(trs)

def trend(closes, fast, slow):
    if len(closes) < 3: return 0
    f, s = ema_series(closes, fast)[-1], ema_series(closes, slow)[-1]
    if abs(f - s) / s < 0.0005: return 0
    return 1 if f > s else -1

# a fallback share of a normal day's volume done by each minute; the engine replaces it with a curve measured on SPY
def default_curve(m):
    if m < RTH_OPEN: return 0.004 + 0.026 * max(0, m - PM_START) / (RTH_OPEN - PM_START)   # premarket: 0.4% -> 3%
    if m >= RTH_CLOSE: return 1.0 + 0.04 * min(1, (m - RTH_CLOSE) / 240)
    x = (m - RTH_OPEN) / 390
    return 0.03 + 0.97 * (0.45 * (1 - (1 - x) ** 3) + 0.55 * x ** 1.0 * (0.6 + 0.4 * x))

def curve_from_profile(minute_vol):
    """minute_vol: {minute: average volume of that minute}, regular session -> cumulative share function"""
    rth = sorted((m, v) for m, v in minute_vol.items() if RTH_OPEN <= m < RTH_CLOSE)
    tot = sum(v for _, v in rth)
    if tot <= 0 or len(rth) < 300: return default_curve
    cum, acc = {}, 0.0
    for m, v in rth: acc += v; cum[m] = acc / tot
    def f(m):
        if m < RTH_OPEN or m >= RTH_CLOSE: return default_curve(m)
        while m not in cum and m > RTH_OPEN: m -= 1
        return max(cum.get(m, 0.0), 0.003)
    return f

# ------------------------------------------------------------------ features of one stock at one moment
def features(sym, bars, now_m, prior_close, adv_shares, curve=default_curve, quote=None, daily=None, cfg=DEFAULTS):
    """bars: today's 1-minute bars up to (not after) now. quote: dict(bid, ask, t_age_s) or None. daily: dict(prior_high,
    prior_low, high20, low20, atr14). Returns a flat dict; values that can't be known are None, never guessed."""
    S = cfg['signals']; daily = daily or {}
    if not bars or not prior_close: return None
    last = bars[-1]; px = last.c
    rth = [b for b in bars if RTH_OPEN <= b.m < RTH_CLOSE]
    pre = [b for b in bars if b.m < RTH_OPEN]
    vol = sum(b.v for b in bars); dvol = sum(b.v * (b.h + b.l + b.c) / 3 for b in bars)
    frac = curve(now_m)
    vol_for_rvol = sum(b.v for b in rth) if now_m >= RTH_OPEN else sum(b.v for b in pre)
    exp = adv_shares * (frac if now_m >= RTH_OPEN else default_curve(now_m)) if adv_shares else 0
    rvol = vol_for_rvol / exp if exp > 0 else None
    vw = vwap_series(bars); v_now = vw[-1]
    base = rth if rth else bars
    k = max(1, S.get('confirm_minutes', 1))
    b5 = resample(bars, 5)
    a5 = atr(b5[-15:]) if len(b5) >= 3 else atr(bars[-15:]) * math.sqrt(5)
    a5 = a5 or max(px * 0.002, 0.01)
    c1 = [b.c for b in bars]; c5 = [b.c for b in b5]
    t1 = trend(c1[-60:], S['ema_fast'], S['ema_slow']); t5 = trend(c5[-40:], S['ema_fast'], S['ema_slow'])
    orh = orl = None
    if now_m >= OR_END:
        orb = [b for b in rth if b.m < OR_END]
        if orb: orh, orl = max(b.h for b in orb), min(b.l for b in orb)
    pmh = max((b.h for b in pre), default=None); pml = min((b.l for b in pre), default=None)
    hod = max(b.h for b in base); lod = min(b.l for b in base)
    op = rth[0].o if rth else None
    gap = (op / prior_close - 1) * 100 if op else ((pre[-1].c / prior_close - 1) * 100 if pre else None)
    # volume with the move: last 3 bars vs the 10 before them
    v3 = sum(b.v for b in bars[-3:]) / max(1, len(bars[-3:])); v10 = sum(b.v for b in bars[-13:-3]) / max(1, len(bars[-13:-3]))
    vol_trend = None if len(bars) < 8 or v10 <= 0 else ('increasing' if v3 > 1.3 * v10 else 'fading' if v3 < 0.7 * v10 else 'steady')
    # VWAP reclaim / rejection over the last 5 bars
    vw_event = None
    if len(bars) >= 3:
        for i in range(max(1, len(bars) - 5), len(bars)):
            if bars[i - 1].c < vw[i - 1] and bars[i].c > vw[i]: vw_event = 'reclaim'
            elif bars[i - 1].c > vw[i - 1] and bars[i].c < vw[i]: vw_event = 'lost'
            elif bars[i].h >= vw[i] > bars[i].c and bars[i].c < bars[i].o and bars[i - 1].c < vw[i - 1]: vw_event = 'rejected'
    spread = None; mid = None
    if quote and quote.get('bid') and quote.get('ask') and quote['ask'] >= quote['bid'] > 0:
        mid = (quote['bid'] + quote['ask']) / 2; spread = (quote['ask'] - quote['bid']) / mid * 100
    levels = {k_: v_ for k_, v_ in dict(or_high=orh, or_low=orl, pm_high=pmh if now_m >= RTH_OPEN else None,
              pm_low=pml if now_m >= RTH_OPEN else None, prior_high=daily.get('prior_high'), prior_low=daily.get('prior_low'),
              high20=daily.get('high20'), low20=daily.get('low20')).items() if v_}
    up_lv = [v_ for v_ in levels.values() if v_ > px]; dn_lv = [v_ for v_ in levels.values() if v_ < px]
    res = min(up_lv) if up_lv else None; sup = max(dn_lv) if dn_lv else None
    return dict(sym=sym, t=last.t, m=last.m, price=px, prior_close=prior_close, chg_pct=(px / prior_close - 1) * 100, gap_pct=gap,
                volume=vol, dollar_volume=dvol, rvol=rvol, adv=adv_shares, spread_pct=spread, mid=mid, vwap=v_now,
                vwap_pos='above' if px > v_now else 'below' if px < v_now else 'at', vwap_event=vw_event,
                vwap_ext_atr=(px - v_now) / a5, atr5=a5, atr_daily=daily.get('atr14'), trend_1m=t1, trend_5m=t5,
                or_high=orh, or_low=orl, pm_high=pmh, pm_low=pml, hod=hod, lod=lod, open=op, levels=levels,
                resistance=res, support=sup, vol_trend=vol_trend,
                new_high=bool(daily.get('high20') and hod > daily['high20']), new_low=bool(daily.get('low20') and lod < daily['low20']),
                range_pct=(hod - lod) / prior_close * 100, confirm_minutes=k)

# ------------------------------------------------------------------ setups: breakout (long) / breakdown (bearish)
def _side_levels(f, side):
    L = f['levels']
    keys = ('or_high', 'pm_high', 'prior_high', 'high20') if side > 0 else ('or_low', 'pm_low', 'prior_low', 'low20')
    return [(k, L[k]) for k in keys if k in L]

def _evaluate(f, bars, side, cfg=DEFAULTS, catalyst=None):
    """One side of one stock. Returns dict(status, checks, warnings, level, trigger, stop, target, reasons).
    status: confirmed | developing | extended | rejected | watching. Only 'confirmed' may become an order."""
    S = cfg['signals']; R = cfg['risk']
    out = dict(side=side, status='watching', checks=[], warnings=[], level=None, level_name=None, trigger=None, stop=None, target=None, reasons=[])
    if f is None or not bars: out['status'] = 'rejected'; out['reasons'] = ['no data']; return out
    k = f['confirm_minutes']; B = resample(bars, k) if k > 1 else bars
    if k > 1 and B and B[-1].m + k > bars[-1].m + 1: B = B[:-1]           # the current k-minute bar has not closed yet
    if len(B) < 3: out['reasons'] = ['not enough closed bars yet']; return out
    a = f['atr5']; px = f['price']; buf = S['breakout_buffer_pct'] / 100
    beyond = (lambda x, L: x > L * (1 + buf)) if side > 0 else (lambda x, L: x < L * (1 - buf))
    back = (lambda x, L: x <= L) if side > 0 else (lambda x, L: x >= L)
    # find the most recent break of a level, within the lookback
    brk = None
    for name, L in _side_levels(f, side):
        for i in range(len(B) - 1, max(0, len(B) - 1 - S['lookback_bars']) - 1, -1):
            if i >= 1 and beyond(B[i].c, L) and not beyond(B[i - 1].c, L):
                if brk is None or i > brk[2]: brk = (name, L, i)
                break
    W = out['warnings']
    if f['spread_pct'] is not None and f['spread_pct'] > S['max_spread_pct']: W.append(f"wide spread {f['spread_pct']:.2f}%")
    if f['trend_1m'] and f['trend_5m'] and f['trend_1m'] != f['trend_5m']: W.append('1-minute and 5-minute trends disagree')
    if abs(f['vwap_ext_atr']) > S['max_vwap_extension_atr']: W.append(f"{abs(f['vwap_ext_atr']):.1f} ATR from VWAP")
    if len(bars) >= 6:
        avgv = sum(b.v for b in bars[-11:-1]) / max(1, len(bars[-11:-1]))
        for b in bars[-5:]:
            if (b.h - b.l) > S['outlier_atr'] * a / math.sqrt(5) * 1.0 and b.v < 0.2 * max(avgv, 1): W.append('single outlier print in the last 5 minutes'); break
    if brk is None:
        # nothing broken: is it building toward a level?
        lv = [(n, L) for n, L in _side_levels(f, side) if (L > px if side > 0 else L < px)]
        if lv:
            n, L = min(lv, key=lambda x: abs(x[1] - px))
            out.update(level=L, level_name=n)
            dist = abs(L - px)
            if dist <= a and (f['rvol'] or 0) >= S['min_rvol'] * 0.75:
                out['status'] = 'developing'; out['reasons'] = [f"{dist / px * 100:.2f}% from {n.replace('_', ' ')}, volume building"]
            else: out['reasons'] = ['no level broken']
        else: out['reasons'] = ['no level to break on this side']
        passed = [L for _, L in _side_levels(f, side) if (L < px if side > 0 else L > px)]
        far_level = passed and min(abs(px - L) for L in passed) / a > S['max_level_extension_atr']
        far_vwap = abs(f['vwap_ext_atr']) > S['max_vwap_extension_atr'] and (f['vwap_ext_atr'] > 0) == (side > 0)
        if (far_level and ((px > f['vwap']) if side > 0 else (px < f['vwap']))) or far_vwap:
            out['status'] = 'extended'; out['reasons'] = ['extended: already moved well past its levels, no reasonable entry nearby']
        return out
    name, L, i = brk; bb = B[i]; after = B[i + 1:]
    out.update(level=L, level_name=name)
    C = out['checks']
    def chk(n, ok, d): C.append(dict(name=n, ok=ok, detail=d))
    chk('close beyond level', True, f"{k}-min close {bb.c:.4g} {'above' if side > 0 else 'below'} {name.replace('_', ' ')} {L:.4g}")
    prior = B[max(0, i - 10):i]; pv = sum(b.v for b in prior) / max(1, len(prior))
    rv = f['rvol']
    vol_ok = (rv is not None and rv >= S['min_rvol']) and pv > 0 and bb.v >= S['min_bar_volume_mult'] * pv
    chk('volume supports the move', vol_ok, f"rel. volume {rv:.1f}x (need {S['min_rvol']}x), break bar {bb.v / pv if pv else 0:.1f}x recent bars" if rv is not None else 'relative volume unknown')
    hold_ok = None
    if any(back(b.c, L) for b in after): hold_ok = False
    elif len(after) >= S['hold_bars']: hold_ok = True
    else:
        tol = S['retest_tolerance_pct'] / 100
        if after and any((b.l <= L * (1 + tol) if side > 0 else b.h >= L * (1 - tol)) for b in after) and not back(after[-1].c, L): hold_ok = True
    chk('holds the level / retest', hold_ok, 'closed back through the level' if hold_ok is False else
        f"{len(after)} of {S['hold_bars']} closes held" if hold_ok is None else f"held {len(after)} closes")
    sp = f['spread_pct']
    chk('spread acceptable', None if sp is None else sp <= S['max_spread_pct'], 'no real-time quote' if sp is None else f"{sp:.2f}% (max {S['max_spread_pct']}%)")
    mind = cfg['candidates']['min_today_dollar_volume_rth']
    chk('liquidity', f['dollar_volume'] >= mind, f"${f['dollar_volume'] / 1e6:.2f}M traded today (min ${mind / 1e6:.2f}M)")
    vw_ok = (px > f['vwap']) if side > 0 else (px < f['vwap'])
    chk('VWAP agrees', vw_ok, f"price {'above' if px > f['vwap'] else 'below'} VWAP {f['vwap']:.4g}")
    tr_bad = f['trend_1m'] == -side and f['trend_5m'] == -side
    chk('trend agrees', not tr_bad, f"1-min {'up' if f['trend_1m'] > 0 else 'down' if f['trend_1m'] < 0 else 'flat'}, 5-min {'up' if f['trend_5m'] > 0 else 'down' if f['trend_5m'] < 0 else 'flat'}")
    # warning signs specific to the break
    rng = bb.h - bb.l
    wick = ((bb.h - max(bb.o, bb.c)) if side > 0 else (min(bb.o, bb.c) - bb.l)) / rng if rng > 0 else 0
    if wick > S['wick_max']: W.append(f"long {'upper' if side > 0 else 'lower'} wick on the break bar ({wick * 100:.0f}% of range)")
    if hold_ok is False: W.append('break reversed right away')
    if after and len(after) >= 2 and sum(b.v for b in after) / len(after) < 0.5 * bb.v and \
       ((after[-1].c <= bb.c) if side > 0 else (after[-1].c >= bb.c)): W.append('weak follow-through on falling volume')
    if bb.v < 0.2 * max(pv, 1) and rng > S['outlier_atr'] * a / math.sqrt(5): W.append('break made by a single outlier print')
    ext_level = abs(px - L) / a
    # stop / target
    stop = (min(L, min(b.l for b in after) if after else bb.l) - 0.1 * a) if side > 0 else (max(L, max(b.h for b in after) if after else bb.h) + 0.1 * a)
    if side > 0: stop = min(stop, px - 0.25 * a)
    else: stop = max(stop, px + 0.25 * a)
    risk = abs(px - stop)
    out.update(trigger=px, stop=round(stop, 4), target=round(px + side * S['target_r'] * risk, 4))
    failed = [c['name'] for c in C if c['ok'] is False]; pending = [c['name'] for c in C if c['ok'] is None]
    hard = hold_ok is False or any('outlier' in w for w in W if 'break made' in w) or (sp is not None and sp > S['max_spread_pct'] * 2)
    if hard: out['status'] = 'rejected'
    elif ext_level > S['max_level_extension_atr'] or (abs(f['vwap_ext_atr']) > S['max_vwap_extension_atr'] and (f['vwap_ext_atr'] > 0) == (side > 0)):
        out['status'] = 'extended'
    elif failed: out['status'] = 'developing' if set(failed) <= {'spread acceptable'} else 'rejected' if len(failed) >= 3 else 'developing'
    elif pending: out['status'] = 'developing'
    elif any(('outlier' in w) or ('reversed' in w) for w in W): out['status'] = 'rejected'
    else: out['status'] = 'confirmed'
    out['reasons'] = ([f"failed: {', '.join(failed)}"] if failed else []) + ([f"waiting: {', '.join(pending)}"] if pending else []) + \
                     (['extended: no reasonable entry nearby'] if out['status'] == 'extended' else [])
    if out['status'] == 'confirmed': out['reasons'] = ['all confirmations passed']
    return out

def strong_checks(f, side, catalyst, S):
    """the stocks-in-play filter as named checks (name, ok, detail)"""
    out = []
    if S.get('strong_only'):
        x = S['strong_min_day_change_pct']; chg = f['chg_pct']
        out.append(('strong mover', chg >= x if side > 0 else chg <= -x, f"{chg:+.1f}% on the day (need {'+' if side > 0 else '-'}{x:g}%)"))
        rv = f['rvol'] or 0
        out.append(('heavy volume', rv >= S['strong_min_rvol'], f"{rv:.1f}x normal for the time of day (need {S['strong_min_rvol']:g}x)"))
        if S['strong_require_catalyst']:
            c = catalyst or {}
            good = [t for t in (c.get('types') or []) if t not in NEGATIVE] if c.get('verified') else []
            ok = bool(good) if side > 0 else bool(c.get('verified') or c.get('negative'))
            out.append(('real news catalyst', ok, (', '.join(good) + ': ' + (c.get('headline') or '')[:80]) if good else 'no verified catalyst found'))
    if S.get('block_negative_news') and side > 0 and catalyst and catalyst.get('negative'):
        out.append(('no dilution / negative news', False, ', '.join(catalyst['negative'])))
    return out

def evaluate(f, bars, side, cfg=DEFAULTS, catalyst=None):
    """One side of one stock, plus the optional strong-stocks filter. Only 'confirmed' may become an order."""
    out = _evaluate(f, bars, side, cfg, catalyst)
    if f is None: return out
    sc = strong_checks(f, side, catalyst, cfg['signals'])
    if not sc: return out
    out['checks'] = [dict(name=n, ok=o, detail=d) for n, o, d in sc] + out['checks']
    bad = [n for n, o, d in sc if not o]
    if bad and out['status'] in ('confirmed', 'developing', 'watching'):
        out['status'] = 'rejected' if out['status'] != 'watching' else 'watching'
        out['reasons'] = [f"not a strong stock: {', '.join(bad)}"] + [r for r in out['reasons'] if r != 'all confirmations passed']
    return out

def rank_score(f, ev_long, ev_short, cat=None):
    """Ranks developing, usable setups, not the biggest % gainers. Returns (score, reasons)."""
    why, s = [], 0.0
    rv = f['rvol'] or 0
    s += min(rv, 10) / 10 * 30; why.append(f"rel. volume {rv:.1f}x")
    lq = min(1.0, max(0.0, (math.log10(max(f['dollar_volume'], 1)) - 5) / 3)); s += lq * 20
    best = max((ev_long, ev_short), key=lambda e: {'confirmed': 4, 'developing': 3, 'watching': 1, 'extended': 0, 'rejected': 0}[e['status']])
    s += {'confirmed': 30, 'developing': 20, 'watching': 5, 'extended': -5, 'rejected': -10}[best['status']]
    why.append(f"{'long' if best['side'] > 0 else 'bearish'} {best['status']}")
    if f['vol_trend'] == 'increasing': s += 6; why.append('volume increasing')
    elif f['vol_trend'] == 'fading': s -= 6; why.append('volume fading')
    if f['spread_pct'] is not None:
        s -= min(f['spread_pct'], 2) * 8
        if f['spread_pct'] > 0.5: why.append(f"spread {f['spread_pct']:.2f}%")
    s -= 3 * len(best['warnings'])
    good = [t for t in (cat or {}).get('types', []) if t not in NEGATIVE] if cat and cat.get('verified') else []
    if good: s += 8; why.append(good[0].lower() + ' news')
    if cat and cat.get('negative'): why.append('negative news: ' + ', '.join(cat['negative']))
    return round(s, 1), why, best

# ------------------------------------------------------------------ sizing and risk gates
def size_position(entry, stop, equity, start_equity, open_exposure, buying_power, side, cfg=DEFAULTS):
    """Shares from the stop distance and dollar risk. Equity used is the lower of now and start of day, so a losing day
    never sizes up to win it back. Buying power only ever caps the size, it never sets it."""
    R = cfg['risk']
    dist = abs(entry - stop)
    if entry <= 0 or dist <= 0 or (side > 0 and stop >= entry) or (side < 0 and stop <= entry):
        return dict(shares=0, reason='invalid stop')
    base = min(equity, start_equity) if start_equity else equity
    risk_d = base * R['risk_per_trade_pct'] / 100
    sh = math.floor(risk_d / dist)
    caps = dict(risk=sh, position=math.floor(base * R['max_position_pct'] / 100 / entry),
                exposure=math.floor(max(0.0, base * R['max_exposure_pct'] / 100 - open_exposure) / entry),
                buying_power=math.floor(max(0.0, buying_power) / entry))
    sh = min(caps.values())
    why = min(caps, key=caps.get)
    if sh < 1: return dict(shares=0, reason=f'size rounds to 0 shares (limited by {why.replace("_", " ")})', caps=caps)
    return dict(shares=sh, risk_dollars=round(sh * dist, 2), cost=round(sh * entry, 2), limited_by=why, caps=caps, risk_budget=round(risk_d, 2))

def entry_blocks(ctx, cfg=DEFAULTS):
    """Every reason a new paper entry is not allowed right now. Empty list = allowed. ctx keys:
    feed_realtime, feed_complete, quote_age_s, bar_age_s, control, now_m, city_pnl_today, account_pnl_today, start_equity,
    open_positions, exposure, daytrade_count, equity, side, sym_open, sym_traded_today, paper_verified, market_open"""
    R, F = cfg['risk'], cfg['feed']; b = []
    if not ctx.get('paper_verified'): b.append('paper account not verified')
    if not ctx.get('market_open'): b.append('market closed')
    if F['require_realtime_sip'] and not (ctx.get('feed_realtime') and ctx.get('feed_complete')):
        b.append('feed is ' + ('delayed' if not ctx.get('feed_realtime') else 'partial (one exchange)') + ': entries need real-time full-market (SIP) data')
    qa, ba = ctx.get('quote_age_s'), ctx.get('bar_age_s')
    if qa is None or qa > F['max_quote_age_s']: b.append('quote stale or missing' + (f' ({qa:.0f}s old)' if qa is not None else ''))
    if ba is None or ba > F['max_bar_age_s']: b.append('price bars stale' + (f' ({ba:.0f}s old)' if ba is not None else ''))
    c = ctx.get('control', 'on')
    if c != 'on': b.append(f'entries paused by control.json ({c})')
    m = ctx.get('now_m', 0)
    if not (hhmm(R['entries_from']) <= m < hhmm(R['entries_until'])): b.append(f"outside entry hours {R['entries_from']}-{R['entries_until']} ET")
    se = ctx.get('start_equity') or ctx.get('equity') or 0
    lim = se * R['max_daily_loss_pct'] / 100
    if ctx.get('city_pnl_today', 0) <= -lim or ctx.get('account_pnl_today', 0) <= -lim:
        b.append(f'daily loss lockout (limit -${lim:,.2f})')
    if ctx.get('open_positions', 0) >= R['max_open_positions']: b.append(f"max open positions ({R['max_open_positions']})")
    if ctx.get('exposure', 0) >= se * R['max_exposure_pct'] / 100: b.append('max exposure reached')
    if (ctx.get('equity') or 0) < 25000 and ctx.get('daytrade_count', 0) >= R['max_day_trades']:
        b.append(f"day-trade limit: {ctx.get('daytrade_count')} day trades in 5 days (account under $25K)")
    if ctx.get('side', 1) < 0 and not R['allow_short_orders']: b.append('short orders are off (bearish setups are watch-only)')
    if ctx.get('sym_open'): b.append('already holding this stock (no adding / averaging down)')
    if R['one_entry_per_symbol_per_day'] and ctx.get('sym_traded_today'): b.append('already traded this stock today')
    return b

def limit_price(side, bid, ask, cfg=DEFAULTS):
    off = cfg['risk']['limit_offset_pct'] / 100
    p = ask * (1 + off) if side > 0 else bid * (1 - off)
    return round(p, 4 if p < 1 else 2)

# ------------------------------------------------------------------ whole-market candidate lists (same code live and in replay)
def candidate_lists(rows, daily, m, cfg=DEFAULTS):
    """rows: {sym: dict(px, chg, v, dv, rv, hi, lo)} from the whole-market snapshot. Returns {list_name: [syms]}.
    A stock can be on a list (worth watching) without being allowed to trade."""
    C = cfg['candidates']; mind = C['min_today_dollar_volume_pre'] if m < RTH_OPEN else C['min_today_dollar_volume_rth']
    lists = {k: [] for k in ('gainers', 'decliners', 'unusual_volume', 'new_highs', 'new_lows', 'near_levels')}
    near = C['near_level_pct'] / 100
    for s, r in rows.items():
        if r['dv'] < mind: continue
        d = daily[s]
        if r['chg'] >= C['move_pct']: lists['gainers'].append(s)
        if r['chg'] <= -C['move_pct']: lists['decliners'].append(s)
        if r['rv'] and r['rv'] >= C['unusual_rvol']: lists['unusual_volume'].append(s)
        if r['hi'] and r['hi'] > d['high20']: lists['new_highs'].append(s)
        if r['lo'] and r['lo'] < d['low20']: lists['new_lows'].append(s)
        if any(abs(r['px'] / L - 1) <= near for L in (d['prior_high'], d['prior_low'], d['high20'], d['low20']) if L) and (r['rv'] or 0) >= 1.5:
            lists['near_levels'].append(s)
    return lists

def prerank(syms, rows):
    """cheap order for choosing which candidates get the full minute-by-minute analysis"""
    return sorted(syms, key=lambda s: -(min(rows[s]['rv'] or 0, 20) * 2 + math.log10(max(rows[s]['dv'], 1)) + min(abs(rows[s]['chg']), 30) * 0.1))

# ------------------------------------------------------------------ fees (Alpaca: $0 commission; regulatory fees on sales)
def sec_rate(d):
    if d < date(2025, 5, 14): return 27.80e-6
    if d < date(2026, 4, 4): return 0.0
    return 20.60e-6

def taf(d):
    if d.year <= 2025: return 0.000166, 8.30
    if d.year == 2026: return 0.000195, 9.79
    return 0.000232, 11.61

def sale_fees(d, shares, price):
    r, mx = taf(d)
    return round(shares * price * sec_rate(d) + min(mx, shares * r), 4)

# ------------------------------------------------------------------ simulated fills (replay)
def sim_limit_fill(side, limit, bars_after, max_participation=0.10, max_wait_bars=1):
    """Fills a marketable limit only if a later bar trades through it, at no better than the limit; size capped at a share of
    that bar's volume (partial fills). Returns (filled_shares_cap, price, bar) or (0, None, None) = failed fill."""
    for b in bars_after[:max_wait_bars]:
        if (side > 0 and b.l <= limit) or (side < 0 and b.h >= limit):
            px = min(limit, max(b.o, b.l)) if side > 0 else max(limit, min(b.o, b.h))
            return int(b.v * max_participation), px, b
    return 0, None, None

def sim_exit(side, stop, target, bars_after, flat_m, slip):
    """Walks bars after entry. A gap through the stop fills at the open (worse), never at the stop. Stop is checked
    before target inside a bar (worst case). Missing minutes (possible halt) are handled the same way: next available open."""
    for b in bars_after:
        if b.m >= flat_m: return b.o - side * slip * b.o, b, 'time'
        if side > 0:
            if b.o <= stop: return b.o * (1 - slip), b, 'stop-gap'
            if b.l <= stop: return stop * (1 - slip), b, 'stop'
            if b.h >= target: return target * (1 - slip), b, 'target'
        else:
            if b.o >= stop: return b.o * (1 + slip), b, 'stop-gap'
            if b.h >= stop: return stop * (1 + slip), b, 'stop'
            if b.l <= target: return target * (1 + slip), b, 'target'
    if bars_after: b = bars_after[-1]; return b.c * (1 - side * slip), b, 'last-bar'
    return None, None, 'no-data'

# ------------------------------------------------------------------ news
CATS = [('EARNINGS', r'\bearnings\b|quarterly results|\bq[1-4]\b.*results|revenue|\beps\b|guidance|fiscal (year|quarter)'),
        ('REGULATORY', r'\bfda\b|approv|clearance|\bema\b|breakthrough (therapy )?designation|orphan drug|\bpdufa\b|\bcrl\b|complete response letter|510\(k\)'),
        ('TRIAL', r'phase (1|2|3|i{1,3})\b|clinical trial|topline|data readout|primary endpoint|enrollment|positive (results|data)|statistically significant'),
        ('PRODUCT', r'\blaunch|unveil|introduces|commercial(ly)? available|first commercial|first shipment|receives? .{0,30}\border\b|record (revenue|sales|orders)'),
        ('PATENT', r'\bpatent'),
        ('CONTRACT', r'\bcontract\b|awarded|\baward\b|purchase order|\bdod\b|department of|government order|supply agreement'),
        ('DEAL', r'merger|acquisi|to acquire|buyout|takeover|definitive agreement|tender offer'),
        ('PARTNERSHIP', r'partnership|collaborat|strategic alliance|joint venture|licens(e|ing) agreement'),
        ('ANALYST', r'upgrade|downgrade|price target|initiates coverage|reiterat|overweight|underweight|outperform'),
        ('OFFERING', r'\boffering\b|registered direct|private placement|at-the-market|\batm\b program|priced .* shares|shelf registration'),
        ('CONVERTIBLE', r'convertible'), ('WARRANTS', r'\bwarrants?\b'),
        ('REVERSE_SPLIT', r'reverse (stock )?split|share consolidation'),
        ('COMPLIANCE', r'nasdaq.*(notice|deficien|compliance|delist)|minimum bid|non-?compliance|delist'),
        ('GOING_CONCERN', r'going concern|substantial doubt'), ('BANKRUPTCY', r'bankrupt|chapter 11|chapter 7'),
        ('FINANCING', r'financing|credit facility|loan agreement|raises \$|funding round')]
NEGATIVE = {'OFFERING', 'CONVERTIBLE', 'WARRANTS', 'REVERSE_SPLIT', 'COMPLIANCE', 'GOING_CONCERN', 'BANKRUPTCY'}
PROMO = r'if you invested|could soar|to buy now|stocks to buy|top \d+ stocks|millionaire|don.t miss|next (nvidia|tesla|amazon)|skyrocket|massive upside|hot stock|penny stocks? to watch|motley fool|why .* stock is (up|down|soaring|falling) today'
ROUNDUP = r'stocks moving|movers|top gainers|top losers|biggest movers|stocks to watch|mid-?day update|market update|premarket session|session\b.*(gainers|losers)|here.s why|these stocks|shares are trading (higher|lower)'
RUMOR = r'reportedly|rumou?r|according to (people|sources)|said to be|in talks|could be|may be considering|speculat|unconfirmed|social media|reddit|stocktwits|twitter|\bx post\b'

def norm_headline(h):
    return ' '.join(re.sub(r'[^a-z0-9 ]', ' ', (h or '').lower()).split()[:14])

@lru_cache(maxsize=20000)
def classify(headline, summary='', n_symbols=1):
    txt = f"{headline} {summary}".lower(); hl = (headline or '').lower()
    types = [n for n, rx in CATS if re.search(rx, hl)] or [n for n, rx in CATS if re.search(rx, txt)]
    promo = bool(re.search(PROMO, txt)); roundup = bool(re.search(ROUNDUP, hl)) or n_symbols > 4
    rumor = bool(re.search(RUMOR, txt))
    neg = [t for t in types if t in NEGATIVE]
    conf = 'low' if (promo or roundup or rumor) else 'high' if types else 'medium'
    return dict(types=types, negative=neg, promo=promo, roundup=roundup, rumor=rumor, confidence=conf)

def group_news(items, now_ts, prior_close_ts, stale_h=24):
    """items: dict(id, t(epoch), received(epoch), h, s, u, sy, sm). Groups repeats of the same story, tags each group."""
    groups = {}
    for it in sorted(items, key=lambda x: x['t']):
        key = norm_headline(it['h'])
        g = groups.get(key)
        if g is None:
            c = classify(it['h'], it.get('sm', ''), len(it.get('sy') or []))
            g = groups[key] = dict(it, repeats=0, sources=[it.get('s')], **{k: (list(v) if isinstance(v, list) else v) for k, v in c.items()})
        else:
            g['repeats'] += 1; g['sy'] = sorted(set(g['sy']) | set(it.get('sy') or []))
            if it.get('s') not in g['sources']: g['sources'].append(it.get('s'))
    out = []
    for g in groups.values():
        age_h = (now_ts - g['t']) / 3600
        g['stale'] = age_h > stale_h or (prior_close_ts is not None and g['t'] < prior_close_ts - 6 * 3600)
        if g['stale'] and g['confidence'] == 'high': g['confidence'] = 'medium'
        g['verified'] = g['confidence'] == 'high' and not g['stale']
        out.append(g)
    return sorted(out, key=lambda x: -x['t'])

def catalyst_for(sym, groups):
    """The best news context for one stock. If nothing qualifies: verified=False and text 'no verified catalyst found'."""
    mine = [g for g in groups if sym in (g.get('sy') or [])]
    neg = sorted({n for g in mine if not g['stale'] for n in g['negative']})
    good = [g for g in mine if g['verified']]
    if good:
        g = good[0]
        return dict(verified=True, types=g['types'], negative=neg, headline=g['h'], source=g.get('s'), t=g['t'], url=g.get('u'), n=len(mine))
    return dict(verified=False, types=[], negative=neg, headline=None, text='no verified catalyst found', n=len(mine))

# ------------------------------------------------------------------ market context
SECTORS = {'XLK': 'Technology', 'XLF': 'Financials', 'XLE': 'Energy', 'XLV': 'Health care', 'XLY': 'Consumer disc.', 'XLP': 'Staples',
           'XLI': 'Industrials', 'XLB': 'Materials', 'XLU': 'Utilities', 'XLRE': 'Real estate', 'XLC': 'Communication'}
INDEXES = ['SPY', 'QQQ', 'IWM', 'DIA']

def market_context(etf, breadth):
    """etf: {sym: dict(chg_pct, above_vwap, t)}; breadth: dict(up, down, flat)"""
    idx = {s: etf[s] for s in INDEXES if s in etf}
    ups = sum(1 for v in idx.values() if v.get('chg_pct', 0) > 0.1); dns = sum(1 for v in idx.values() if v.get('chg_pct', 0) < -0.1)
    direction = 'up' if ups >= 3 else 'down' if dns >= 3 else 'mixed'
    sec = sorted(((s, SECTORS[s], etf[s]['chg_pct']) for s in SECTORS if s in etf and etf[s].get('chg_pct') is not None), key=lambda x: -x[2])
    tot = sum(breadth.values()) or 1
    vol = etf.get('VIXY', {}).get('chg_pct')
    return dict(direction=direction, indexes=idx, sectors=sec, breadth=dict(breadth, up_pct=round(breadth.get('up', 0) / tot * 100, 1)),
                volatility=dict(proxy='VIXY', chg_pct=vol, state=None if vol is None else 'rising' if vol > 2 else 'falling' if vol < -2 else 'steady'),
                events=None, events_note='no economic-calendar source is connected, so scheduled events are not shown')
