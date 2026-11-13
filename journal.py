"""Vantex trade journal + scorecard. Read-only: places no trades.

Every fill from the Alpaca PAPER account is matched with the bot decision that caused it
(from logs/*.jsonl and the bots' live files), then scored per bot:
  NA      noise-area intraday strategy (stocks)
  ORB     opening-range breakout (stocks)
  CRYPTO  BTC / ETH trend bot
Publishes journal.json to the 'live-journal' branch for the Vantex City page.
"""
import os, sys, json, re, time, math, subprocess, requests
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
KEY, SECRET = os.environ.get('APCA_API_KEY_ID') or '', os.environ.get('APCA_API_SECRET_KEY') or ''
if not KEY.startswith('PK'): sys.exit('Refusing to run: APCA_API_KEY_ID must be a PAPER key (starts with PK).')
H = {'APCA-API-KEY-ID': KEY, 'APCA-API-SECRET-KEY': SECRET}
TRADE, DATA = 'https://paper-api.alpaca.markets', 'https://data.alpaca.markets'
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
OUT = os.environ.get('VANTEX_JOURNAL_DIR', '/tmp/vantex-journal')
LOGS = [os.environ.get('VANTEX_LOG', 'logs/live_log.jsonl'), os.environ.get('VANTEX_CRYPTO_LOG', 'logs/crypto_log.jsonl')]
START = os.environ.get('VANTEX_JOURNAL_START', '2026-11-01')   # first day of the paper record
NAMES = {'NA': 'Noise-area stocks', 'ORB': 'Opening breakout', 'CRYPTO': 'Crypto trend'}

# Estimated real-money costs (paper fills are free). Stocks: SEC fee on sells + FINRA TAF per share sold.
# Crypto: Alpaca's taker fee for small accounts, both sides.
SEC_FEE = 27.80 / 1_000_000
TAF_PER_SHARE, TAF_MAX = 0.000166, 8.30
CRYPTO_FEE = 0.0025

# Readiness gate: every line must pass before real money is even considered.
GATE_DAYS = 20
SLOTS = 12             # noise-area checks per day: every 30 minutes from 10:00 AM to 3:30 PM
GATE_PF = 1.2
GATE_MAX_DD = 5.0      # % from peak
GATE_WORST_DAY = 1.0   # % of equity (the bot's own daily loss limit)
GATE_SLIP_BPS = 5.0    # average slippage per order, in hundredths of a percent

def req(method, url, **kw):
    r = None
    for i in range(6):
        r = requests.request(method, url, headers=H, timeout=30, **kw)
        if r.status_code == 429 or r.status_code >= 500: time.sleep(2 + 2 * i); continue
        return r
    return r

def ts(t):
    """ISO time (Alpaca nanoseconds or bot offsets) -> aware datetime."""
    if not t: return None
    if isinstance(t, datetime): return t
    return datetime.fromisoformat(re.sub(r'(\.\d{6})\d+', r'\1', str(t).replace('Z', '+00:00')))

def r2(x, n=2): return None if x is None else round(float(x), n)

# ---------------- inputs ----------------
def all_orders():
    """Every order since START, oldest first, with bracket legs kept under their parent."""
    out, seen, after = [], set(), f'{START}T00:00:00Z'
    for _ in range(40):
        r = req('GET', f'{TRADE}/v2/orders', params=dict(status='all', after=after, direction='asc', limit=500, nested='true'))
        if not r.ok: raise RuntimeError(f'orders {r.status_code}: {r.text[:160]}')
        batch = r.json() or []
        new = [o for o in batch if o['id'] not in seen]
        for o in new: seen.add(o['id']); out.append(o)
        if len(batch) < 500 or not new: break
        after = batch[-1]['submitted_at']
    return out

def strat_of(cid, sym):
    cid = cid or ''
    if cid.startswith('NA-'): return 'NA'
    if cid.startswith('ORB-'): return 'ORB'
    if cid.startswith('CRY-') or '/' in sym: return 'CRYPTO'
    return None

def fills_from(orders):
    F = []
    for o in orders:
        parent = strat_of(o.get('client_order_id'), o['symbol'])
        for x, leg in [(o, None)] + [(l, l.get('type')) for l in (o.get('legs') or [])]:
            q = float(x.get('filled_qty') or 0)
            if q <= 0 or not x.get('filled_at'): continue
            cr = '/' in x['symbol'] or (x.get('asset_class') or o.get('asset_class')) == 'crypto'
            sym = x['symbol'].replace('/', '')[:-3] if cr and x['symbol'].replace('/', '').endswith('USD') else x['symbol']
            F.append(dict(id=x['id'], cid=o.get('client_order_id') or '', sym=sym, side=x['side'], qty=q, price=float(x['filled_avg_price']),
                          t=ts(x['filled_at']), strat=parent or ('CRYPTO' if cr else None), leg=leg, type=x.get('type'), crypto=cr))
    return sorted(F, key=lambda f: f['t'])

def raw(path):
    try:
        r = requests.get(f'https://raw.githubusercontent.com/{REPO}/{path}?t={int(time.time())}', timeout=20)
        return r.json() if r.ok else None
    except Exception: return None

def events():
    """Decisions from the committed logs plus the newest ones the bots published live today."""
    E, keys = [], set()
    def add(e):
        k = (e.get('ts'), e.get('event'), e.get('sym') or e.get('coin'), e.get('slot'), e.get('cid'))
        if k in keys or not e.get('ts'): return
        keys.add(k); E.append(e)
    for p in LOGS:
        try:
            for line in open(p):
                line = line.strip()
                if line:
                    try: add(json.loads(line))
                    except Exception: pass
        except FileNotFoundError: pass
    for path in ('live/state.json', 'live-crypto/crypto.json'):
        d = raw(path) or {}
        for e in d.get('events') or []: add(e)
    for e in E: e['_t'] = ts(e['ts'])
    return sorted(E, key=lambda e: e['_t'])

def equity_history():
    r = req('GET', f'{TRADE}/v2/account/portfolio/history', params=dict(period='1A', timeframe='1D'))
    d = r.json() if r.ok else {}
    rows = [(datetime.fromtimestamp(t, ET).date(), e) for t, e in zip(d.get('timestamp') or [], d.get('equity') or []) if e]
    return [x for x in rows if str(x[0]) >= START]

def qqq_return(d0):
    for feed in ('sip', 'iex'):
        end = datetime.now(timezone.utc) - timedelta(minutes=16 if feed == 'sip' else 0)
        r = req('GET', f'{DATA}/v2/stocks/bars', params=dict(symbols='QQQ', timeframe='1Day', start=f'{d0}T00:00:00Z', end=end.isoformat(), feed=feed, adjustment='split'))
        if r.ok:
            b = (r.json().get('bars') or {}).get('QQQ') or []
            if len(b) >= 2: return round((b[-1]['c'] / b[0]['o'] - 1) * 100, 2)
    return None

def market_days(d0, d1):
    r = req('GET', f'{TRADE}/v2/calendar', params=dict(start=str(d0), end=str(d1)))
    return [date.fromisoformat(c['date']) for c in (r.json() if r.ok else [])]

# ---------------- matching decisions to fills ----------------
def context(E):
    """For each bot order, the decision just before it: what the bot saw and the price it expected."""
    na = {}; orb = {}; cry = {}
    for e in E:
        d = e['_t'].astimezone(ET).date()
        if e['event'] == 'na_check' and e.get('have') != e.get('want'): na[(e['sym'], d, e.get('slot'))] = e
        elif e['event'] == 'orb_signal': orb[(e['sym'], d)] = e
        elif e['event'] == 'crypto_check' and e.get('have') != e.get('want'): cry.setdefault(e['coin'], []).append(e)
    return na, orb, cry

def why_na(c):
    p, ub, lb, vw, h, w = c['price'], c['upper'], c['lower'], c['vwap'], c['have'], c['want']
    if w == 1: return f'Price {p} broke above the upper band {ub}' + (' (flip from short)' if h == -1 else '')
    if w == -1: return f'Price {p} broke below the lower band {lb}' + (' (flip from long)' if h == 1 else '')
    if h == 1: return f'Price {p} fell back under {max(ub, vw)} (band / VWAP): exit long'
    return f'Price {p} rose back over {min(lb, vw)} (band / VWAP): exit short'

def action(side, before, after):
    if abs(before) < 1e-9: return 'BUY' if side == 'buy' else 'SHORT'
    if abs(after) < 1e-9 or (after > 0) == (before > 0) and abs(after) < abs(before): return 'SELL' if before > 0 else 'COVER'
    if (after > 0) == (before > 0): return 'ADD'
    return 'FLIP LONG' if after > 0 else 'FLIP SHORT'

# ---------------- trades, P/L, costs ----------------
def cost_of(f):
    n = f['qty'] * f['price']
    if f['crypto']: return n * CRYPTO_FEE
    return (n * SEC_FEE + min(f['qty'] * TAF_PER_SHARE, TAF_MAX)) if f['side'] == 'sell' else 0.0

def build(F, E):
    na, orb, cry = context(E)
    pos = {}       # (strat, sym) -> open trade
    trades, rows = [], []
    for f in F:
        sg = 1 if f['side'] == 'buy' else -1
        # who owns this fill: its bot, or (for end-of-day / kill-switch closes) whichever bot holds the opposite side
        owners = [(f['strat'], f['qty'])] if f['strat'] else []
        if not owners:
            left = f['qty']
            for s in ('ORB', 'NA', 'CRYPTO'):
                p = pos.get((s, f['sym']))
                if p and p['q'] * sg < 0 and left > 1e-9:
                    take = min(left, abs(p['q'])); owners.append((s, take)); left -= take
            if left > 1e-9: owners.append(('OTHER', left))
        fee_rate = cost_of(f) / f['qty']
        for s, q in owners:
            key = (s, f['sym']); p = pos.get(key)
            before = p['q'] if p else 0.0
            qq = q * sg; realized = 0.0
            if p and p['q'] * qq < 0:                     # closing (part of) the position
                c = min(abs(qq), abs(p['q'])); d = 1 if p['q'] > 0 else -1
                realized = (f['price'] - p['avg']) * c * d
                p['pnl'] += realized; p['cost'] += fee_rate * c; p['q'] -= c * d; qq += c * d; p['exit_n'] += c * f['price']; p['exit_q'] += c
                if abs(p['q']) < 1e-9:
                    trades.append(dict(bot=s, sym=f['sym'], dir='Long' if p['dir'] > 0 else 'Short', qty=r2(p['mx'], 6), entry=r2(p['avg0']),
                                       exit=r2(p['exit_n'] / p['exit_q']), open=p['t0'].isoformat(), close=f['t'].isoformat(),
                                       pnl=r2(p['pnl']), net=r2(p['pnl'] - p['cost']), day=str(f['t'].astimezone(ET).date())))
                    pos.pop(key); p = None
            if abs(qq) > 1e-9:                            # opening or adding
                if not p:
                    p = pos[key] = dict(q=0.0, avg=0.0, avg0=0.0, n0=0.0, q0=0.0, dir=1 if qq > 0 else -1, mx=0.0, pnl=0.0, cost=0.0, t0=f['t'], exit_n=0.0, exit_q=0.0)
                p['avg'] = (p['avg'] * abs(p['q']) + f['price'] * abs(qq)) / (abs(p['q']) + abs(qq)); p['q'] += qq
                p['n0'] += abs(qq) * f['price']; p['q0'] += abs(qq); p['avg0'] = p['n0'] / p['q0']
                p['mx'] = max(p['mx'], abs(p['q'])); p['cost'] += fee_rate * abs(qq)
            after = pos[key]['q'] if key in pos else 0.0
            rows.append(journal_row(f, s, q, before, after, realized, na, orb, cry))
    return trades, rows, pos

def journal_row(f, s, q, before, after, realized, na, orb, cry):
    t = f['t'].astimezone(ET); d = t.date(); exp = None; why = ''
    act = action(f['side'], before, after)
    if s == 'OTHER': act, why = 'MANUAL', 'Fill not made by a Vantex bot'
    elif f['strat'] is None:      # a close the bot made without a strategy tag: end of day, kill switch or loss limit
        act = 'CLOSED'; why = 'End-of-day close (3:55 PM)' if t.hour * 60 + t.minute >= 950 else 'Closed by the bot (kill switch or loss limit)'
    elif s == 'NA':
        m = re.match(r'NA-[A-Z.]+-\d{8}-(\d+)-', f['cid'])
        c = na.get((f['sym'], d, int(m.group(1)))) if m else None
        if c: exp, why = c['price'], why_na(c)
        else: why = 'Noise-area signal (details appear after the bot\'s run is saved)'
    elif s == 'ORB':
        c = orb.get((f['sym'], d))
        if f['leg'] == 'limit': act, why = 'TARGET HIT', 'Take-profit order filled'
        elif f['leg'] == 'stop': act, why = 'STOP HIT', 'Stop-loss order filled'
        elif c:
            exp = c['price']; why = f"First 5 minutes closed {'up' if c['dir'] > 0 else 'down'}: stop {c['stop']}, target {c['target']}"
        else: why = 'Opening-range breakout'
    elif s == 'CRYPTO':
        prior = [e for e in cry.get(f['sym'], []) if e['_t'] <= f['t'] and (f['t'] - e['_t']).total_seconds() < 900]
        c = prior[-1] if prior else None
        if c:
            exp = c['price']
            why = (f"20-bar avg {c['ema20']} above 50-bar avg {c['ema50']}, price {c['price']} in the uptrend" if c['want'] == 1
                   else f"Trend ended: 20-bar avg {c['ema20']} vs 50-bar avg {c['ema50']}, price {c['price']}")
        else: why = 'Crypto trend signal'
    slip = None
    if exp and f['type'] == 'market':
        slip = round((f['price'] - exp) / exp * 1e4 * (1 if f['side'] == 'buy' else -1), 1)
    return dict(t=f['t'].isoformat(), bot=s, sym=f['sym'], act=act, side=f['side'], qty=r2(q, 6), fill=r2(f['price'], 4 if f['price'] < 1 else 2),
                exp=exp, slip=slip, pnl=r2(realized) if realized else None, why=why)

def blocked_rows(E, since):
    R = []
    for e in E:
        if e['_t'] < since or e['_t'].astimezone(ET).date().isoformat() < START: continue
        if e['event'] == 'order_blocked':
            R.append(dict(t=e['_t'].isoformat(), bot='CRYPTO' if e.get('coin') else 'STOCKS', sym=e.get('sym') or e.get('coin'), act='BLOCKED', why=e.get('why', '')))
        elif e['event'] == 'na_skip' or (e['event'] == 'orb_skip' and 'position size' in str(e.get('why', ''))):
            R.append(dict(t=e['_t'].isoformat(), bot='NA' if e['event'] == 'na_skip' else 'ORB', sym=e.get('sym'), act='SKIPPED', why=e.get('why', '')))
        elif e['event'] == 'stale_skip':
            R.append(dict(t=e['_t'].isoformat(), bot='ORB' if e.get('where') == 'orb' else 'NA', sym=e.get('sym'), act='SKIPPED', why='Price data was stale (over 10 min old)'))
        elif e['event'] == 'order' and str(e.get('status')) not in ('200', '201'):
            R.append(dict(t=e['_t'].isoformat(), bot='CRYPTO' if e.get('coin') else ('ORB' if str(e.get('cid', '')).startswith('ORB') else 'NA'),
                          sym=e.get('sym') or e.get('coin'), act='REJECTED', why=str(e.get('resp', ''))[:140]))
        elif e['event'] in ('loss_limit', 'kill_switch'):
            R.append(dict(t=e['_t'].isoformat(), bot='STOCKS', sym='', act='LOSS LIMIT' if e['event'] == 'loss_limit' else 'KILL SWITCH',
                          why=f"Day P/L {e.get('pl')}" if e['event'] == 'loss_limit' else f"Mode set to {e.get('mode')}"))
    return R

# ---------------- $2,500 real-money test ----------------
SMALL_START = float(os.environ.get('VANTEX_SMALL_START', '2500'))
SMALL_SLOTS = 4          # a $2,500 account can hold about 4 positions at once (about $625 each)
GOALS = (100_000, 200_000)

def small_account(trades):
    """Replays the bots' real trades (same signals, same fill prices) as if the account were $2,500 of real money.
    Rules a real small margin account lives by: at most SMALL_SLOTS positions at once, each sized to equity / SLOTS,
    fractional shares for longs and crypto, whole shares only for shorts (a short that can't afford 1 share is skipped),
    real-money fees on every trade. Profits compound: positions grow as the account grows."""
    ev = []
    for i, t in enumerate(trades):
        if t['bot'] == 'OTHER': continue
        ev.append((ts(t['open']), 1, i)); ev.append((ts(t['close']), 0, i))
    ev.sort(key=lambda e: (e[0], e[1]))                 # at the same moment, close before open
    eq = SMALL_START; held = {}; taken = skip_slot = skip_short = 0; curve = []; peak = eq; mdd = 0.0; wins = losses = 0; gw = gl = 0.0
    for t0, kind, i in ev:
        t = trades[i]
        if kind == 1:
            if len(held) >= SMALL_SLOTS: skip_slot += 1; continue
            alloc = eq / SMALL_SLOTS; px = t['entry']; crypto = t['bot'] == 'CRYPTO'
            if t['dir'] == 'Short':
                q = math.floor(alloc / px)
                if q < 1: skip_short += 1; continue
            else: q = round(alloc / px, 6)
            held[i] = q; taken += 1
        elif i in held:
            q = held.pop(i); d = 1 if t['dir'] == 'Long' else -1; crypto = t['bot'] == 'CRYPTO'
            pnl = (t['exit'] - t['entry']) * q * d
            sell_px = t['exit'] if d == 1 else t['entry']
            fee = (q * (t['entry'] + t['exit']) * CRYPTO_FEE) if crypto else (q * sell_px * SEC_FEE + min(q * TAF_PER_SHARE, TAF_MAX))
            pnl -= fee; eq += pnl
            if pnl > 0: wins += 1; gw += pnl
            else: losses += 1; gl -= pnl
            peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100)
            curve.append([int(t0.timestamp()), round(eq, 2)])
    out = dict(start=SMALL_START, equity=round(eq, 2), ret_pct=round((eq / SMALL_START - 1) * 100, 2), slots=SMALL_SLOTS,
               trades=wins + losses, skipped_full=skip_slot, skipped_short=skip_short, max_dd_pct=round(mdd, 2),
               win_rate=round(wins / (wins + losses) * 100, 1) if wins + losses else None,
               pf=round(gw / gl, 2) if gl > 0 else None, curve=curve[-400:])
    if curve:
        days = max(1.0, (curve[-1][0] - ts(START + 'T09:30:00-05:00').timestamp()) / 86400)
        out['days'] = round(days, 1)
        if eq > SMALL_START and days >= 5:
            monthly = (eq / SMALL_START) ** (30.4 / days) - 1
            out['monthly_pct'] = round(monthly * 100, 2)
            out['goal_months'] = {str(g): round(math.log(g / eq) / math.log(1 + monthly), 1) for g in GOALS}
    return out

# ---------------- scoring ----------------
def score(T, rows):
    if not T: return dict(trades=0)
    pn = [t['net'] for t in T]; wins = [x for x in pn if x > 0]; losses = [x for x in pn if x <= 0]
    streak = run = 0
    for x in pn:
        run = run + 1 if x <= 0 else 0; streak = max(streak, run)
    slips = [r['slip'] for r in rows if r.get('slip') is not None]
    gl = -sum(losses)
    return dict(trades=len(T), wins=len(wins), losses=len(losses), win_rate=round(len(wins) / len(T) * 100, 1),
                avg_win=r2(sum(wins) / len(wins)) if wins else 0, avg_loss=r2(sum(losses) / len(losses)) if losses else 0,
                pf=round(sum(wins) / gl, 2) if gl > 0 else None, gross=r2(sum(t['pnl'] for t in T)), net=r2(sum(pn)),
                costs=r2(sum(t['pnl'] for t in T) - sum(pn)), best=r2(max(pn)), worst=r2(min(pn)), losing_streak=streak,
                expectancy=r2(sum(pn) / len(T)), slip_bps=round(sum(slips) / len(slips), 1) if slips else None, slip_n=len(slips),
                days=len({t['day'] for t in T}))

def account_start():
    """The record starts on the day this paper account was opened (a new $2,500 account starts a fresh record)."""
    global START
    try:
        r = req('GET', f'{TRADE}/v2/account')
        made = (r.json() or {}).get('created_at') if r.ok else None
        if made:
            d = ts(made).astimezone(ET).date().isoformat()
            if d > START: START = d
    except Exception as e: print('account start check failed', str(e)[:120], flush=True)

def main():
    t0 = datetime.now(ET); os.makedirs(OUT, exist_ok=True)
    account_start()
    orders = all_orders(); F = fills_from(orders); E = events()
    trades, rows, open_pos = build(F, E)
    since = datetime.now(timezone.utc) - timedelta(days=21)
    journal = rows + blocked_rows(E, since)
    journal = sorted([r for r in journal if ts(r['t']) >= since], key=lambda r: r['t'], reverse=True)[:400]

    bots = {}
    for s in ('NA', 'ORB', 'CRYPTO'):
        bots[s] = dict(name=NAMES[s], **score([t for t in trades if t['bot'] == s], [r for r in rows if r['bot'] == s]))
    combined = score([t for t in trades if t['bot'] != 'OTHER'], [r for r in rows if r['bot'] != 'OTHER'])

    # account level
    eq = equity_history()
    acct = dict(days=len(eq))
    if eq:
        peak, mdd = eq[0][1], 0.0
        for _, e in eq: peak = max(peak, e); mdd = max(mdd, (peak - e) / peak * 100)
        daily = [(eq[i][0], eq[i][1] - eq[i - 1][1]) for i in range(1, len(eq))]
        worst = min(daily, key=lambda x: x[1]) if daily else (None, 0)
        acct.update(start=str(eq[0][0]), start_equity=r2(eq[0][1]), equity=r2(eq[-1][1]), ret_pct=round((eq[-1][1] / eq[0][1] - 1) * 100, 2),
                    max_dd_pct=round(mdd, 2), worst_day=r2(worst[1]), worst_day_date=str(worst[0]) if worst[0] else None,
                    worst_day_pct=round(worst[1] / eq[0][1] * 100, 2), qqq_ret_pct=qqq_return(eq[0][0]))

    # a $2,500-style account is already the real test: no replay needed
    if acct.get('start_equity') and acct['start_equity'] < 25_000: out_small = None
    else: out_small = small_account(trades)
    # did the stock bot show up, and run all 12 half-hourly checks, every market day?
    bot_days = sorted({e['_t'].astimezone(ET).date() for e in E if e['_t'].astimezone(ET).date().isoformat() >= START and e['event'] in ('na_check', 'orb_signal', 'orb_skip', 'order', 'stale_skip') and not e.get('coin')})
    slots = {}
    for e in E:
        if e['event'] == 'na_check' and e['_t'].astimezone(ET).date().isoformat() >= START: slots.setdefault(e['_t'].astimezone(ET).date(), set()).add(e.get('slot'))
    coverage, recent_missed, missed = [], [], []
    if bot_days:
        today = t0.date(); end = today - timedelta(days=1)          # judge finished days only
        cal = [d for d in market_days(bot_days[0], end) if d <= end]
        coverage = [dict(day=str(d), checks=len(slots.get(d, ())), of=SLOTS) for d in cal]
        missed = [str(d) for d in cal if d not in set(bot_days)]
        recent_missed = [c for c in coverage[-GATE_DAYS:] if c['checks'] < SLOTS - 1]   # allow one late check a day
    rejects = sum(1 for r in journal if r.get('act') == 'REJECTED' and ts(r['t']) >= datetime.now(timezone.utc) - timedelta(days=10))

    n = len(bot_days); enough = n >= GATE_DAYS
    G = [
        (True, f'{GATE_DAYS}+ trading days of results', f'{n} of {GATE_DAYS}'),          # only time can pass this one
        (bool(coverage) and not recent_missed, 'Bot ran full days, every market day (last 20)', f"{len(recent_missed)} short or missed" if recent_missed else (f'{len(coverage)} full days' if coverage else 'no finished days yet')),
        ((combined.get('net') or 0) > 0, 'Profitable after estimated costs', f"{combined.get('net', 0):+,.2f}" if combined.get('trades') else 'no trades yet'),
        ((combined.get('pf') or 0) >= GATE_PF, f'Profit factor {GATE_PF} or better ($ won ÷ $ lost)', str(combined.get('pf')) if combined.get('pf') else '–'),
        (bool(eq) and acct.get('max_dd_pct', 99) < GATE_MAX_DD, f'Biggest drop from a high under {GATE_MAX_DD:g}%', f"{acct.get('max_dd_pct', 0):.2f}%" if eq else '–'),
        (bool(eq) and acct.get('worst_day_pct', -99) > -GATE_WORST_DAY, f'Worst day inside the {GATE_WORST_DAY:g}% loss limit', f"{acct.get('worst_day_pct', 0):.2f}%" if eq else '–'),
        (combined.get('slip_bps') is not None and combined['slip_bps'] <= GATE_SLIP_BPS, f'Average slippage {GATE_SLIP_BPS / 100:.2f}% or less', f"{combined['slip_bps'] / 100:.3f}%" if combined.get('slip_bps') is not None else '–'),
        (rejects == 0, 'No rejected orders in the last 10 days', f'{rejects} rejected'),
    ]
    # pass = good and proven over 20+ days · track = good so far, not enough days yet · fail = not good right now
    items = [dict(state='pass' if good and enough else 'track' if good else 'fail', t=t, v=v) for good, t, v in G]
    gate = dict(ready=all(i['state'] == 'pass' for i in items), items=items)

    out = dict(updated=t0.isoformat(timespec='seconds'), start=START, account=acct, small=out_small, bots=bots, all=combined, gate=gate,
               bot_days=len(bot_days), missed=missed[-30:], coverage=coverage[-30:], open=[dict(bot=k[0], sym=k[1], qty=r2(v['q'], 6), avg=r2(v['avg'])) for k, v in open_pos.items()],
               trades=trades[-80:][::-1], journal=journal,
               costs_note='Paper fills are free. Costs are estimated as real money would pay: SEC + FINRA fees on stock sales, 0.25% per side on crypto.')
    json.dump(out, open(f'{OUT}/journal.json', 'w'), separators=(',', ':'))
    print(json.dumps(dict(event='journal', fills=len(F), trades=len(trades), rows=len(journal), net=combined.get('net'), ready=gate['ready'])), flush=True)
    push()

def push():
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True)
    subprocess.run(['git', 'init', '-q', '-b', 'live-journal', OUT], check=True)
    subprocess.run(g + ['add', '-A'], check=True)
    subprocess.run(g + ['commit', '-q', '-m', 'journal'], check=True)
    subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{REPO}.git', 'live-journal'], check=True, timeout=90, capture_output=True)

if __name__ == '__main__':
    main()
