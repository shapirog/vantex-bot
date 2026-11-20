"""
VANTEX City research: SELLING PUT CREDIT SPREADS (collect the option premium buyers overpay). Research only: NO orders.

Why (2026-11-20): options_bt.md showed call BUYERS lose 1-4% a week on real Alpaca prices; the seller is on the other side.
A put credit spread = sell a put below the price, buy a cheaper put further below. Cash comes in up front; the most you can
lose is (width - credit), known in advance. Rules fixed before running:
  underlyings  SPY, QQQ, IWM, DIA and the 15 most-traded optionable stocks (20-day dollar volume, price >= $20) each week
  entry        the session after each Friday close, at the options' daily VWAP; we receive short*(1-3%) - long*(1+3%)
  short put    ~1 week: first Friday >= 6 days out, strike ~2% below the price
               ~1 month: first monthly (3rd Friday) >= 30 days out, strike ~5% below the price
  long put     the listed strike closest to (short strike - width), width = ~2.5% of the price (1 week: ~1.5%)
  exits        A) hold to expiration: settles at intrinsic value from the stock's close on expiration day
               B) managed: close when the spread can be bought back for <= 50% of the credit (take profit) or when it costs
                  >= 2x the credit (stop), checked at each day's option VWAPs (+/-3% spread penalty), else expiration
  returns      per trade on the money at risk (width - credit); dollars at $500 risk per trade
  periods      Feb 2024 - now (Alpaca option history starts Feb 2024; covers the April 2025 crash). Only trades that have expired.
  compared     SPY buy and hold over the same span.

  python city_putspread.py   -> live-replay/putspread.md / .json / putspread_trades.csv
"""
import csv, io, json, math, os, sys
from collections import defaultdict
from datetime import date, datetime, timedelta

from city_engine import Data
from city_replay import ET, log, publish
from city_overnight import universe
from city_options_bt import occ, third_friday, opt_bars

PEN = 0.03
ETFS = ['SPY', 'QQQ', 'IWM', 'DIA']
STAKE = 500.0
PLANS = {'~1 week': dict(min_days=6, monthly=False, otm=0.02, width=0.015), '~1 month': dict(min_days=30, monthly=True, otm=0.05, width=0.025)}

def expiry_for(entry, min_days, monthly):
    t = entry + timedelta(days=min_days)
    if monthly:
        y, m = t.year, t.month; f = third_friday(y, m)
        if f < t: y, m = (y + 1, 1) if m == 12 else (y, m + 1); f = third_friday(y, m)
        return f
    while t.weekday() != 4: t += timedelta(days=1)
    return t

def candidates(px, target, n=4):
    """listed-looking strikes around target, using the usual increments for that price level"""
    steps = (0.5, 1.0) if px < 25 else (1.0, 2.5) if px < 100 else (1.0, 2.5, 5.0, 10.0)
    out = set()
    for st in steps:
        base = math.floor(target / st) * st
        for k in range(-n, n + 1): out.add(round(base + k * st, 2))
    return sorted(x for x in out if x > 0)

def nearest_traded(ob, root, exp, strikes, target, day, below=None):
    best = None
    for k in strikes:
        if below is not None and k >= below: continue
        sym = occ(root, exp, 'P', k)
        if any(b['t'][:10] == day for b in ob.get(sym, [])):
            if best is None or abs(k - target) < abs(best - target): best = k
    return best

def px_on(ob, sym, day):
    for b in ob.get(sym, []):
        if b['t'][:10] == day: return b.get('vw') or b['c']
    return None

def settle(short_k, long_k, close):
    """value of the spread (what the seller owes) at expiration"""
    return max(0.0, short_k - close) - max(0.0, long_k - close)

def run_trade(ob, root, exp, sk, lk, d_in, days_after, und_close_exp, managed):
    s_sym, l_sym = occ(root, exp, 'P', sk), occ(root, exp, 'P', lk)
    s0, l0 = px_on(ob, s_sym, d_in), px_on(ob, l_sym, d_in)
    if s0 is None or l0 is None: return None
    credit = s0 * (1 - PEN) - l0 * (1 + PEN); width = sk - lk
    if credit <= 0.02 or credit >= width: return None
    risk = width - credit
    if managed:
        for d in days_after:
            s1, l1 = px_on(ob, s_sym, d), px_on(ob, l_sym, d)
            if s1 is None or l1 is None: continue
            cost = s1 * (1 + PEN) - l1 * (1 - PEN)
            if cost <= 0.5 * credit: return dict(credit=credit, risk=risk, pnl=credit - cost, how='take profit', exit_day=d)
            if cost >= 2 * credit: return dict(credit=credit, risk=risk, pnl=credit - cost, how='stop', exit_day=d)
    if und_close_exp is None: return None
    owe = settle(sk, lk, und_close_exp)
    return dict(credit=credit, risk=risk, pnl=credit - owe, how='expired' if owe == 0 else 'assigned/settled', exit_day=exp.isoformat())

def stats(T):
    if not T: return dict(n=0)
    r = [t['pnl'] / t['risk'] for t in T]; n = len(r); mu = sum(r) / n; srt = sorted(r)
    sd = (sum((x - mu) ** 2 for x in r) / max(1, n - 1)) ** 0.5
    return dict(n=n, win_pct=round(100 * sum(x > 0 for x in r) / n, 1), avg_on_risk_pct=round(100 * mu, 2), median_pct=round(100 * srt[n // 2], 2),
                worst_pct=round(100 * srt[0], 1), max_loss_trades_pct=round(100 * sum(x <= -0.95 for x in r) / n, 1),
                t=round(mu / (sd / n ** 0.5), 2) if sd else None)

def by_month(T):
    m = defaultdict(float)
    for t in T: m[t['exit_day'][:7]] += STAKE * t['pnl'] / t['risk']
    xs = list(m.values())
    return dict(months=len(xs), avg_usd=round(sum(xs) / len(xs), 0), up_pct=round(100 * sum(x > 0 for x in xs) / len(xs), 0),
                worst=min(m.items(), key=lambda x: x[1]) if m else None, total_usd=round(sum(xs), 0)) if xs else dict(months=0)

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    D = Data(key, sec)
    act = sorted(s for s, v in universe(key, sec).items() if v == 'active')
    s0 = datetime(2023, 12, 1, tzinfo=ET); s1 = datetime.now(ET) - timedelta(minutes=20)
    bars = {}
    for k in range(0, len(act + ETFS), 100):
        for s, L in D.bars((act + ETFS)[k:k + 100], '1Day', s0, s1, 'sip', 'raw').items():
            if len(L) > 40: bars[s] = {x['t'][:10]: x for x in L}
    cal = sorted(bars['SPY']); pos = {d: k for k, d in enumerate(cal)}
    weeks = [d for k, d in enumerate(cal) if d >= '2024-02-09' and k + 1 < len(cal) and date.fromisoformat(cal[k + 1]).isocalendar()[1] != date.fromisoformat(d).isocalendar()[1]]
    trades = []
    for w in weeks:
        k = pos[w]; d_in = cal[k + 1]; e_in = date.fromisoformat(d_in)
        liq = []
        for s, B in bars.items():
            if s in ETFS or w not in B or B[w]['c'] < 20: continue
            ds = [d for d in cal[max(0, k - 19):k + 1] if d in B]
            if len(ds) >= 15: liq.append((sum(B[d]['c'] * B[d]['v'] for d in ds) / len(ds), s))
        roots = ETFS + [s for _, s in sorted(liq, reverse=True)[:15]]
        plan = []
        for root in roots:
            if w not in bars.get(root, {}): continue
            px = bars[root][w]['c']
            for lab, P in PLANS.items():
                exp = expiry_for(e_in, P['min_days'], P['monthly'])
                if exp.isoformat() > cal[-1]: continue
                tgt = px * (1 - P['otm']); syms = [occ(root, exp, 'P', x) for x in candidates(px, tgt) + candidates(px, tgt - px * P['width'])]
                plan.append((root, lab, P, exp, px, tgt, sorted(set(syms))))
        allsyms = sorted({s for p in plan for s in p[6]})
        last_exp = max((p[3] for p in plan), default=e_in)
        ob = opt_bars(D, allsyms, d_in, last_exp.isoformat())
        for root, lab, P, exp, px, tgt, _ in plan:
            ks = candidates(px, tgt) + candidates(px, tgt - px * P['width'])
            sk = nearest_traded(ob, root, exp, ks, tgt, d_in)
            if sk is None: continue
            lk = nearest_traded(ob, root, exp, ks, sk - px * P['width'], d_in, below=sk)
            if lk is None: continue
            after = [d for d in cal if d_in < d <= exp.isoformat()]
            close_exp = bars[root].get(exp.isoformat(), {}).get('c')
            if close_exp is None:                                                # holiday expiry: last close before it
                prior = [d for d in cal if d <= exp.isoformat() and d in bars[root]]; close_exp = bars[root][prior[-1]]['c'] if prior else None
            for managed, mlab in ((False, 'hold to expiry'), (True, 'managed (50% profit / 2x stop)')):
                r = run_trade(ob, root, exp, sk, lk, d_in, after, close_exp, managed)
                if r: trades.append(dict(r, root=root, kind='ETF' if root in ETFS else 'stock', plan=lab, exits=mlab, entry=d_in, expiry=exp.isoformat(),
                                         short=sk, long=lk, und=px))
        log(w, 'priced', len(trades))
    res = {}; rows = ['| underlyings | expiry | exits | trades | win rate | avg return on risk | median | worst trade | lost ~all | t-stat | months | avg month ($500/trade) | months up | worst month | total |',
                      '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for kind in ('ETF', 'stock'):
        for lab in PLANS:
            for ex in ('hold to expiry', 'managed (50% profit / 2x stop)'):
                T = [t for t in trades if t['kind'] == kind and t['plan'] == lab and t['exits'] == ex]
                if not T: continue
                S = stats(T); M = by_month(T); res[f'{kind} | {lab} | {ex}'] = dict(S, month=M)
                wm = f"{M['worst'][0]}: ${M['worst'][1]:+,.0f}" if M.get('worst') else ''
                rows.append(f"| {'SPY/QQQ/IWM/DIA' if kind == 'ETF' else 'top-15 stocks'} | {lab} | {ex} | {S['n']} | {S['win_pct']}% | {S['avg_on_risk_pct']:+}% | {S['median_pct']:+}% | {S['worst_pct']}% | "
                            f"{S['max_loss_trades_pct']}% | {S['t']} | {M['months']} | ${M['avg_usd']:+,.0f} | {M['up_pct']:.0f}% | {wm} | ${M['total_usd']:+,.0f} |")
    spy = bars['SPY']; a, b = '2024-02-12', cal[-1]
    a = min(d for d in spy if d >= a); bh = spy[b]['c'] / spy[a]['o'] - 1
    md = ['# VANTEX City research: selling put credit spreads (Feb 2024 - now)', '',
          'Sell a put ~2% (weekly) or ~5% (monthly) below the price, buy one further below; credit at daily VWAPs minus 3% per leg. '
          'Return = profit / money at risk. Dollar columns: $500 at risk per trade, every signal taken (several trades open at once).', ''] + rows + [
          '', f'SPY buy and hold over the same span: {bh * 100:+.1f}%.', '',
          'Daily VWAPs, not live quotes: a real order may get a worse credit. Early assignment and dividends are ignored (European-style settlement at the '
          'expiration close). A backtest is not proof.']
    buf = io.StringIO(); w_ = csv.writer(buf); cols = ['root', 'plan', 'exits', 'entry', 'expiry', 'exit_day', 'und', 'short', 'long', 'credit', 'risk', 'pnl', 'how']
    w_.writerow(cols)
    for t in trades: w_.writerow([round(t[c], 4) if isinstance(t[c], float) else t[c] for c in cols])
    publish({}); publish({'putspread.md': '\n'.join(md) + '\n', 'putspread.json': res, 'putspread_trades.csv': buf.getvalue()})
    log('done', len(trades))

if __name__ == '__main__':
    main()
