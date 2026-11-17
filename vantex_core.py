    why.append(f"{'long' if best['side'] > 0 else 'bearish'} {best['status']}")
    if f['vol_trend'] == 'increasing': s += 6; why.append('volume increasing')
    elif f['vol_trend'] == 'fading': s -= 6; why.append('volume fading')
    if f['spread_pct'] is not None:
        s -= min(f['spread_pct'], 2) * 8
        if f['spread_pct'] > 0.5: why.append(f"spread {f['spread_pct']:.2f}%")
    s -= 3 * len(best['warnings'])
    good = [t for t in (cat or {}).get('types', []) if t not in NEGATIVE] if cat and cat.get('verified') else []
    if good: s += 8; why.append(good[0].lower() + ' news')
    if cat and cat.get('negative'): why.append('negative news: ' + ', '.join(cat['negative']))
    return round(s, 1), why, best

# ------------------------------------------------------------------ sizing and risk gates
def size_position(entry, stop, equity, start_equity, open_exposure, buying_power, side, cfg=DEFAULTS):
    """Shares from the stop distance and dollar risk. Equity used is the lower of now and start of day, so a losing day
    never sizes up to win it back. Buying power only ever caps the size, it never sets it."""
    R = cfg['risk']
    dist = abs(entry - stop)
    if entry <= 0 or dist <= 0 or (side > 0 and stop >= entry) or (side < 0 and stop <= entry):
        return dict(shares=0, reason='invalid stop')
    base = min(equity, start_equity) if start_equity else equity
    risk_d = base * R['risk_per_trade_pct'] / 100
    sh = math.floor(risk_d / dist)
    caps = dict(risk=sh, position=math.floor(base * R['max_position_pct'] / 100 / entry),
                exposure=math.floor(max(0.0, base * R['max_exposure_pct'] / 100 - open_exposure) / entry),
                buying_power=math.floor(max(0.0, buying_power) / entry))
    sh = min(caps.values())
    why = min(caps, key=caps.get)
    if sh < 1: return dict(shares=0, reason=f'size rounds to 0 shares (limited by {why.replace("_", " ")})', caps=caps)
    return dict(shares=sh, risk_dollars=round(sh * dist, 2), cost=round(sh * entry, 2), limited_by=why, caps=caps, risk_budget=round(risk_d, 2))

def entry_blocks(ctx, cfg=DEFAULTS):
    """Every reason a new paper entry is not allowed right now. Empty list = allowed. ctx keys:
    feed_realtime, feed_complete, quote_age_s, bar_age_s, control, now_m, city_pnl_today, account_pnl_today, start_equity,
    open_positions, exposure, daytrade_count, equity, side, sym_open, sym_traded_today, paper_verified, market_open"""
    R, F = cfg['risk'], cfg['feed']; b = []
    if not ctx.get('paper_verified'): b.append('paper account not verified')
    if not ctx.get('market_open'): b.append('market closed')
    if F['require_realtime_sip'] and not (ctx.get('feed_realtime') and ctx.get('feed_complete')):
        b.append('feed is ' + ('delayed' if not ctx.get('feed_realtime') else 'partial (one exchange)') + ': entries need real-time full-market (SIP) data')
    qa, ba = ctx.get('quote_age_s'), ctx.get('bar_age_s')
    if qa is None or qa > F['max_quote_age_s']: b.append('quote stale or missing' + (f' ({qa:.0f}s old)' if qa is not None else ''))
    if ba is None or ba > F['max_bar_age_s']: b.append('price bars stale' + (f' ({ba:.0f}s old)' if ba is not None else ''))
    c = ctx.get('control', 'on')
    if c != 'on': b.append(f'entries paused by control.json ({c})')
    m = ctx.get('now_m', 0)
    if not (hhmm(R['entries_from']) <= m < hhmm(R['entries_until'])): b.append(f"outside entry hours {R['entries_from']}-{R['entries_until']} ET")
    se = ctx.get('start_equity') or ctx.get('equity') or 0
    lim = se * R['max_daily_loss_pct'] / 100
    if ctx.get('city_pnl_today', 0) <= -lim or ctx.get('account_pnl_today', 0) <= -lim:
        b.append(f'daily loss lockout (limit -${lim:,.2f})')
    if ctx.get('open_positions', 0) >= R['max_open_positions']: b.append(f"max open positions ({R['max_open_positions']})")
    if ctx.get('exposure', 0) >= se * R['max_exposure_pct'] / 100: b.append('max exposure reached')
    if (ctx.get('equity') or 0) < 25000 and ctx.get('daytrade_count', 0) >= R['max_day_trades']:
        b.append(f"day-trade limit: {ctx.get('daytrade_count')} day trades in 5 days (account under $25K)")
    if ctx.get('side', 1) < 0 and not R['allow_short_orders']: b.append('short orders are off (bearish setups are watch-only)')
    if ctx.get('sym_open'): b.append('already holding this stock (no adding / averaging down)')
    if R['one_entry_per_symbol_per_day'] and ctx.get('sym_traded_today'): b.append('already traded this stock today')
    return b

def limit_price(side, bid, ask, cfg=DEFAULTS):
    off = cfg['risk']['limit_offset_pct'] / 100
    p = ask * (1 + off) if side > 0 else bid * (1 - off)
    return round(p, 4 if p < 1 else 2)

# ------------------------------------------------------------------ whole-market candidate lists (same code live and in replay)
def candidate_lists(rows, daily, m, cfg=DEFAULTS):
    """rows: {sym: dict(px, chg, v, dv, rv, hi, lo)} from the whole-market snapshot. Returns {list_name: [syms]}.
    A stock can be on a list (worth watching) without being allowed to trade."""
    C = cfg['candidates']; mind = C['min_today_dollar_volume_pre'] if m < RTH_OPEN else C['min_today_dollar_volume_rth']
    lists = {k: [] for k in ('gainers', 'decliners', 'unusual_volume', 'new_highs', 'new_lows', 'near_levels')}
    near = C['near_level_pct'] / 100
    for s, r in rows.items():
        if r['dv'] < mind: continue
        d = daily[s]
        if r['chg'] >= C['move_pct']: lists['gainers'].append(s)
        if r['chg'] <= -C['move_pct']: lists['decliners'].append(s)
        if r['rv'] and r['rv'] >= C['unusual_rvol']: lists['unusual_volume'].append(s)
        if r['hi'] and r['hi'] > d['high20']: lists['new_highs'].append(s)
        if r['lo'] and r['lo'] < d['low20']: lists['new_lows'].append(s)
        if any(abs(r['px'] / L - 1) <= near for L in (d['prior_high'], d['prior_low'], d['high20'], d['low20']) if L) and (r['rv'] or 0) >= 1.5:
            lists['near_levels'].append(s)
    return lists

def prerank(syms, rows):
    """cheap order for choosing which candidates get the full minute-by-minute analysis"""
    return sorted(syms, key=lambda s: -(min(rows[s]['rv'] or 0, 20) * 2 + math.log10(max(rows[s]['dv'], 1)) + min(abs(rows[s]['chg']), 30) * 0.1))

# ------------------------------------------------------------------ fees (Alpaca: $0 commission; regulatory fees on sales)
def sec_rate(d):
    if d < date(2025, 5, 14): return 27.80e-6
    if d < date(2026, 4, 4): return 0.0
    return 20.60e-6

def taf(d):
    if d.year <= 2025: return 0.000166, 8.30
    if d.year == 2026: return 0.000195, 9.79
    return 0.000232, 11.61

def sale_fees(d, shares, price):
    r, mx = taf(d)
    return round(shares * price * sec_rate(d) + min(mx, shares * r), 4)

# ------------------------------------------------------------------ simulated fills (replay)
def sim_limit_fill(side, limit, bars_after, max_participation=0.10, max_wait_bars=1):
    """Fills a marketable limit only if a later bar trades through it, at no better than the limit; size capped at a share of
    that bar's volume (partial fills). Returns (filled_shares_cap, price, bar) or (0, None, None) = failed fill."""
    for b in bars_after[:max_wait_bars]:
        if (side > 0 and b.l <= limit) or (side < 0 and b.h >= limit):
            px = min(limit, max(b.o, b.l)) if side > 0 else max(limit, min(b.o, b.h))
            return int(b.v * max_participation), px, b
    return 0, None, None

def sim_exit(side, stop, target, bars_after, flat_m, slip):
    """Walks bars after entry. A gap through the stop fills at the open (worse), never at the stop. Stop is checked
    before target inside a bar (worst case). Missing minutes (possible halt) are handled the same way: next available open."""
    for b in bars_after:
        if b.m >= flat_m: return b.o - side * slip * b.o, b, 'time'
        if side > 0:
            if b.o <= stop: return b.o * (1 - slip), b, 'stop-gap'
            if b.l <= stop: return stop * (1 - slip), b, 'stop'
            if b.h >= target: return target * (1 - slip), b, 'target'
        else:
            if b.o >= stop: return b.o * (1 + slip), b, 'stop-gap'
            if b.h >= stop: return stop * (1 + slip), b, 'stop'
            if b.l <= target: return target * (1 + slip), b, 'target'
    if bars_after: b = bars_after[-1]; return b.c * (1 - side * slip), b, 'last-bar'
    return None, None, 'no-data'

# ------------------------------------------------------------------ news
CATS = [('EARNINGS', r'\bearnings\b|quarterly results|\bq[1-4]\b.*results|revenue|\beps\b|guidance|fiscal (year|quarter)'),
        ('REGULATORY', r'\bfda\b|approv|clearance|\bema\b|breakthrough (therapy )?designation|orphan drug|\bpdufa\b|\bcrl\b|complete response letter|510\(k\)'),
        ('TRIAL', r'phase (1|2|3|i{1,3})\b|clinical trial|topline|data readout|primary endpoint|enrollment|positive (results|data)|statistically significant'),
        ('PRODUCT', r'\blaunch|unveil|introduces|commercial(ly)? available|first commercial|first shipment|receives? .{0,30}\border\b|record (revenue|sales|orders)'),
        ('PATENT', r'\bpatent'),
        ('CONTRACT', r'\bcontract\b|awarded|\baward\b|purchase order|\bdod\b|department of|government order|supply agreement'),
        ('DEAL', r'merger|acquisi|to acquire|buyout|takeover|definitive agreement|tender offer'),
        ('PARTNERSHIP', r'partnership|collaborat|strategic alliance|joint venture|licens(e|ing) agreement'),
        ('ANALYST', r'upgrade|downgrade|price target|initiates coverage|reiterat|overweight|underweight|outperform'),
        ('OFFERING', r'\boffering\b|registered direct|private placement|at-the-market|\batm\b program|priced .* shares|shelf registration'),
        ('CONVERTIBLE', r'convertible'), ('WARRANTS', r'\bwarrants?\b'),
        ('REVERSE_SPLIT', r'reverse (stock )?split|share consolidation'),
        ('COMPLIANCE', r'nasdaq.*(notice|deficien|compliance|delist)|minimum bid|non-?compliance|delist'),
        ('GOING_CONCERN', r'going concern|substantial doubt'), ('BANKRUPTCY', r'bankrupt|chapter 11|chapter 7'),
        ('FINANCING', r'financing|credit facility|loan agreement|raises \$|funding round')]
NEGATIVE = {'OFFERING', 'CONVERTIBLE', 'WARRANTS', 'REVERSE_SPLIT', 'COMPLIANCE', 'GOING_CONCERN', 'BANKRUPTCY'}
PROMO = r'if you invested|could soar|to buy now|stocks to buy|top \d+ stocks|millionaire|don.t miss|next (nvidia|tesla|amazon)|skyrocket|massive upside|hot stock|penny stocks? to watch|motley fool|why .* stock is (up|down|soaring|falling) today'
ROUNDUP = r'stocks moving|movers|top gainers|top losers|biggest movers|stocks to watch|mid-?day update|market update|premarket session|session\b.*(gainers|losers)|here.s why|these stocks|shares are trading (higher|lower)'
RUMOR = r'reportedly|rumou?r|according to (people|sources)|said to be|in talks|could be|may be considering|speculat|unconfirmed|social media|reddit|stocktwits|twitter|\bx post\b'

def norm_headline(h):
    return ' '.join(re.sub(r'[^a-z0-9 ]', ' ', (h or '').lower()).split()[:14])

@lru_cache(maxsize=20000)
def classify(headline, summary='', n_symbols=1):
    txt = f"{headline} {summary}".lower(); hl = (headline or '').lower()
    types = [n for n, rx in CATS if re.search(rx, hl)] or [n for n, rx in CATS if re.search(rx, txt)]
    promo = bool(re.search(PROMO, txt)); roundup = bool(re.search(ROUNDUP, hl)) or n_symbols > 4
    rumor = bool(re.search(RUMOR, txt))
    neg = [t for t in types if t in NEGATIVE]
    conf = 'low' if (promo or roundup or rumor) else 'high' if types else 'medium'
    return dict(types=types, negative=neg, promo=promo, roundup=roundup, rumor=rumor, confidence=conf)

def group_news(items, now_ts, prior_close_ts, stale_h=24):
    """items: dict(id, t(epoch), received(epoch), h, s, u, sy, sm). Groups repeats of the same story, tags each group."""
    groups = {}
    for it in sorted(items, key=lambda x: x['t']):
        key = norm_headline(it['h'])
        g = groups.get(key)
        if g is None:
            c = classify(it['h'], it.get('sm', ''), len(it.get('sy') or []))
            g = groups[key] = dict(it, repeats=0, sources=[it.get('s')], **{k: (list(v) if isinstance(v, list) else v) for k, v in c.items()})
        else:
            g['repeats'] += 1; g['sy'] = sorted(set(g['sy']) | set(it.get('sy') or []))
            if it.get('s') not in g['sources']: g['sources'].append(it.get('s'))
    out = []
    for g in groups.values():
        age_h = (now_ts - g['t']) / 3600
        g['stale'] = age_h > stale_h or (prior_close_ts is not None and g['t'] < prior_close_ts - 6 * 3600)
        if g['stale'] and g['confidence'] == 'high': g['confidence'] = 'medium'
        g['verified'] = g['confidence'] == 'high' and not g['stale']
        out.append(g)
    return sorted(out, key=lambda x: -x['t'])

def catalyst_for(sym, groups):
    """The best news context for one stock. If nothing qualifies: verified=False and text 'no verified catalyst found'."""
    mine = [g for g in groups if sym in (g.get('sy') or [])]
    neg = sorted({n for g in mine if not g['stale'] for n in g['negative']})
    good = [g for g in mine if g['verified']]
    if good:
        g = good[0]
        return dict(verified=True, types=g['types'], negative=neg, headline=g['h'], source=g.get('s'), t=g['t'], url=g.get('u'), n=len(mine))
    return dict(verified=False, types=[], negative=neg, headline=None, text='no verified catalyst found', n=len(mine))

# ------------------------------------------------------------------ market context
SECTORS = {'XLK': 'Technology', 'XLF': 'Financials', 'XLE': 'Energy', 'XLV': 'Health care', 'XLY': 'Consumer disc.', 'XLP': 'Staples',
           'XLI': 'Industrials', 'XLB': 'Materials', 'XLU': 'Utilities', 'XLRE': 'Real estate', 'XLC': 'Communication'}
INDEXES = ['SPY', 'QQQ', 'IWM', 'DIA']

def market_context(etf, breadth):
    """etf: {sym: dict(chg_pct, above_vwap, t)}; breadth: dict(up, down, flat)"""
    idx = {s: etf[s] for s in INDEXES if s in etf}
    ups = sum(1 for v in idx.values() if v.get('chg_pct', 0) > 0.1); dns = sum(1 for v in idx.values() if v.get('chg_pct', 0) < -0.1)
    direction = 'up' if ups >= 3 else 'down' if dns >= 3 else 'mixed'
    sec = sorted(((s, SECTORS[s], etf[s]['chg_pct']) for s in SECTORS if s in etf and etf[s].get('chg_pct') is not None), key=lambda x: -x[2])
    tot = sum(breadth.values()) or 1
    vol = etf.get('VIXY', {}).get('chg_pct')
    return dict(direction=direction, indexes=idx, sectors=sec, breadth=dict(breadth, up_pct=round(breadth.get('up', 0) / tot * 100, 1)),
                volatility=dict(proxy='VIXY', chg_pct=vol, state=None if vol is None else 'rising' if vol > 2 else 'falling' if vol < -2 else 'steady'),
                events=None, events_note='no economic-calendar source is connected, so scheduled events are not shown')
