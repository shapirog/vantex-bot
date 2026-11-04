"""Vantex paper bot: noise-area momentum + 5-min opening range breakout, shares, Alpaca PAPER only."""
import os, sys, json, math, time, requests, numpy as np, pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
ET = ZoneInfo('America/New_York')
E = {k: os.environ.get(k) for k in ('APCA_API_KEY_ID', 'APCA_API_SECRET_KEY')}
if not (E['APCA_API_KEY_ID'] or '').startswith('PK'): sys.exit('Refusing to run: APCA_API_KEY_ID must be a PAPER key (starts with PK).')
H = {'APCA-API-KEY-ID': E['APCA_API_KEY_ID'], 'APCA-API-SECRET-KEY': E['APCA_API_SECRET_KEY']}
TRADE = 'https://paper-api.alpaca.markets'
DATA = 'https://data.alpaca.markets'
NA_SYMS = ['QQQ', 'AAPL', 'NVDA', 'AMZN', 'GOOGL', 'TSLA']
ORB_SYMS = ['QQQ', 'MSFT', 'NVDA', 'AMZN', 'TSLA']
SLEEVES = len(NA_SYMS) + len(ORB_SYMS)
LOG = os.environ.get('VANTEX_LOG', 'logs/live_log.jsonl')

def log(**k):
    k['ts'] = datetime.now(ET).isoformat(timespec='seconds'); print(json.dumps(k), flush=True)
    os.makedirs(os.path.dirname(LOG) or '.', exist_ok=True)
    open(LOG, 'a').write(json.dumps(k) + '\n')

def req(method, url, **kw):
    for i in range(6):
        r = requests.request(method, url, headers=H, timeout=30, **kw)
        if r.status_code == 429 or r.status_code >= 500: time.sleep(2 + 2 * i); continue
        return r
    return r

def clock(): return req('GET', f'{TRADE}/v2/clock').json()
def equity(): return float(req('GET', f'{TRADE}/v2/account').json()['equity'])
def positions(): return {p['symbol']: float(p['qty']) for p in req('GET', f'{TRADE}/v2/positions').json()}

def bars(sym, start, end, feed):
    out, tok = [], None
    while True:
        p = dict(timeframe='1Min', start=start.isoformat(), end=end.isoformat(), limit=10000, feed=feed, adjustment='split')
        if tok: p['page_token'] = tok
        d = req('GET', f'{DATA}/v2/stocks/{sym}/bars', params=p).json()
        out += d.get('bars') or []; tok = d.get('next_page_token')
        if not tok: break
    df = pd.DataFrame(out, columns=['t', 'o', 'h', 'l', 'c', 'v', 'n', 'vw'])
    if len(df): df['t'] = pd.to_datetime(df.t).dt.tz_convert(ET); df = df.set_index('t')
    return df

def today_orders():
    start = datetime.now(ET).replace(hour=4, minute=0, second=0, microsecond=0)
    return req('GET', f'{TRADE}/v2/orders', params=dict(status='all', after=start.isoformat(), limit=500, nested='true')).json()

def sleeve_qty(orders, prefix):
    q = 0.0
    for o in orders:
        if (o.get('client_order_id') or '').startswith(prefix):
            q += float(o.get('filled_qty') or 0) * (1 if o['side'] == 'buy' else -1)
    return q

def order(sym, qty, side, cid, **extra):
    body = dict(symbol=sym, qty=str(int(qty)), side=side, type='market', time_in_force='day', client_order_id=cid[:120], **extra)
    r = req('POST', f'{TRADE}/v2/orders', json=body)
    log(event='order', sym=sym, side=side, qty=int(qty), cid=cid, status=r.status_code, resp=(r.json().get('status') if r.ok else r.text[:200]))
    return r

def session_minutes(df):
    df = df.between_time('09:30', '15:59')
    return df.assign(k=(df.index.hour * 60 + df.index.minute - 570))

def na_levels(sym, now):
    hist = session_minutes(bars(sym, now - timedelta(days=30), now - timedelta(minutes=16), 'sip'))
    days = sorted(set(hist.index.date)); today = now.date()
    past = [d for d in days if d < today]
    full = [d for d in past if (hist.index.date == d).sum() >= 380][-14:]
    moves = []
    for d in full:
        g = hist[hist.index.date == d]; c = g.set_index('k').c.reindex(range(390)).ffill().bfill()
        moves.append(np.abs(c.values / g.o.iloc[0] - 1))
    sig = np.mean(moves, axis=0)
    prev_close = hist[hist.index.date == past[-1]].c.iloc[-1]
    tdy = hist[hist.index.date == today]
    return sig, prev_close, (tdy.o.iloc[0] if len(tdy) else None)

def na_step(now, slot_k, orders, eq):
    for sym in NA_SYMS:
        try:
            sig, pc, op = na_levels(sym, now)
            live = session_minutes(bars(sym, now.replace(hour=9, minute=30, second=0, microsecond=0), now, 'iex'))
            if op is None: op = live.o.iloc[0]
            live = live[live.k < slot_k]; p = live.c.iloc[-1]
            tp = (live.h + live.l + live.c) / 3; vw = (tp * live.v).sum() / max(live.v.sum(), 1)
            s = sig[slot_k - 1]; ub = max(op, pc) * (1 + s); lb = min(op, pc) * (1 - s)
            cur = sleeve_qty(orders, f'NA-{sym}-'); d = int(np.sign(cur)); want = d
            if d == 0: want = 1 if p > ub else (-1 if p < lb else 0)
            elif d == 1: want = -1 if p < lb else (0 if p < max(ub, vw) else 1)
            else: want = 1 if p > ub else (0 if p > min(lb, vw) else -1)
            log(event='na_check', sym=sym, slot=slot_k, price=round(p, 2), upper=round(ub, 2), lower=round(lb, 2), vwap=round(vw, 2), have=d, want=want)
            if want == d: continue
            delta = want * math.floor(eq / SLEEVES / p) - cur
            if delta: order(sym, abs(delta), 'buy' if delta > 0 else 'sell', f'NA-{sym}-{now:%Y%m%d}-{slot_k}-{int(time.time())}')
        except Exception as e:
            log(event='error', where='na', sym=sym, err=str(e)[:300])

def orb_step(now, orders, eq):
    for sym in ORB_SYMS:
        try:
            if any((o.get('client_order_id') or '').startswith(f'ORB-{sym}-{now:%Y%m%d}') for o in orders): continue
            b = session_minutes(bars(sym, now.replace(hour=9, minute=30, second=0, microsecond=0), now, 'iex'))
            f5 = b[b.k < 5]
            if len(f5) < 3: log(event='orb_skip', sym=sym, why='not enough bars'); continue
            O, C, Hh, Ll = f5.o.iloc[0], f5.c.iloc[-1], f5.h.max(), f5.l.min()
            if C == O: log(event='orb_skip', sym=sym, why='doji'); continue
            d = 1 if C > O else -1; p = b.c.iloc[-1]
            stop = Ll if d == 1 else Hh; risk = abs(p - stop)
            if risk < 0.01 or (d == 1 and stop >= p) or (d == -1 and stop <= p): log(event='orb_skip', sym=sym, why='price past stop'); continue
            tgt = p + d * 10 * risk; qty = math.floor(eq / SLEEVES / p)
            log(event='orb_signal', sym=sym, dir=d, price=round(p, 2), stop=round(stop, 2), target=round(tgt, 2), qty=qty)
            order(sym, qty, 'buy' if d == 1 else 'sell', f'ORB-{sym}-{now:%Y%m%d}-{int(time.time())}',
                  order_class='bracket', take_profit=dict(limit_price=str(round(tgt, 2))), stop_loss=dict(stop_price=str(round(stop, 2))))
        except Exception as e:
            log(event='error', where='orb', sym=sym, err=str(e)[:300])

def flatten():
    r = req('DELETE', f'{TRADE}/v2/positions', params=dict(cancel_orders='true'))
    log(event='flatten', status=r.status_code)

def loop(max_minutes=None):
    done = set(); t0 = time.time()
    while True:
        if max_minutes and time.time() - t0 > max_minutes * 60:
            log(event='handoff', why='runtime limit'); sys.exit(3)
        c = clock()
        if not c['is_open']:
            nxt = datetime.fromisoformat(c['next_open'])
            wait = (nxt - datetime.now(nxt.tzinfo)).total_seconds()
            if 'flat' in done or wait > 100 * 60:
                log(event='market_closed', next_open=c['next_open']); return
            time.sleep(min(max(wait, 5), 300)); continue
        now = datetime.now(ET); m = now.hour * 60 + now.minute - 570
        eq = equity()
        if 5 <= m < 15 and 'orb' not in done:
            orb_step(now, today_orders(), eq); done.add('orb')
        for k in range(30, 390, 30):
            if k <= m < k + 10 and f'na{k}' not in done:
                na_step(now, k, today_orders(), eq); done.add(f'na{k}')
        if m >= 385 and 'flat' not in done:
            flatten(); done.add('flat'); return
        time.sleep(20)

if __name__ == '__main__':
    loop(float(sys.argv[2]) if len(sys.argv) > 2 else None)
