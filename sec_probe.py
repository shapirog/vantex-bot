"""SEC EDGAR access check (read-only): is the contact header accepted, and how much filing data can we reach?"""
import os, re
from collections import Counter
import city_sec

def main():
    print('contact header set:', bool(os.environ.get('SEC_USER_AGENT')))
    S = city_sec.SEC()
    for sym in ('AAPL', 'NVDA', 'SOUN'):
        f = S.filings(sym)
        print(sym, 'filings:', len(f), 'latest:', [(x['form'], x['items']) for x in f[-3:]])
    for q in ('2025/QTR4', '2026/QTR3'):
        r = S._get(f'https://www.sec.gov/Archives/edgar/full-index/{q}/form.idx')
        if r is None: print(q, 'index: refused'); continue
        c = Counter(re.split(r'\s{2,}', ln.strip())[0] for ln in r.text.splitlines()[10:] if ln.strip())
        print(q, 'index rows:', sum(c.values()), {k: c[k] for k in ('SCHEDULE 13D', 'SC 13D', '4', '8-K', 'SCHEDULE 13G')})
    print('calls', S.calls, 'errors', S.errors)

if __name__ == '__main__':
    main()
