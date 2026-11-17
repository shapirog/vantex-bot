"""
VANTEX City SEC check: official company filings from SEC EDGAR (free, no key, years of history).
  - catalyst: an 8-K the company filed before this minute (deal, agreement, earnings, other announced events)
  - dilution: an offering / resale prospectus or unregistered share sale filed in the last 30 days
Read-only. Only filings accepted by the SEC BEFORE the decision minute are used (no look-ahead).
SEC asks automated users to identify themselves and stay under 10 requests a second.
"""
import os, time
from datetime import datetime
import requests

UA = os.environ.get('SEC_USER_AGENT', 'VantexCity research vantex-bot@users.noreply.github.com')
H = {'User-Agent': UA, 'Accept-Encoding': 'gzip, deflate'}
TICKERS = 'https://www.sec.gov/files/company_tickers.json'
SUBMISSIONS = 'https://data.sec.gov/submissions/CIK{:010d}.json'

# 8-K item numbers -> what they mean for a trader
ITEM_CATALYST = {'1.01': 'AGREEMENT', '2.01': 'DEAL', '2.02': 'EARNINGS', '7.01': 'ANNOUNCEMENT', '8.01': 'ANNOUNCEMENT'}
ITEM_NEGATIVE = {'3.01': 'COMPLIANCE', '3.02': 'DILUTION', '1.03': 'BANKRUPTCY', '4.02': 'RESTATEMENT'}
DILUTION_FORMS = ('424B1', '424B2', '424B3', '424B4', '424B5', '424B7', 'S-1', 'S-1/A', 'F-1', 'F-1/A', 'S-3', 'S-3/A', 'F-3', 'F-3/A')
DILUTION_DAYS = 30

def _epoch(s):
    try: return datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
    except Exception: return None

class SEC:
    def __init__(self, http=None):
        self.http = http or requests; self.cik = None; self.cache = {}; self.calls = 0; self.errors = 0; self._last = 0.0

    def _get(self, url):
        wait = 0.12 - (time.time() - self._last)                              # stay well under 10 requests a second
        if wait > 0: time.sleep(wait)
        self._last = time.time()
        for i in range(3):
            try:
                r = self.http.get(url, headers=H, timeout=30); self.calls += 1
                if r.status_code == 429 or r.status_code >= 500: time.sleep(2 + 2 * i); continue
                return r if r.ok else None
            except Exception: time.sleep(1 + i)
        self.errors += 1
        return None

    def filings(self, sym):
        """every recent filing for a stock: list of dict(form, items, t, desc, url), oldest first ([] if unknown)"""
        if sym in self.cache: return self.cache[sym]
        if self.cik is None:
            r = self._get(TICKERS)
            try: self.cik = {v['ticker'].upper(): int(v['cik_str']) for v in r.json().values()} if r is not None else {}
            except Exception: self.cik = {}
        out = []
        c = self.cik.get(sym.upper())
        if c:
            r = self._get(SUBMISSIONS.format(c))
            try:
                R = r.json()['filings']['recent'] if r is not None else {}
                n = len(R.get('form', []))
                for i in range(n):
                    t = _epoch(R['acceptanceDateTime'][i])
                    if t is None: continue
                    acc = R['accessionNumber'][i].replace('-', '')
                    out.append(dict(form=R['form'][i], items=[x.strip() for x in (R.get('items', [''] * n)[i] or '').split(',') if x.strip()], t=t,
                                    desc=(R.get('primaryDocDescription', [''] * n)[i] or '')[:80],
                                    url=f"https://www.sec.gov/Archives/edgar/data/{c}/{acc}/{R['primaryDocument'][i]}"))
            except Exception: self.errors += 1; out = []
        out.sort(key=lambda x: x['t'])
        self.cache[sym] = out
        return out

def check(filings, ts, since_ts):
    """What the SEC record says about a stock at time ts. Catalyst window: since_ts..ts. Dilution window: 30 days back."""
    seen = [f for f in filings if f['t'] < ts]
    cat_types, cat = [], None
    for f in seen:
        if f['t'] < since_ts or not f['form'].startswith('8-K'): continue
        ty = [ITEM_CATALYST[i] for i in f['items'] if i in ITEM_CATALYST]
        if ty: cat = f; cat_types = sorted(set(cat_types) | set(ty))
    neg = set()
    for f in seen:
        if f['t'] < ts - DILUTION_DAYS * 86400: continue
        if f['form'] in DILUTION_FORMS: neg.add('DILUTION' if not f['form'].startswith(('S-3', 'F-3')) else 'SHELF')
        if f['form'].startswith('8-K'): neg |= {ITEM_NEGATIVE[i] for i in f['items'] if i in ITEM_NEGATIVE}
    return dict(catalyst=bool(cat), types=cat_types, negative=sorted(neg), n=len([f for f in seen if f['t'] >= since_ts]),
                headline=(f"SEC {cat['form']} items {', '.join(cat['items'])}" + (f": {cat['desc']}" if cat['desc'] else '')) if cat else None,
                url=cat['url'] if cat else None)

def merge(cat, sec):
    """adds the SEC record to a news catalyst dict (from vantex_core.catalyst_for). A filed 8-K counts as a verified catalyst."""
    c = dict(cat)
    c['negative'] = sorted(set(c.get('negative') or []) | set(sec['negative']))
    c['sec'] = dict(catalyst=sec['catalyst'], types=sec['types'], negative=sec['negative'], headline=sec['headline'])
    if not c.get('verified') and sec['catalyst']:
        c.update(verified=True, types=['SEC_' + t for t in sec['types']], headline=sec['headline'], source='sec.gov', url=sec['url'])
    return c
