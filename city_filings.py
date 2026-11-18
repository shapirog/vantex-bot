"""
VANTEX City research: ChatGPT ideas #1 (activist 13D) and #3 (clustered insider buying). Research only: places NO orders.

Data: SEC EDGAR (free; contact header from the SEC_USER_AGENT secret).
  F1 activist stake   a new SCHEDULE 13D (not an amendment, not 13G) whose subject company is a stock we can trade.
                      Source: EDGAR quarterly form index. Only the filing DATE is used, so we enter at the NEXT session's open
                      (conservative: a filing at 8 am could be traded the same day). Substitution: ChatGPT also asked for Item 4
                      to describe an influence plan; a 13D is by law the non-passive form, the text is not parsed here.
  F3 insider cluster  2+ different insiders report open-market PURCHASES (code P) in the same company within 5 business days,
                      each >= $50k, together >= $250k. Source: SEC "Form 3/4/5 data sets" (quarterly). Signal day = filing date
                      of the filing that completes the cluster; enter the next session's open.
  Exit (both)         after 20 sessions at the close, or at the next open after a close 2 x ATR(14) below the entry.
  Compared with       SPY over the same days (excess return) and a placebo: a random tradable stock entered the same day.
  Costs               by liquidity per side (0.05-0.5%, +1% under $1); also a 2x-cost check.
Dev = filings 2023-2025, test = filings in 2026. Ticker mapping for 13D uses today's SEC list (delisted names are missing).

  python city_filings.py   -> live-replay/filings.md / .json / filings_trades.csv
"""
import csv, io, json, os, random, re, sys, time, zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta

import city_sec
from city_engine import Data
from city_replay import ET, log, publish
from city_overnight import universe
from city_news_study import load_ohlcv, cost, net

QUARTERS = [(y, q) for y in (2023, 2024, 2025, 2026) for q in (1, 2, 3, 4) if (y, q) <= (2026, 3)]
INSIDER_ZIP = 'https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{y}q{q}_form345.zip'
FORM_IDX = 'https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/form.idx'

# ------------------------------------------------------------------ parsing (tested)
def parse_form_idx(text):
    """rows of the fixed-width EDGAR form index -> list of (form, company, cik, date)"""
    out = []
    for ln in text.splitlines():
        m = re.match(r'^(\S.*?)\s{2,}(.+?)\s{2,}(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(edgar/\S+)', ln)
        if m: out.append((m.group(1).strip(), m.group(2).strip(), int(m.group(3)), m.group(4), m.group(5)))
    return out

def initial_13d(rows, cik_to_sym):
    """file name -> [(cik, date)] for SCHEDULE 13D; each filing is listed once for the subject and once per filer.
    Keep filings where exactly one listed company is a tradable ticker (that one is the subject)."""
    by = defaultdict(list)
    for form, comp, cik, d, fn in rows:
        if form in ('SCHEDULE 13D', 'SC 13D'): by[fn].append((cik, d))
    out = []
    for fn, L in by.items():
        syms = {cik_to_sym[c] for c, _ in L if c in cik_to_sym}
        if len(syms) == 1: out.append((syms.pop(), L[0][1]))
    return out

def parse_date(s):
    s = (s or '').strip()
    for f in ('%d-%b-%Y', '%Y-%m-%d', '%m/%d/%Y'):
        try: return datetime.strptime(s.title() if '-' in s and s[3:6].isalpha() else s, f).date().isoformat()
        except ValueError: pass
    return None

def insider_buys(zbytes):
    """Form 4 open-market purchases from one quarterly data set -> list of dict(sym, owner, filed, value)"""
    z = zipfile.ZipFile(io.BytesIO(zbytes))
    def table(name):
        n = [x for x in z.namelist() if x.upper().endswith(name)][0]
        lines = z.read(n).decode('utf-8', 'replace').splitlines()
        hdr = lines[0].split('\t')
        return [dict(zip(hdr, ln.split('\t'))) for ln in lines[1:]]
    sub = {r['ACCESSION_NUMBER']: r for r in table('SUBMISSION.TSV') if r.get('DOCUMENT_TYPE', '').strip() in ('4', '4/A')}
    own = {}
    for r in table('REPORTINGOWNER.TSV'): own.setdefault(r['ACCESSION_NUMBER'], r.get('RPTOWNERCIK', ''))
    out = []
    for r in table('NONDERIV_TRANS.TSV'):
        a = r['ACCESSION_NUMBER']
        if a not in sub or r.get('TRANS_CODE', '').strip() != 'P' or r.get('TRANS_ACQUIRED_DISP_CD', 'A').strip() != 'A': continue
        try: v = float(r.get('TRANS_SHARES') or 0) * float(r.get('TRANS_PRICEPERSHARE') or 0)
        except ValueError: continue
        s = sub[a]; sym = (s.get('ISSUERTRADINGSYMBOL') or '').strip().upper(); d = parse_date(s.get('FILING_DATE'))
        if sym and d and v > 0: out.append(dict(sym=sym, owner=own.get(a, a), filed=d, value=v, acc=a))
    return out

def clusters(buys, cal):
    """signal days: the filing that makes >= 2 different insiders, each >= $50k (summed per owner), >= $250k together, within
    5 business days (by filing date). One signal per stock per 20 sessions."""
    pos = {d: k for k, d in enumerate(cal)}
    def k_of(d):
        while d not in pos and d <= cal[-1]: d = (date.fromisoformat(d) + timedelta(days=1)).isoformat()
        return pos.get(d)
    by = defaultdict(list)
    for b in buys:
        k = k_of(b['filed'])
        if k is not None: by[b['sym']].append((k, b['owner'], b['value']))
    out = []
    for s, L in by.items():
        L.sort(); last = -99
        for j, (k, _, _) in enumerate(L):
            win = [x for x in L[:j + 1] if k - x[0] <= 4]
            per = defaultdict(float)
            for _, o, v in win: per[o] += v
            big = {o: v for o, v in per.items() if v >= 50e3}
            if len(big) >= 2 and sum(big.values()) >= 250e3 and k - last >= 20:
                out.append((s, cal[k])); last = k
    return out

def atr(S, i, n=14):
    trs = [max(S['h'][j] - S['l'][j], abs(S['h'][j] - S['c'][j - 1]), abs(S['l'][j] - S['c'][j - 1])) for j in range(max(1, i - n + 1), i + 1)]
    return sum(trs) / len(trs) if trs else 0.0

def trade(S, k_sig, last_cal, days=20):
    """enter at the open after the signal day k_sig; exit at the close after `days` sessions, or at the next open after a
    close 2 x ATR(14, as of the signal day) below the entry. Returns (entry, exit, i_in, i_out, how) or None."""
    i = k_sig + 1
    if i >= len(S['d']): return None
    ent = S['o'][i]; stop = ent - 2 * atr(S, k_sig)
    for j in range(i, min(i + days, len(S['d']))):
        if S['c'][j] < stop and j < i + days - 1:
            if j + 1 < len(S['d']): return ent, S['o'][j + 1], i, j + 1, 'stop'
            break
        if j == i + days - 1: return ent, S['c'][j], i, j, 'time'
    if S['d'][-1] >= last_cal: return None                                 # still running
    return ent, S['c'][-1], i, len(S['d']) - 1, 'stopped trading'

def stats(rs):
    if not rs: return dict(n=0)
    n = len(rs); mu = sum(rs) / n; sd = (sum((x - mu) ** 2 for x in rs) / max(1, n - 1)) ** 0.5; srt = sorted(rs)
    wo = srt[:-5] if n > 10 else srt
    return dict(n=n, win_pct=round(100 * sum(x > 0 for x in rs) / n, 1), avg_pct=round(100 * mu, 3), median_pct=round(100 * srt[n // 2], 3),
                t=round(mu / (sd / n ** 0.5), 2) if sd else None, avg_wo_best5_pct=round(100 * sum(wo) / len(wo), 3))

# ------------------------------------------------------------------ run
def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    if not os.environ.get('SEC_USER_AGENT'): sys.exit('SEC_USER_AGENT secret missing')
    E = city_sec.SEC(); E.filings('AAPL')                                    # loads the ticker <-> CIK list
    cik_to_sym = {v: k for k, v in (E.cik or {}).items()}
    D = Data(key, sec); uni = universe(key, sec)
    s0 = datetime(2022, 11, 1, tzinfo=ET); s1 = datetime.now(ET) - timedelta(minutes=20)
    stocks = load_ohlcv(D, sorted(uni), s0, s1); log('stocks', len(stocks))
    sp = D.bars(['SPY'], '1Day', s0, s1, 'sip', 'all').get('SPY', []); cal = [x['t'][:10] for x in sp]; last_cal = cal[-1]
    spy = {x['t'][:10]: (x['o'], x['c']) for x in sp}
    sig = {'F1 activist 13D (new stake)': [], 'F3 insider buying cluster': []}; buys = []
    for y, q in QUARTERS:
        r = E._get(FORM_IDX.format(y=y, q=q))
        if r is not None: sig['F1 activist 13D (new stake)'] += initial_13d(parse_form_idx(r.text), cik_to_sym)
        r = E._get(INSIDER_ZIP.format(y=y, q=q))
        if r is not None:
            try: buys += insider_buys(r.content)
            except Exception as e: log('insider data', y, q, 'failed', type(e).__name__, e)
        log(y, q, '13D so far', len(sig['F1 activist 13D (new stake)']), 'insider buys', len(buys))
    sig['F3 insider buying cluster'] = clusters(buys, cal)
    rng = random.Random(5); syms = sorted(stocks); trades = []
    for name, L in sig.items():
        for s, d in L:
            S = stocks.get(s)
            if not S or d < '2023-01-01': continue
            k = next((j for j, x in enumerate(S['d']) if x >= d), None)       # signal session = filing date or the next session
            if k is None or k < 21: continue
            if S['d'][k] > d: k -= 1                                         # filed on a non-trading day: signal = the session before, enter next open
            adv = sum(S['c'][j] * S['v'][j] for j in range(k - 19, k + 1)) / 20; px = S['c'][k]
            if px < 1 or adv < 1e6: continue
            r = trade(S, k, last_cal)
            if not r: continue
            ent, ext, i, j, how = r; c = cost(adv, px)
            spy_r = spy[S['d'][j]][1] / spy[S['d'][i]][0] - 1 if S['d'][i] in spy and S['d'][j] in spy else 0.0
            # placebo: a random tradable stock entered the same day, same exit rule
            pl = None
            for _ in range(20):
                P = stocks[rng.choice(syms)]
                try: kp = P['d'].index(S['d'][k])
                except ValueError: continue
                if kp < 21 or P['c'][kp] < 1: continue
                rp = trade(P, kp, last_cal)
                if rp: pl = net(rp[0], rp[1], cost(sum(P['c'][x] * P['v'][x] for x in range(kp - 19, kp + 1)) / 20, P['c'][kp])); break
            trades.append(dict(rule=name, sym=s, filed=d, buy_day=S['d'][i], sell_day=S['d'][j], how=how, price=round(px, 2), adv_m=round(adv / 1e6, 1),
                               net=net(ent, ext, c), net2=net(ent, ext, 2 * c), excess=net(ent, ext, c) - spy_r, placebo=pl,
                               split='dev' if d < '2026-01-01' else 'test', liquid=px >= 5 and adv >= 20e6))
    res = {}; rows = ['| rule | stocks | period | trades | win rate | avg net (20 days) | median | avg w/o best 5 | t-stat | vs SPY | random-stock placebo | at 2x costs |',
                      '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for name in sig:
        for lab, f in (('all ($1+, $1M+/day)', lambda t: True), ('liquid ($5+, $20M+/day)', lambda t: t['liquid'])):
            for spl in ('dev', 'test'):
                T = [t for t in trades if t['rule'] == name and t['split'] == spl and f(t)]
                if not T: continue
                S1 = stats([t['net'] for t in T]); ex = sum(t['excess'] for t in T) / len(T); pls = [t['placebo'] for t in T if t['placebo'] is not None]
                a2 = sum(t['net2'] for t in T) / len(T)
                res[f'{name} | {lab} | {spl}'] = dict(S1, vs_spy_pct=round(100 * ex, 3), placebo_avg_pct=round(100 * sum(pls) / len(pls), 3) if pls else None, avg_2x_pct=round(100 * a2, 3))
                o = res[f'{name} | {lab} | {spl}']
                rows.append(f"| {name} | {lab} | {spl} | {S1['n']} | {S1['win_pct']}% | {S1['avg_pct']}% | {S1['median_pct']}% | {S1['avg_wo_best5_pct']}% | {S1['t']} | "
                            f"{o['vs_spy_pct']:+}% | {o['placebo_avg_pct']}% | {o['avg_2x_pct']}% |")
    md = ['# VANTEX City research: SEC filings (ChatGPT ideas #1 and #3)', '',
          f"New activist 13D filings found for tradable stocks: {len(sig['F1 activist 13D (new stake)'])}; insider open-market buys: {len(buys)}; "
          f"insider clusters: {len(sig['F3 insider buying cluster'])}. Enter the open after the filing day, hold 20 sessions (2 x ATR stop). Costs included.", ''] + rows + [
          '', '"vs SPY" = average net return minus SPY over the same days. Placebo = a random tradable stock entered the same day with the same exit. '
          'Filing dates only (not times), so entries are one day later than the earliest possible. 13D ticker mapping uses today\'s SEC list (survivorship). '
          'A backtest is not proof.']
    buf = io.StringIO(); w = csv.writer(buf); cols = ['rule', 'split', 'sym', 'filed', 'buy_day', 'sell_day', 'how', 'price', 'adv_m', 'net', 'excess']
    w.writerow(cols)
    for t in trades: w.writerow([round(t[c] * 100, 3) if c in ('net', 'excess') else t[c] for c in cols])
    publish({}); publish({'filings.md': '\n'.join(md) + '\n', 'filings.json': res, 'filings_trades.csv': buf.getvalue()})
    log('done', len(trades), 'sec calls', E.calls, 'errors', E.errors)

if __name__ == '__main__':
    main()
