"""
VANTEX City: social-media buzz COLLECTOR. Research data only: places NO orders, changes no trading rules.

Why: there is no free history of Reddit / StockTwits buzz, so the only honest way to test "trade what social media is
excited about" is to start recording it now and test it on the weeks that follow. Every run saves one snapshot:
  - ApeWisdom (free, no key): Reddit mention counts per ticker, rank, mentions 24h ago (all stock subreddits)
  - StockTwits trending symbols (public endpoint; skipped quietly if it refuses)
Snapshots go to branch 'live-social' as social/<day>.jsonl (one JSON line per snapshot).

  python city_social.py        -> one snapshot
"""
import json, os, time
from datetime import datetime

import requests

from city_replay import ET, OUT, log, publish

BRANCH = 'live-social'
UA = {'User-Agent': 'Mozilla/5.0 (compatible; vantex-city-research/1.0)'}

def apewisdom(pages=3, http=requests):
    rows = []
    for p in range(1, pages + 1):
        try:
            r = http.get(f'https://apewisdom.io/api/v1.0/filter/all-stocks/page/{p}', headers=UA, timeout=30)
            if not r.ok: break
            j = r.json(); rows += [compact_ape(x) for x in j.get('results') or []]
            if p >= int(j.get('pages') or 1): break
        except Exception as e:
            log('apewisdom error', type(e).__name__); break
    return rows

def compact_ape(x):
    def num(k):
        try: return int(float(x.get(k)))
        except Exception: return None
    return dict(sym=x.get('ticker'), rank=num('rank'), rank_24h=num('rank_24h_ago'), mentions=num('mentions'), mentions_24h=num('mentions_24h_ago'), upvotes=num('upvotes'))

def stocktwits(http=requests):
    try:
        r = http.get('https://api.stocktwits.com/api/2/trending/symbols.json', headers=UA, timeout=30)
        if not r.ok: return None, f'http {r.status_code}'
        return [dict(sym=s.get('symbol'), title=(s.get('title') or '')[:60], watchers=s.get('watchlist_count')) for s in r.json().get('symbols') or []], 'ok'
    except Exception as e:
        return None, type(e).__name__

def main():
    t = datetime.now(ET); day = t.date().isoformat()
    ape = apewisdom(); st, st_status = stocktwits()
    snap = dict(t=t.isoformat(timespec='minutes'), apewisdom=ape, stocktwits=st, stocktwits_status=st_status)
    publish({}, branch=BRANCH)
    path = f'{OUT}/social/{day}.jsonl'; os.makedirs(os.path.dirname(path), exist_ok=True)
    old = open(path).read() if os.path.exists(path) else ''
    publish({f'social/{day}.jsonl': old + json.dumps(snap) + '\n',
             'social/latest.json': dict(t=snap['t'], apewisdom_rows=len(ape), top10=[x['sym'] for x in ape[:10]], stocktwits_status=st_status,
                                        stocktwits_top10=[x['sym'] for x in (st or [])[:10]])}, branch=BRANCH)
    log('saved', len(ape), 'reddit rows; stocktwits', st_status)

if __name__ == '__main__':
    main()
