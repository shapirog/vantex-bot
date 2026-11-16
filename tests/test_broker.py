"""Paper-only routing tests: the City broker can only ever reach Alpaca's paper host, and refuses non-paper keys/accounts."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
import city_broker as CB

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Resp:
    def __init__(self, code, j): self.status_code, self._j, self.content = code, j, b'x'
    @property
    def ok(self): return 200 <= self.status_code < 300
    def json(self): return self._j

class Sess:
    def __init__(self, account): self.account, self.calls = account, []
    def request(self, method, url, **kw):
        self.calls.append((method, url, kw.get('json')))
        if url.endswith('/v2/account'): return Resp(200, self.account)
        if url.endswith('/v2/orders') and method == 'POST': return Resp(200, dict(id='o1', status='accepted'))
        return Resp(200, {})

ACCT = dict(account_number='PA33TEST', status='ACTIVE', trading_blocked=False, account_blocked=False, equity='2500')

def test_refuses_live_key():
    with pytest.raises(CB.NotPaper): CB.PaperBroker(key='AK123', secret='x', session=Sess(ACCT))

def test_refuses_non_paper_account():
    b = CB.PaperBroker(key='PK1', secret='x', session=Sess(dict(ACCT, account_number='123456789')))
    with pytest.raises(CB.NotPaper): b.verify()
    with pytest.raises(CB.NotPaper): b.submit_bracket('ACME', 1, 'buy', 10, 9.8, 10.4)

def test_refuses_wrong_paper_account():
    b = CB.PaperBroker(key='PK1', secret='x', expected_account='PA99OTHER', session=Sess(ACCT))
    with pytest.raises(CB.NotPaper): b.verify()

def test_refuses_blocked_account():
    b = CB.PaperBroker(key='PK1', secret='x', session=Sess(dict(ACCT, trading_blocked=True)))
    with pytest.raises(CB.NotPaper): b.verify()

def test_orders_go_to_paper_host_and_reverify():
    s = Sess(ACCT); b = CB.PaperBroker(key='PK1', secret='x', session=s)
    ok, o, body = b.submit_bracket('ACME', 5, 'buy', 10.01, 9.8, 10.42)
    assert ok and body['order_class'] == 'bracket' and body['type'] == 'limit' and body['client_order_id'].startswith('city-')
    ok, o, body = b.submit_exit('ACME', 5, 'sell')
    assert ok and body['client_order_id'].startswith('city-exit')
    assert all(u.startswith('https://paper-api.alpaca.markets/') for _, u, _ in s.calls)
    assert sum(1 for m, u, _ in s.calls if u.endswith('/v2/account')) == 2           # verified before each order

def test_host_is_constant():
    b = CB.PaperBroker(key='PK1', secret='x', session=Sess(ACCT))
    assert b.host == 'https://paper-api.alpaca.markets'

def test_no_live_endpoint_in_city_code():
    """No City file may contain Alpaca's live trading host or an order path outside the broker."""
    live = re.compile(r'https://api\.alpaca\.markets')
    for f in ('city_broker.py', 'city_engine.py', 'city_replay.py', 'vantex_core.py', 'hq.js'):
        p = os.path.join(ROOT, f)
        if not os.path.exists(p): continue
        src = open(p).read()
        assert not live.search(src), f
        if f != 'city_broker.py': assert "'/v2/orders'" not in src and '/v2/positions/' not in src, f
