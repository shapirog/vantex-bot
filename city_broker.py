"""
VANTEX City paper broker. The ONLY module that can send orders, and it can only reach Alpaca's PAPER endpoint.
There is no live endpoint, no live mode and no setting that changes the host. Before any order it re-checks:
  1. the API key is a paper key (starts with PK)
  2. the account the key opens is a paper account (number starts with PA) and, if VANTEX_PAPER_ACCOUNT is set, is that one
  3. the account is ACTIVE and not blocked from trading
Every City order carries a client_order_id starting with 'city-', so its P&L is kept apart from the other Vantex bots.
"""
import os, time, uuid

import requests

PAPER_HOST = 'https://paper-api.alpaca.markets'          # constant on purpose: never read from config or environment
ORDER_PREFIX = 'city-'

class NotPaper(Exception):
    pass

class PaperBroker:
    def __init__(self, key=None, secret=None, expected_account=None, session=None):
        self.key = key if key is not None else os.environ.get('APCA_API_KEY_ID', '')
        self.secret = secret if secret is not None else os.environ.get('APCA_API_SECRET_KEY', '')
        self.expected = expected_account if expected_account is not None else os.environ.get('VANTEX_PAPER_ACCOUNT') or None
        self.http = session or requests.Session()
        self.verified_at = 0.0
        self.account = None
        if not self.key.startswith('PK'): raise NotPaper('APCA_API_KEY_ID is not a paper key (paper keys start with PK)')

    @property
    def host(self): return PAPER_HOST

    def _req(self, method, path, **kw):
        url = PAPER_HOST + path
        assert url.startswith('https://paper-api.alpaca.markets/'), 'paper host only'
        r = None
        for i in range(4):
            r = self.http.request(method, url, headers={'APCA-API-KEY-ID': self.key, 'APCA-API-SECRET-KEY': self.secret}, timeout=20, **kw)
            if r.status_code == 429 or r.status_code >= 500: time.sleep(1 + 2 * i); continue
            return r
        return r

    def verify(self, max_age_s=300):
        """Confirms this is the paper account. Raises NotPaper otherwise. Cached for max_age_s."""
        if self.account and time.time() - self.verified_at < max_age_s: return self.account
        r = self._req('GET', '/v2/account')
        if r is None or not r.ok: raise NotPaper(f'could not read the paper account ({getattr(r, "status_code", "no response")})')
        a = r.json(); num = str(a.get('account_number', ''))
        if not num.startswith('PA'): raise NotPaper('account number is not a paper account (PA...)')
        if self.expected and num != self.expected: raise NotPaper('paper account does not match VANTEX_PAPER_ACCOUNT')
        if a.get('status') != 'ACTIVE' or a.get('trading_blocked') or a.get('account_blocked'): raise NotPaper('paper account is not active for trading')
        self.account = a; self.verified_at = time.time()
        return a

    def clock(self): return self._req('GET', '/v2/clock').json()
    def positions(self): return self._req('GET', '/v2/positions').json()
    def orders(self, status='all', after=None, limit=500):
        p = dict(status=status, limit=limit, direction='desc', nested='true')
        if after: p['after'] = after
        return self._req('GET', '/v2/orders', params=p).json()
    def asset(self, sym): return self._req('GET', f'/v2/assets/{sym}').json()

    def submit_bracket(self, sym, qty, side, limit, stop, target, tag='entry'):
        """Limit entry with attached stop-loss and take-profit (Alpaca bracket order). Re-verifies the paper account first.
        A stop is a request, not a guarantee: in a halt or a gap it fills at the next available price."""
        self.verify(max_age_s=0)
        if qty < 1: raise ValueError('qty must be >= 1')
        if side not in ('buy', 'sell'): raise ValueError('side')
        body = dict(symbol=sym, qty=str(int(qty)), side=side, type='limit', time_in_force='day', limit_price=f'{limit:.4f}' if limit < 1 else f'{limit:.2f}',
                    order_class='bracket', take_profit=dict(limit_price=f'{target:.2f}' if target >= 1 else f'{target:.4f}'),
                    stop_loss=dict(stop_price=f'{stop:.2f}' if stop >= 1 else f'{stop:.4f}'),
                    client_order_id=f'{ORDER_PREFIX}{tag}-{sym}-{uuid.uuid4().hex[:10]}')
        r = self._req('POST', '/v2/orders', json=body)
        return r.ok, (r.json() if r.content else {}), body

    def cancel(self, order_id):
        r = self._req('DELETE', f'/v2/orders/{order_id}')
        return r.status_code in (200, 204, 404, 422)

    def submit_exit(self, sym, qty, side, tag='exit'):
        """Closes only the City's own shares (the other Vantex bots may hold the same stock), with a market order so a
        time-stop or a lockout exit is never skipped. Slippage is logged from the fill."""
        self.verify(max_age_s=0)
        body = dict(symbol=sym, qty=str(int(qty)), side=side, type='market', time_in_force='day',
                    client_order_id=f'{ORDER_PREFIX}{tag}-{sym}-{uuid.uuid4().hex[:10]}')
        r = self._req('POST', '/v2/orders', json=body)
        return r.ok, (r.json() if r.content else {}), body
