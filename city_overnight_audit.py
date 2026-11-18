"""
VANTEX City research: AUDIT of Strategy A (overnight bias). Research/backtest only: no orders, no live code, nothing in the
live City changes.

Reproduces city_overnight.py exactly (monthly 252-session OLS of overnight log returns on full-session log returns, one-sided
5% intercept screen, buy at the close / sell at the next open, price >= $5, 20-day average dollar volume >= $20M), then audits it:
  1. signal: monthly eligible counts and pass rates vs the 5% expected by chance; Benjamini-Hochberg FDR screens (q = 5%, 10%);
     1,000 random portfolios drawn from the same eligible list with the same number of names, sizing and schedule (sector
     matching is NOT possible: no point-in-time sector data); moving-block bootstrap (21-day blocks) confidence intervals;
     a corporate-action check (stock-nights with |overnight move| > 25%).
  2. practical sizing at $30,000 with whole shares: 25 / 50 / 100 names and all qualifiers; rankings by intercept, t-statistic
     and intercept lower-confidence-bound are ADAPTATIONS, not the published baseline.
  3. costs: 0, 0.5, 1, 2.5, 5 bp per side; $0.005 per share per side; SEC + FINRA TAF fees on sales; break-even cost; turnover.
Both periods are reported: dev (Jun 2023 - Dec 2025) and 2026. 2026 was already examined, so it is shown but nothing is chosen from it.

  python city_overnight_audit.py    -> live-replay/overnight_audit.md / .json / _trades.csv
"""
import csv, io, json, math, os, random, sys, time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

import numpy as np

import vantex_core as V
from city_engine import Data
from city_replay import ET, log, publish
from city_overnight import LOOKBACK, MIN_OBS, TCRIT, CAP, universe, load_all, month_ends, eligible, index

PERIODS = {'dev': ('2023-06-01', '2025-12-31'), '2026 (already examined)': ('2026-01-01', '2026-12-31')}
BPS = (0.0, 0.5, 1.0, 2.5, 5.0)
N_RANDOM, BLOCK, N_BOOT, START_EQ = 1000, 21, 3000, 30000.0

def regress(S, i):
    """(intercept, standard error, t, n) of r_on = a + b r_d over the 252 sessions ending at i; None when < 220 observations"""
    ds, op, cl, vol = S; xs, ys = [], []
    for j in range(max(1, i - LOOKBACK + 1), i + 1):
        if cl[j - 1] > 0 and op[j] > 0 and cl[j] > 0:
            ys.append(math.log(op[j] / cl[j - 1])); xs.append(math.log(cl[j] / cl[j - 1]))
    n = len(xs)
    if n < MIN_OBS: return None
    mx, my = sum(xs) / n, sum(ys) / n; sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0: return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx; a = my - b * mx
    s2 = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys)) / (n - 2); se = math.sqrt(s2 * (1 / n + mx * mx / sxx))
    return (a, se, a / se, n) if se > 0 else None

def p_one_sided(t): return 0.5 * math.erfc(t / math.sqrt(2))

def bh(pvals, q):
    """Benjamini-Hochberg: indices passing at false-discovery rate q"""
    order = sorted(range(len(pvals)), key=lambda k: pvals[k]); m = len(pvals); cut = -1
    for r, k in enumerate(order, 1):
        if pvals[k] <= q * r / m: cut = r
    return set(order[:cut]) if cut > 0 else set()

def build(stocks, idx, cal):
    """aligned arrays: close[s, t], open[s, t]; overnight[s, t] = open[t+1] / close[t] - 1 (NaN when either is missing)"""
    syms = sorted(stocks); n, T = len(syms), len(cal); pos = {d: k for k, d in enumerate(cal)}
    C = np.full((n, T), np.nan); O = np.full((n, T), np.nan)
    for r, s in enumerate(syms):
        ds, op, cl, _ = stocks[s]
        for i, d in enumerate(ds):
            k = pos.get(d)
            if k is not None: C[r, k] = cl[i]; O[r, k] = op[i]
    ON = np.full((n, T), np.nan); ON[:, :-1] = O[:, 1:] / C[:, :-1] - 1
    return syms, C, O, ON

def monthly(stocks, idx, cal, first, last):
    """month-end -> dict(eligible=[sym], stats={sym: (a, se, t, n)}), using only data up to the month-end close"""
    out = {}
    for me in month_ends(cal):
        if me < first or me > last: continue
        elig, st = [], {}
        for s, S in stocks.items():
            i = idx[s].get(me)
            if i is None or not eligible(S, i): continue
            elig.append(s); r = regress(S, i)
            if r: st[s] = r
        out[me] = dict(eligible=elig, stats=st)
    return out

def selections(M):
    """month-end -> {screen: [syms]} for the published 5% screen and the FDR screens"""
    sel = {}
    for me, x in M.items():
        names = sorted(x['stats']); p = [p_one_sided(x['stats'][s][2]) for s in names]
        base = [s for s in names if x['stats'][s][2] >= TCRIT]
        sel[me] = {'published 5%': base, 'FDR q=10%': [names[k] for k in sorted(bh(p, 0.10))], 'FDR q=5%': [names[k] for k in sorted(bh(p, 0.05))]}
    return sel

def schedule(cal, mes, a, b):
    """trading day index -> month-end whose selection applies (latest month-end strictly before that day)"""
    out = {}; mes = sorted(mes)
    for k, d in enumerate(cal[:-1]):
        if not (a <= d <= b): continue
        prior = [m for m in mes if m < d]
        if prior: out[k] = prior[-1]
    return out

def port_daily(ON, rows, days):
    """equal weight, each capped at 5%, over names with a valid overnight return that day: (gross return, exposure) per day"""
    if not rows: return np.zeros(len(days)), np.zeros(len(days))
    X = ON[np.ix_(rows, days)]; valid = ~np.isnan(X); nv = valid.sum(0)
    w = np.where(nv > 0, np.minimum(CAP, 1.0 / np.maximum(nv, 1)), 0.0)
    return np.nansum(X, 0) * w, w * nv

def net(gross, expo, bp):
    """daily net return: every invested dollar pays the cost once going in (at the close) and once coming out (at the open)"""
    return gross - 2 * (bp / 1e4) * expo

def stats(r, spy=None, per=252):
    r = np.asarray(r, float)
    if len(r) == 0: return dict(days=0)
    eq = np.cumprod(1 + r); peak = np.maximum.accumulate(eq); dd = float(((peak - eq) / peak).max() * 100)
    sd = r.std(ddof=1); out = dict(days=int(len(r)), total_return_pct=round(float((eq[-1] - 1) * 100), 2),
                                    sharpe=round(float(r.mean() / sd * per ** 0.5), 2) if sd > 0 else None, max_drawdown_pct=round(dd, 1))
    if spy is not None and len(spy) == len(r) and np.var(spy) > 0: out['beta_vs_spy'] = round(float(np.cov(spy, r)[0, 1] / np.var(spy, ddof=1)), 3)
    return out

def by_year(r, dates):
    y = defaultdict(lambda: 1.0)
    for d, x in zip(dates, r): y[d[:4]] *= 1 + x
    return {k: round((v - 1) * 100, 1) for k, v in sorted(y.items())}

def block_boot(r, rng, per=252):
    r = np.asarray(r); n = len(r)
    if n < BLOCK * 3: return None
    starts = rng.integers(0, n - BLOCK + 1, size=(N_BOOT, math.ceil(n / BLOCK)))
    ann, sh = [], []
    for row in starts:
        x = np.concatenate([r[s:s + BLOCK] for s in row])[:n]
        ann.append((np.prod(1 + x) ** (per / n) - 1) * 100); sd = x.std(ddof=1); sh.append(x.mean() / sd * per ** 0.5 if sd > 0 else 0)
    q = lambda v: [round(float(np.percentile(v, 2.5)), 2), round(float(np.percentile(v, 97.5)), 2)]
    return dict(annual_return_pct_95ci=q(ann), sharpe_95ci=q(sh), prob_annual_return_below_0=round(float(np.mean(np.array(ann) < 0)), 3))

def random_portfolios(ON, sched, M, sel_counts, sym_row, days, rng):
    """N_RANDOM portfolios: each month, the same number of names drawn from that month's eligible list. Returns total gross returns."""
    months = defaultdict(list)
    for k in days: months[sched[k]].append(k)
    tot = np.ones(N_RANDOM)
    for me, ks in months.items():
        elig = [sym_row[s] for s in M[me]['eligible'] if s in sym_row]; n = sel_counts[me]
        if n == 0 or not elig: continue
        X = ON[np.array(elig)][:, ks]
        for j in range(N_RANDOM):
            pick = rng.choice(len(elig), size=min(n, len(elig)), replace=False); Y = X[pick]; valid = ~np.isnan(Y); nv = valid.sum(0)
            w = np.where(nv > 0, np.minimum(CAP, 1.0 / np.maximum(nv, 1)), 0.0); tot[j] *= np.prod(1 + np.nansum(Y, 0) * w)
    return (tot - 1) * 100

def whole_share_sim(C, O, ON, sched, sel_rank, sym_row, days, cal, n_names, cost):
    """$30K account, whole shares, equal dollars per name each night; cost = ('bp', x) or ('share', $); SEC + TAF on every sale"""
    eq = START_EQ; rets, idle, orders, maxw = [], [], [], []
    for k in days:
        names = [sym_row[s] for s in sel_rank[sched[k]] if s in sym_row]
        names = [r for r in names if not np.isnan(ON[r, k])][:n_names] if n_names else [r for r in names if not np.isnan(ON[r, k])]
        if not names: rets.append(0.0); idle.append(1.0); orders.append(0); continue
        alloc = eq / len(names); pnl = 0.0; used = 0.0; cnt = 0; mw = 0.0
        sale_day = date.fromisoformat(cal[k + 1])
        for r in names:
            px_in, px_out = C[r, k], O[r, k + 1]; sh = math.floor(alloc / px_in)
            if sh < 1: continue
            cnt += 2; used += sh * px_in; mw = max(mw, sh * px_in / eq)
            fee = V.sale_fees(sale_day, sh, px_out)
            c = (cost[1] / 1e4) * sh * (px_in + px_out) if cost[0] == 'bp' else cost[1] * sh * 2
            pnl += sh * (px_out - px_in) - c - fee
        rets.append(pnl / eq); idle.append(1 - used / eq); orders.append(cnt); maxw.append(mw); eq += pnl
    return rets, dict(avg_idle_cash_pct=round(100 * float(np.mean(idle)), 1), avg_orders_per_day=round(float(np.mean(orders)), 1),
                      max_position_weight_pct=round(100 * max(maxw or [0]), 1), final_equity=round(eq, 2))

def main():
    key, sec = os.environ.get('APCA_API_KEY_ID', ''), os.environ.get('APCA_API_SECRET_KEY', '')
    if not key.startswith('PK'): sys.exit('Refusing to run: paper key (PK...) required')
    D = Data(key, sec); uni = universe(key, sec)
    s0 = datetime(2022, 4, 1, tzinfo=ET); s1 = datetime.now(ET) - timedelta(days=1)
    stocks = load_all(D, sorted(uni), s0, s1); idx = index(stocks)
    spyL = D.bars(['SPY'], '1Day', s0, s1, 'sip', 'all').get('SPY', [])
    cal = [x['t'][:10] for x in spyL]; spy_c = np.array([x['c'] for x in spyL]); spy_o = np.array([x['o'] for x in spyL])
    spy_on = np.full(len(cal), np.nan); spy_on[:-1] = spy_o[1:] / spy_c[:-1] - 1
    syms, C, O, ON = build(stocks, idx, cal); sym_row = {s: r for r, s in enumerate(syms)}; log('arrays', C.shape)
    M = monthly(stocks, idx, cal, '2023-04-25', '2026-12-31'); SEL = selections(M); log('month-ends', len(M))
    rng = np.random.default_rng(20261117); out = dict(updated=datetime.now(ET).isoformat(timespec='seconds'), periods={})
    monthly_rows = [dict(month_end=me, eligible=len(x['eligible']), with_regression=len(x['stats']), passed_5pct=len(SEL[me]['published 5%']),
                         pass_rate_pct=round(100 * len(SEL[me]['published 5%']) / max(1, len(x['stats'])), 1),
                         expected_by_chance=round(0.05 * len(x['stats']), 1), fdr10=len(SEL[me]['FDR q=10%']), fdr5=len(SEL[me]['FDR q=5%'])) for me, x in sorted(M.items())]
    out['monthly_screen'] = monthly_rows
    big = np.abs(ON) > 0.25; out['corporate_action_check'] = dict(stock_nights_over_25pct=int(np.nansum(big)), note='overnight moves above 25% (possible bad adjustments) are excluded in the sensitivity row')
    rank = {m: {'t-statistic': sorted(SEL[m]['published 5%'], key=lambda s: -M[m]['stats'][s][2]),
                'intercept': sorted(SEL[m]['published 5%'], key=lambda s: -M[m]['stats'][s][0]),
                'intercept lower bound': sorted(SEL[m]['published 5%'], key=lambda s: -(M[m]['stats'][s][0] - TCRIT * M[m]['stats'][s][1])),
                'all qualifying': SEL[m]['published 5%']} for m in SEL}
    csv_rows = []
    for pname, (a, b) in PERIODS.items():
        sched = schedule(cal, list(M), a, b); days = sorted(sched); dates = [cal[k] for k in days]; P = dict(days=len(days))
        if not days: continue
        spy_r = np.nan_to_num(spy_on[days])
        # 1. published baseline and screens, by cost
        screens = {}
        for scr in ('published 5%', 'FDR q=10%', 'FDR q=5%'):
            g = np.zeros(len(days)); e = np.zeros(len(days)); months = defaultdict(list)
            for j, k in enumerate(days): months[sched[k]].append(j)
            for me, js in months.items():
                rows = [sym_row[s] for s in SEL[me][scr] if s in sym_row]; gg, ee = port_daily(ON, rows, [days[j] for j in js])
                g[js] = gg; e[js] = ee
            screens[scr] = (g, e)
            res = {}
            for bp in BPS:
                r = net(g, e, bp); res[f'{bp} bp'] = dict(stats(r, spy_r), by_year=by_year(r, dates))
            avg_names = round(float(np.mean([len(SEL[sched[k]][scr]) for k in days])), 1)
            mean_e = float(e.mean()); be = float(g.mean()) / (2 * mean_e) * 1e4 if mean_e > 0 else None
            P[scr] = dict(avg_names=avg_names, avg_exposure_pct=round(100 * mean_e, 1), daily_turnover_pct=round(200 * mean_e, 1),
                          breakeven_cost_bp_per_side=round(be, 2) if be is not None else None, by_cost=res)
        g, e = screens['published 5%']
        # winners-removed and corporate-action sensitivity on the published baseline
        by_me = defaultdict(list)                                           # month-end -> positions j in `days`
        for j, k in enumerate(days): by_me[sched[k]].append(j)
        legs = []
        for me, js in by_me.items():
            for s in SEL[me]['published 5%']:
                r_ = sym_row.get(s)
                if r_ is None: continue
                for j in js:
                    v = ON[r_, days[j]]
                    if not np.isnan(v): legs.append((cal[days[j]], s, float(v)))
        L = sorted((x[2] for x in legs), reverse=True)
        P['avg_stock_night_gross_pct'] = round(100 * float(np.mean(L)), 4) if L else None
        P['avg_stock_night_gross_pct_without_top10'] = round(100 * float(np.mean(L[10:])), 4) if len(L) > 10 else None
        g_clip = np.zeros(len(days))
        for me, js in by_me.items():
            rows = [sym_row[s] for s in SEL[me]['published 5%'] if s in sym_row]
            if rows:
                X = ON[np.ix_(rows, [days[j] for j in js])].copy(); X[np.abs(X) > 0.25] = np.nan; valid = ~np.isnan(X); nv = valid.sum(0)
                g_clip[js] = np.nansum(X, 0) * np.where(nv > 0, np.minimum(CAP, 1.0 / np.maximum(nv, 1)), 0.0)
        P['without_moves_over_25pct_gross'] = stats(g_clip, spy_r)
        P['spy_overnight_only'] = stats(spy_r, spy_r); P['spy_buy_and_hold_close_to_close'] = stats(np.nan_to_num(spy_c[days[0]:days[-1] + 2][1:] / spy_c[days[0]:days[-1] + 2][:-1] - 1))
        # random portfolios and bootstrap
        counts = {me: len(SEL[me]['published 5%']) for me in M}
        rnd = random_portfolios(ON, sched, M, counts, sym_row, days, rng); strat_total = float((np.prod(1 + g) - 1) * 100)
        P['random_portfolios'] = dict(n=N_RANDOM, strategy_gross_total_pct=round(strat_total, 2), random_median_pct=round(float(np.median(rnd)), 2),
                                     random_95th_pct=round(float(np.percentile(rnd, 95)), 2), strategy_percentile=round(float(np.mean(rnd < strat_total) * 100), 1),
                                     note='same eligible list, same number of names each month, same equal weights and schedule; sectors not matched (no sector data)')
        P['bootstrap'] = {f'{bp} bp': block_boot(net(g, e, bp), rng) for bp in (0.0, 1.0, 2.5)}
        # 2. $30K whole-share sizing, rankings are adaptations
        sizing = []
        for method in ('all qualifying', 't-statistic', 'intercept', 'intercept lower bound'):
            for nn in ((None,) if method == 'all qualifying' else (25, 50, 100)):
                for cost in (('bp', 0.0), ('bp', 1.0), ('bp', 2.5), ('share', 0.005)):
                    r, info = whole_share_sim(C, O, ON, sched, {m: rank[m][method] for m in rank}, sym_row, days, cal, nn, cost)
                    sizing.append(dict(method=method, names=nn or 'all', cost=f"{cost[1]} bp/side" if cost[0] == 'bp' else f"${cost[1]}/share/side",
                                       **stats(r, spy_r), **info))
        P['sizing_30k'] = sizing
        if pname == 'dev':
            for d, s, v in legs[:200000]: csv_rows.append((d, s, round(v * 100, 4)))
        out['periods'][pname] = P; log(pname, 'done')
    # report
    md = ['# Strategy A (overnight bias) audit', '',
          'Research only. Theoretical fills at the daily bar close and next open (consolidated last trade / first trade, close to but not exactly the official auction prices). '
          'Alpaca paper fills are simulated against quotes and are NOT evidence of auction slippage.', '']
    mr = out['monthly_screen']; avg_e = np.mean([x['with_regression'] for x in mr]); avg_p = np.mean([x['passed_5pct'] for x in mr])
    md += ['## 1. Is the screen picking real signals?', '',
           f"Average month: {avg_e:.0f} stocks tested, {avg_p:.0f} pass the 5% screen ({100 * avg_p / max(avg_e, 1):.1f}%); about {0.05 * avg_e:.0f} would pass by chance alone. "
           f"FDR q=10% keeps {np.mean([x['fdr10'] for x in mr]):.0f}, FDR q=5% keeps {np.mean([x['fdr5'] for x in mr]):.0f}.", '',
           '| month-end | tested | passed 5% | expected by chance | FDR 10% | FDR 5% |', '|---|---|---|---|---|---|'] + \
          [f"| {x['month_end']} | {x['with_regression']} | {x['passed_5pct']} | {x['expected_by_chance']} | {x['fdr10']} | {x['fdr5']} |" for x in mr]
    for pname, P in out['periods'].items():
        md += ['', f'## {pname}', '', '| screen | names | cost/side | total | Sharpe | max drawdown | beta | by year |', '|---|---|---|---|---|---|---|---|']
        for scr in ('published 5%', 'FDR q=10%', 'FDR q=5%'):
            for c, v in P[scr]['by_cost'].items():
                md.append(f"| {scr} | {P[scr]['avg_names']} | {c} | {v.get('total_return_pct', 0):+}% | {v.get('sharpe')} | {v.get('max_drawdown_pct')}% | {v.get('beta_vs_spy')} | "
                          f"{', '.join(f'{y}: {x:+}%' for y, x in v['by_year'].items())} |")
        md += ['', '| screen | break-even cost per side | daily turnover |', '|---|---|---|'] + \
              [f"| {scr} | {P[scr]['breakeven_cost_bp_per_side']} bp | {P[scr]['daily_turnover_pct']}% of capital |" for scr in ('published 5%', 'FDR q=10%', 'FDR q=5%')]
        R = P['random_portfolios']; B = P['bootstrap']
        md += ['', f"- Random portfolios ({R['n']}): strategy gross {R['strategy_gross_total_pct']:+}% vs random median {R['random_median_pct']:+}% "
                   f"(95th percentile {R['random_95th_pct']:+}%); the strategy beats {R['strategy_percentile']}% of them.",
               f"- Block bootstrap (21-day blocks): " + '; '.join(f"{k}: annual return 95% CI {v['annual_return_pct_95ci']}%, Sharpe {v['sharpe_95ci']}, P(loss) {v['prob_annual_return_below_0']}"
                                                         for k, v in B.items() if v),
               f"- Average stock-night (gross): {P['avg_stock_night_gross_pct']}%; without the 10 best: {P['avg_stock_night_gross_pct_without_top10']}%.",
               f"- Without overnight moves over 25% (possible bad adjustments): gross total {P['without_moves_over_25pct_gross'].get('total_return_pct')}%.",
               f"- SPY overnight only: {P['spy_overnight_only'].get('total_return_pct')}%; SPY buy and hold: {P['spy_buy_and_hold_close_to_close'].get('total_return_pct')}%.", '',
               '### $30,000 whole-share sizing (ranked versions are adaptations)', '',
               '| method | names | cost | total | Sharpe | max drawdown | idle cash | orders/day | largest position |', '|---|---|---|---|---|---|---|---|---|'] + \
              [f"| {x['method']} | {x['names']} | {x['cost']} | {x.get('total_return_pct', 0):+}% | {x.get('sharpe')} | {x.get('max_drawdown_pct')}% | {x['avg_idle_cash_pct']}% | "
               f"{x['avg_orders_per_day']} | {x['max_position_weight_pct']}% |" for x in P['sizing_30k']]
    md += ['', '## Execution facts (official Alpaca docs, checked 2026-11-17)', '',
           '- Market-on-open = time_in_force "opg"; orders after 9:28 am ET are rejected until 7:00 pm, then queue for the next open. Unfilled opg orders are cancelled after the open.',
           '- Market-on-close = time_in_force "cls"; orders after 3:50 pm ET are rejected until 7:00 pm. Routed to the primary exchange closing auction.',
           '- Fractional (dollar) orders are NOT supported for opg / cls, so whole shares only. The docs mark opg/cls with a "contact sales" asterisk.',
           '- Paper trading is a simulation against quotes: not routed to an exchange, no market impact, no latency slippage, random 10% partial fills.',
           '', 'Sector concentration could not be measured: no point-in-time sector data is available to this system.']
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(['night_of', 'symbol', 'overnight_return_pct']); w.writerows(csv_rows)
    publish({})
    publish({'overnight_audit.json': out, 'overnight_audit.md': '\n'.join(md) + '\n', 'overnight_audit_trades.csv': buf.getvalue()})

if __name__ == '__main__':
    main()
