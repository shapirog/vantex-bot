"""Vantex options bot: calls and puts on QQQ / SPY and on stocks that move on NEWS. Alpaca PAPER only.

It hunts three setups, in both directions (a call when the move is up, a put when it is down):
  1. INDEX BREAK   QQQ / SPY break out of their 9:30-10:00 range and hold      -> same-day options
  2. STOCK BREAK   a news stock breaks out of its 9:30-9:45 range and holds    -> this week's options
  3. NEWS SHOCK    a stock suddenly moves 2.5%+ in 20 minutes on heavy volume
                   with fresh news behind it (e.g. NVDA drops on a China story) -> this week's options
Stocks it watches: a list of big names with busy option markets (NVDA, TSLA, AAPL, AMD, META ...)
plus whatever the scanner's Radar finds moving on news today.

Why it's moving: before every stock trade it reads today's headlines for that stock (Alpaca news).
  - no news at all on a single stock  -> needs much heavier volume, and the card says "no news found"
  - the news points the OTHER way      -> skipped (a move against the news is often a trap)

Anti-trap rules (so a fake move doesn't trick it):
  - never the first candle: a break must hold 3 straight one-minute closes
  - the move needs real volume behind it (index 1.5x, stocks 2.5x, news shock 3x the day's average minute)
  - calls only above VWAP, puts only below it (index also the 50-minute EMA)
  - a news shock that has already given back 40%+ of its move is skipped (fading = trap)
  - no chasing: skip if the stock already ran too far past the level, or 8%+ in the shock
  - only option contracts with tight spreads and real open interest (thin options = bad fills)
  - fresh prices only (under 3 minutes old)

Risk (built for a small account; "options_risk" in control.json changes the size, 0.05-0.40):
  - default 15% of equity paid per trade, at most 2 open, 4 a day, one try per stock per direction
  - stop -30% of the premium; backup stop at the broker at -45% in case the bot is offline
  - at +50%: half off (or, with 1 contract, the stop jumps to +25%), then it trails 25% under the best price
  - out if the move fails (index/stock back inside the range, or a shock back across VWAP)
  - options day loss limit: if today's options trades lose 25% of the account, no new options today
  - same-day index options closed by 3:00 PM, stock options by 3:45 PM (it never holds overnight)
  - stops for the day if the main bot's profit lock / target / loss limit fires

Calendar guard (the days that trick traders):
  - Fed decision days (2:00 PM): no new entries after 1:30 PM, and anything open is closed at 1:55 PM
  - CPI inflation mornings (8:30 AM report): no entries before 10:30 AM, after the first swings settle
  - earnings: no options on a stock that reports today (after the close) or in the next 3 days,
    because option prices are inflated before earnings and collapse right after ("IV crush")
Market mood (trade with the market, not against it):
  - no calls while SPY is below VWAP and down 0.4%+; no puts while SPY is above VWAP and up 0.4%+
    (exception: a news shock whose headline agrees with the move, like NVDA on a China story)
  - wild day (VIXY, the fear-gauge fund, up 8%+): trade size is cut in half
Backtest: setups the weekly backtest marks "off" (losing over 15+ past trades) are skipped.
"""
import os, sys, json, math, re, time, subprocess, requests
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
KEY, SECRET = os.environ.get('APCA_API_KEY_ID') or '', os.environ.get('APCA_API_SECRET_KEY') or ''
if not KEY.startswith('PK'): sys.exit('Refusing to run: APCA_API_KEY_ID must be a PAPER key (starts with PK).')
H = {'APCA-API-KEY-ID': KEY, 'APCA-API-SECRET-KEY': SECRET}
TRADE, DATA = 'https://paper-api.alpaca.markets', 'https://data.alpaca.markets'
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
NTFY = os.environ.get('NTFY_TOPIC')
LOG = os.environ.get('VANTEX_OPT_LOG', 'logs/options_log.jsonl')
LIVE_DIR = '/tmp/vantex-opt'

INDEXES = ['QQQ', 'SPY']
LIQUID = ['NVDA', 'TSLA', 'AAPL', 'AMD', 'META', 'AMZN', 'MSFT', 'GOOGL', 'NFLX', 'AVGO', 'PLTR', 'COIN', 'MU', 'MSTR', 'UBER', 'BA']
MAX_RADAR = 8                       # scanner news movers added each day
RISK_PCT = 0.15                     # default share of equity paid for one trade
MAX_OPEN, MAX_ENTRIES, MAX_QTY = 2, 4, 10
DAY_LOSS_PCT = 0.25                 # options day loss limit
IDX_OR, STK_OR = 30, 15             # opening ranges in minutes
ENTRY_FROM, ENTRY_TO = 10 * 60, 14 * 60          # range breaks: 10:00 AM - 2:00 PM
SHOCK_TO = 14 * 60 + 30                          # news shocks: until 2:30 PM
IDX_LAST, STK_FLAT = 13 * 60 + 30, 15 * 60 + 45  # index entries end 1:30 PM; stock options closed 3:45 PM
IDX_FLAT = 15 * 60                               # same-day index options closed 3:00 PM
HOLD_BARS, EMA_LEN = 3, 50
IDX_VOL, STK_VOL, SHOCK_VOL, NONEWS_VOL = 1.5, 2.5, 3.0, 4.0
IDX_PAST, STK_PAST = 0.005, 0.015
SHOCK_MIN, SHOCK_MAX, SHOCK_BARS, SHOCK_GIVEBACK = 0.025, 0.08, 20, 0.40
MAX_SPREAD_IDX, MAX_SPREAD_STK, MIN_OI = 0.15, 0.12, 300
STOP_PCT, BROKER_STOP_PCT = 0.30, 0.45
PARTIAL_PCT, LOCK_PCT, TRAIL_PCT = 0.50, 0.25, 0.25
STALE_SEC = 180
NEWS_HOURS = 18                     # headlines since yesterday evening count as "why"
MOOD_PCT, WILD_VIXY = 0.004, 0.08   # SPY move that sets the market mood; VIXY jump that means a wild day
FOMC_STOP, FOMC_FLAT, CPI_FROM = 13 * 60 + 30, 13 * 60 + 55, 10 * 60 + 30
# Fed decision days (federalreserve.gov; 2027 dates are the Fed's tentative schedule)
FOMC = {'2026-01-28', '2026-03-18', '2026-04-29', '2026-06-17', '2026-07-29', '2026-09-16', '2026-10-28', '2026-12-09',
        '2027-01-27', '2027-03-17', '2027-04-28', '2027-06-09', '2027-07-28', '2027-09-15', '2027-10-27', '2027-12-08'}
# CPI release days, 8:30 AM ET (bls.gov schedule)
CPI = {'2026-01-13', '2026-02-13', '2026-03-11', '2026-04-10', '2026-05-12', '2026-06-10', '2026-07-14', '2026-08-12',
       '2026-09-11', '2026-10-14', '2026-11-10', '2026-12-10', '2027-01-13', '2027-02-11', '2027-03-10', '2027-04-13',
       '2027-05-12', '2027-06-10', '2027-07-14', '2027-08-11', '2027-09-14', '2027-10-14', '2027-11-10', '2027-12-10'}

# which way a headline points
UPW = r'upgrade|beats?\b|tops\b|raises|raised|record|approv|wins?\b|award|contract|partner|deal\b|acquir|buyback|surge|soar|jump|rall(y|ies)|price target (raised|hike)|outperform|strong demand|launch|breakthrough|expands?\b|bullish'
DNW = r'downgrade|miss(es)?\b|cuts?\b|lowers|warns?\b|probe|investigat|lawsuit|sues\b|recall|\bban\b|banned|restrict|export (curb|control|ban)|sanction|tariff|china|\bspy\b|espionage|halt|delay|fraud|short seller|layoff|plunge|tumble|slump|sinks?\b|drops?\b|falls?\b|slides?\b|bearish|underperform|offering|dilut|resign'

EVENTS = []
def log(**k):
    k['ts'] = datetime.now(ET).isoformat(timespec='seconds'); print(json.dumps(k), flush=True)
    if k.get('event') not in ('opt_scan',): EVENTS.append(k); del EVENTS[:-60]
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

_CTRL = {'t': 0, 'mode': 'on', 'risk': RISK_PCT}
def control():
    """Same kill switch as the other bots (control.json in the repo). Also reads "options_risk"."""
    if time.time() - _CTRL['t'] < 60: return _CTRL['mode']
    tok = os.environ.get('GH_TOKEN'); mode = _CTRL['mode']; risk = _CTRL['risk']
    try:
        if tok:
            r = requests.get(f'https://api.github.com/repos/{REPO}/contents/control.json?ref=main',
                             headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github.raw'}, timeout=15)
            if r.status_code == 200:
                c = json.loads(r.text); mode = str(c.get('trading', 'on')).strip().lower()
                try: risk = min(0.40, max(0.05, float(c.get('options_risk', RISK_PCT))))
                except Exception: risk = RISK_PCT
            elif r.status_code == 404: mode = 'on'
    except Exception as e: print('control check failed', str(e)[:120], flush=True)
    if mode not in ('on', 'pause', 'stop'): mode = 'pause'
    _CTRL.update(t=time.time(), mode=mode, risk=risk); return mode

def raw(path):
    try:
        r = requests.get(f'https://raw.githubusercontent.com/{REPO}/{path}?t={int(time.time())}', timeout=20)
        return r.json() if r.ok else None
    except Exception: return None

_DAY = {'t': 0, 'done': None}
def day_done():
    """The main bot's daily profit target / profit lock / loss limit also ends the options day."""
    if time.time() - _DAY['t'] < 60: return _DAY['done']
    st = raw('live/state.json') or {}
    ds = st.get('day_status') or {}
    today = datetime.now(ET).date().isoformat()
    done = ds.get('done') if ds.get('date') == today else None
    _DAY.update(t=time.time(), done=done if done in ('profit_target', 'profit_lock_hit', 'loss_limit') else None)
    return _DAY['done']

# ---------------- calendar guard ----------------
EARN = {'day': None, 'by': {}}
def nasdaq_earnings(d):
    """Earnings on one date from Nasdaq's public calendar: {SYM: 'pre' | 'post' | '?'}."""
    try:
        r = requests.get('https://api.nasdaq.com/api/calendar/earnings', params=dict(date=d.isoformat()), timeout=20,
                         headers={'User-Agent': 'Mozilla/5.0 (vantex-bot)', 'Accept': 'application/json'})
        if not r.ok: return None
        rows = (r.json().get('data') or {}).get('rows') or []
        return {x['symbol']: ('pre' if 'pre' in str(x.get('time', '')) else 'post' if 'after' in str(x.get('time', '')) else '?') for x in rows if x.get('symbol')}
    except Exception as e:
        print('earnings calendar failed', str(e)[:120], flush=True); return None

def load_earnings(today):
    if EARN['day'] == today: return
    by = {}
    for k in range(0, 4):
        d = today + timedelta(days=k); e = nasdaq_earnings(d)
        if e is None: continue
        for s, when in e.items(): by.setdefault(s, []).append((k, when))
    EARN.update(day=today, by=by)

def earnings_block(sym, by=None):
    """Reports after today's close or within the next 3 days -> option prices are inflated; skip."""
    for k, when in (by if by is not None else EARN['by']).get(sym, []):
        if k == 0 and when != 'pre': return 'reports earnings today'
        if 1 <= k <= 3: return f'reports earnings in {k} day{"s" if k > 1 else ""}'
    return None

def calendar_block(day_iso, m):
    if day_iso in FOMC and m >= FOMC_STOP: return 'Fed decision day: no new trades after 1:30 PM'
    if day_iso in CPI and m < CPI_FROM: return 'CPI morning: waiting until 10:30 AM'
    return None

def mood(L_by):
    """(spy_chg, spy_above_vwap, wild) from SPY and VIXY bars."""
    S = L_by.get('SPY'); V = L_by.get('VIXY')
    spy_chg = above = None; wild = False
    if S and S['today']:
        p = S['today'][-1]['c']; spy_chg = p / S['open'] - 1; above = bool(S['vwap']) and p >= S['vwap']
    if V and V['today']: wild = V['today'][-1]['c'] / V['open'] - 1 >= WILD_VIXY
    return spy_chg, above, wild

def mood_block(d, setup, note, md):
    spy_chg, above, _ = md
    if spy_chg is None or (setup == 'news shock' and note == 'news agrees'): return None
    if d == 1 and above is False and spy_chg <= -MOOD_PCT: return f'market falling (SPY {spy_chg * 100:+.1f}%, below VWAP): no calls'
    if d == -1 and above is True and spy_chg >= MOOD_PCT: return f'market rising (SPY {spy_chg * 100:+.1f}%, above VWAP): no puts'
    return None

BT = {'t': 0, 'off': set()}
def backtest_off():
    """Setups the weekly backtest found losing (15+ trades, profit factor under 0.9)."""
    if time.time() - BT['t'] < 3600: return BT['off']
    b = raw('live-backtest/backtest.json') or {}
    BT.update(t=time.time(), off={k for k, v in (b.get('verdict') or {}).items() if v.get('status') == 'off'}); return BT['off']

# ---------------- market data ----------------
def _bars(params, syms):
    out, tok = {}, None
    for _ in range(30):
        p = dict(params, symbols=','.join(syms))
        if tok: p['page_token'] = tok
        r = req('GET', f'{DATA}/v2/stocks/bars', params=p)
        if not r.ok: break
        j = r.json()
        for s, B in (j.get('bars') or {}).items(): out.setdefault(s, []).extend(B)
        tok = j.get('next_page_token')
        if not tok: break
    res = {}
    for s, B in out.items():
        L = []
        for b in B:
            t = datetime.fromisoformat(b['t'].replace('Z', '+00:00')).astimezone(ET)
            if 9 * 60 + 30 <= t.hour * 60 + t.minute < 16 * 60: L.append(dict(t=t, o=b['o'], h=b['h'], l=b['l'], c=b['c'], v=b['v']))
        res[s] = sorted(L, key=lambda b: b['t'])
    return res

def all_bars(syms, now):
    """Indexes get 5 days (for the 50-minute EMA); stocks get today."""
    idx = [s for s in syms if s in INDEXES]; stk = [s for s in syms if s not in INDEXES]
    B = {}
    if idx: B.update(_bars(dict(timeframe='1Min', start=(now - timedelta(days=5)).isoformat(), end=now.isoformat(), limit=10000, feed='iex'), idx))
    if stk: B.update(_bars(dict(timeframe='1Min', start=now.replace(hour=9, minute=30, second=0, microsecond=0).isoformat(), end=now.isoformat(), limit=10000, feed='iex'), stk))
    return B

def ema(vals, n):
    if not vals: return None
    k, e = 2 / (n + 1), vals[0]
    for v in vals[1:]: e = v * k + e * (1 - k)
    return e

def last_trade(sym):
    r = req('GET', f'{DATA}/v2/stocks/{sym}/trades/latest', params=dict(feed='iex'))
    t = (r.json().get('trade') or {}) if r.ok else {}
    if not t.get('p'): return None, None
    return float(t['p']), datetime.fromisoformat(t['t'].replace('Z', '+00:00').split('.')[0] + '+00:00')

def levels(bars, now, or_min):
    """Opening range, VWAP, EMA and the day's average minute volume."""
    today = [b for b in bars if b['t'].date() == now.date()]
    cut = now.replace(hour=9, minute=30, second=0, microsecond=0) + timedelta(minutes=or_min)
    orb = [b for b in today if b['t'] < cut]; after = [b for b in today if b['t'] >= cut]
    if not orb: return None
    pv = sum((b['h'] + b['l'] + b['c']) / 3 * b['v'] for b in today); vv = sum(b['v'] for b in today)
    return dict(today=today, orb=orb, after=after, or_min=or_min, hi=max(b['h'] for b in orb), lo=min(b['l'] for b in orb), open=today[0]['o'],
                vwap=pv / vv if vv else None, ema=ema([b['c'] for b in bars], EMA_LEN), avg_v=vv / len(today) if today else 0)

def break_setup(d, L, idx, vol_mult):
    """Range break: d = +1 call (up), -1 put (down)."""
    if not L or len(L['orb']) < L['or_min'] - 5 or len(L['after']) < HOLD_BARS: return False, 'not enough bars'
    level = L['hi'] if d == 1 else L['lo']
    last = L['after'][-HOLD_BARS:]
    if not all((b['c'] > level) if d == 1 else (b['c'] < level) for b in last): return False, f'break not held {HOLD_BARS} minutes'
    i0 = next((i for i, b in enumerate(L['after']) if (b['c'] > level if d == 1 else b['c'] < level)), None)
    if i0 is None or max(b['v'] for b in L['after'][i0:]) < vol_mult * L['avg_v']: return False, 'breakout volume too light'
    p = last[-1]['c']
    if L['vwap'] and ((d == 1 and p < L['vwap']) or (d == -1 and p > L['vwap'])): return False, 'wrong side of VWAP'
    if idx and L['ema'] and ((d == 1 and p < L['ema']) or (d == -1 and p > L['ema'])): return False, 'wrong side of the 50 EMA'
    if abs(p / level - 1) > (IDX_PAST if idx else STK_PAST): return False, 'already too far past the range (chasing)'
    return True, dict(setup='range break', level=round(level, 2), hi=round(L['hi'], 2), lo=round(L['lo'], 2),
                      vwap=round(L['vwap'], 2) if L['vwap'] else None, ema=round(L['ema'], 2) if L['ema'] else None, price=p)

def shock_setup(d, L, vol_mult):
    """News shock: a sudden 2.5%+ move in the last 20 minutes on heavy volume that is HOLDING (not fading)."""
    if not L or len(L['after']) < SHOCK_BARS + 1: return False, 'not enough bars'
    win = L['today'][-SHOCK_BARS:]; base = L['today'][-SHOCK_BARS - 1]['c']; p = win[-1]['c']
    move = (p / base - 1) * d
    if move < SHOCK_MIN: return False, 'no sudden move'
    if move > SHOCK_MAX: return False, 'already moved too far (chasing)'
    ext = max(b['h'] for b in win) if d == 1 else min(b['l'] for b in win)
    if abs(ext - base) > 0 and abs(ext - p) / abs(ext - base) > SHOCK_GIVEBACK: return False, 'move is fading (gave back 40%+)'
    if not all(((b['c'] / base - 1) * d) >= SHOCK_MIN * 0.6 for b in win[-HOLD_BARS:]): return False, f'move not held {HOLD_BARS} minutes'
    pre = L['today'][:-SHOCK_BARS]; base_v = sum(b['v'] for b in pre) / len(pre) if pre else L['avg_v']   # volume BEFORE the move
    if max(b['v'] for b in win) < vol_mult * base_v: return False, 'shock volume too light'
    if L['vwap'] and ((d == 1 and p < L['vwap']) or (d == -1 and p > L['vwap'])): return False, 'wrong side of VWAP'
    return True, dict(setup='news shock', level=round(base, 2), hi=round(L['hi'], 2), lo=round(L['lo'], 2),
                      vwap=round(L['vwap'], 2) if L['vwap'] else None, ema=None, price=p, move_pct=round(move * 100 * d, 2))

# ---------------- news: why is it moving? ----------------
NEWS = {'t': 0, 'by': {}}
def load_news(syms, now):
    if time.time() - NEWS['t'] < 120: return
    by = {}; start = (now - timedelta(hours=NEWS_HOURS)).astimezone(timezone.utc).isoformat()
    for i in range(0, len(syms), 25):
        r = req('GET', f'{DATA}/v1beta1/news', params=dict(symbols=','.join(syms[i:i + 25]), start=start, limit=50, sort='desc'))
        for n in ((r.json().get('news') or []) if r.ok else []):
            for s in n.get('symbols') or []:
                if s in syms: by.setdefault(s, []).append(dict(h=n.get('headline', '')[:160], t=n.get('created_at'), src=n.get('source')))
    NEWS.update(t=time.time(), by=by)

def tone(h):
    t = h.lower(); return (1 if re.search(UPW, t) else 0) - (1 if re.search(DNW, t) else 0)

def why(sym, d):
    """(ok, headline, note). Index trades don't need a headline."""
    items = NEWS['by'].get(sym) or []
    if sym in INDEXES: return True, items[0]['h'] if items else '', 'index'
    if not items: return True, '', 'no news found'
    agree = [n for n in items if tone(n['h']) * d > 0]; against = [n for n in items if tone(n['h']) * d < 0]
    if agree: return True, agree[0]['h'], 'news agrees'
    if against: return False, against[0]['h'], 'news points the other way'
    return True, items[0]['h'], 'news found'

# ---------------- option contracts ----------------
def occ_parts(sym):
    """NVDA251121C00185000 -> ('NVDA', '2025-11-21', 'C', 185.0)"""
    k = sym[-15:]
    return sym[:-15], f'20{k[0:2]}-{k[2:4]}-{k[4:6]}', k[6], int(k[7:]) / 1000

def expiry_window(und, today):
    """Index: same day. Stocks: nearest expiry 2-10 days out (weeklies), so time decay doesn't eat a day trade."""
    if und in INDEXES: return [dict(expiration_date=today.isoformat()), dict(expiration_date_gte=today.isoformat(), expiration_date_lte=(today + timedelta(days=7)).isoformat())]
    return [dict(expiration_date_gte=(today + timedelta(days=2)).isoformat(), expiration_date_lte=(today + timedelta(days=10)).isoformat())]

def chain(und, kind, price, today):
    base = dict(feed='indicative', type=kind, strike_price_gte=round(price * 0.96, 2), strike_price_lte=round(price * 1.04, 2), limit=1000)
    for extra in expiry_window(und, today):
        r = req('GET', f'{DATA}/v1beta1/options/snapshots/{und}', params={**base, **extra})
        snaps = (r.json().get('snapshots') or {}) if r.ok else {}
        if snaps:
            first = min(occ_parts(s)[1] for s in snaps)
            return {s: v for s, v in snaps.items() if occ_parts(s)[1] == first}
    return {}

def open_interest(und, exp, kind):
    r = req('GET', f'{TRADE}/v2/options/contracts', params=dict(underlying_symbols=und, expiration_date=exp, type=kind, status='active', limit=1000))
    return {c['symbol']: int(float(c.get('open_interest') or 0)) for c in ((r.json().get('option_contracts') or []) if r.ok else [])}

def pick_contract(und, d, price, budget, today):
    """At the money first, then a little out of the money if that's too expensive. Never far out (lottery tickets)."""
    kind = 'call' if d == 1 else 'put'; idx = und in INDEXES
    snaps = chain(und, kind, price, today)
    if not snaps: return None, 'no option quotes for this expiry'
    exp = occ_parts(next(iter(snaps)))[1]
    oi = {} if idx else open_interest(und, exp, kind)
    rows = []
    for s, v in snaps.items():
        q = v.get('latestQuote') or {}; ap, bp = float(q.get('ap') or 0), float(q.get('bp') or 0)
        if ap <= 0 or bp <= 0: continue
        k = occ_parts(s)[3]; otm = (k - price) * d
        if otm < -price * (0.004 if idx else 0.01): continue          # not deep in the money
        if otm > price * (0.006 if idx else 0.02): continue           # not far out of the money
        mid = (ap + bp) / 2
        rows.append(dict(sym=s, k=k, exp=exp, ap=ap, bp=bp, mid=mid, spread=(ap - bp) / mid, otm=otm, oi=oi.get(s)))
    rows.sort(key=lambda r: abs(r['otm']))
    why_not = 'no contract near the money'
    for r in rows[:6]:
        if r['spread'] > (MAX_SPREAD_IDX if idx else MAX_SPREAD_STK): why_not = 'option spreads too wide'; continue
        if not idx and (r['oi'] or 0) < MIN_OI: why_not = f'open interest under {MIN_OI} (thin option)'; continue
        if r['ap'] * 100 > budget: why_not = f"cheapest fitting contract ${r['ap'] * 100:.0f} is over the ${budget:.0f} budget"; continue
        r['qty'] = min(MAX_QTY, int(budget // (r['ap'] * 100)))
        return r, None
    return None, why_not

def option_quote(sym):
    r = req('GET', f'{DATA}/v1beta1/options/snapshots', params=dict(symbols=sym, feed='indicative'))
    v = ((r.json().get('snapshots') or {}).get(sym) or {}) if r.ok else {}
    q = v.get('latestQuote') or {}; ap, bp = float(q.get('ap') or 0), float(q.get('bp') or 0)
    return (ap + bp) / 2 if ap > 0 and bp > 0 else None

# ---------------- orders ----------------
def place(body):
    r = req('POST', f'{TRADE}/v2/orders', json=body)
    if not r.ok:
        log(event='opt_reject', sym=body['symbol'], body=body, err=r.text[:200])
        notify(f"Vantex options order rejected: {body['symbol']}", r.text[:160], 'warning')
        return None
    return r.json()

def wait_fill(oid, secs=25):
    for _ in range(secs):
        o = req('GET', f'{TRADE}/v2/orders/{oid}').json()
        if o.get('status') == 'filled': return o
        if o.get('status') in ('canceled', 'rejected', 'expired'): return None
        time.sleep(1)
    req('DELETE', f'{TRADE}/v2/orders/{oid}'); time.sleep(1)
    o = req('GET', f'{TRADE}/v2/orders/{oid}').json()
    return o if float(o.get('filled_qty') or 0) > 0 else None

def cancel_mine(sym=None):
    for o in req('GET', f'{TRADE}/v2/orders', params=dict(status='open', limit=500)).json():
        if (o.get('client_order_id') or '').startswith('OPT-') and (sym is None or o['symbol'] == sym):
            req('DELETE', f"{TRADE}/v2/orders/{o['id']}")

def sell(sym, qty, tag):
    return place(dict(symbol=sym, qty=str(int(qty)), side='sell', type='market', time_in_force='day', client_order_id=f'OPT-{sym}-{tag}-{int(time.time())}'))

def broker_stop(sym, qty, entry):
    stop = max(0.01, round(entry * (1 - BROKER_STOP_PCT), 2))
    place(dict(symbol=sym, qty=str(int(qty)), side='sell', type='stop', stop_price=str(stop), time_in_force='day', client_order_id=f'OPT-{sym}-s-{int(time.time())}'))

def close_trade(sym, T, why_, now, price=None):
    cancel_mine(sym); time.sleep(1)
    pos = req('GET', f'{TRADE}/v2/positions/{sym}')
    if pos.status_code == 200:
        q = abs(float(pos.json()['qty']))
        if q >= 1: sell(sym, q, 'x')
    T['closed'] = now.isoformat(timespec='seconds'); T['exit_why'] = why_
    if price: T['exit'] = round(price, 2)
    log(event='opt_exit', sym=sym, und=T['und'], why=why_, price=price)

# ---------------- state across runs ----------------
STATE = {'date': None, 'trades': {}, 'tries': [], 'movers': []}
def load_state():
    today = datetime.now(ET).date().isoformat()
    st = raw('live-opt/options.json') or {}
    if st.get('date') == today: STATE.update(date=today, trades=st.get('trades') or {}, tries=st.get('tries') or [], movers=st.get('movers') or [])
    else: STATE.update(date=today, trades={}, tries=[], movers=[])

def account():
    return req('GET', f'{TRADE}/v2/account').json()

def radar_names():
    """Today's news movers from the scanner (up on good news, down on bad news), $10+ so they have real options."""
    rd = raw('live-scan/radar.json') or {}
    if rd.get('day') != datetime.now(ET).date().isoformat(): return []
    up = [x['sym'] for x in rd.get('stocks') or [] if x.get('p', 0) >= 10 and any(t.startswith('NEWS ') for t in x.get('tags', []))]
    dn = [x['sym'] for x in rd.get('fades') or [] if x.get('p', 0) >= 10]
    return list(dict.fromkeys(up + dn))[:MAX_RADAR]

def options_pl_today():
    def px(T):
        for k in ('exit', 'now'):
            if T.get(k) is not None: return T[k]
        return T['entry']
    return sum((px(T) - T['entry']) * T['qty'] * 100 for T in STATE['trades'].values())

# ---------------- one pass ----------------
def manage(now, L_by):
    """Stops, the +50% half, the trailing stop and the failed-move exit."""
    open_pos = {p['symbol']: p for p in req('GET', f'{TRADE}/v2/positions').json() if p.get('asset_class') == 'us_option'}
    for sym, T in list(STATE['trades'].items()):
        if T.get('closed'): continue
        if sym not in open_pos:
            T['closed'] = now.isoformat(timespec='seconds'); T['exit_why'] = 'backup stop filled at the broker'
            T['exit'] = round(T['entry'] * (1 - BROKER_STOP_PCT), 2)
            log(event='opt_closed', sym=sym, why=T['exit_why']); continue
        P = open_pos[sym]; q = abs(float(P['qty']))
        p = float(P.get('current_price') or 0) or option_quote(sym) or T['entry']
        T['now'] = round(p, 2); T['peak'] = max(T.get('peak', T['entry']), p)
        gain = p / T['entry'] - 1; T['gain_pct'] = round(gain * 100, 1)
        L = L_by.get(T['und'])
        if L and len(L['today']) >= 2 and not T.get('half'):
            c2 = [b['c'] for b in L['today'][-2:]]
            if T.get('setup') == 'news shock':
                back = bool(L['vwap']) and all((c < L['vwap']) if T['d'] == 1 else (c > L['vwap']) for c in c2); why_ = f"{T['und']} fell back across VWAP"
            else:
                back = all((c < T['level']) if T['d'] == 1 else (c > T['level']) for c in c2); why_ = f"{T['und']} back inside its morning range"
            if back:
                close_trade(sym, T, why_, now, p)
                notify(f"Vantex options: {T['und']} move failed", f'Out of {sym} at ${p:.2f} ({gain * 100:+.0f}%).', 'warning'); continue
        if not T.get('half') and gain >= PARTIAL_PCT:
            if q >= 2:
                cancel_mine(sym); time.sleep(1)
                half = int(q // 2); sell(sym, half, 'h'); time.sleep(2)
                broker_stop(sym, q - half, T['entry'])
            T.update(half=True, stop=round(T['entry'] * (1 + (0 if q >= 2 else LOCK_PCT)), 2))
            log(event='opt_partial', sym=sym, price=p, gain_pct=round(gain * 100, 1), sold=int(q // 2) if q >= 2 else 0)
            notify(f"Vantex options: {T['und']} {T['kind']} +{gain * 100:.0f}%",
                   'Took half off. The rest trails.' if q >= 2 else f"Stop raised to +{LOCK_PCT * 100:.0f}%. It trails from here.", 'moneybag')
        stop = T['entry'] * (1 - STOP_PCT)
        if T.get('half'): stop = max(T.get('stop', 0), T['peak'] * (1 - TRAIL_PCT))
        T['stop'] = round(stop, 2)
        if p <= stop:
            close_trade(sym, T, 'trailing stop' if T.get('half') else f'stop -{STOP_PCT * 100:.0f}%', now, p)
            notify(f"Vantex options: out of {T['und']} {T['kind']}", f'{sym} at ${p:.2f} ({gain * 100:+.0f}%).', 'chart_with_downwards_trend' if gain < 0 else 'white_check_mark')

def candidates(now, L_by):
    """Every setup that is confirmed right now, best first. Also builds the 'why they're moving' list."""
    m = now.hour * 60 + now.minute; out = []; movers = []; md = mood(L_by); off = backtest_off(); day_iso = now.date().isoformat()
    STATE['mood'] = dict(spy_chg=round(md[0] * 100, 2) if md[0] is not None else None, spy_above_vwap=md[1], wild=md[2],
                         calendar=calendar_block(day_iso, m) or ('Fed day' if day_iso in FOMC else 'CPI day' if day_iso in CPI else None))
    for und, L in L_by.items():
        if und == 'VIXY' or not L or not L['today']: continue
        idx = und in INDEXES
        p = L['today'][-1]['c']
        if not idx:
            chg = (p / L['open'] - 1) * 100
            items = NEWS['by'].get(und) or []
            if abs(chg) >= 2 or items:
                movers.append(dict(sym=und, p=round(p, 2), chg=round(chg, 2), news=items[0]['h'] if items else '', tone=tone(items[0]['h']) if items else 0))
        if idx and m > IDX_LAST: continue
        for d in (1, -1):
            key = f'{und}{d}'
            if key in STATE['tries']: continue
            if idx: ok, info = break_setup(d, L, True, IDX_VOL)
            else:
                ok, info = shock_setup(d, L, SHOCK_VOL) if m <= SHOCK_TO else (False, 'too late for a shock')
                if not ok and m <= ENTRY_TO: ok, info = break_setup(d, L, False, STK_VOL)
            if not ok: continue
            good, headline, note = why(und, d)
            if not good:
                STATE['tries'].append(key); log(event='opt_skip', und=und, dir=d, why=f'{note}: {headline}'); continue
            if note == 'no news found' and max(b['v'] for b in L['today'][-SHOCK_BARS:]) < NONEWS_VOL * L['avg_v']:
                continue
            info.update(headline=headline, news_note=note)
            setup_key = 'index break' if idx else info['setup']
            block = (f'backtest turned off "{setup_key}"' if setup_key in off else None) or calendar_block(day_iso, m) \
                or (None if idx else earnings_block(und)) or mood_block(d, info['setup'], note, md)
            if block:
                if f'blk{key}' not in STATE['tries']: STATE['tries'].append(f'blk{key}'); log(event='opt_skip', und=und, dir=d, why=block)
                continue
            rank = (2 if info['setup'] == 'news shock' else 1) + (1 if note == 'news agrees' else 0)
            out.append((rank, und, d, info))
    movers.sort(key=lambda x: -abs(x['chg'])); STATE['movers'] = movers[:12]
    return [c[1:] for c in sorted(out, key=lambda c: -c[0])]

def hunt(now, acct, L_by):
    m = now.hour * 60 + now.minute
    cands = candidates(now, L_by)                       # always refresh the movers list
    if control() != 'on' or day_done(): return
    if not (ENTRY_FROM <= m <= SHOCK_TO): return
    if int(acct.get('options_trading_level') or 0) < 2:
        if 'level' not in STATE['tries']: STATE['tries'].append('level'); log(event='opt_skip', why='account options level is below 2 (buying calls/puts)')
        return
    eq = float(acct['equity'])
    if options_pl_today() <= -DAY_LOSS_PCT * eq:
        if 'dayloss' not in STATE['tries']:
            STATE['tries'].append('dayloss'); log(event='opt_skip', why='options day loss limit hit'); notify('Vantex options: day loss limit', 'No new options trades today.', 'no_entry')
        return
    live = [s for s, T in STATE['trades'].items() if not T.get('closed')]
    if len(live) >= MAX_OPEN or len(STATE['trades']) >= MAX_ENTRIES: return
    busy = {STATE['trades'][s]['und'] for s in live}
    obp = float(acct.get('options_buying_power') or acct.get('buying_power') or 0)
    budget = min(eq * _CTRL['risk'] * (0.5 if mood(L_by)[2] else 1), obp)
    for und, d, info in cands:
        if und in busy: continue
        px, pt = last_trade(und)
        if px is None or (datetime.now(timezone.utc) - pt).total_seconds() > STALE_SEC: continue
        STATE['tries'].append(f'{und}{d}')
        c, why_not = pick_contract(und, d, px, budget, now.date())
        if not c: log(event='opt_skip', und=und, dir=d, why=why_not); continue
        lim = round(c['ap'] * 1.02 + 0.005, 2)
        o = place(dict(symbol=c['sym'], qty=str(c['qty']), side='buy', type='limit', limit_price=str(lim), time_in_force='day', client_order_id=f"OPT-{c['sym']}-e-{int(time.time())}"))
        f = wait_fill(o['id']) if o else None
        if not f: log(event='opt_skip', und=und, sym=c['sym'], why='entry did not fill'); continue
        fill = float(f['filled_avg_price']); fq = int(float(f['filled_qty']))
        broker_stop(c['sym'], fq, fill)
        kind = 'CALL' if d == 1 else 'PUT'
        STATE['trades'][c['sym']] = dict(und=und, d=d, kind=kind, strike=c['k'], exp=c['exp'], qty=fq, entry=fill, peak=fill, now=fill,
                                         stop=round(fill * (1 - STOP_PCT), 2), level=info['level'], hi=info['hi'], lo=info['lo'], und_entry=px,
                                         cost=round(fill * fq * 100, 2), t=now.isoformat(timespec='seconds'), gain_pct=0.0,
                                         setup=info['setup'], headline=info.get('headline', ''), news_note=info.get('news_note', ''), move_pct=info.get('move_pct'))
        log(event='opt_entry', sym=c['sym'], und=und, dir=d, qty=fq, price=fill, cost=round(fill * fq * 100, 2), setup=info['setup'], level=info['level'],
            vwap=info['vwap'], ema=info['ema'], headline=info.get('headline', ''), news_note=info.get('news_note', ''))
        notify(f"Vantex options BUY {fq} {und} {c['k']:g} {kind}",
               f"${fill:.2f} each (${fill * fq * 100:,.0f}) · {info['setup']}: {und} {'up' if d == 1 else 'down'}"
               + (f" · why: {info['headline'][:90]}" if info.get('headline') else ' · no news found') + f" · stop -{STOP_PCT * 100:.0f}%",
               'green_circle' if d == 1 else 'red_circle')
        live.append(c['sym']); busy.add(und)
        if len(live) >= MAX_OPEN or len(STATE['trades']) >= MAX_ENTRIES: return

def chart_data(L):
    """What the city draws in the sky: today's line, the range and VWAP."""
    if not L: return None
    pts = L['today'][-150:]
    return dict(t0=pts[0]['t'].strftime('%H:%M') if pts else None, c=[round(b['c'], 2) for b in pts],
                hi=round(L['hi'], 2), lo=round(L['lo'], 2), vwap=round(L['vwap'], 2) if L['vwap'] else None, ema=round(L['ema'], 2) if L['ema'] else None)

def publish(eq, L_by):
    show = set(INDEXES) | {T['und'] for T in STATE['trades'].values()}
    st = dict(updated=datetime.now(ET).isoformat(timespec='seconds'), date=STATE['date'], equity=eq, trades=STATE['trades'], tries=STATE['tries'],
              movers=STATE['movers'], mood=STATE.get('mood'), earnings_soon=sorted(s for s in EARN['by'] if s in set(LIQUID) | {T['und'] for T in STATE['trades'].values()} and earnings_block(s)), backtest_off=sorted(BT['off']), charts={u: chart_data(L_by.get(u)) for u in show}, day_done=_DAY['done'], events=EVENTS[-40:],
              rules=dict(risk_pct=_CTRL['risk'], max_open=MAX_OPEN, max_entries=MAX_ENTRIES, stop_pct=STOP_PCT, partial_pct=PARTIAL_PCT, trail_pct=TRAIL_PCT,
                         day_loss_pct=DAY_LOSS_PCT, indexes=INDEXES, liquid=LIQUID))
    os.makedirs(LIVE_DIR, exist_ok=True); json.dump(st, open(f'{LIVE_DIR}/options.json', 'w'), separators=(',', ':'))
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', LIVE_DIR, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    try:
        subprocess.run(['rm', '-rf', f'{LIVE_DIR}/.git'], check=True); subprocess.run(['git', 'init', '-q', '-b', 'live-opt', LIVE_DIR], check=True)
        subprocess.run(g + ['add', '-A'], check=True); subprocess.run(g + ['commit', '-q', '-m', 'options'], check=True)
        subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{REPO}.git', 'live-opt'], check=True, timeout=60, capture_output=True)
    except Exception as e: print('push failed', str(e)[:200], flush=True)

def flat_time(T):
    return IDX_FLAT if T['und'] in INDEXES else STK_FLAT

def loop(max_minutes):
    t0 = time.time(); load_state(); last_pub = 0; eq = 0.0; L_by = {}; last_bars = 0; universe = INDEXES + LIQUID; last_uni = 0
    while True:
        if time.time() - t0 > max_minutes * 60:
            log(event='handoff', why='runtime limit'); publish(float(account()['equity']), L_by); sys.exit(3)
        c = req('GET', f'{TRADE}/v2/clock').json()
        if not c.get('is_open'):
            nxt = datetime.fromisoformat(c['next_open']); wait = (nxt - datetime.now(nxt.tzinfo)).total_seconds()
            if wait > 100 * 60: log(event='market_closed'); return
            time.sleep(min(max(wait, 5), 300)); continue
        now = datetime.now(ET); m = now.hour * 60 + now.minute
        try:
            acct = account(); eq = float(acct['equity'])
            if time.time() - last_uni > 300:
                universe = list(dict.fromkeys(INDEXES + LIQUID + ['VIXY'] + radar_names() + [T['und'] for T in STATE['trades'].values()])); last_uni = time.time()
                load_earnings(now.date())
            if time.time() - last_bars > 50:
                B = all_bars(universe, now)
                L_by = {u: levels(B.get(u, []), now, IDX_OR if u in INDEXES else STK_OR) for u in universe}; last_bars = time.time()
                load_news([u for u in universe if u not in INDEXES and u != 'VIXY'], now)
            done = day_done(); ctl = control()
            for sym, T in STATE['trades'].items():
                if T.get('closed'): continue
                fomc = now.date().isoformat() in FOMC and m >= FOMC_FLAT
                if ctl == 'stop' or done or m >= flat_time(T) or fomc:
                    close_trade(sym, T, 'kill switch stop' if ctl == 'stop' else (f'main bot day ended: {done}' if done else 'closed before the 2:00 PM Fed decision' if fomc else
                                ('3:00 PM close (same-day option)' if T['und'] in INDEXES else '3:45 PM close (no overnight holds)')), now, T.get('now'))
            if m >= STK_FLAT: publish(eq, L_by); return
            if ctl != 'stop' and not done:
                manage(now, L_by); hunt(now, acct, L_by)
        except Exception as e:
            log(event='error', where='options', err=str(e)[:300])
        if time.time() - last_pub > 60:
            try: publish(eq, L_by)
            except Exception as e: log(event='error', where='publish', err=str(e)[:200])
            last_pub = time.time()
        time.sleep(15)

if __name__ == '__main__':
    loop(float(sys.argv[1]) if len(sys.argv) > 1 else 330)
