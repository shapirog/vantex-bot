"""
Vantex Early Bird - tiny-float mover ALERTS from 3:00 to 9:30 AM ET. Read-only: places NO orders (paper keys only).

Each weekday:
  ~2:40 AM  builds today's watch list: active NASDAQ/NYSE/AMEX common stocks, last close $0.50-$20,
            shares outstanding <= 10M (latest SEC filing; split-adjusted), with 20-day average volume.
  3:00-9:30 every ~10 min:
            before 4:00 AM  -> Alpaca 'overnight' feed (Blue Ocean ATS, 8 PM-4 AM session; trades 15 min delayed on free plan)
            from 4:00 AM    -> 'delayed_sip' snapshots (15 min delayed on the free plan), falling back to live IEX
            ALERT when a watch-list stock is >= +10% vs yesterday's close, has traded in the last 60 min, and has
            >= $10K (overnight) / $25K (premarket) traded today. Re-alerts only if it climbs another 15 points.
            Push to your phone (NTFY_TOPIC) with % change, price, volume, shares outstanding and the latest headline.
Every alert is logged to the 'live-earlybird' branch (alerts.jsonl) so we can later test which alerts actually ran.
This is a WATCH tool. It is not a tested strategy and it does not trade.
"""
import json, os, re, subprocess, sys, time
from datetime import date, datetime, timedelta, timezone

import requests

KEY = os.environ.get('APCA_API_KEY_ID') or ''
if not KEY.startswith('PK'): sys.exit('Refusing to run: APCA_API_KEY_ID must be a PAPER key (starts with PK).')
sys.argv = [sys.argv[0], '300']
import lab5 as L5
import lab6 as L6

ET = L5.ET; DATA = L5.DATA; get, log = L5.get, L5.log
OUT = os.environ.get('VANTEX_EB_DIR', '/tmp/vantex-earlybird')
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
TOK = os.environ.get('GH_TOKEN'); NTFY = os.environ.get('NTFY_TOPIC')
BRANCH = 'live-earlybird'
PMIN, PMAX, SH_MAX = 0.50, 20.0, 10_000_000
UP, REALERT, FRESH_MIN = 10.0, 15.0, 60
MIN_DV = {'overnight': 10_000, 'premarket': 25_000}
START, END = 3 * 60 - 5, 9 * 60 + 35

def sh(*a, check=True): return subprocess.run(list(a), check=check, capture_output=True, text=True)

def checkout():
    """OUT = a working copy of the live-earlybird branch (created on first run)"""
    if os.path.isdir(f'{OUT}/.git'): return
    os.makedirs(OUT, exist_ok=True)
    url = f'https://x-access-token:{TOK}@github.com/{REPO}.git' if TOK else f'https://github.com/{REPO}.git'
    if sh('git', 'clone', '-q', '--depth', '1', '-b', BRANCH, url, OUT, check=False).returncode != 0:
        sh('git', 'init', '-q', '-b', BRANCH, OUT)

def save(msg):
    if not TOK: return
    g = ['git', '-C', OUT, '-c', 'user.name=vantex-bot', '-c', 'user.email=vantex-bot@users.noreply.github.com']
    sh(*g, 'add', '-A'); sh(*g, 'commit', '-q', '-m', msg, check=False)
    sh(*g, 'push', '-q', f'https://x-access-token:{TOK}@github.com/{REPO}.git', f'HEAD:{BRANCH}')

def rd(name, default):
    try: return json.load(open(f'{OUT}/{name}'))
    except Exception: return default

def build_universe(today):
    t0 = time.time()
    U, dropped = L5.universe()
    syms = sorted(s for s, a in U.items() if a.get('status') == 'active')
    D = L5.daily_multi(syms, datetime.combine(today - timedelta(days=45), datetime.min.time(), ET), datetime.combine(today, datetime.min.time(), ET), 'raw')
    band = {s: A for s, A in D.items() if len(A) >= 5 and PMIN <= A[-1, 4] <= PMAX}
    log('in price band', len(band))
    SH = L6.sec_shares(sorted(band))
    SP, ok = L6.splits(sorted(band), today - timedelta(days=400), today)
    W = {}
    for s, A in band.items():
        v, why = L6.shares_on(s, today.isoformat(), SH, SP)
        if v is None or v > SH_MAX: continue
        W[s] = dict(prev_close=float(A[-1, 4]), prev_day=date.fromordinal(int(A[-1, 0])).isoformat(), avg_vol20=float(A[-20:, 5].mean()),
                    shares_out=v, name=U[s].get('name', ''))
    json.dump(dict(day=today.isoformat(), built=datetime.now(ET).isoformat(timespec='seconds'), count=len(W), splits_ok=ok, stocks=W),
              open(f'{OUT}/universe.json', 'w'), indent=0)
    log('watch list', len(W), 'tiny-float stocks', round(time.time() - t0), 's')
    return W

def snapshots(syms, feed):
    out = {}
    for i in range(0, len(syms), 400):
        r = get(f'{DATA}/v2/stocks/snapshots', dict(symbols=','.join(syms[i:i + 400]), feed=feed))
        if r is None or not r.ok: log('snapshots', feed, getattr(r, 'status_code', None), (r.text[:150] if r is not None else '')); return None
        d = r.json() or {}
        if isinstance(d.get('snapshots'), dict): d = d['snapshots']
        out.update({k: v for k, v in d.items() if isinstance(v, dict)})
    return out

def ts(t):
    if not t: return None
    try: return datetime.fromisoformat(re.sub(r'(\.\d{6})\d+', r'\1', t.replace('Z', '+00:00')))
    except Exception: return None

def volumes(syms, start, feed):
    """shares traded since `start` from 1-minute bars (boats = overnight venue, sip = 16 min delayed, iex = live)"""
    end = datetime.now(timezone.utc) - (timedelta(minutes=16) if feed in ('sip', 'boats') else timedelta(0))
    V, tok = {s: 0.0 for s in syms}, None
    for _ in range(20):
        p = dict(symbols=','.join(syms), timeframe='1Min', start=start.astimezone(timezone.utc).isoformat(), end=end.isoformat(), limit=10000, feed=feed)
        if tok: p['page_token'] = tok
        r = get(f'{DATA}/v2/stocks/bars', p)
        if r is None or not r.ok: log('bars', feed, getattr(r, 'status_code', None)); break
        j = r.json()
        for s, bars in (j.get('bars') or {}).items(): V[s] = V.get(s, 0.0) + sum(float(b.get('v') or 0) for b in bars)
        tok = j.get('next_page_token')
        if not tok: break
    return V

def headline(syms):
    r = get(f'{DATA}/v1beta1/news', dict(symbols=','.join(syms), start=(datetime.now(timezone.utc) - timedelta(hours=18)).isoformat(),
                                         limit=50, sort='desc', include_content='false'))
    H = {}
    for n in (r.json().get('news') or []) if r is not None and r.ok else []:
        for s in n.get('symbols') or []:
            if s in syms and s not in H: H[s] = n.get('headline', '')[:110]
    return H

def push(title, body):
    if not NTFY: log('no NTFY_TOPIC; would send:', title, body); return
    try: requests.post(f'https://ntfy.sh/{NTFY}', data=body.encode('utf-8'), headers={'Title': title, 'Tags': 'bird,chart_with_upwards_trend', 'Priority': '4'}, timeout=15)
    except Exception as e: log('ntfy failed', e)

def fmt(n):
    return f'{n / 1e6:.1f}M' if n >= 1e6 else f'{n / 1e3:.0f}K' if n >= 1e3 else str(int(n))

def main():
    now = datetime.now(ET); today = now.date(); m = now.hour * 60 + now.minute
    checkout()
    U = rd('universe.json', {})
    W = U.get('stocks') if U.get('day') == today.isoformat() else None
    if W is None:
        W = build_universe(today); save(f'watch list {today}')
    force = os.environ.get('EB_FORCE') == '1'                          # manual test run: scan now, whatever the time
    if not force and (not (START <= m <= END) or today.weekday() >= 5): log('outside 3:00-9:30 AM ET; watch list ready'); return
    session = 'overnight' if (m < 240 or m >= 20 * 60) else 'premarket'
    feeds = ['overnight'] if session == 'overnight' else ['delayed_sip', 'iex']
    S, used = None, None
    for f in feeds:
        S = snapshots(sorted(W), f)
        if S: used = f; break
    if not S: log('no snapshot data from', feeds); return
    st = rd('state.json', {})
    if st.get('day') != today.isoformat(): st = dict(day=today.isoformat(), alerted={})
    cands = []
    for s, sn in S.items():
        w = W.get(s)
        if not w: continue
        lt, q = sn.get('latestTrade') or {}, sn.get('latestQuote') or {}
        px = lt.get('p'); t = ts(lt.get('t'))
        if not px or not t or (datetime.now(timezone.utc) - t).total_seconds() > (FRESH_MIN + (15 if used != 'iex' else 0)) * 60: continue
        chg = (px / w['prev_close'] - 1) * 100
        if chg < UP: continue
        last = st['alerted'].get(s)
        if last is not None and chg < last + REALERT: continue
        cands.append(dict(sym=s, chg=round(chg, 1), px=px, shares_out=w['shares_out'], avg_vol20=w['avg_vol20'],
                          bid=q.get('bp'), ask=q.get('ap'), trade_time=t.astimezone(ET).strftime('%H:%M'), feed=used, session=session))
    hits = []
    if cands:
        if session == 'overnight':
            vfeed, vstart = 'boats', datetime.combine(today - timedelta(days=1), datetime.min.time(), ET) + timedelta(hours=20)
        else:
            vfeed, vstart = ('iex' if used == 'iex' else 'sip'), datetime.combine(today, datetime.min.time(), ET) + timedelta(hours=4)
        V = volumes([c['sym'] for c in cands], vstart, vfeed)
        for c in cands:
            c['vol'] = V.get(c['sym'], 0.0); c['dv'] = round(c['px'] * c['vol']); c['volume_feed'] = vfeed
            if c['dv'] >= MIN_DV[session]: hits.append(c)
    hits.sort(key=lambda h: -h['chg'])
    if hits:
        H = headline([h['sym'] for h in hits[:10]])
        lines = []
        for h in hits[:8]:
            sp = f" spread {((h['ask'] - h['bid']) / ((h['ask'] + h['bid']) / 2) * 100):.1f}%" if h['bid'] and h['ask'] and h['ask'] > h['bid'] else ''
            lines.append(f"{h['sym']} +{h['chg']}% ${h['px']} | vol {fmt(h['vol'])} (${fmt(h['dv'])}) | {fmt(h['shares_out'])} sh out{sp}"
                         + (f"\n  {H[h['sym']]}" if h['sym'] in H else '\n  no news found'))
        delay = '' if used == 'iex' else ' (prices ~15 min delayed)'
        push(f"Early Bird {now.strftime('%-I:%M %p')} {session}: {len(hits)} tiny-float mover{'s' if len(hits) > 1 else ''}",
             '\n'.join(lines) + f"\n{delay.strip()}\nWatch only - not a tested buy signal.")
        for h in hits:
            st['alerted'][h['sym']] = h['chg']; h['news'] = H.get(h['sym']); h['at'] = now.isoformat(timespec='seconds')
        with open(f'{OUT}/alerts.jsonl', 'a') as f:
            for h in hits: f.write(json.dumps(h) + '\n')
    json.dump(st, open(f'{OUT}/state.json', 'w'))
    log(session, used, 'snapshots', len(S), 'alerts', [h['sym'] for h in hits])
    if hits or not os.path.exists(f'{OUT}/.saved-{today}'):
        open(f'{OUT}/.saved-{today}', 'w').close(); save(f'early bird {now:%H:%M}')

if __name__ == '__main__':
    main()
