"""Checks how far back Alpaca's news history goes. Read-only: places no orders. Result -> live-replay/news_probe.md"""
import os, sys
from datetime import date, datetime, timedelta
from city_engine import Data
from city_replay import publish, ET

key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
D = Data(key, sec)
days = [date(2025, 6, 2), date(2025, 9, 30), date(2025, 11, 3), date(2026, 1, 23), date(2026, 3, 30), date(2026, 4, 23),
        date(2026, 6, 1), date(2026, 8, 3), date(2026, 10, 1), date(2026, 11, 3), date(2026, 11, 13)]
rows = ['| day | ask | status | articles | sources | first headline |', '|---|---|---|---|---|---|']
for d in days:
    a = datetime.combine(d, datetime.min.time(), ET)
    for label, extra in (('whole market', {}), ('TSLA,AAPL,NVDA', dict(symbols='TSLA,AAPL,NVDA')), ('TLRY,QS,PATH', dict(symbols='TLRY,QS,PATH'))):
        p = dict(start=(a - timedelta(hours=20)).isoformat(), end=(a + timedelta(hours=20)).isoformat(), limit=50, sort='asc', include_content='false', **extra)
        r = D.get('/v1beta1/news', p, 'news')
        if r is None: rows.append(f'| {d} | {label} | no response | | | |'); continue
        n = r.json().get('news', []) if r.ok else []
        src = sorted({x.get('source') or '?' for x in n})
        msg = (n[0].get('headline') or '')[:80].replace('|', '/') if n else (r.text[:80].replace('|', '/') if not r.ok else '')
        rows.append(f"| {d} | {label} | {r.status_code} | {len(n)}{'+' if r.ok and r.json().get('next_page_token') else ''} | {', '.join(src)[:60]} | {msg} |")
md = '# Alpaca news history probe\n\n' + '\n'.join(rows) + '\n'
print(md)
publish({})
publish({'news_probe.md': md})
