"""Vantex market scanner: every US stock + market news, pre-market to after-hours. Read-only: places no trades.

Publishes to the 'live-scan' branch for the Vantex City page:
  market.json  price, % change, volume, relative volume for every stock
  assets.json  symbol + company name list for the search box
  news.json    market news from the last 36 hours, tagged by symbol
  radar.json   Vantex Radar: penny / small stocks with a news catalyst, unusual volume and momentum
"""
import os, sys, json, math, re, time, subprocess, requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
KEY, SECRET = os.environ.get('APCA_API_KEY_ID') or '', os.environ.get('APCA_API_SECRET_KEY') or ''
if not KEY.startswith('PK'): sys.exit('Refusing to run: APCA_API_KEY_ID must be a PAPER key (starts with PK).')
H = {'APCA-API-KEY-ID': KEY, 'APCA-API-SECRET-KEY': SECRET}
TRADE, DATA = 'https://paper-api.alpaca.markets', 'https://data.alpaca.markets'
OUT = os.environ.get('VANTEX_SCAN_DIR', '/tmp/vantex-scan')
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
NTFY = os.environ.get('NTFY_TOPIC')
MAX_PRICE = 10.0          # radar looks at stocks under $10 (under $5 tagged PENNY)
MIN_PRICE = 0.05
MIN_DOLLAR_VOL = 50_000   # skip names too thin to trade
MAX_QUOTE_AGE_H = 4       # radar ignores prices older than this (no trades = no real move)
BOT_SILENT_MIN = 12       # warn if the trading bot hasn't reported for this long during market hours
CHART_SYMS = ['QQQ', 'AAPL', 'NVDA', 'AMZN', 'GOOGL', 'TSLA', 'MSFT']   # the bot's stocks get full chart history
CHART_COINS = {'BTC': 'BTC/USD', 'ETH': 'ETH/USD'}

GOOD = [('FDA', r'\bfda\b|approv|clearance|breakthrough designation|orphan drug'), ('TRIAL', r'phase [123i]|trial|topline|data readout'),
        ('DEAL', r'merger|acquisi|acquire|buyout|takeover|definitive agreement'), ('CONTRACT', r'contract|award|order|purchase order|government'),
        ('PARTNER', r'partner|collaborat|alliance|joint venture|licens'), ('EARNINGS', r'earnings|revenue|results|guidance|profit|record quarter'),
        ('AI', r'\bai\b|artificial intelligence|quantum|nvidia'), ('CRYPTO', r'bitcoin|crypto|blockchain|treasury'), ('UPLIST', r'uplist|nasdaq listing|regains compliance')]
ROUNDUP = r'stocks moving|movers|top gainers|top losers|biggest movers|stocks to watch|stocks trading|mid-day|midday update|market update|session\b'
BAD = [('OFFERING', r'offering|dilut|registered direct|at-the-market|warrant'), ('SPLIT', r'reverse (stock )?split'),
       ('DELIST', r'delist|non-compliance|deficiency'), ('BANKRUPT', r'bankrupt|chapter 11|going concern')]

def req(method, url, **kw):
    r = None
    for i in range(6):
        r = requests.request(method, url, headers=H, timeout=30, **kw)
        if r.status_code == 429 or r.status_code >= 500: time.sleep(2 + 2 * i); continue
        return r
    return r

def now(): return datetime.now(ET)

def epoch(t):
    """Alpaca timestamps carry nanoseconds; trim to microseconds before parsing."""
    if not t: return None
    try: return int(datetime.fromisoformat(re.sub(r'(\.\d{6})\d+', r'\1', t.replace('Z', '+00:00'))).timestamp())
    except Exception: return None

def assets():
    r = req('GET', f'{TRADE}/v2/assets', params=dict(status='active', asset_class='us_equity'))
    ok = ('NYSE', 'NASDAQ', 'ARCA', 'AMEX', 'BATS')
    return sorted((a['symbol'], (a.get('name') or '')[:48]) for a in r.json()
                  if a.get('tradable') and a.get('exchange') in ok and a['symbol'].isalpha())

def snapshots(syms):
    """Full-market (15-min delayed SIP) when the plan allows it, otherwise the live IEX feed."""
    for feed in ('delayed_sip', 'iex'):
        rows, okc = [], 0
        for i in range(0, len(syms), 400):
            r = req('GET', f'{DATA}/v2/stocks/snapshots', params=dict(symbols=','.join(syms[i:i + 400]), feed=feed))
            if not r.ok:
                if i == 0: break
                continue
            okc += 1; d = r.json() or {}
            if isinstance(d.get('snapshots'), dict): d = d['snapshots']
            today = now().date()
            for sym, sn in d.items():
                if not isinstance(sn, dict): continue
                db, pb, lt = sn.get('dailyBar') or {}, sn.get('prevDailyBar') or {}, sn.get('latestTrade') or {}
                px = lt.get('p') or db.get('c')
                if not px: continue
                bar_day = datetime.fromisoformat(db['t'].replace('Z', '+00:00')).astimezone(ET).date() if db.get('t') else None
                if bar_day == today: ref, v, pv = pb.get('c'), int(db.get('v') or 0), int(pb.get('v') or 0)
                else: ref, v, pv = db.get('c'), 0, int(db.get('v') or 0)      # before today's open: compare with yesterday's close
                if not ref: continue
                qt = lt.get('t') or db.get('t')
                qts = epoch(qt)
                rows.append([sym, round(px, 4 if px < 1 else 2), round((px / ref - 1) * 100, 2), v, round(v / pv, 2) if pv and v else None, qts])
        if okc: return rows, feed
    return [], 'none'

def news(hours=36, pages=18):
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    items, tok = [], None
    for _ in range(pages):
        p = dict(start=start, limit=50, sort='desc', include_content='false', exclude_contentless='true')
        if tok: p['page_token'] = tok
        r = req('GET', f'{DATA}/v1beta1/news', params=p)
        if not r.ok: break
        d = r.json()
        for n in d.get('news') or []:
            if not n.get('symbols'): continue
            sy = [x for x in n['symbols'] if x.isalpha()]
            h = n.get('headline', '')[:220]
            items.append(dict(t=n['created_at'], h=h, s=n.get('source', ''), u=n.get('url', ''), sy=sy[:8], sm=(n.get('summary') or '')[:240],
                              ru=len(sy) > 4 or bool(re.search(ROUNDUP, h.lower()))))   # round-up lists of movers are not catalysts
        tok = d.get('next_page_token')
        if not tok: break
    return items

def stock_bars(syms, tf, start):
    """Bars for several stocks: full-market SIP (ends 16 min ago, free plan rule), else live IEX."""
    for feed, end in (('sip', datetime.now(timezone.utc) - timedelta(minutes=16)), ('iex', datetime.now(timezone.utc))):
        out, tok, ok = {}, None, False
        while True:
            p = dict(symbols=','.join(syms), timeframe=tf, start=start.isoformat(), end=end.isoformat(), limit=10000, adjustment='split', feed=feed)
            if tok: p['page_token'] = tok
            r = req('GET', f'{DATA}/v2/stocks/bars', params=p)
            if not r.ok: break
            ok = True; d = r.json()
            for k, v in (d.get('bars') or {}).items(): out.setdefault(k, []).extend(v)
            tok = d.get('next_page_token')
            if not tok: break
        if ok: return out
    return {}

def crypto_bars(tf, start):
    out, tok = {}, None
    while True:
        p = dict(symbols=','.join(CHART_COINS.values()), timeframe=tf, start=start.isoformat(), limit=10000)
        if tok: p['page_token'] = tok
        r = req('GET', f'{DATA}/v1beta3/crypto/us/bars', params=p)
        if not r.ok: break
        d = r.json()
        for k, v in (d.get('bars') or {}).items(): out.setdefault(k, []).extend(v)
        tok = d.get('next_page_token')
        if not tok: break
    return out

def charts():
    """Price history for the bot's stocks and coins: 1D (5-min), 5D (15-min), 3M (daily). Times are unix seconds."""
    utc = datetime.now(timezone.utc); out = {}
    def pts(bars, regular=True):
        L = []
        for b in bars:
            t = epoch(b['t'])
            if t is None: continue
            if regular:
                et = datetime.fromtimestamp(t, ET); m = et.hour * 60 + et.minute
                if not (570 <= m < 960): continue                      # regular session only
            L.append([t, round(float(b['c']), 4 if b['c'] < 1 else 2)])
        return L
    def by_day(L):
        days = {}
        for t, v in L: days.setdefault(datetime.fromtimestamp(t, ET).date(), []).append([t, v])
        return [days[d] for d in sorted(days)]
    m5 = stock_bars(CHART_SYMS, '5Min', utc - timedelta(days=5))
    m15 = stock_bars(CHART_SYMS, '15Min', utc - timedelta(days=10))
    d1 = stock_bars(CHART_SYMS, '1Day', utc - timedelta(days=100))
    for s in CHART_SYMS:
        D1 = by_day(pts(m5.get(s, [])))
        D5 = by_day(pts(m15.get(s, [])))
        out[s] = {'1D': D1[-1] if D1 else [], '5D': [p for d in D5[-5:] for p in d], '3M': pts(d1.get(s, []), regular=False)[-66:]}
    c15 = crypto_bars('15Min', utc - timedelta(hours=24)); c1h = crypto_bars('1Hour', utc - timedelta(days=5)); cd = crypto_bars('1Day', utc - timedelta(days=100))
    for k, pair in CHART_COINS.items():
        out[k] = {'1D': pts(c15.get(pair, []), False), '5D': pts(c1h.get(pair, []), False), '3M': pts(cd.get(pair, []), False)[-92:]}
    return out

def tags_for(text):
    t = text.lower()
    return [k for k, rx in GOOD if re.search(rx, t)], [k for k, rx in BAD if re.search(rx, t)]

def radar(rows, names, items):
    by = {}
    for n in items:
        for s in n['sy']: by.setdefault(s, []).append(n)
    t_now = datetime.now(timezone.utc); out = []
    for sym, p, chg, v, rv, qt in rows:
        if not (MIN_PRICE <= p <= MAX_PRICE): continue
        if qt is None or (t_now.timestamp() - qt) > MAX_QUOTE_AGE_H * 3600: continue   # stale price: skip
        if chg < -2: continue                                    # radar hunts for stocks going up
        if chg > 300 and (rv is None or rv < 1): continue        # a giant jump on no volume is a split, not a move
        nl = by.get(sym, [])
        recent = [n for n in nl if (t_now - datetime.fromisoformat(n['t'].replace('Z', '+00:00'))).total_seconds() < 24 * 3600]
        fresh = [n for n in recent if not n.get('ru')]           # real, company-specific news only
        age_h = min(((t_now - datetime.fromisoformat(n['t'].replace('Z', '+00:00'))).total_seconds() / 3600 for n in fresh), default=None)
        dollar = v * p
        cat = bool(fresh)
        if v and dollar < MIN_DOLLAR_VOL and not cat: continue
        qualifies = chg >= 10 or (rv and rv >= 4 and chg >= 3) or (cat and (chg >= 3 or (rv and rv >= 2)))
        if not qualifies: continue
        good, bad = tags_for(' '.join(n['h'] + ' ' + n['sm'] for n in fresh))
        score = min(chg, 150) / 10 + (math.log2(rv) * 1.5 if rv and rv > 1 else 0) + (3 if cat else 0) + 1.2 * min(len(good), 2) - 1.5 * len(bad)
        if dollar >= 1_000_000: score += 1
        tg = []
        if age_h is not None and age_h <= 3 and -2 <= chg < 25 and good and not bad: tg.append('EARLY'); score += 2
        if cat: tg += [f'NEWS {g}' for g in good[:2]] or ['NEWS']
        if rv and rv >= 3: tg.append('VOL 999x+' if rv >= 999 else f'VOL {rv:.0f}x')
        if chg >= 20: tg.append('RUNNER')
        if p < 5: tg.append('PENNY')
        tg += [f'RISK {b}' for b in bad[:1]]
        stage = 'early' if 'EARLY' in tg else 'running' if chg >= 20 else 'building'
        out.append(dict(sym=sym, name=names.get(sym, ''), p=p, chg=chg, v=v, rv=rv, qt=qt, stage=stage, score=round(score, 2), tags=tg,
                        news=[dict(t=n['t'], h=n['h'], s=n['s'], u=n['u']) for n in (fresh + [n for n in recent if n.get('ru')])[:3]]))
    out.sort(key=lambda x: -x['score'])
    return out[:40]

def previous_radar():
    try:
        r = requests.get(f'https://raw.githubusercontent.com/{REPO}/live-scan/radar.json?t={int(time.time())}', timeout=15)
        d = r.json() if r.ok else {}
        return d if d.get('day') == str(now().date()) else {}
    except Exception: return {}

def watchdog(prev):
    """During market hours, warn once a day if the trading bot has stopped reporting."""
    if prev.get('bot_warned'): return True
    try:
        if not req('GET', f'{TRADE}/v2/clock').json().get('is_open'): return False
        t = now(); m = t.hour * 60 + t.minute
        if m < 575 or m > 950: return False                      # 9:35 AM to 3:50 PM ET
        r = requests.get(f'https://raw.githubusercontent.com/{REPO}/live/state.json?t={int(time.time())}', timeout=15)
        upd = datetime.fromisoformat(r.json()['updated']) if r.ok else None
        age = (t - upd).total_seconds() / 60 if upd else 9999
        if age > BOT_SILENT_MIN:
            notify('Vantex bot is not reporting', f"No update from the trading bot for {age:.0f} minutes. Check Actions > Vantex paper trading.", 'warning')
            return True
    except Exception as e: print('watchdog failed', str(e)[:160], flush=True)
    return False

def notify(title, msg, tags='rocket'):
    if not NTFY: return
    try: requests.post(f'https://ntfy.sh/{NTFY}', data=msg.encode('utf-8'), headers={'Title': title, 'Tags': tags}, timeout=10)
    except Exception as e: print('notify failed', str(e)[:120], flush=True)

def push():
    tok = os.environ.get('GH_TOKEN')
    if not (tok and os.environ.get('GITHUB_REPOSITORY')): return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    subprocess.run(['rm', '-rf', f'{OUT}/.git'], check=True)
    subprocess.run(['git', 'init', '-q', '-b', 'live-scan', OUT], check=True)
    subprocess.run(g + ['add', '-A'], check=True)
    subprocess.run(g + ['commit', '-q', '-m', 'market scan'], check=True)
    subprocess.run(g + ['push', '-q', '-f', f'https://x-access-token:{tok}@github.com/{REPO}.git', 'live-scan'], check=True, timeout=90, capture_output=True)

def session(t):
    m = t.hour * 60 + t.minute
    return 'pre-market' if m < 570 else 'regular' if m < 960 else 'after-hours'

def main():
    t0 = now(); os.makedirs(OUT, exist_ok=True)
    A = assets(); names = dict(A)
    rows, feed = snapshots([s for s, _ in A])
    items = news()
    rad = radar(rows, names, items)
    stamp = t0.isoformat(timespec='seconds')
    prev = previous_radar(); alerted = set(prev.get('alerted') or []); new_alerts = []
    bot_warned = watchdog(prev)
    for x in [y for y in rad if y['stage'] != 'running'][:5]:       # alert on early and building setups, not stocks already up 20%+
        good_news = any(t.startswith('NEWS ') for t in x['tags']) and not any(t.startswith('RISK') for t in x['tags'])
        if x['sym'] not in alerted and good_news and len(new_alerts) < 3:
            new_alerts.append(x['sym']); alerted.add(x['sym'])
            notify(f"Vantex Radar: {x['sym']} {x['chg']:+.1f}%", f"${x['p']} · {', '.join(x['tags'][:3])}\n{x['news'][0]['h'] if x['news'] else ''}")
    def dump(name, obj): json.dump(obj, open(f'{OUT}/{name}', 'w'), separators=(',', ':'))
    dump('assets.json', dict(updated=stamp, assets=[list(a) for a in A]))
    dump('market.json', dict(updated=stamp, feed=feed, session=session(t0), rows=rows))
    dump('news.json', dict(updated=stamp, items=items[:900]))
    try: dump('charts.json', dict(updated=stamp, syms=charts()))
    except Exception as e: print('charts failed', str(e)[:200], flush=True)   # charts are extra: never stop the scan
    dump('radar.json', dict(updated=stamp, day=str(t0.date()), session=session(t0), feed=feed, alerted=sorted(alerted), bot_warned=bot_warned, stocks=rad))
    print(json.dumps(dict(event='scan', stocks=len(rows), feed=feed, news=len(items), radar=len(rad), top=[x['sym'] for x in rad[:8]], alerts=new_alerts)), flush=True)
    push()

if __name__ == '__main__':
    main()
