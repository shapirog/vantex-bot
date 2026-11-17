"""Tests for the SEC filings check: parsing EDGAR, catalysts vs dilution, and no look-ahead."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import city_sec as S

T = 1_800_000_000
DAY = 86400

class R:
    def __init__(self, code, j): self.status_code = code; self.ok = code == 200; self._j = j
    def json(self): return self._j

class Http:
    def __init__(self): self.urls = []
    def get(self, url, headers=None, timeout=None):
        self.urls.append(url); assert 'User-Agent' in headers
        if url == S.TICKERS: return R(200, {'0': dict(cik_str=123, ticker='ACME', title='Acme Inc')})
        if url == S.SUBMISSIONS.format(123):
            return R(200, dict(filings=dict(recent=dict(
                form=['8-K', '424B5', '8-K'], items=['1.01,9.01', '', '5.02'],
                acceptanceDateTime=['2027-01-15T12:00:00.000Z', '2027-01-10T12:00:00.000Z', '2027-01-15T13:00:00.000Z'],
                accessionNumber=['0001-26-000001', '0001-26-000002', '0001-26-000003'], primaryDocument=['a.htm', 'b.htm', 'c.htm'],
                primaryDocDescription=['8-K', '424B5', '8-K']))))
        return R(404, {})

def test_parses_edgar_and_caches():
    h = Http(); sec = S.SEC(http=h)
    F = sec.filings('ACME')
    assert [f['form'] for f in F] == ['424B5', '8-K', '8-K'] and F[1]['items'] == ['1.01', '9.01']
    assert 'edgar/data/123/' in F[1]['url']
    n = len(h.urls); sec.filings('ACME'); assert len(h.urls) == n          # cached
    assert sec.filings('ZZZZ') == []                                       # unknown ticker: nothing, not an error

def f(form, items, t): return dict(form=form, items=items, t=t, desc='', url='u')

def test_catalyst_only_from_filings_before_now():
    F = [f('8-K', ['1.01'], T + 100)]
    assert not S.check(F, T + 50, T - DAY)['catalyst']                     # filed after the decision minute: not seen
    c = S.check(F, T + 200, T - DAY)
    assert c['catalyst'] and c['types'] == ['AGREEMENT'] and c['headline'].startswith('SEC 8-K')

def test_officer_change_is_not_a_catalyst_and_old_8k_is_stale():
    assert not S.check([f('8-K', ['5.02'], T)], T + 10, T - DAY)['catalyst']
    assert not S.check([f('8-K', ['8.01'], T - 3 * DAY)], T + 10, T - DAY)['catalyst']

def test_dilution_flags():
    c = S.check([f('424B5', [], T - 5 * DAY), f('8-K', ['3.02'], T - DAY)], T, T - DAY)
    assert c['negative'] == ['DILUTION']
    assert S.check([f('S-3', [], T - 2 * DAY)], T, T - DAY)['negative'] == ['SHELF']
    assert S.check([f('424B5', [], T - 40 * DAY)], T, T - DAY)['negative'] == []   # older than 30 days

def test_merge_adds_sec_catalyst_and_keeps_news_negatives():
    news = dict(verified=False, types=[], negative=['OFFERING'], headline=None)
    m = S.merge(news, S.check([f('8-K', ['2.02'], T)], T + 10, T - DAY))
    assert m['verified'] and m['types'] == ['SEC_EARNINGS'] and m['negative'] == ['OFFERING']
    good = dict(verified=True, types=['CONTRACT'], negative=[], headline='Wins contract')
    assert S.merge(good, S.check([], T, T - DAY))['types'] == ['CONTRACT']  # real news stays first
