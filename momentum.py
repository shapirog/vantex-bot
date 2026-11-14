"""Vantex momentum bot: trades the scanner's movers in both directions. Alpaca PAPER only.

  UP:   a Radar pick with real good news breaks ABOVE its opening range  -> buy
  DOWN: a falling stock with bad news / heavy selling breaks BELOW it      -> short (easy-to-borrow only)

Anti-trap rules (so a fake move doesn't trick it):
  - no entries before 9:45 (the opening range must form first) or after 2:30 PM
  - the break must HOLD for 3 straight one-minute closes beyond the level
  - the breakout minute must trade at least 2x the day's average minute volume
  - buys only above VWAP, shorts only below it
  - no chasing: skip if already 6%+ past the level, or up 40%+ / down 50%+ on the day
  - prices must be fresh (last trade under 3 minutes old)
  - failed break: if price falls back inside the opening range within 15 minutes, exit at once

Risk: about 20% of equity per trade ($500 on $2,500), at most 2 open, 4 entries a day, one per stock per day.
Every position gets a stop at the broker the moment it fills (-8% for buys, +8% for shorts).
At +20% in its favour, half is taken off and the rest rides a 10% trailing stop. Everything is closed by 3:50 PM.
"""
import os, sys, json, math, time, subprocess, requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
KEY, SECRET = os.environ.get('APCA_API_KEY_ID') or '', os.environ.get('APCA_API_SECRET_KEY') or ''
if not KEY.startswith('PK'): sys.exit('Refusing to run: APCA_API_KEY_ID must be a PAPER key (starts with PK).')
H = {'APCA-API-KEY-ID': KEY, 'APCA-API-SECRET-KEY': SECRET}
TRADE, DATA = 'https://paper-api.alpaca.markets', 'https://data.alpaca.markets'
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
NTFY = os.environ.get('NTFY_TOPIC')
LOG = os.environ.get('VANTEX_MOM_LOG', 'logs/momentum_log.jsonl')
LIVE_DIR = '/tmp/vantex-mom'
BOT_SYMS = {'QQQ', 'AAPL', 'NVDA', 'AMZN', 'GOOGL', 'TSLA', 'MSFT'}   # the main bot's stocks: never touched here

SIZE_PCT = 0.20          # of equity per trade
MAX_OPEN, MAX_ENTRIES = 2, 4
OR_MIN = 15              # opening range = first 15 minutes
ENTRY_FROM, ENTRY_TO, FLAT_AT = 9 * 60 + 45, 14 * 60 + 30, 15 * 60 + 50
HOLD_BARS, VOL_MULT = 3, 2.0
MAX_PAST_LEVEL = 0.06
MAX_DAY_UP, MAX_DAY_DOWN = 40, -50
STOP_PCT, PARTIAL_PCT, TRAIL_PCT = 0.08, 0.20, 10.0
FAIL_WINDOW = 15 * 60    # seconds after entry in which a failed break exits
STALE_SEC = 180

EVENTS = []
def log(**k):
    k['ts'] = datetime.now(ET).isoformat(timespec='seconds'); print(json.dumps(k), flush=True)
    if k.get('event') not in ('mom_scan',): EVENTS.append(k); del EVENTS[:-60]
    os.makedirs(os.path.dirname(LOG) or '.', exist_ok=True)
    open(LOG, 'a').write(json.dumps(k) + '\n')

def notify(title, msg, tags=''):
    if not NTFY: return
    try: requests.post(f'https://ntfy.sh/{NTFY}', data=msg.encode('utf-8'), headers={'Title': title, 'Tags': tags}, timeout=10)
    except Exception as e: print('notify failed', str(e)[:120], flush=True)

def req(method, url, **kw):
    r = None
    for i in range(5):
        r = requests.request(method, url, headers=H, timeout=30, **kw)
        if r.status_code == 429 or r.status_code >= 500: time.sleep(2 + 2 * i); continue
        return r
    return r

_CTRL = {'t': 0, 'mode': 'on'}
def control():
    """Same kill switch as the other bots (control.json in the repo)."""
    if time.time() - _CTRL['t'] < 60: return _CTRL['mode']
    tok = os.environ.get('GH_TOKEN'); mode = _CTRL['mode']
    try:
        if tok:
            r = requests.get(f'https://api.github.com/repos/{REPO}/contents/control.json?ref=main',
                             headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github.raw'}, timeout=15)
            if r.status_code == 200: mode = str(json.loads(r.text).get('trading', 'on')).strip().lower()
            elif r.status_code == 404: mode = 'on'
    except Exception as e: print('control check failed', str(e)[:120], flush=True)
    if mode not in ('on', 'pause', 'stop'): mode = 'pause'
    _CTRL.update(t=time.time(), mode=mode); return mode

def raw(path):
    try:
        r = requests.get(f'https://raw.githubusercontent.com/{REPO}/{path}?t={int(time.time())}', timeout=20)
        return r.json() if r.ok else None
    except Exception: return None

# ---------------- market data ----------------
def minute_bars(sym, now):
    start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    r = req('GET', f'{DATA}/v2/stocks/{sym}/bars', params=dict(timeframe='1Min', start=start.isoformat(), end=now.isoformat(), limit=1000, feed='iex'))
    B = (r.json().get('bars') or []) if r.ok else []
    return [dict(t=datetime.fromisoformat(b['t'].replace('Z', '+00:00')).astimezone(ET), o=b['o'], h=b['h'], l=b['l'], c=b['c'], v=b['v']) for b in B]

def last_trade(sym):
    r = req('GET', f'{DATA}/v2/stocks/{sym}/trades/latest', params=dict(feed='iex'))
    t = (r.json().get('trade') or {}) if r.ok else {}
    if not t.get('p'): return None, None
    return float(t['p']), datetime.fromisoformat(t['t'].replace('Z', '+00:00').split('.')[0] + '+00:00')

def setup(sym, d, bars, now):
    """Checks one candidate. Returns (ok, details). d = +1 long, -1 short."""
    orb = [b for b in bars if b['t'] < now.replace(hour=9, minute=30 + OR_MIN, second=0, microsecond=0)]
    after = [b for b in bars if b not in orb]
    if len(orb) < OR_MIN - 3 or len(after) < HOLD_BARS: return False, 'not enough bars'
    hi, lo = max(b['h'] for b in orb), min(b['l'] for b in orb)
    pv = sum((b['h'] + b['l'] + b['c']) / 3 * b['v'] for b in bars); vv = sum(b['v'] for b in bars)
    vwap = pv / vv if vv else None
    last = after[-HOLD_BARS:]
    level = hi if d == 1 else lo
    held = all((b['c'] > level) if d == 1 else (b['c'] < level) for b in last)
    if not held: return False, f'break not held {HOLD_BARS} minutes'
    avg_v = vv / len(bars)
    i0 = next((i for i, b in enumerate(after) if (b['c'] > level if d == 1 else b['c'] < level)), None)
    if i0 is None or max(b['v'] for b in after[i0:]) < VOL_MULT * avg_v: return False, 'breakout volume too light'   # real buyers/sellers showed up
    p = last[-1]['c']
    if vwap and ((d == 1 and p < vwap) or (d == -1 and p > vwap)): return False, 'wrong side of VWAP'
    if abs(p / level - 1) > MAX_PAST_LEVEL: return False, 'already too far past the level (chasing)'
    return True, dict(level=round(level, 4), hi=round(hi, 4), lo=round(lo, 4), vwap=round(vwap, 4) if vwap else None, price=p)

# ---------------- orders ----------------
def place(body):
    r = req('POST', f'{TRADE}/v2/orders', json=body)
    if not r.ok:
        log(event='mom_reject', sym=body['symbol'], body=body, err=r.text[:200])
        notify(f"Vantex momentum order rejected: {body['symbol']}", r.text[:160], 'warning')
        return None
    return r.json()

def wait_fill(oid, secs=20):
    for _ in range(secs):
        o = req('GET', f'{TRADE}/v2/orders/{oid}').json()
        if o.get('status') == 'filled': return o
        if o.get('status') in ('canceled', 'rejected', 'expired'): return None
        time.sleep(1)
    req('DELETE', f'{TRADE}/v2/orders/{oid}'); return None

def cancel_mine(sym=None):
    for o in req('GET', f'{TRADE}/v2/orders', params=dict(status='open', limit=500)).json():
        if (o.get('client_order_id') or '').startswith('MOM-') and (sym is None or o['symbol'] == sym):
            req('DELETE', f"{TRADE}/v2/orders/{o['id']}")

def close_position(sym, why):
    cancel_mine(sym); time.sleep(1)
    pos = req('GET', f'{TRADE}/v2/positions/{sym}')
    if pos.status_code != 200: return
    q = float(pos.json()['qty']); side = 'sell' if q > 0 else 'buy'
    place(dict(symbol=sym, qty=str(int(abs(q))), side=side, type='market', time_in_force='day', client_order_id=f'MOM-{sym}-x-{int(time.time())}'))
    log(event='mom_exit', sym=sym, why=why)

# ---------------- state across runs ----------------
STATE = {'date': None, 'trades': {}}     # sym -> dict(d, qty, entry, stop, level, lo, hi, t, half, trail)
def load_state():
    today = datetime.now(ET).date().isoformat()
    st = raw('live-mom/momentum.json') or {}
    if st.get('date') == today: STATE.update(date=today, trades=st.get('trades') or {})
    else: STATE.update(date=today, trades={})

def equity():
    a = req('GET', f'{TRADE}/v2/account').json(); return float(a['equity']), a

def candidates():
    rd = raw('live-scan/radar.json') or {}
    if rd.get('day') != datetime.now(ET).date().isoformat(): return [], []
    longs = [x for x in rd.get('stocks') or [] if 1 <= x['p'] <= 20 and x['stage'] in ('early', 'building') and x['sym'] not in BOT_SYMS
             and any(t.startswith('NEWS ') for t in x['tags']) and not any(t.startswith('RISK') for t in x['tags']) and x['chg'] < MAX_DAY_UP]
    shorts = [x for x in rd.get('fades') or [] if x['sym'] not in BOT_SYMS and x['chg'] > MAX_DAY_DOWN]
    return longs[:8], shorts[:6]

# ---------------- one pass ----------------
def manage(now):
    """Protect what is open: failed breaks, the +20% half, trailing stops, and anything closed by its stop."""
    open_pos = {p['symbol']: p for p in req('GET', f'{TRADE}/v2/positions').json() if p.get('asset_class') == 'us_equity'}
    for sym, T in list(STATE['trades'].items()):
        if T.get('closed'): continue
        if sym not in open_pos:                                   # the broker stop / trailing stop closed it
            T['closed'] = now.isoformat(timespec='seconds'); log(event='mom_closed', sym=sym, why='stop or trailing stop filled'); continue
        q = abs(float(open_pos[sym]['qty'])); p = float(open_pos[sym]['current_price']); d = T['d']
        gain = (p / T['entry'] - 1) * d
        age = (now - datetime.fromisoformat(T['t'])).total_seconds()
        back_inside = (p < T['level']) if d == 1 else (p > T['level'])
        if not T.get('half') and age < FAIL_WINDOW and back_inside and gain < 0:
            close_position(sym, f"failed break: back inside the opening range at {p}"); T['closed'] = now.isoformat(timespec='seconds')
            notify(f'Vantex momentum: {sym} failed break', f'Back inside the range at ${p}. Out at once.', 'warning'); continue
        if not T.get('half') and gain >= PARTIAL_PCT and q >= 2:
            cancel_mine(sym); time.sleep(1)
            half = int(q // 2); side = 'sell' if d == 1 else 'buy'
            place(dict(symbol=sym, qty=str(half), side=side, type='market', time_in_force='day', client_order_id=f'MOM-{sym}-h-{int(time.time())}'))
            time.sleep(2)
            place(dict(symbol=sym, qty=str(int(q - half)), side=side, type='trailing_stop', trail_percent=str(TRAIL_PCT), time_in_force='day',
                       client_order_id=f'MOM-{sym}-t-{int(time.time())}'))
            T.update(half=True, trail=True); log(event='mom_partial', sym=sym, price=p, gain_pct=round(gain * 100, 1))
            notify(f'Vantex momentum: {sym} +{gain * 100:.0f}%', f'Took half at ${p}. The rest rides a {TRAIL_PCT:.0f}% trailing stop.', 'moneybag')

def hunt(now, eq):
    if control() != 'on': return
    m = now.hour * 60 + now.minute
    if not (ENTRY_FROM <= m <= ENTRY_TO): return
    live = [s for s, T in STATE['trades'].items() if not T.get('closed')]
    if len(live) >= MAX_OPEN or len(STATE['trades']) >= MAX_ENTRIES: return
    longs, shorts = candidates()
    for d, L in ((1, longs), (-1, shorts)):
        for x in L:
            sym = x['sym']
            if sym in STATE['trades']: continue                     # one try per stock per day
            px, pt = last_trade(sym)
            if px is None or (datetime.now(timezone.utc) - pt).total_seconds() > STALE_SEC: continue
            ok, info = setup(sym, d, minute_bars(sym, now), now)
            log(event='mom_scan', sym=sym, dir=d, ok=ok, info=info if not ok else 'setup confirmed')
            if not ok: continue
            qty = int(eq * SIZE_PCT // px)
            if qty < 1: continue
            o = place(dict(symbol=sym, qty=str(qty), side='buy' if d == 1 else 'sell', type='market', time_in_force='day', client_order_id=f'MOM-{sym}-e-{int(time.time())}'))
            f = wait_fill(o['id']) if o else None
            if not f: log(event='mom_skip', sym=sym, why='entry did not fill'); continue
            fill = float(f['filled_avg_price']); fq = int(float(f['filled_qty']))
            stop = round(fill * (1 - STOP_PCT * d), 2)
            place(dict(symbol=sym, qty=str(fq), side='sell' if d == 1 else 'buy', type='stop', stop_price=str(stop), time_in_force='day',
                       client_order_id=f'MOM-{sym}-s-{int(time.time())}'))
            STATE['trades'][sym] = dict(d=d, qty=fq, entry=fill, stop=stop, level=info['level'], lo=info['lo'], hi=info['hi'], t=now.isoformat(timespec='seconds'),
                                        why=('; '.join(x.get('tags', [])[:3]) + (' · ' + x['news'][0]['h'][:120] if x.get('news') else '')))
            log(event='mom_entry', sym=sym, dir=d, qty=fq, price=fill, stop=stop, level=info['level'], vwap=info['vwap'])
            notify(f"Vantex momentum {'BUY' if d == 1 else 'SHORT'} {sym}",
                   f"{fq} @ ${fill} · broke {'above' if d == 1 else 'below'} {info['level']} and held · stop ${stop}", 'green_circle' if d == 1 else 'red_circle')
            live.append(sym)
            if len(live) >= MAX_OPEN or len(STATE['trades']) >= MAX_ENTRIES: return

def publish(eq):
    longs, shorts = candidates()
    st = dict(updated=datetime.now(ET).isoformat(timespec='seconds'), date=STATE['date'], equity=eq, trades=STATE['trades'],
              watch_long=[dict(sym=x['sym'], p=x['p'], chg=x['chg'], tags=x['tags'][:3]) for x in longs],
              watch_short=[dict(sym=x['sym'], p=x['p'], chg=x['chg'], tags=x['tags'][:3]) for x in shorts],
              events=EVENTS[-40:], rules=dict(size_pct=SIZE_PCT, max_open=MAX_OPEN, max_entries=MAX_ENTRIES, stop_pct=STOP_PCT, partial_pct=PARTIAL_PCT, trail_pct=TRAIL_PCT))
    os.makedirs(LIVE_DIR, exist_ok=True); json.dump(st, open(f'{LIVE_DIR}/momentum.json', 'w'), separators=(',', ':'))
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', LIVE_DIR, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    try:
        subprocess.run(['rm', '-rf', f'{LIVE_DIR}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', 'live-mom', LIVE_DIR], check=True)
        subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', 'momentum'], check=True)
        subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{REPO}.git', 'live-mom'], check=True, timeout=60, capture_output=True)
    except Exception as e: print('push failed', str(e)[:200], flush=True)

def loop(max_minutes):
    t0 = time.time(); load_state(); last_pub = 0; eq = 0.0
    while True:
        if time.time() - t0 > max_minutes * 60: log(event='handoff', why='runtime limit'); publish(equity()[0]); sys.exit(3)
        c = req('GET', f'{TRADE}/v2/clock').json()
        if not c.get('is_open'):
            nxt = datetime.fromisoformat(c['next_open']); wait = (nxt - datetime.now(nxt.tzinfo)).total_seconds()
            if wait > 100 * 60: log(event='market_closed'); return
            time.sleep(min(max(wait, 5), 300)); continue
        now = datetime.now(ET); m = now.hour * 60 + now.minute
        try:
            eq, _ = equity()
            if control() == 'stop' or m >= FLAT_AT:
                for sym, T in STATE['trades'].items():
                    if not T.get('closed'): close_position(sym, 'end of day' if m >= FLAT_AT else 'kill switch stop'); T['closed'] = now.isoformat(timespec='seconds')
                if m >= FLAT_AT: publish(eq); return
            else:
                manage(now); hunt(now, eq)
        except Exception as e:
            log(event='error', where='momentum', err=str(e)[:300])
        if time.time() - last_pub > 60:
            try: publish(eq)
            except Exception as e: log(event='error', where='publish', err=str(e)[:200])
            last_pub = time.time()
        time.sleep(20)

if __name__ == '__main__':
    loop(float(sys.argv[1]) if len(sys.argv) > 1 else 330)
