import city_social as C

class R:
    def __init__(self, j, ok=True, code=200): self._j = j; self.ok = ok; self.status_code = code
    def json(self): return self._j

class H:
    def __init__(self, pages): self.pages = pages; self.calls = []
    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        if 'stocktwits' in url: return R({}, ok=False, code=403)
        p = int(url.rstrip('/').split('/')[-1]); return R(dict(pages=len(self.pages), results=self.pages[p - 1]))

def test_apewisdom_pages_and_compact():
    h = H([[dict(ticker='GME', rank='1', rank_24h_ago='3', mentions='120', mentions_24h_ago='40', upvotes='900')], [dict(ticker='AMC', rank=2, mentions=None)]])
    rows = C.apewisdom(pages=5, http=h)
    assert [r['sym'] for r in rows] == ['GME', 'AMC'] and len(h.calls) == 2
    assert rows[0]['mentions'] == 120 and rows[0]['rank_24h'] == 3 and rows[1]['mentions'] is None

def test_stocktwits_refused_is_quiet():
    st, status = C.stocktwits(http=H([]))
    assert st is None and status == 'http 403'
