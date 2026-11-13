"""Vantex paper bot: noise-area momentum + 5-min opening range breakout, shares, Alpaca PAPER only."""
import os, sys, json, math, time, subprocess, requests, numpy as np, pandas as pd
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
DAILY_LOSS_LIMIT = 0.01   # stop trading for the day if the account is down 1% (about $1,000)
LIVE_DIR = '/tmp/vantex-live'
NTFY = os.environ.get('NTFY_TOPIC')
SCAN_EVERY = 300          # seconds between full-market scans
HIST_EVERY = 1800         # seconds between track-record refreshes
MAX_ORDER_DOLLARS = 12_000  # hard cap on any single new order (a normal sleeve is equity / 11, about $9,100)
MAX_ORDERS_PER_DAY = 40     # hard cap on new strategy orders per day (a normal day is under 20)
STALE_MINUTES = 10          # skip a signal if the latest price bar is older than this (halt or data outage)

# ---------- kill switch: control.json in the repo's main branch ----------
# "on"    = trade normally
# "pause" = no new positions; exits that reduce risk are still allowed; positions are kept
# "stop"  = no new orders and close every position now
_CTRL = {'t': 0, 'mode': 'on'}
def control():
    if time.time() - _CTRL['t'] < 60: return _CTRL['mode']
    tok, repo = os.environ.get('GH_TOKEN'), os.environ.get('GITHUB_REPOSITORY')
    mode = _CTRL['mode']
    try:
        if tok and repo:
            r = requests.get(f'https://api.github.com/repos/{repo}/contents/control.json?ref=main',
                             headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github.raw'}, timeout=15)
            if r.status_code == 200: mode = str(json.loads(r.text).get('trading', 'on')).strip().lower()
            elif r.status_code == 404: mode = 'on'
    except Exception as e:
        print('control check failed, keeping', mode, str(e)[:120], flush=True)   # network blip: keep the last known setting
    if mode not in ('on', 'pause', 'stop'): mode = 'pause'                      # a typo in control.json fails safe
    _CTRL.update(t=time.time(), mode=mode)
    return mode

def notify(title, msg, tags=''):
    """Push a phone alert through ntfy.sh. Never raises: alerts must not break trading."""
    if not NTFY: return
    try: requests.post(f'https://ntfy.sh/{NTFY}', data=msg.encode('utf-8'), headers={'Title': title, 'Tags': tags}, timeout=10)
    except Exception as e: print('notify failed', str(e)[:120], flush=True)

_ERR = {}
def log(**k):
    k['ts'] = datetime.now(ET).isoformat(timespec='seconds'); print(json.dumps(k), flush=True); remember(k)
    if k.get('event') == 'error':
        key = k.get('where', '?')
        if time.time() - _ERR.get(key, 0) > 1800:
            _ERR[key] = time.time(); notify('Vantex bot error', f"{key} {k.get('sym', '')}: {str(k.get('err', ''))[:160]}", 'warning')
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

def order(sym, qty, side, cid, price=None, reduce=False, exposure=None, **extra):
    """Every order passes these checks first. Orders that only shrink a position (reduce=True) skip the caps and pause."""
    mode = control()
    why = None
    if mode == 'stop' or (mode == 'pause' and not reduce): why = f'kill switch is {mode}'
    elif not reduce:
        size = exposure if exposure is not None else (qty * price if price else 0)   # the position this order leaves you with
        if size > MAX_ORDER_DOLLARS: why = f'position ${size:,.0f} would be over the ${MAX_ORDER_DOLLARS:,} cap'
        else:
            n = sum(1 for o in today_orders() if (o.get('client_order_id') or '').startswith(('NA-', 'ORB-')))
            if n >= MAX_ORDERS_PER_DAY: why = f'{n} orders today, at the {MAX_ORDERS_PER_DAY} daily cap'
    if why:
        log(event='order_blocked', sym=sym, side=side, qty=int(qty), why=why)
        return None
    body = dict(symbol=sym, qty=str(int(qty)), side=side, type='market', time_in_force='day', client_order_id=cid[:120], **extra)
    r = req('POST', f'{TRADE}/v2/orders', json=body)
    log(event='order', sym=sym, side=side, qty=int(qty), cid=cid, status=r.status_code, resp=(r.json().get('status') if r.ok else r.text[:200]))
    if not r.ok:
        notify(f'Vantex order rejected: {sym}', f'{side.upper()} {int(qty)} {sym} was rejected ({r.status_code}): {r.text[:160]}', 'warning')
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

_LV = {}
def levels(sym, now):
    hit = _LV.get(sym)
    if hit and hit[0] == now.date() and hit[3] is not None: return hit[1:]
    sig, pc, op = na_levels(sym, now); _LV[sym] = (now.date(), sig, pc, op)
    return sig, pc, op

def na_step(now, slot_k, orders, eq):
    for sym in NA_SYMS:
        try:
            sig, pc, op = levels(sym, now)
            live = session_minutes(bars(sym, now.replace(hour=9, minute=30, second=0, microsecond=0), now, 'iex'))
            if not len(live) or (now - live.index[-1]).total_seconds() > STALE_MINUTES * 60:
                log(event='stale_skip', sym=sym, slot=slot_k, last_bar=str(live.index[-1]) if len(live) else None); continue
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
            if delta: order(sym, abs(delta), 'buy' if delta > 0 else 'sell', f'NA-{sym}-{now:%Y%m%d}-{slot_k}-{int(time.time())}',
                            price=p, reduce=abs(cur + delta) < abs(cur), exposure=abs(cur + delta) * p)
        except Exception as e:
            log(event='error', where='na', sym=sym, err=str(e)[:300])

def orb_step(now, orders, eq):
    for sym in ORB_SYMS:
        try:
            if any((o.get('client_order_id') or '').startswith(f'ORB-{sym}-{now:%Y%m%d}') for o in orders): continue
            b = session_minutes(bars(sym, now.replace(hour=9, minute=30, second=0, microsecond=0), now, 'iex'))
            f5 = b[b.k < 5]
            if len(f5) < 3: log(event='orb_skip', sym=sym, why='not enough bars'); continue
            if (now - b.index[-1]).total_seconds() > STALE_MINUTES * 60: log(event='stale_skip', sym=sym, where='orb'); continue
            O, C, Hh, Ll = f5.o.iloc[0], f5.c.iloc[-1], f5.h.max(), f5.l.min()
            if C == O: log(event='orb_skip', sym=sym, why='doji'); continue
            d = 1 if C > O else -1; p = b.c.iloc[-1]
            stop = Ll if d == 1 else Hh; risk = abs(p - stop)
            if risk < 0.01 or (d == 1 and stop >= p) or (d == -1 and stop <= p): log(event='orb_skip', sym=sym, why='price past stop'); continue
            tgt = p + d * 10 * risk; qty = math.floor(eq / SLEEVES / p)
            log(event='orb_signal', sym=sym, dir=d, price=round(p, 2), stop=round(stop, 2), target=round(tgt, 2), qty=qty)
            order(sym, qty, 'buy' if d == 1 else 'sell', f'ORB-{sym}-{now:%Y%m%d}-{int(time.time())}', price=p,
                  order_class='bracket', take_profit=dict(limit_price=str(round(tgt, 2))), stop_loss=dict(stop_price=str(round(stop, 2))))
        except Exception as e:
            log(event='error', where='orb', sym=sym, err=str(e)[:300])

ALL_SYMS = list(dict.fromkeys(NA_SYMS + ORB_SYMS))
EVENTS = []
def remember(k):
    if k.get('event') in ('order', 'orb_signal', 'flatten', 'error', 'loss_limit', 'order_blocked', 'stale_skip', 'kill_switch') or (k.get('event') == 'na_check' and k.get('have') != k.get('want')):
        EVENTS.append(k); del EVENTS[:-60]

def snapshot(market_open=True):
    now = datetime.now(ET)
    acct = req('GET', f'{TRADE}/v2/account').json()
    pos = {p['symbol']: p for p in req('GET', f'{TRADE}/v2/positions').json()}
    orders = today_orders(); flat = []
    for o in orders: flat += [o] + (o.get('legs') or [])
    out = {}
    for sym in ALL_SYMS:
        try:
            b = session_minutes(bars(sym, now.replace(hour=9, minute=30, second=0, microsecond=0), now, 'iex'))
            if not len(b): continue
            price = float(b.c.iloc[-1]); tp = (b.h + b.l + b.c) / 3; vw = float((tp * b.v).sum() / max(b.v.sum(), 1))
            d = dict(price=round(price, 2), vwap=round(vw, 2), series=[[int(k), round(float(c), 2)] for k, c in zip(b.k, b.c)][-150:],
                     strategies=[x for x, L in (('NA', NA_SYMS), ('ORB', ORB_SYMS)) if sym in L])
            if sym in NA_SYMS:
                sig, pc, op = levels(sym, now); op = op or float(b.o.iloc[0]); m = min(int(b.k.iloc[-1]), 389)
                d.update(upper=round(max(op, pc) * (1 + sig[m]), 2), lower=round(min(op, pc) * (1 - sig[m]), 2),
                         na_pos=int(np.sign(sleeve_qty(orders, f'NA-{sym}-'))))
            ob = [o for o in orders if (o.get('client_order_id') or '').startswith(f'ORB-{sym}-')]
            if ob:
                o = ob[0]; legs = o.get('legs') or []
                stop = next((l.get('stop_price') for l in legs if l.get('stop_price')), None)
                tgt = next((l.get('limit_price') for l in legs if l.get('limit_price')), None)
                d['orb'] = dict(dir=1 if o['side'] == 'buy' else -1, stop=stop, target=tgt,
                                open=any(l['status'] not in ('filled', 'canceled', 'expired') for l in legs))
            cash = sum((1 if o['side'] == 'sell' else -1) * float(o.get('filled_qty') or 0) * float(o.get('filled_avg_price') or 0) for o in flat if o['symbol'] == sym)
            q = float(pos[sym]['qty']) if sym in pos else 0.0
            d.update(qty=q, pl_day=round(cash + q * price, 2), trades=sum(1 for o in flat if o['symbol'] == sym and float(o.get('filled_qty') or 0) > 0))
            out[sym] = d
        except Exception as e:
            out[sym] = dict(error=str(e)[:200])
    fills = sorted([dict(id=o['id'], sym=o['symbol'], side=o['side'], qty=float(o['filled_qty']), price=float(o.get('filled_avg_price') or 0), ts=o['filled_at'],
                         strat=('ORB' if (o.get('client_order_id') or '').startswith('ORB') else 'NA' if (o.get('client_order_id') or '').startswith('NA') else 'exit'))
                    for o in flat if o['symbol'] in ALL_SYMS and float(o.get('filled_qty') or 0) > 0 and o.get('filled_at')], key=lambda x: x['ts'])
    state = dict(updated=now.isoformat(timespec='seconds'), market_open=market_open, equity=float(acct['equity']), fills=fills[-80:],
                 day_pl=round(float(acct['equity']) - float(acct['last_equity']), 2), symbols=out, events=EVENTS[-40:],
                 control=control(), limits=dict(max_order=MAX_ORDER_DOLLARS, max_orders=MAX_ORDERS_PER_DAY, stale_min=STALE_MINUTES))
    alert_fills(fills, out)
    if not market_open:
        notify('Vantex day recap', f"Day P/L {state['day_pl']:+,.2f} · {len(fills)} fills · equity ${state['equity']:,.2f}", 'bar_chart')
    push_state(state)

_SEEN = None
def alert_fills(fills, syms):
    global _SEEN
    ids = {f['id'] for f in fills}
    if _SEEN is None: _SEEN = ids; return          # first snapshot of this run: don't re-alert earlier fills
    why = {'NA': 'noise-area', 'ORB': 'opening breakout', 'exit': 'exit'}
    for f in fills:
        if f['id'] in _SEEN: continue
        pl = (syms.get(f['sym']) or {}).get('pl_day')
        extra = f" · {f['sym']} day P/L {pl:+,.2f}" if isinstance(pl, (int, float)) else ''
        notify(f"Vantex {f['side'].upper()} {f['sym']}", f"{f['side'].upper()} {f['qty']:g} {f['sym']} @ {f['price']:.2f} ({why.get(f['strat'], f['strat'])}){extra}",
               'green_circle' if f['side'] == 'buy' else 'red_circle')
    _SEEN |= ids

def load_assets():
    """Every active, tradable US-listed stock (about 10,000), cached for the day, saved for the page's search box."""
    today = datetime.now(ET).date()
    if _ASSETS.get('day') == today and _ASSETS.get('list'): return _ASSETS['list']
    r = req('GET', f'{TRADE}/v2/assets', params=dict(status='active', asset_class='us_equity'))
    ok = ('NYSE', 'NASDAQ', 'ARCA', 'AMEX', 'BATS')
    lst = sorted((a['symbol'], (a.get('name') or '')[:48]) for a in r.json()
                 if a.get('tradable') and a.get('exchange') in ok and a['symbol'].isalpha())
    _ASSETS.update(day=today, list=lst)
    os.makedirs(LIVE_DIR, exist_ok=True)
    json.dump(dict(updated=datetime.now(ET).isoformat(timespec='seconds'), assets=[list(x) for x in lst]),
              open(f'{LIVE_DIR}/assets.json', 'w'), separators=(',', ':'))
    return lst
_ASSETS = {}

def market_scan():
    """Price, % change, volume and relative volume for every stock, from Alpaca snapshots (IEX feed)."""
    syms = [s for s, _ in load_assets()]
    rows = []
    for i in range(0, len(syms), 400):
        d = req('GET', f'{DATA}/v2/stocks/snapshots', params=dict(symbols=','.join(syms[i:i + 400]), feed='iex')).json() or {}
        if isinstance(d.get('snapshots'), dict): d = d['snapshots']
        for sym, sn in d.items():
            if not isinstance(sn, dict): continue
            db, pb = sn.get('dailyBar') or {}, sn.get('prevDailyBar') or {}
            px = (sn.get('latestTrade') or {}).get('p') or db.get('c'); pc = pb.get('c')
            if not px or not pc: continue
            v, pv = int(db.get('v') or 0), int(pb.get('v') or 0)
            rows.append([sym, round(px, 4 if px < 1 else 2), round((px / pc - 1) * 100, 2), v, round(v / pv, 2) if pv else None])
    os.makedirs(LIVE_DIR, exist_ok=True)
    json.dump(dict(updated=datetime.now(ET).isoformat(timespec='seconds'), feed='iex', rows=rows),
              open(f'{LIVE_DIR}/market.json', 'w'), separators=(',', ':'))
    return len(rows)

def track_record():
    """Daily equity and P/L for the paper account (last 3 months) for the page's equity curve."""
    d = req('GET', f'{TRADE}/v2/account/portfolio/history', params=dict(period='3M', timeframe='1D')).json()
    days = [[datetime.fromtimestamp(t, ET).strftime('%Y-%m-%d'), round(e, 2), round(p or 0, 2)]
            for t, e, p in zip(d.get('timestamp') or [], d.get('equity') or [], d.get('profit_loss') or []) if e]
    os.makedirs(LIVE_DIR, exist_ok=True)
    json.dump(dict(updated=datetime.now(ET).isoformat(timespec='seconds'), days=days),
              open(f'{LIVE_DIR}/history.json', 'w'), separators=(',', ':'))

def push_state(state):
    d = LIVE_DIR; os.makedirs(d, exist_ok=True)
    json.dump(state, open(f'{d}/state.json', 'w'), separators=(',', ':'))
    tok, repo = os.environ.get('GH_TOKEN'), os.environ.get('GITHUB_REPOSITORY')
    if not (tok and repo): return
    g = ['git', '-C', d, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    try:
        subprocess.run(['rm', '-rf', f'{d}/.git'], check=True)
        subprocess.run(['git', 'init', '-q', '-b', 'live', d], check=True)
        subprocess.run(g + ['add', '-A'], check=True)
        subprocess.run(g + ['commit', '-q', '-m', 'live state'], check=True)
        subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{repo}.git', 'live'], check=True, timeout=60, capture_output=True)
    except Exception as e:
        print('push failed', str(e)[:200], flush=True)

def flatten():
    """Cancel stock orders and close stock positions only; crypto positions keep running."""
    for o in req('GET', f'{TRADE}/v2/orders', params=dict(status='open', limit=500, nested='false')).json():
        if o.get('asset_class', 'us_equity') == 'us_equity': req('DELETE', f"{TRADE}/v2/orders/{o['id']}")
    time.sleep(2); codes = []
    for attempt in range(2):
        left = [p for p in req('GET', f'{TRADE}/v2/positions').json() if p.get('asset_class') == 'us_equity']
        if not left: break
        for p in left: codes.append(req('DELETE', f"{TRADE}/v2/positions/{p['symbol']}").status_code)
        time.sleep(3)
    log(event='flatten', status=codes)

def loop(max_minutes=None):
    done = set(); t0 = time.time(); last_snap = 0; last_scan = 0; last_hist = 0; last_mode = 'on'
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
        mode = control()
        if mode != last_mode:
            log(event='kill_switch', mode=mode)
            notify(f'Vantex trading {mode.upper()}', {'on': 'Trading is back on.', 'pause': 'No new positions. Exits that reduce risk still allowed.',
                                                      'stop': 'Stopping: no new orders, closing all stock positions.'}[mode], 'warning' if mode != 'on' else 'white_check_mark')
            last_mode = mode
        if mode == 'stop' and 'killed' not in done:
            flatten(); done.add('killed')
        if mode == 'on': done.discard('killed')
        a = req('GET', f'{TRADE}/v2/account').json(); eq = float(a['equity']); start_eq = float(a['last_equity'])
        if eq - start_eq <= -DAILY_LOSS_LIMIT * start_eq and 'limit' not in done:
            log(event='loss_limit', pl=round(eq - start_eq, 2)); notify('Vantex loss limit hit', f'Down {eq - start_eq:,.2f} today. Stocks closed, trading stopped until tomorrow.', 'warning'); flatten(); done.update({'limit', 'orb', 'flat'} | {f'na{k}' for k in range(30, 390, 30)})
        if 5 <= m < 15 and 'orb' not in done and mode == 'on':
            orb_step(now, today_orders(), eq); done.add('orb')
        for k in range(30, 390, 30):
            if k <= m < k + 10 and f'na{k}' not in done:
                na_step(now, k, today_orders(), eq); done.add(f'na{k}')
        if m >= 385 and 'flat' not in done:
            flatten(); done.add('flat'); time.sleep(20)
            try: track_record()
            except Exception as e: log(event='error', where='track_record', err=str(e)[:300])
            try: snapshot(market_open=False)
            except Exception as e: log(event='error', where='snapshot', err=str(e)[:300])
            return
        if time.time() - last_scan > SCAN_EVERY:
            try: log(event='market_scan', stocks=market_scan())
            except Exception as e: log(event='error', where='market_scan', err=str(e)[:300])
            last_scan = time.time()
        if time.time() - last_hist > HIST_EVERY:
            try: track_record()
            except Exception as e: log(event='error', where='track_record', err=str(e)[:300])
            last_hist = time.time()
        if time.time() - last_snap > 55:
            try: snapshot()
            except Exception as e: log(event='error', where='snapshot', err=str(e)[:300])
            last_snap = time.time()
        time.sleep(10)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'snapshot': snapshot(); sys.exit()
    loop(float(sys.argv[2]) if len(sys.argv) > 2 else None)
