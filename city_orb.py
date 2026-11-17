"""
VANTEX City strategy tester #1: the 5-minute opening-range breakout on stocks in play. Research only: places NO orders.

One strategy, tested on its own, following the published rules of Zarattini, Barbon & Aziz (2024),
"A Profitable Day Trading Strategy for the U.S. Equity Market":
  universe   1,000 most liquid stocks (14-day average dollar volume), price > $5, 14-day ATR > $0.50
  in play    relative volume of the first 5 minutes > 1; take the top 20 by that relative volume
  direction  first 5-minute candle (9:30-9:35) closes up -> long only above its high; closes down -> short only below its low
  entry      stop order at the range high (long) / low (short), any time after 9:35; fills at the level or the worse open
  stop       10% of the 14-day ATR from the entry
  exit       at the close (or the stop). Exit variants are tested separately below.
Sizing from the stop: risk per trade is a fixed share of equity, capped at an equal share (1/20) of 4x buying power.
Every decision is logged: ranked candidates, why each was skipped, entry, stop, exit and result in R and dollars.
Approximation (stated in the report): first-5-minute relative volume uses the stock's 14-day average daily volume times the
share of a normal day's volume done by 9:35 (measured on SPY), not the stock's own 14-day first-5-minute average.

  python city_orb.py dev 20     -> live-replay/orb_dev.md / .json  (test = the untouched Oct-Nov period: run once, at the end)
"""
import json, math, os, random, sys, time
from collections import Counter
from datetime import date, datetime, timedelta

import vantex_core as V
from city_engine import Data
from city_replay import Replay, ET, DEV, TEST, EXTRA_SLIP, log, publish

OR_END = 575                                                       # 9:35
CLOSE_EXIT = 959                                                   # exit on the 3:59 bar's close
VARIANTS = {
    'F1_paper': dict(name='F1. ORB as published (long + short, stop 10% ATR, exit at close)', sides=(1, -1), stop_atr=0.10, target_r=None),
    'F2_long': dict(name='F2. Same, long only', sides=(1,), stop_atr=0.10, target_r=None),
    'F3_2R': dict(name='F3. Same entries, exit at 2R target instead of the close', sides=(1, -1), stop_atr=0.10, target_r=2.0),
    'F4_wide': dict(name='F4. Same, wider stop (25% ATR), exit at close', sides=(1, -1), stop_atr=0.25, target_r=None),
}
P = dict(universe=1000, min_price=5.0, min_atr=0.50, top=20, min_rvol=1.0, risk_pct=0.5, leverage=4.0, max_spread_pct=0.5)

def select(uni, daily, BARS, curve):
    """stocks in play at 9:35, using only bars that closed before 9:35. Returns (ranked list, skip counts)."""
    skip = Counter()
    liquid = sorted((s for s in uni if daily[s]['prior_close'] > P['min_price'] and daily[s]['atr14'] > P['min_atr']),
                    key=lambda s: -daily[s]['adv_dollars'])[:P['universe']]
    frac = max(curve(OR_END - 1), 1e-4)
    rows = []
    for s in liquid:
        orb = [b for b in BARS.get(s, []) if V.RTH_OPEN <= b.m < OR_END]
        if not orb: skip['no trades in the first 5 minutes'] += 1; continue
        v5 = sum(b.v for b in orb); rv = v5 / (daily[s]['adv'] * frac) if daily[s]['adv'] else 0
        if rv <= P['min_rvol']: continue
        o, c = orb[0].o, orb[-1].c
        rows.append(dict(sym=s, rvol=round(rv, 2), open=o, close=c, high=max(b.h for b in orb), low=min(b.l for b in orb),
                         side=1 if c > o else -1 if c < o else 0, atr=daily[s]['atr14']))
    rows.sort(key=lambda r: -r['rvol'])
    return rows[:P['top']], skip, len(liquid)

def simulate(r, side, BARS, stop_atr, target_r):
    """walk the bars after 9:35: stop-entry at the range edge, then stop / target / close. Returns a trade dict or a skip reason."""
    lvl = r['high'] if side > 0 else r['low']
    after = [b for b in BARS[r['sym']] if OR_END <= b.m <= CLOSE_EXIT]
    for i, b in enumerate(after):
        if (side > 0 and b.h >= lvl) or (side < 0 and b.l <= lvl):
            entry = max(lvl, b.o) if side > 0 else min(lvl, b.o)              # gap through the level fills at the worse open
            dist = stop_atr * r['atr']; stop = entry - side * dist
            target = entry + side * target_r * dist if target_r else None
            rest = after[i:]
            for j, x in enumerate(rest):
                if j == 0:                                                     # entry bar: only a stop after the entry can count
                    if (side > 0 and x.c <= stop) or (side < 0 and x.c >= stop): return dict(entry=entry, exit=stop, why='stop', m_in=b.m, m_out=x.m, dist=dist)
                    continue
                if side > 0 and x.o <= stop: return dict(entry=entry, exit=x.o, why='stop-gap', m_in=b.m, m_out=x.m, dist=dist)
                if side < 0 and x.o >= stop: return dict(entry=entry, exit=x.o, why='stop-gap', m_in=b.m, m_out=x.m, dist=dist)
                if (side > 0 and x.l <= stop) or (side < 0 and x.h >= stop): return dict(entry=entry, exit=stop, why='stop', m_in=b.m, m_out=x.m, dist=dist)
                if target and ((side > 0 and x.h >= target) or (side < 0 and x.l <= target)):
                    return dict(entry=entry, exit=target, why='target', m_in=b.m, m_out=x.m, dist=dist)
            return dict(entry=entry, exit=rest[-1].c, why='close', m_in=b.m, m_out=rest[-1].m, dist=dist)
    return 'range never broken'

class ORB(Replay):
    def run_orb(self, d, cm, data, eq_by_variant):
        uni, daily, curve, BARS = data['uni'], data['daily'], data['curve'], data['BARS']
        picks, skip, n_liquid = select(uni, daily, BARS, curve)
        day_ts = datetime.combine(d, datetime.min.time(), ET).timestamp()
        out = {k: [] for k in VARIANTS}; rej = {k: Counter(skip) for k in VARIANTS}
        quotes = {}
        for k, VV in VARIANTS.items():
            eq = eq_by_variant[k]; pnl_day = 0.0
            for r in picks:
                side = r['side']
                if side == 0: rej[k]['first candle flat (no direction)'] += 1; continue
                if side not in VV['sides']: rej[k]['short side not tested in this variant'] += 1; continue
                t = simulate(r, side, BARS, VV['stop_atr'], VV['target_r'])
                if isinstance(t, str): rej[k][t] += 1; continue
                ts = day_ts + t['m_in'] * 60
                if (r['sym'], t['m_in']) not in quotes: quotes[(r['sym'], t['m_in'])] = self.quote_at(r['sym'], ts)
                q = quotes[(r['sym'], t['m_in'])]
                if not q: rej[k]['no quote at entry'] += 1; continue
                sp = (q['ask'] - q['bid']) / ((q['ask'] + q['bid']) / 2) * 100
                if sp > P['max_spread_pct']: rej[k]['spread too wide at entry'] += 1; continue
                slip = (q['ask'] - q['bid']) / 2 / t['entry'] + EXTRA_SLIP          # paid on the way in and again on the way out
                entry = t['entry'] * (1 + side * slip); exit_ = t['exit'] * (1 - side * slip)
                risk_d = eq * P['risk_pct'] / 100
                qty = min(math.floor(risk_d / t['dist']), math.floor(eq * P['leverage'] / P['top'] / entry))
                if qty < 1: rej[k]['size rounds to 0 shares'] += 1; continue
                fees = V.sale_fees(d, qty, exit_ if side > 0 else entry)
                pnl = side * (exit_ - entry) * qty - fees
                out[k].append(dict(day=d.isoformat(), sym=r['sym'], side='long' if side > 0 else 'short', rvol=r['rvol'], qty=qty, entry=round(entry, 4),
                                   stop=round(t['entry'] - side * t['dist'], 4), exit=round(exit_, 4), why=t['why'], m_in=t['m_in'], m_out=t['m_out'],
                                   pnl=round(pnl, 2), R=round(pnl / (qty * t['dist']), 3), fees=round(fees, 4)))
                pnl_day += pnl
            eq_by_variant[k] = eq + pnl_day
        spy = BARS.get('SPY', [])
        spy_day = (spy[-1].c / daily['SPY']['prior_close'] - 1) * 100 if spy and 'SPY' in daily else None
        log(d, 'liquid', n_liquid, 'in play', len(picks), {k: len(v) for k, v in out.items()})
        return dict(day=d.isoformat(), picks=picks, trades=out, rejected={k: dict(v) for k, v in rej.items()}, spy_pct=spy_day, liquid=n_liquid)

def stats(trades, days, start_eq=2500.0):
    T = trades; R = [t['R'] for t in T]
    wins = [t for t in T if t['pnl'] > 0]; losses = [t for t in T if t['pnl'] <= 0]
    daily = Counter()
    for t in T: daily[t['day']] += t['pnl']
    series = [daily.get(d, 0.0) for d in days]
    eq, peak, dd = start_eq, start_eq, 0.0
    for p in series: eq += p; peak = max(peak, eq); dd = max(dd, peak - eq)
    rets = [p / start_eq for p in series]
    mu = sum(rets) / len(rets) if rets else 0; sd = (sum((x - mu) ** 2 for x in rets) / (len(rets) - 1)) ** 0.5 if len(rets) > 1 else 0
    gw = sum(t['pnl'] for t in wins); gl = -sum(t['pnl'] for t in losses)
    return dict(trades=len(T), win_rate_pct=round(100 * len(wins) / len(T), 1) if T else None, net_pnl=round(sum(t['pnl'] for t in T), 2),
                expectancy_R=round(sum(R) / len(R), 3) if R else None, avg_win_R=round(sum(t['R'] for t in wins) / len(wins), 2) if wins else None,
                avg_loss_R=round(sum(t['R'] for t in losses) / len(losses), 2) if losses else None, profit_factor=round(gw / gl, 2) if gl > 0 else None,
                max_drawdown=round(dd, 2), sharpe_daily_annualized=round(mu / sd * 252 ** 0.5, 2) if sd > 0 else None,
                winning_days=sum(1 for p in series if p > 0), losing_days=sum(1 for p in series if p < 0), exits=dict(Counter(t['why'] for t in T)))

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    split = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else 'dev'; n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].strip() else 20
    cfg = json.load(open('city_config.json')) if os.path.exists('city_config.json') else {}
    RP = ORB(Data(key, sec), key, sec, cfg)
    a, b = DEV if split == 'dev' else TEST
    b = b or (date.today() - timedelta(days=1))
    ss = RP.sessions(a, b); random.Random(11).shuffle(ss); pick = sorted(ss[:n])
    eq = {k: 2500.0 for k in VARIANTS}; days = []
    for d, cm in pick:
        try:
            data = RP.load_day(d, cm); days.append(RP.run_orb(d, cm, data, eq)); del data
        except Exception as e: log('day failed', d, e)
    names = [x['day'] for x in days]
    out = dict(split=split, sessions=names, updated=datetime.now(ET).isoformat(timespec='seconds'), params=P,
               variants={k: dict(VV, sides=list(VV['sides']), summary=stats([t for x in days for t in x['trades'][k]], names),
                                 rejected=dict(sum((Counter(x['rejected'][k]) for x in days), Counter())),
                                 trades=[t for x in days for t in x['trades'][k]]) for k, VV in VARIANTS.items()},
               days=[dict(day=x['day'], spy_pct=x['spy_pct'], liquid=x['liquid'], in_play=[dict(sym=p['sym'], rvol=p['rvol'], side=p['side']) for p in x['picks']]) for x in days])
    spy = [x['spy_pct'] for x in days if x['spy_pct'] is not None]
    spy_total = (math.prod(1 + p / 100 for p in spy) - 1) * 100 if spy else None
    rows = ['| rule set | trades | win rate | avg win | avg loss | expectancy | profit factor | net P&L | max drawdown | Sharpe |', '|---|---|---|---|---|---|---|---|---|---|']
    for k, v in out['variants'].items():
        S = v['summary']
        rows.append(f"| {v['name']} | {S['trades']} | {S['win_rate_pct']}% | {S['avg_win_R']}R | {S['avg_loss_R']}R | {S['expectancy_R']}R | {S['profit_factor']} | ${S['net_pnl']} | ${S['max_drawdown']} | {S['sharpe_daily_annualized']} |")
    md = [f"# VANTEX City strategy test: 5-minute opening-range breakout on stocks in play - {split} - {len(days)} sessions", '',
          'One strategy, published rules, full real-time market data (what entries would need live), costs included: half the quoted spread in and out, '
          '0.02% extra slippage, SEC/FINRA fees. Every in-play stock that triggers is taken. $2,500 start, 0.5% risk per trade.',
          f"Buy-and-hold SPY over the same {len(spy)} sessions: {spy_total:+.2f}%." if spy_total is not None else '', ''] + rows + ['', '## Why candidates were not traded (F1)', ''] + \
         [f"- {k}: {v}" for k, v in sorted(out['variants']['F1_paper']['rejected'].items(), key=lambda x: -x[1])] + ['',
          'Approximation: first-5-minute relative volume = first-5-minute volume / (14-day average daily volume x share of a normal day done by 9:35, measured on SPY).',
          'A backtest is not proof. The Oct-Nov test period stays untouched until one rule set earns it.']
    publish({})
    publish({f'orb_{split}.json': out, f'orb_{split}.md': '\n'.join(md) + '\n'})

if __name__ == '__main__':
    main()
