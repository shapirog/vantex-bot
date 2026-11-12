"""Vantex crypto paper bot: BTC and ETH trend-following on 15-minute bars, 24/7, Alpaca PAPER only, long-only.

Rule: hold a coin while its 20-bar EMA is above its 50-bar EMA and price is above the 20-bar EMA.
Exit when the 20-bar EMA drops below the 50-bar EMA or price falls below the 50-bar EMA.
Each coin trades a fixed dollar sleeve (CRYPTO_SLEEVE, default $2,000).
"""
import os, sys, json, time, subprocess, requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
KEY, SECRET = os.environ.get('APCA_API_KEY_ID') or '', os.environ.get('APCA_API_SECRET_KEY') or ''
if not KEY.startswith('PK'): sys.exit('Refusing to run: APCA_API_KEY_ID must be a PAPER key (starts with PK).')
H = {'APCA-API-KEY-ID': KEY, 'APCA-API-SECRET-KEY': SECRET}
TRADE = 'https://paper-api.alpaca.markets'
DATA = 'https://data.alpaca.markets'
COINS = {'BTC': 'BTC/USD', 'ETH': 'ETH/USD'}
SLEEVE = float(os.environ.get('CRYPTO_SLEEVE', '2000'))
STEP_EVERY = 300           # seconds between trading decisions
PUBLISH_EVERY = 60         # seconds between live updates for the city
LOG = os.environ.get('VANTEX_CRYPTO_LOG', 'logs/crypto_log.jsonl')
LIVE_DIR = '/tmp/vantex-crypto'
NTFY = os.environ.get('NTFY_TOPIC')
EVENTS = []

def log(**k):
    k['ts'] = datetime.now(ET).isoformat(timespec='seconds'); print(json.dumps(k), flush=True)
    if k.get('event') in ('order', 'exit', 'error') or (k.get('event') == 'crypto_check' and k.get('have') != k.get('want')):
        EVENTS.append(k); del EVENTS[:-40]
    os.makedirs(os.path.dirname(LOG) or '.', exist_ok=True)
    open(LOG, 'a').write(json.dumps(k) + '\n')

def notify(title, msg, tags=''):
    if not NTFY: return
    try: requests.post(f'https://ntfy.sh/{NTFY}', data=msg.encode('utf-8'), headers={'Title': title, 'Tags': tags}, timeout=10)
    except Exception as e: print('notify failed', str(e)[:120], flush=True)

def req(method, url, **kw):
    r = None
    for i in range(6):
        r = requests.request(method, url, headers=H, timeout=30, **kw)
        if r.status_code == 429 or r.status_code >= 500: time.sleep(2 + 2 * i); continue
        return r
    return r

def ema(vals, n):
    k = 2 / (n + 1); e = vals[0]; out = []
    for v in vals: e = v * k + e * (1 - k); out.append(e)
    return out

def bars(pair):
    start = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    d = req('GET', f'{DATA}/v1beta3/crypto/us/bars', params=dict(symbols=pair, timeframe='15Min', start=start, limit=1000)).json()
    return [(b['t'], float(b['c'])) for b in (d.get('bars') or {}).get(pair, [])]

def last_price(pair):
    d = req('GET', f'{DATA}/v1beta3/crypto/us/latest/trades', params=dict(symbols=pair)).json()
    t = (d.get('trades') or {}).get(pair) or {}
    return float(t['p']) if t.get('p') else None

def position(coin):
    r = req('GET', f'{TRADE}/v2/positions/{coin}USD')
    return r.json() if r.status_code == 200 else None

def signal(closes, price, have):
    """Returns (want, ema20, ema50). want: 1 = hold the coin, 0 = be out."""
    e20, e50 = ema(closes, 20)[-1], ema(closes, 50)[-1]
    if e20 > e50 and price > e20: want = 1
    elif e20 < e50 or price < e50: want = 0
    else: want = have
    return want, e20, e50

CACHE = {}
def step():
    for coin, pair in COINS.items():
        try:
            b = bars(pair)
            if len(b) < 60: log(event='crypto_skip', coin=coin, why='not enough bars'); continue
            p = last_price(pair) or b[-1][1]
            pos = position(coin); have = 1 if pos and float(pos.get('qty') or 0) > 0 else 0
            want, e20, e50 = signal([c for _, c in b], p, have)
            CACHE[coin] = dict(series=b[-96:], ema20=e20, ema50=e50)
            log(event='crypto_check', coin=coin, price=round(p, 2), ema20=round(e20, 2), ema50=round(e50, 2), have=have, want=want)
            if want and not have:
                r = req('POST', f'{TRADE}/v2/orders', json=dict(symbol=pair, notional=str(SLEEVE), side='buy', type='market', time_in_force='gtc',
                                                             client_order_id=f'CRY-{coin}-{int(time.time())}'))
                log(event='order', coin=coin, side='buy', notional=SLEEVE, status=r.status_code, resp=(r.json().get('status') if r.ok else r.text[:200]))
            elif have and not want:
                r = req('DELETE', f'{TRADE}/v2/positions/{coin}USD')
                log(event='exit', coin=coin, status=r.status_code)
        except Exception as e:
            log(event='error', where='step', coin=coin, err=str(e)[:300])

_SEEN = None
def publish():
    global _SEEN
    acct = req('GET', f'{TRADE}/v2/account').json()
    after = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    orders = req('GET', f'{TRADE}/v2/orders', params=dict(status='all', after=after, limit=500, symbols=','.join(COINS.values()))).json()
    fills = sorted([dict(id=o['id'], coin=o['symbol'].split('/')[0], side=o['side'], qty=float(o['filled_qty']), price=float(o.get('filled_avg_price') or 0), ts=o['filled_at'])
                    for o in orders if float(o.get('filled_qty') or 0) > 0 and o.get('filled_at') and o['symbol'] in COINS.values()], key=lambda x: x['ts'])
    coins = {}
    for coin, pair in COINS.items():
        try:
            p = last_price(pair); pos = position(coin); c = CACHE.get(coin, {})
            coins[coin] = dict(pair=pair, price=round(p, 2) if p else None, ema20=round(c.get('ema20', 0), 2) or None, ema50=round(c.get('ema50', 0), 2) or None,
                               qty=float(pos['qty']) if pos else 0.0, value=round(float(pos['market_value']), 2) if pos else 0.0,
                               upl=round(float(pos['unrealized_pl']), 2) if pos else 0.0, avg=round(float(pos['avg_entry_price']), 2) if pos else None,
                               signal='LONG' if pos else 'FLAT', series=[[t, round(v, 2)] for t, v in c.get('series', [])], sleeve=SLEEVE)
        except Exception as e:
            coins[coin] = dict(pair=pair, error=str(e)[:200])
    ids = {f['id'] for f in fills}
    if _SEEN is None: _SEEN = ids
    else:
        for f in fills:
            if f['id'] not in _SEEN:
                notify(f"Vantex crypto {f['side'].upper()} {f['coin']}", f"{f['side'].upper()} {f['qty']:g} {f['coin']} @ ${f['price']:,.2f}",
                       'green_circle' if f['side'] == 'buy' else 'red_circle')
        _SEEN |= ids
    state = dict(updated=datetime.now(ET).isoformat(timespec='seconds'), equity=float(acct['equity']), coins=coins, fills=fills[-60:], events=EVENTS[-30:])
    push(state)

def push(state):
    d = LIVE_DIR; os.makedirs(d, exist_ok=True)
    json.dump(state, open(f'{d}/crypto.json', 'w'), separators=(',', ':'))
    tok, repo = os.environ.get('GH_TOKEN'), os.environ.get('GITHUB_REPOSITORY')
    if not (tok and repo): return
    g = ['git', '-C', d, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    try:
        subprocess.run(['rm', '-rf', f'{d}/.git'], check=True)
        subprocess.run(['git', 'init', '-q', '-b', 'live-crypto', d], check=True)
        subprocess.run(g + ['add', '-A'], check=True)
        subprocess.run(g + ['commit', '-q', '-m', 'crypto state'], check=True)
        subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{repo}.git', 'live-crypto'], check=True, timeout=60, capture_output=True)
    except Exception as e:
        print('push failed', str(e)[:200], flush=True)

def loop(max_minutes):
    t0 = time.time(); last_step = 0; last_pub = 0
    while time.time() - t0 < max_minutes * 60:
        if time.time() - last_step >= STEP_EVERY: step(); last_step = time.time()
        if time.time() - last_pub >= PUBLISH_EVERY:
            try: publish()
            except Exception as e: log(event='error', where='publish', err=str(e)[:300])
            last_pub = time.time()
        time.sleep(10)
    log(event='handoff', why='runtime limit')

if __name__ == '__main__':
    loop(float(sys.argv[1]) if len(sys.argv) > 1 else 55)
