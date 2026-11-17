"""
VANTEX City free-data check: would the City still trade well on Alpaca's FREE plan? Research only: places NO orders.

On the free plan the City can see, in real time, only the IEX exchange (about 2-3% of all trading); the full-market
picture arrives about 16 minutes late. This replays past days the way a free-plan City would see them:
  - the market-wide scan (who is up big, who has volume) uses full-market data from 16 minutes earlier,
  - each stock's chart, volume, VWAP and setup come from IEX trades only, live,
  - a stock is skipped when IEX has printed nothing for 5 minutes (too quiet to read),
  - fills, stops and targets still play out against the real full market, with the same costs as every replay.
The same days are also run with full real-time data, so the table shows exactly what the free feed costs.

  python city_iexcheck.py 3      -> 3 sessions from the development period -> live-replay/iexcheck.md / .json
"""
import json, os, random, sys, time
from collections import Counter
from datetime import date, datetime, timedelta, timezone

import vantex_core as V
from city_engine import Data, to_bar, epoch
from city_replay import Replay, ET, DEV, log, publish, summarize, only_spread_pending, variant_configs, VARIANT_NOTES

DELAY_M = 16                                                      # free plan: full-market data ends ~16 minutes before now
QUIET_M = 5                                                       # IEX silent this long = too quiet to read
RULES = ('A_original', 'B_strong_news', 'C_strong_volume')

class IEXReplay(Replay):
    def load_iex(self, d, data):
        uni = data['uni']; a = datetime.combine(d, datetime.min.time(), ET)
        raw = self.D.bars(uni, '1Min', a + timedelta(hours=4), a + timedelta(minutes=960), 'iex')
        data['IBARS'] = {s: [to_bar(b) for b in L] for s, L in raw.items()}
        dl = self.D.bars(uni, '1Day', a - timedelta(days=45), a, 'iex')
        data['iex_adv'] = {s: sum(b['v'] for b in L[-14:]) / 14 for s, L in dl.items() if len(L) >= 5}
        log(d, 'IEX: symbols with minute bars', len(data['IBARS']), 'with daily history', len(data['iex_adv']))
        return data

    def iex_quote_at(self, sym, ts):
        r = self.D.get('/v2/stocks/quotes', dict(symbols=sym, start=datetime.fromtimestamp(ts - 120, timezone.utc).isoformat(),
                                                 end=datetime.fromtimestamp(ts, timezone.utc).isoformat(), limit=1, sort='desc', feed='iex'), 'iex_quote')
        if r is None or not r.ok: return None
        q = ((r.json().get('quotes') or {}).get(sym) or [None])[0]
        if not q or not q.get('bp') or not q.get('ap') or q['ap'] < q['bp']: return None
        return dict(bid=q['bp'], ask=q['ap'], t=epoch(q['t']))

    def run_free(self, d, close_m, state, data, cfg):
        saved = self.cfg; self.cfg = cfg
        try: return self._run_free(d, close_m, state, data)
        finally: self.cfg = saved

    def _run_free(self, d, close_m, state, data):
        t0 = time.time()
        uni, daily, curve, BARS, news, IB, iadv = data['uni'], data['daily'], data['curve'], data['BARS'], data['news'], data['IBARS'], data['iex_adv']
        R = self.cfg['risk']
        flat_m = min(V.hhmm(R['flat_at']), close_m - 10); until_m = min(V.hhmm(R['entries_until']), close_m - 30)
        cfg = V.merge(self.cfg, {'risk': {'entries_until': f'{until_m // 60:02d}:{until_m % 60:02d}'}})
        ptr = {s: 0 for s in BARS}; dptr = {s: 0 for s in BARS}; iptr = {s: 0 for s in IB}
        dagg = {s: dict(v=0, dv=0.0, hi=None, lo=None, px=None) for s in BARS}
        st = state; eq0 = st['equity']; eq = eq0
        open_pos = {}; traded = set(); trades = []; signals = Counter(); blocks = Counter(); events = []; prev = {}
        stats = Counter()
        day_ts = datetime.combine(d, datetime.min.time(), ET).timestamp()
        for m in range(V.PM_START + 1, close_m + 1):
            ts = day_ts + m * 60
            for s, L in BARS.items():                                          # real market (fills and exits) ...
                i = ptr[s]
                while i < len(L) and L[i].m < m: i += 1
                ptr[s] = i
                j = dptr[s]; a = dagg[s]                                       # ... and the delayed full-market view (scan)
                while j < len(L) and L[j].m < m - DELAY_M:
                    b = L[j]; a['v'] += b.v; a['dv'] += b.v * (b.h + b.l + b.c) / 3; a['px'] = b.c
                    a['hi'] = b.h if a['hi'] is None else max(a['hi'], b.h); a['lo'] = b.l if a['lo'] is None else min(a['lo'], b.l)
                    j += 1
                dptr[s] = j
            for s, L in IB.items():                                            # live IEX prints
                k = iptr[s]
                while k < len(L) and L[k].m < m: k += 1
                iptr[s] = k
            for s in list(open_pos):
                p = open_pos[s]; L = BARS[s]; i = ptr[s]
                newb = L[p['k']:i]
                if newb:
                    px, b, why = V.sim_exit(p['side'], p['stop'], p['target'], newb, flat_m, p['slip'])
                    if b is not None and why not in ('last-bar', 'no-data'):
                        self.close(p, px, b, why, d, trades, events); eq += trades[-1]['pnl']; del open_pos[s]; continue
                    p['k'] = i
                if m >= flat_m + 1 and s in open_pos:
                    L2 = [b for b in L if b.m >= flat_m]
                    if L2: self.close(p, L2[0].o * (1 - p['side'] * p['slip']), L2[0], 'time', d, trades, events); eq += trades[-1]['pnl']; del open_pos[s]
            sess = V.session(m - 1)
            if sess != 'regular' or m >= close_m: continue
            rows = {}
            for s in uni:
                a = dagg.get(s)
                if not a or a['px'] is None: continue
                dd = daily[s]; dm = m - DELAY_M
                rv = a['v'] / (dd['adv'] * (curve(dm) if dm >= V.RTH_OPEN else V.default_curve(dm))) if dd['adv'] and a['v'] else None
                rows[s] = dict(px=a['px'], chg=(a['px'] / dd['prior_close'] - 1) * 100, v=a['v'], dv=a['dv'], rv=rv, hi=a['hi'], lo=a['lo'])
            lists = V.candidate_lists(rows, daily, m - DELAY_M, cfg)
            cand = set().union(*lists.values())
            deep = list(dict.fromkeys(list(open_pos) + V.prerank(cand, rows)[:cfg['candidates']['deep_scan']]))
            vis = [n for n in news if n['t'] and n['t'] < ts]
            groups = V.group_news(vis[-600:], ts, day_ts - 8 * 3600) if vis else []
            for s in deep:
                stats['looked'] += 1
                B = IB.get(s, [])[:iptr.get(s, 0)]
                if not B or not iadv.get(s): stats['no IEX data'] += 1; continue
                if m - 1 - B[-1].m >= QUIET_M: stats['IEX too quiet'] += 1; continue
                dd = daily[s]
                f = V.features(s, B, m - 1, dd['prior_close'], iadv[s], curve, None, dd, cfg)
                if not f: continue
                f['dollar_volume'] = rows.get(s, {}).get('dv', 0.0)              # liquidity from the (delayed) full market, as live
                stats['read'] += 1
                cat = self.catalyst_at(s, f, ts, d, day_ts, groups)
                eL = V.evaluate(f, B, 1, cfg, cat); eS = V.evaluate(f, B, -1, cfg, cat)
                if any(only_spread_pending(e) for e in (eL, eS)):
                    q = self.iex_quote_at(s, ts)
                    if q:
                        f = dict(V.features(s, B, m - 1, dd['prior_close'], iadv[s], curve, dict(bid=q['bid'], ask=q['ask']), dd, cfg), dollar_volume=f['dollar_volume'])
                        eL = V.evaluate(f, B, 1, cfg, cat); eS = V.evaluate(f, B, -1, cfg, cat)
                    else: stats['no IEX quote'] += 1
                for side, e in ((1, eL), (-1, eS)):
                    kk = (s, side)
                    if prev.get(kk) != e['status']: signals[('long' if side > 0 else 'bearish', e['status'])] += 1
                    prev[kk] = e['status']
                    if e['status'] == 'confirmed' and s not in open_pos:
                        self.try_entry(s, side, e, f, B, BARS[s], ptr[s], m, ts, eq, eq0, open_pos, traded, st, cfg, blocks, events, d)
        for s, p in list(open_pos.items()):
            L = BARS[s]
            if L: self.close(p, L[-1].c * (1 - p['side'] * p['slip']), L[-1], 'last-bar', d, trades, events); eq += trades[-1]['pnl']
        st['equity'] = eq
        log(d, 'free-plan trades', len(trades), 'pnl', round(eq - eq0, 2), dict(stats), round(time.time() - t0), 's')
        return dict(day=d.isoformat(), trades=trades, pnl=round(eq - eq0, 2), signals={f'{a}:{b}': v for (a, b), v in signals.items()},
                    blocks=dict(blocks), stats=dict(stats))

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].strip() else 3
    cfg = json.load(open('city_config.json')) if os.path.exists('city_config.json') else {}
    RP = IEXReplay(Data(key, sec), key, sec, cfg)
    ss = RP.sessions(*DEV); random.Random(11).shuffle(ss); pick = sorted(ss[:n])
    V_ = {k: c for k, c in variant_configs(RP.cfg).items() if k in RULES}
    res = {(k, mode): [] for k in V_ for mode in ('full', 'free')}
    st = {key_: dict(equity=2500.0, daytrades=[], pdt=False) for key_ in res}
    stats = Counter()
    for d, cm in pick:
        try:
            data = RP.load_iex(d, RP.load_day(d, cm))
            for k, c in V_.items():
                res[(k, 'full')].append(RP.run_day(d, cm, frames=False, state=st[(k, 'full')], data=data, cfg=c))
                r = RP.run_free(d, cm, st[(k, 'free')], data, c); res[(k, 'free')].append(r)
                if k == 'A_original': stats.update(r['stats'])
            del data
        except Exception as e: log('day failed', d, e)
    rows = ['| rule set | data | trades | win rate | net P&L after costs | worst day |', '|---|---|---|---|---|---|']
    out = dict(sessions=[d.isoformat() for d, _ in pick], updated=datetime.now(ET).isoformat(timespec='seconds'), iex_reading=dict(stats), results={})
    for (k, mode), v in res.items():
        S = summarize(v, f'{k} {mode}')
        out['results'][f'{k}:{mode}'] = dict(summary={x: y for x, y in S.items() if x != 'equity_curve'}, trades=[dict(t, day=x['day']) for x in v for t in x['trades']])
        label = 'full real-time (paid)' if mode == 'full' else 'FREE: IEX live + 16-min delayed scan'
        rows.append(f"| {VARIANT_NOTES[k]['name']} | {label} | {S['trades']} | {S['win_rate_pct']}% | ${S['net_pnl']} | {S['worst_day']} |")
    lk = max(1, stats['looked'])
    md = [f"# VANTEX City free-data check - {len(pick)} sessions: {', '.join(out['sessions'])}", '',
          'Same days, same rules, same costs and fills. "FREE" sees the market the way the free Alpaca plan would: the scan is 16 minutes late and '
          'each stock is read from IEX trades only.', ''] + rows + ['',
          f"IEX coverage (original rules): of {stats['looked']} times a stock was picked for a closer look, it could be read {stats['read']} times "
          f"({stats['read'] / lk * 100:.0f}%); IEX too quiet {stats['IEX too quiet']} ({stats['IEX too quiet'] / lk * 100:.0f}%); no IEX data {stats['no IEX data']}; "
          f"no IEX quote when needed {stats['no IEX quote']}.", '',
          'A few sessions are a first look, not proof. Paper trading only.']
    publish({})
    publish({'iexcheck.json': out, 'iexcheck.md': '\n'.join(md) + '\n'})

if __name__ == '__main__':
    main()
