"""
VANTEX City overnight trial: Strategy A (overnight bias) trading by itself on the PAPER account. Paper only.

Asked for by Guillo on 2026-11-17: start with the existing $2,500 paper account, same system, trade for 3 days, then stop.

What it does each trading day (all times New York):
  buy    (job starts ~3:10 pm)  picks stocks from last month-end's overnight-bias screen (one-sided 5%, published rule),
         ranked by t-statistic; with $2,500 that is the top 10 names, about $250 each, whole shares only (auction orders
         can't be fractional), skipping any stock that costs more than its slot. At 3:44 pm it sends market-on-close buys
         (time_in_force "cls", cutoff 3:50). If Alpaca rejects "cls", it falls back to a plain market order at 3:57.
  sell   (job starts ~8:05 pm)  sends market-on-open sells (time_in_force "opg", accepted after 7:00 pm for the next open)
         for exactly the shares this trial bought; nothing else in the account is touched.
  check  (job starts ~9:35 am)  anything of the trial's still held after the open is sold with a market order; fills are
         written to the ledger.
Safety: the PaperBroker refuses anything but a paper key and a paper account. Orders carry client_order_id 'ovn-'.
control.json  "trading": "stop" / "pause"  or  "overnight": "off"  blocks new buys (sells always run so nothing is left open).
After TRIAL_DAYS buy days it stops buying by itself. State and ledger: branch live-overnight (state.json, ledger.json).
This is a paper trial of the mechanics. Alpaca paper fills are simulated against quotes, not real auction prices.
"""
import json, math, os, sys, time, uuid
from datetime import date, datetime, timedelta

import requests

from city_broker import PaperBroker, PAPER_HOST
from city_engine import Data, gh_file
from city_replay import ET, OUT, log, publish
from city_overnight import universe, load_all, eligible, month_ends, TCRIT
from city_overnight_audit import regress

BRANCH = 'live-overnight'
BUDGET = float(os.environ.get('OVN_BUDGET', '2500'))
SLOTS = int(os.environ.get('OVN_SLOTS', '10'))
TRIAL_DAYS = int(os.environ.get('OVN_TRIAL_DAYS', '3'))
PREFIX = 'ovn-'

def now(): return datetime.now(ET)

def load_state():
    publish({}, branch=BRANCH)                                            # fetches the branch into OUT (first call only)
    st, led = {}, []
    try: st = json.load(open(f'{OUT}/state.json'))
    except Exception: pass
    try: led = json.load(open(f'{OUT}/ledger.json'))
    except Exception: pass
    st.setdefault('buy_days', []); st.setdefault('open', []); st.setdefault('events', [])
    return st, led

def save(st, led):
    st['updated'] = now().isoformat(timespec='seconds')
    publish({'state.json': st, 'ledger.json': led, 'summary.json': summary(st, led)}, branch=BRANCH)

def summary(st, led):
    closed = [x for x in led if x.get('exit_price')]
    pnl = sum((x['exit_price'] - x['entry_price']) * x['qty'] for x in closed)
    return dict(trial_days_done=len(st['buy_days']), trial_days=TRIAL_DAYS, open_positions=len(st['open']), closed_trades=len(closed),
                net_pnl=round(pnl, 2), winners=sum(1 for x in closed if x['exit_price'] > x['entry_price']), updated=now().isoformat(timespec='seconds'),
                note='paper trial of the overnight-bias strategy; paper fills are simulated, not real auction prices')

def control_blocks():
    ctl = gh_file('control.json') or {}
    t = str(ctl.get('trading', 'on')).lower(); o = str(ctl.get('overnight', 'on')).lower()
    return [f'control.json trading={t}'] if t in ('stop', 'pause', 'off') else ([f'control.json overnight={o}'] if o in ('off', 'stop', 'pause') else [])

def selection(D, key, sec, ref):
    """last completed month-end's screen, ranked by t-statistic (cached on the branch per month)"""
    cache = f'{OUT}/selection.json'
    try:
        c = json.load(open(cache))
        if c.get('month_end') and c['month_end'] < ref and c.get('for_month') == ref[:7]: return c
    except Exception: pass
    uni = {s: v for s, v in universe(key, sec).items() if v == 'active'}
    s0 = datetime.combine(date.fromisoformat(ref) - timedelta(days=420), datetime.min.time(), ET)
    stocks = load_all(D, sorted(uni), s0, datetime.combine(date.fromisoformat(ref), datetime.min.time(), ET))
    cal = sorted({d for S in stocks.values() for d in S[0]})
    me = [m for m in month_ends(cal) if m < ref and m[:7] < ref[:7]][-1]
    rows = []
    for s, S in stocks.items():
        try: i = S[0].index(me)
        except ValueError: continue
        if not eligible(S, i): continue
        r = regress(S, i)
        if r and r[2] >= TCRIT: rows.append(dict(sym=s, t=round(r[2], 3), intercept=r[0], last_close=S[2][-1]))
    rows.sort(key=lambda x: -x['t'])
    c = dict(month_end=me, for_month=ref[:7], passed=len(rows), ranked=rows, computed=now().isoformat(timespec='seconds'))
    json.dump(c, open(cache, 'w')); return c

def wait_until(h, m):
    while True:
        t = now()
        if (t.hour, t.minute) >= (h, m): return
        time.sleep(min(30, max(1, (datetime.combine(t.date(), datetime.min.time(), ET) + timedelta(hours=h, minutes=m) - t).total_seconds())))

def order(B, sym, qty, side, tif, typ='market'):
    B.verify(max_age_s=0)
    body = dict(symbol=sym, qty=str(int(qty)), side=side, type=typ, time_in_force=tif, client_order_id=f'{PREFIX}{side}-{sym}-{uuid.uuid4().hex[:10]}')
    r = B._req('POST', '/v2/orders', json=body)
    return r.ok, (r.json() if r is not None and r.content else {}), body

def do_buy(B, D, key, sec, dry=False):
    st, led = load_state(); today = now().date().isoformat()
    clk = B.clock()
    if not dry and not clk.get('is_open'): log('market closed today, nothing to do'); return
    if not dry and today in st['buy_days']: log('already bought today'); return
    if len(st['buy_days']) >= TRIAL_DAYS: log(f'trial finished ({TRIAL_DAYS} days): no new buys'); st['events'].append(dict(t=today, kind='trial over')); save(st, led); return
    bl = control_blocks()
    if bl: log('blocked:', bl); st['events'].append(dict(t=today, kind='blocked', why=bl)); save(st, led); return
    acct = B.verify(); budget = min(BUDGET, float(acct.get('buying_power', 0)) * 0.95)
    sel = selection(D, key, sec, today); slot = budget / SLOTS; held = {p['symbol'] for p in B.positions()}
    plan = []
    for x in sel['ranked']:
        if len(plan) >= SLOTS: break
        px = x['last_close']; q = math.floor(slot / (px * 1.03))           # 3% room for today's move
        if q < 1 or x['sym'] in held: continue
        plan.append(dict(sym=x['sym'], qty=q, est_price=px, t=x['t']))
    log('selection month-end', sel['month_end'], 'passed', sel['passed'], 'plan', [(p['sym'], p['qty']) for p in plan])
    if dry: print(json.dumps(dict(budget=budget, plan=plan), indent=1)); return
    wait_until(15, 44)
    if (now().hour, now().minute) >= (15, 50): fallback = True
    else: fallback = False
    sent = []
    for p in plan:
        ok, res, body = (False, {}, {}) if fallback else order(B, p['sym'], p['qty'], 'buy', 'cls')
        if ok: sent.append(dict(p, order_id=res.get('id'), tif='cls')); continue
        sent.append(dict(p, order_id=None, tif='cls', rejected=str(res)[:200]))
    if any(s['order_id'] is None for s in sent):
        wait_until(15, 57)
        for s in sent:
            if s['order_id'] is None and (now().hour, now().minute) < (15, 59):
                ok, res, body = order(B, s['sym'], s['qty'], 'buy', 'day')
                if ok: s.update(order_id=res.get('id'), tif='day (fallback)')
    st['buy_days'].append(today); st['events'].append(dict(t=today, kind='buy sent', n=len(sent)))
    wait_until(16, 5)
    for s in sent:
        if not s['order_id']: continue
        o = B._req('GET', f"/v2/orders/{s['order_id']}").json()
        q = float(o.get('filled_qty') or 0)
        if q > 0:
            pos = dict(sym=s['sym'], qty=int(q), entry_price=float(o['filled_avg_price']), entry_day=today, tif=s['tif'], t=s['t'])
            st['open'].append(pos); led.append(dict(pos))
    log('filled', len(st['open']))
    save(st, led)

def do_sell(B):
    st, led = load_state()
    for p in st['open']:
        if p.get('sell_order'): continue
        ok, res, body = order(B, p['sym'], p['qty'], 'sell', 'opg')
        p['sell_order'] = res.get('id') if ok else None; p['sell_tif'] = 'opg' if ok else f"rejected: {str(res)[:120]}"
    st['events'].append(dict(t=now().isoformat(timespec='minutes'), kind='opg sells sent', n=len(st['open'])))
    save(st, led)

def do_check(B):
    st, led = load_state(); still = []
    for p in st['open']:
        filled = None
        if p.get('sell_order'):
            o = B._req('GET', f"/v2/orders/{p['sell_order']}").json()
            if float(o.get('filled_qty') or 0) >= p['qty']: filled = float(o['filled_avg_price'])
        if filled is None:                                                 # not sold at the open: sell now (only our shares)
            ok, res, body = order(B, p['sym'], p['qty'], 'sell', 'day')
            if ok:
                time.sleep(5); o = B._req('GET', f"/v2/orders/{res['id']}").json()
                if float(o.get('filled_qty') or 0) >= p['qty']: filled = float(o['filled_avg_price'])
        if filled is None: still.append(p); continue
        for x in led:
            if x['sym'] == p['sym'] and x['entry_day'] == p['entry_day'] and not x.get('exit_price'):
                x.update(exit_price=filled, exit_day=now().date().isoformat(), how=p.get('sell_tif')); break
    st['open'] = still; st['events'].append(dict(t=now().isoformat(timespec='minutes'), kind='morning check', still_open=len(still)))
    save(st, led)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'dry'
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    B = PaperBroker(key, sec); B.verify()
    if mode in ('buy', 'dry'): do_buy(B, Data(key, sec), key, sec, dry=(mode == 'dry'))
    elif mode == 'sell': do_sell(B)
    elif mode == 'check': do_check(B)

if __name__ == '__main__':
    main()
