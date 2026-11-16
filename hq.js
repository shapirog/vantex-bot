/* VANTEX City HQ: the market-wide scanner, setups, news, paper positions, risk, health and replay, inside the City.
   Loaded by index.html after the City's own script. It only READS the JSON the City engine publishes to the live-city
   branch (and live-replay for replays). It holds no keys and cannot place orders.
   Every visual effect it adds to the City is driven by that data; with no fresh data the effects switch off. */
(() => {
'use strict';
const REPO = location.hostname.endsWith('github.io') ? location.hostname.split('.')[0] + '/' + (location.pathname.split('/')[1] || 'vantex-bot') : 'shapirog/vantex-bot';
const RAW = p => `https://raw.githubusercontent.com/${REPO}/${p}`;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
async function getJSON(p) { try { const r = await fetch(RAW(p) + '?t=' + Date.now(), { cache: 'no-store' }); return r.ok ? await r.json() : null } catch (e) { return null } }
const store = { get(k, d) { try { const v = localStorage.getItem('hq.' + k); return v == null ? d : JSON.parse(v) } catch (e) { return d } }, set(k, v) { try { localStorage.setItem('hq.' + k, JSON.stringify(v)) } catch (e) {} } };

/* ---------------- formatting ---------------- */
const px = v => v == null ? '–' : (v < 1 ? v.toFixed(4) : v.toFixed(2));
const pct = (v, d = 2) => v == null ? '–' : (v > 0 ? '+' : '') + v.toFixed(d) + '%';
const big = v => v == null ? '–' : v >= 1e9 ? (v / 1e9).toFixed(2) + 'B' : v >= 1e6 ? (v / 1e6).toFixed(2) + 'M' : v >= 1e3 ? (v / 1e3).toFixed(1) + 'K' : String(Math.round(v));
const money = v => v == null ? '–' : (v < 0 ? '-' : '') + '$' + Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const etTime = t => { if (t == null) return '–'; const d = typeof t === 'number' ? new Date(t * 1000) : new Date(t); return isNaN(d) ? '–' : d.toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit' }) };
const etFull = t => { const d = typeof t === 'number' ? new Date(t * 1000) : new Date(t); return isNaN(d) ? '–' : d.toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' ET' };
const ago = t => { if (!t) return '–'; const s = (Date.now() - new Date(t).getTime()) / 1000; return s < 90 ? Math.round(s) + 's ago' : s < 5400 ? Math.round(s / 60) + ' min ago' : s < 172800 ? Math.round(s / 3600) + ' h ago' : Math.round(s / 86400) + ' d ago' };
const mm = m => `${((Math.floor(m / 60) + 11) % 12) + 1}:${String(m % 60).padStart(2, '0')} ${m >= 720 ? 'PM' : 'AM'}`;
const STATUS = { confirmed: ['CONFIRMED', 'var(--call)'], developing: ['DEVELOPING', 'var(--vwap)'], extended: ['EXTENDED', '#ff9f43'], rejected: ['REJECTED', 'var(--put)'], watching: ['WATCHING', 'var(--dim)'] };
const chip = (s, side) => { const [t, c] = STATUS[s] || [String(s || '–').toUpperCase(), 'var(--dim)']; return `<span class="hq-chip" style="color:${c}">${t}${side ? (side > 0 ? ' · LONG' : ' · BEARISH') : ''}</span>` };
const catCell = c => { if (!c) return '–'; const pos = (c.verified ? c.types : []).filter(t => !c.negative.includes(t)); return [...pos.slice(0, 1).map(t => esc(t)), ...c.negative.slice(0, 1).map(t => `<span class="dn">${esc(t.replace('_', ' '))}</span>`)].join(' · ') || '–' };
const ok = v => v === true ? '<b class="hq-ok">✓</b>' : v === false ? '<b class="hq-no">✗</b>' : '<b class="hq-pend">…</b>';

/* ---------------- styles ---------------- */
const css = document.createElement('style');
css.textContent = `
.tabs{grid-template-columns:repeat(7,1fr)!important}
#p-hq .hq-strip{display:flex;flex-wrap:wrap;gap:4px 10px;font-size:10.5px;color:var(--dim);margin:0 0 8px}
#p-hq .hq-strip b{color:var(--ink);font-weight:600}
.hq-badge{font:700 9.5px var(--display);letter-spacing:.12em;padding:2px 7px;border-radius:99px;border:1px solid currentColor}
.hq-badge.live{color:var(--call)}.hq-badge.delayed{color:var(--vwap)}.hq-badge.stale,.hq-badge.off{color:var(--put)}.hq-badge.replay{color:var(--ema)}
.hq-nav{display:flex;gap:5px;overflow-x:auto;padding-bottom:6px;margin-bottom:8px;scrollbar-width:none}.hq-nav::-webkit-scrollbar{display:none}
.hq-nav button,.hq-btn{flex:none;background:rgba(12,10,40,.7);border:1px solid var(--line);color:var(--dim);border-radius:99px;padding:5px 11px;font:600 11px var(--mono);cursor:pointer}
.hq-nav button[aria-pressed=true]{color:var(--ink);border-color:var(--ema);box-shadow:0 0 10px rgba(77,216,255,.3)}
.hq-btn{color:var(--ink);border-radius:8px}.hq-btn:disabled{opacity:.45;cursor:default}
.hq-chip{font:700 9px var(--display);letter-spacing:.1em;padding:2px 6px;border-radius:99px;border:1px solid currentColor;white-space:nowrap}
.hq-ok{color:var(--call)}.hq-no{color:var(--put)}.hq-pend{color:var(--vwap)}
.hq-grid{display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
.hq-card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px;min-width:0}
.hq-card h4{margin:0 0 6px;font:700 11px var(--display);letter-spacing:.14em;color:var(--dim);display:flex;gap:8px;align-items:center}
.hq-card .hq-sym{font:700 16px var(--display);cursor:pointer}
.hq-row{display:flex;justify-content:space-between;gap:8px;padding:4px 0;border-bottom:1px solid rgba(120,110,255,.12);font-size:11.5px;font-variant-numeric:tabular-nums}.hq-row:last-child{border:0}
.hq-row span:first-child{color:var(--dim)}
.hq-meter{height:5px;border-radius:3px;background:rgba(255,255,255,.08);overflow:hidden;margin:6px 0}.hq-meter i{display:block;height:100%;background:linear-gradient(90deg,var(--violet),var(--ema))}
.hq-why{font-size:10.5px;color:var(--dim);line-height:1.5}
.hq-tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
.hq-table{border-collapse:collapse;width:100%;font-size:11px;font-variant-numeric:tabular-nums;white-space:nowrap}
.hq-table th{position:sticky;top:0;background:#0d0b2c;color:var(--dim);font-weight:600;text-align:left;padding:7px 8px;cursor:pointer;user-select:none}
.hq-table th[aria-sort]{color:var(--ema)}
.hq-table td{padding:6px 8px;border-top:1px solid rgba(120,110,255,.12)}
.hq-table tr.tap{cursor:pointer}.hq-table tr.tap:hover td{background:rgba(77,216,255,.06)}
.up{color:var(--call)}.dn{color:var(--put)}
.hq-checks{display:grid;gap:3px;font-size:11px;margin:6px 0}.hq-checks div{display:grid;grid-template-columns:16px 1fr;gap:4px}
.hq-checks em{font-style:normal;color:var(--dim)}
.hq-warn{font-size:10.5px;color:#ff9f43;margin:2px 0}
.hq-dec{margin-top:6px;padding:7px 8px;border-radius:8px;font-size:11px;line-height:1.5;border:1px solid var(--line)}
.hq-dec.hq-go{border-color:var(--call);background:rgba(61,255,168,.06)}.hq-dec.hq-hold{border-color:rgba(255,201,77,.6);background:rgba(255,201,77,.05)}
.hq-dec b{font:700 10px var(--display);letter-spacing:.12em}
.hq-news{display:grid;gap:6px}.hq-news .n{padding:8px;border:1px solid var(--line);border-radius:9px;background:var(--panel);font-size:11.5px;line-height:1.45}
.hq-news .n a{color:var(--ink)}.hq-news .n.low{opacity:.62}
.hq-tag{display:inline-block;font:600 9px var(--mono);padding:1px 5px;border-radius:4px;margin:2px 3px 0 0;border:1px solid var(--line);color:var(--dim)}
.hq-tag.neg{color:var(--put);border-color:rgba(255,61,113,.5)}.hq-tag.cat{color:var(--call);border-color:rgba(61,255,168,.4)}.hq-tag.low{color:var(--vwap);border-color:rgba(255,201,77,.4)}
.hq-sect{display:grid;grid-template-columns:110px 1fr 54px;gap:6px;align-items:center;font-size:11px;margin:3px 0}
.hq-sect .bar{height:6px;background:rgba(255,255,255,.06);border-radius:3px;position:relative}.hq-sect .bar i{position:absolute;top:0;bottom:0;border-radius:3px}
.hq-chart{position:fixed;z-index:14;left:0;right:0;bottom:0;max-height:calc(100dvh - 60px);overflow-y:auto;background:#09081e;isolation:isolate;border-top:1px solid var(--violet);
  padding:12px max(16px,env(safe-area-inset-right)) calc(env(safe-area-inset-bottom) + 16px) max(16px,env(safe-area-inset-left));box-shadow:0 -10px 40px rgba(0,0,0,.6)}
.hq-chart[hidden]{display:none}
@media(min-width:900px){.hq-chart{left:auto;top:0;width:560px;max-height:none;border-top:0;border-left:1px solid var(--violet)}}
.hq-chart header{display:flex;align-items:center;gap:10px;margin-bottom:6px}.hq-chart header h3{margin:0;font:700 22px var(--display)}.hq-chart header button{margin-left:auto}
#hqCv{width:100%;height:300px;display:block;margin-top:6px;background:#09081e}
.hq-ctl{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:11px;color:var(--dim)}
.hq-ctl input{width:44px;background:#0d0b2c;border:1px solid var(--line);color:var(--ink);border-radius:6px;padding:3px 5px;font:inherit}
.hq-leg{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:10px;color:var(--dim);margin-top:4px}.hq-leg i{display:inline-block;width:12px;height:2px;margin-right:4px;vertical-align:middle}
.hq-empty{padding:16px;text-align:center;color:var(--dim);font-size:12px;border:1px dashed var(--line);border-radius:10px}
.hq-play{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.hq-play input[type=range]{flex:1;min-width:160px}
.hq-play select,.hq-in{background:#0d0b2c;border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:5px 8px;font:inherit;font-size:12px}
/* the City itself */
#hqOverlay{position:absolute;inset:0;pointer-events:none}
#hqSky{position:absolute;left:0;right:0;top:0;height:46%;opacity:0;transition:opacity 2s,background 2s;mix-blend-mode:screen}
#hqBeam{position:absolute;width:.5%;transform:translateX(-50%);opacity:0;transition:opacity .8s;mix-blend-mode:screen;border-radius:50% 50% 0 0;
  background:linear-gradient(to top,#fff 0%,var(--hqc,#8b7bff) 6%,color-mix(in srgb,var(--hqc,#8b7bff) 60%,transparent) 55%,transparent 100%);box-shadow:0 0 .6cqw var(--hqc,#8b7bff)}
#hqBeam.on{opacity:1;animation:hqflick 2.6s ease-in-out infinite}@keyframes hqflick{50%{opacity:.7}}
#hqLbl{position:absolute;pointer-events:auto;cursor:pointer;transform:translate(-50%,-100%);background:#09091a;border:.12cqw solid var(--hqc,#8b7bff);border-radius:.35cqw;
  padding:.35cqw .7cqw;text-align:center;font:700 .95cqw/1.2 "Chakra Petch",system-ui,sans-serif;color:#e9e7ff;box-shadow:0 0 .55cqw color-mix(in srgb,var(--hqc,#8b7bff) 55%,transparent);white-space:nowrap}
#hqLbl small{display:block;font:600 .7cqw/1.3 "JetBrains Mono",monospace;color:#9a96cf}
#hqLbl.flash{animation:hqnews 1.2s ease-out 3}@keyframes hqnews{30%{box-shadow:0 0 1.8cqw #ffc94d;border-color:#ffc94d}}
#hqLbl:focus-visible{outline:2px solid #4dd8ff;outline-offset:2px}
@media (prefers-reduced-motion:reduce){#hqBeam.on,#hqLbl.flash{animation:none}}
`;
document.head.appendChild(css);

/* ---------------- DOM: tab, pane, chart drawer, City overlay ---------------- */
const tabs = $('tabs');
const tabBtn = document.createElement('button');
tabBtn.id = 'hqTab'; tabBtn.type = 'button';
tabBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 12l6-4"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/><path d="M12 3v3M21 12h-3"/></svg>HQ';
tabs.appendChild(tabBtn);

const pane = document.createElement('section');
pane.className = 'pane'; pane.id = 'p-hq'; pane.hidden = true; pane.setAttribute('aria-label', 'Market HQ');
const VIEWS = [['radar', 'Radar'], ['scanner', 'Scanner'], ['long', 'Long setups'], ['bear', 'Bearish setups'], ['news', 'News & context'], ['positions', 'Paper positions'],
  ['risk', 'Risk controls'], ['history', 'Trade history'], ['health', 'Data & health'], ['replay', 'Replay']];
pane.innerHTML = `<h2>MARKET HQ</h2><div class="hq-strip" id="hqStrip">Loading…</div>
  <div class="hq-nav" role="group" aria-label="HQ sections">${VIEWS.map(([k, t]) => `<button type="button" data-hq="${k}" aria-pressed="false">${t}</button>`).join('')}</div>
  <div id="hqBody"></div>`;
document.body.appendChild(pane);

const drawer = document.createElement('section');
drawer.className = 'hq-chart'; drawer.id = 'hqChart'; drawer.hidden = true; drawer.setAttribute('role', 'dialog'); drawer.setAttribute('aria-labelledby', 'hqcSym');
drawer.innerHTML = `<header><h3 id="hqcSym">–</h3><span id="hqcChip"></span><button type="button" class="hq-btn" id="hqcClose">✕ Close</button></header>
  <div class="hq-why" id="hqcName"></div>
  <div class="hq-ctl" style="margin-top:6px"><span>Candles</span><button type="button" class="hq-btn" data-tf="1">1-min</button><button type="button" class="hq-btn" data-tf="5">5-min</button>
    <button type="button" class="hq-btn" id="hqcRth">Regular hours only</button><span style="margin-left:6px">EMAs</span><input id="hqcE1" inputmode="numeric" aria-label="First moving average length"><input id="hqcE2" inputmode="numeric" aria-label="Second moving average length"></div>
  <canvas id="hqCv"></canvas>
  <div class="hq-leg" id="hqcLeg"></div>
  <div id="hqcInfo"></div>`;
document.body.appendChild(drawer);

const world = $('world');
const ov = document.createElement('div'); ov.id = 'hqOverlay';
const HQX = 1300, HQY = 788, IW = 2291, IH = 1230;                     // the round plaza on the river island, between the towers
ov.innerHTML = `<div id="hqSky"></div><div id="hqBeam" style="left:${HQX / IW * 100}%;top:2%;height:${(HQY - 25) / IH * 100 - 2}%"></div>
  <div id="hqLbl" role="button" tabindex="0" style="left:${HQX / IW * 100}%;top:${(HQY - 10) / IH * 100}%" aria-label="Open Market HQ">MARKET HQ<small id="hqL1">connecting…</small><small id="hqL2"></small></div>`;
if (world) world.appendChild(ov);

/* ---------------- state ---------------- */
let CITY = null, NEWS = null, CHARTS = null, EVENTS = null, HIST = null, COV = null;
let view = store.get('view', 'radar'), open = false, chartSym = null, tf = store.get('tf', 1), rthOnly = store.get('rth', false);
let emas = store.get('emas', null);
let sortKey = store.get('sort', 'score'), sortDir = store.get('dir', -1), statusFilter = 'all', newsFilter = 'all';
const RP = { idx: null, day: null, data: null, i: 0, playing: false, speed: 2, timer: null, on: false, evalDev: null, evalTest: null };
const seenNews = new Set();

const fresh = () => CITY && !CITY.idle && (Date.now() - new Date(CITY.updated).getTime()) < 180000;
const delayed = () => CITY && CITY.feed && !CITY.feed.realtime;

/* ---------------- loading ---------------- */
async function loadCity() {
  const c = await getJSON('live-city/city.json');
  if (c) {
    const firstLoad = !CITY; CITY = c;
    // a NEW verified catalyst on a candidate makes the HQ label flash; nothing else does
    let flash = false;
    (c.candidates || []).forEach(r => { const k = r.catalyst && r.catalyst.verified && r.sym + '|' + r.catalyst.headline; if (k && !seenNews.has(k)) { seenNews.add(k); if (!firstLoad) flash = true } });
    if (flash && !RP.on) { const l = $('hqLbl'); l.classList.remove('flash'); void l.offsetWidth; l.classList.add('flash') }
  }
  paintCity(); if (open) render();
}
async function loadFor(v) {
  if (v === 'news' || v === 'radar') NEWS = (await getJSON('live-city/news.json')) || NEWS;
  if (v === 'history' || v === 'positions') { EVENTS = (await getJSON('live-city/events.json')) || EVENTS; HIST = (await getJSON('live-city/history.json')) || HIST }
  if (v === 'health' && !COV) COV = await getJSON('live-city/coverage.json');
  if (v === 'replay' && !RP.idx) { RP.idx = await getJSON('live-replay/index.json'); RP.evalDev = await getJSON('live-replay/eval_dev.json'); RP.evalTest = await getJSON('live-replay/eval_test.json') }
}

/* ---------------- the City overlay: only real state drives it ---------------- */
function paintCity() {
  const beam = $('hqBeam'), sky = $('hqSky'), lbl = $('hqLbl'), l1 = $('hqL1'), l2 = $('hqL2');
  if (!beam) return;
  let color = '#8b7bff', on = false, line1 = 'offline: no recent data', line2 = '', breadth = null;
  if (RP.on && RP.data) {
    const f = RP.data.frames[RP.i]; if (f) {
      const conf = f.top.filter(r => r.st === 'confirmed'), dev = f.top.filter(r => r.st === 'developing');
      on = true; color = conf.some(r => r.side > 0) ? '#3dffa8' : conf.length ? '#ff3d71' : dev.length ? '#ffc94d' : '#8b7bff';
      line1 = `REPLAY ${RP.data.day} ${mm(f.m)}`; line2 = `${conf.length} confirmed · ${dev.length} developing · ${f.pos.length} pos`;
      const b = f.breadth || {}; const t = (b.up || 0) + (b.down || 0) + (b.flat || 0); breadth = t ? (b.up || 0) / t * 100 : null;
    }
  } else if (fresh()) {
    const C = CITY.candidates || [];
    const confL = C.filter(r => r.long && r.long.status === 'confirmed'), confB = C.filter(r => r.bear && r.bear.status === 'confirmed');
    const dev = C.filter(r => r.status === 'developing');
    const stale = CITY.health && CITY.health.stale;
    on = !stale && (CITY.session === 'premarket' || CITY.session === 'regular' || CITY.session === 'afterhours');
    color = stale ? '#ff3d71' : confL.length ? '#3dffa8' : confB.length ? '#ff3d71' : dev.length ? '#ffc94d' : '#8b7bff';
    const np = (CITY.risk && CITY.risk.open_positions || []).length;
    line1 = stale ? 'DATA STALE: entries off' : `${(CITY.coverage && CITY.coverage.eligible || 0).toLocaleString()} stocks · ${CITY.session}`;
    line2 = `${confL.length + confB.length} confirmed · ${dev.length} developing` + (np ? ` · ${np} paper pos` : '');
    breadth = CITY.context && CITY.context.breadth && CITY.context.breadth.up_pct;
    if (delayed()) line1 += ' · delayed';
  } else if (CITY && CITY.idle) { line1 = 'closed: scanning resumes 4:00 AM ET' }
  ov.style.setProperty('--hqc', color); lbl.style.setProperty('--hqc', color); beam.style.setProperty('--hqc', color);
  beam.classList.toggle('on', on);
  l1.textContent = line1; l2.textContent = line2;
  lbl.title = 'Market HQ. Beam: on only while the engine is publishing fresh data. Green = a long setup confirmed, red = bearish confirmed or data stale, amber = setups developing, violet = scanning. Sky tint = market breadth.';
  if (breadth != null && (on || RP.on)) {
    const d = (breadth - 50) / 50; const c = d >= 0 ? '61,255,168' : '255,61,113';
    sky.style.background = `linear-gradient(to bottom, rgba(${c},.55), transparent)`; sky.style.opacity = Math.min(0.28, Math.abs(d) * 0.6).toFixed(3);
  } else sky.style.opacity = 0;
}

/* ---------------- pane open / close (works alongside the City's own tabs) ---------------- */
function openHQ(v) {
  open = true; if (v) view = v; store.set('view', view);
  document.querySelectorAll('.pane').forEach(p => { if (p !== pane) p.hidden = true });
  pane.hidden = false; const bb = $('boardBox'); if (bb) bb.style.display = 'none';
  tabs.querySelectorAll('button').forEach(b => b.removeAttribute('aria-current')); tabBtn.setAttribute('aria-current', 'page');
  render(true);
}
function closeHQ() { open = false; pane.hidden = true; tabBtn.removeAttribute('aria-current') }
tabs.addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; if (b === tabBtn) setTimeout(() => openHQ(), 0); else closeHQ() });
$('hqLbl').addEventListener('click', e => { e.stopPropagation(); openHQ('radar') });
$('hqLbl').addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openHQ('radar') } });
['pointerdown', 'mousedown', 'touchstart'].forEach(t => $('hqLbl').addEventListener(t, e => e.stopPropagation(), { passive: true }));
pane.querySelector('.hq-nav').addEventListener('click', e => { const b = e.target.closest('[data-hq]'); if (b) { view = b.dataset.hq; store.set('view', view); render(true) } });

/* ---------------- header strip ---------------- */
function strip() {
  const S = $('hqStrip');
  if (RP.on && RP.data) { const f = RP.data.frames[RP.i]; S.innerHTML = `<span class="hq-badge replay">REPLAY</span><span>Session <b>${RP.data.day}</b> at <b>${f ? mm(f.m) : '–'} ET</b></span><span>Historical data, minute by minute. Nothing here is live.</span><button type="button" class="hq-btn" id="hqExitRp">Back to live</button>`; return }
  if (!CITY) { S.innerHTML = '<span class="hq-badge off">NO DATA</span><span>The City engine has not published yet. It runs 4:00 AM to 8:00 PM ET on market days.</span>'; return }
  const H = CITY.health || {}, F = CITY.feed || {};
  const b = !fresh() ? '<span class="hq-badge off">OFFLINE</span>' : H.stale ? '<span class="hq-badge stale">STALE</span>' : F.realtime ? '<span class="hq-badge live">REAL-TIME</span>' : '<span class="hq-badge delayed">DELAYED 15 MIN</span>';
  S.innerHTML = `${b}<span>Session <b>${esc(CITY.session || '–')}</b></span><span>Feed <b>${esc(F.label || '–')}</b></span><span>Updated <b>${etTime(CITY.updated)}</b> (${ago(CITY.updated)})</span>` +
    (H.data_age_s != null ? `<span>Newest trade <b>${Math.round(H.data_age_s / 60)} min</b> old</span>` : '') +
    (CITY.coverage ? `<span>Universe <b>${(CITY.coverage.eligible || 0).toLocaleString()}</b> of ${(CITY.coverage.listed || 0).toLocaleString()} listed</span>` : '');
}
document.addEventListener('click', e => { if (e.target && e.target.id === 'hqExitRp') stopReplay() });

/* ---------------- views ---------------- */
async function render(load) {
  if (!open) return;
  pane.querySelectorAll('[data-hq]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.hq === view)));
  if (load) await loadFor(view);
  strip();
  const B = $('hqBody');
  const fn = { radar: vRadar, scanner: vScanner, long: () => vSetups(1), bear: () => vSetups(-1), news: vNews, positions: vPositions, risk: vRisk, history: vHistory, health: vHealth, replay: vReplay }[view] || vRadar;
  const keep = B.querySelector('.hq-tablewrap') ? B.querySelector('.hq-tablewrap').scrollLeft : 0;
  const active = document.activeElement && B.contains(document.activeElement) ? document.activeElement.id : null;
  const vals = {}; B.querySelectorAll('input[id],select[id]').forEach(i => { if (i.type !== 'range') vals[i.id] = i.value });
  const whyOut = $('hqWhyOut') ? $('hqWhyOut').innerHTML : '';
  B.innerHTML = fn();
  Object.entries(vals).forEach(([k, v]) => { if ($(k) && k !== 'hqRpDay') $(k).value = v });
  if ($('hqWhyOut') && whyOut) $('hqWhyOut').innerHTML = whyOut;
  const tw = B.querySelector('.hq-tablewrap'); if (tw) tw.scrollLeft = keep;
  if (active && $(active)) $(active).focus();
}
const noData = () => '<div class="hq-empty">No scanner data yet. The City engine publishes once a minute from 4:00 AM to 8:00 PM ET on market days.</div>';
const cands = () => (RP.on ? [] : (CITY && CITY.candidates) || []);

function vRadar() {
  if (RP.on) return vReplayFrame();
  if (!CITY || !CITY.candidates) return noData();
  const C = CITY.candidates.slice(0, 12);
  const top = Math.max(1, ...C.map(r => r.score));
  return contextCard(true) + `<p class="note">Ranked by developing setups with usable liquidity and confirmable price action, not by the biggest % gain. ${delayed() ? 'Prices and charts are 15 minutes delayed on this data plan.' : ''}</p>` +
    (C.length ? `<div class="hq-grid">${C.map(r => `<div class="hq-card"><h4><span class="hq-sym" data-sym="${esc(r.sym)}">${esc(r.sym)}</span>${chip(r.status, r.status === 'watching' ? 0 : r.side)}<span style="margin-left:auto" class="${r.f.chg_pct >= 0 ? 'up' : 'dn'}">${pct(r.f.chg_pct)}</span></h4>
      <div class="hq-why">${esc(r.name || '')}</div>
      <div class="hq-meter" title="Rank score ${r.score}"><i style="width:${Math.max(4, r.score / top * 100)}%"></i></div>
      <div class="hq-row"><span>Price</span><span>$${px(r.f.price)} · ${r.f.vwap_pos} VWAP</span></div>
      <div class="hq-row"><span>Rel. volume</span><span>${r.f.rvol != null ? r.f.rvol.toFixed(1) + 'x' : '–'} · ${esc(r.f.vol_trend || '–')}</span></div>
      <div class="hq-why">Why it ranks: ${r.why.map(esc).join(' · ')}</div>
      ${r.catalyst && r.catalyst.verified ? `<div class="hq-why">${r.catalyst.types.map(t => `<span class="hq-tag ${r.catalyst.negative.includes(t) ? 'neg' : 'cat'}">${esc(t.replace('_', ' '))}</span>`).join('')}${esc(r.catalyst.headline)}</div>` : '<div class="hq-why">No verified catalyst found</div>'}
      ${(r.catalyst && !r.catalyst.verified ? r.catalyst.negative : []).map(n => `<span class="hq-tag neg">${esc(n)}</span>`).join('')}
    </div>`).join('')}</div>` : '<div class="hq-empty">No candidates right now. Nothing on the market is moving with unusual volume.</div>');
}

const COLS = [['sym', 'Ticker'], ['price', 'Price'], ['chg', 'Change'], ['vol', 'Volume'], ['rvol', 'Rel vol'], ['vwap', 'VWAP'], ['spread', 'Spread'], ['cat', 'Catalyst'], ['flags', 'Risk flags'], ['time', 'Data time'], ['status', 'Status'], ['score', 'Rank']];
function val(r, k) {
  const f = r.f; return { sym: r.sym, price: f.price, chg: f.chg_pct, vol: f.volume, rvol: f.rvol ?? -1, vwap: f.vwap_ext_atr, spread: f.spread_pct ?? 99, cat: r.catalyst && r.catalyst.verified ? r.catalyst.types[0] || 'NEWS' : '',
    flags: flags(r).length, time: f.t, status: ['confirmed', 'developing', 'watching', 'extended', 'rejected'].indexOf(r.status), score: r.score }[k];
}
function flags(r) {
  const s = new Set([...(r.long.warnings || []), ...(r.bear.warnings || []), ...(r.data_warnings || [])].filter(w => !/delayed; spread from IEX/.test(w)));
  if (r.f.spread_pct == null) s.add('no real-time spread');
  return [...s];
}
function vScanner() {
  if (RP.on) return vReplayFrame();
  if (!CITY || !CITY.candidates) return noData();
  let C = cands().slice();
  if (statusFilter !== 'all') C = C.filter(r => r.status === statusFilter || (r.long.status === statusFilter) || (r.bear.status === statusFilter));
  C.sort((a, b) => { const x = val(a, sortKey), y = val(b, sortKey); return (x > y ? 1 : x < y ? -1 : 0) * sortDir });
  const lc = CITY.list_counts || {};
  return `<p class="note">${(CITY.health && CITY.health.candidates) || 0} candidates found across the whole market this minute (${Object.entries(lc).map(([k, v]) => `${k.replace('_', ' ')} ${v}`).join(', ')}). The top ${(CITY.health && CITY.health.deep_scan) || 0} get full minute-by-minute analysis; ${C.length} shown. Tap a row for its chart.</p>
  <div class="hq-nav" role="group" aria-label="Status filter">${['all', 'confirmed', 'developing', 'extended', 'rejected', 'watching'].map(s => `<button type="button" data-sf="${s}" aria-pressed="${statusFilter === s}">${s === 'all' ? 'All' : STATUS[s][0][0] + STATUS[s][0].slice(1).toLowerCase()}</button>`).join('')}</div>
  <div class="hq-tablewrap"><table class="hq-table"><thead><tr>${COLS.map(([k, t]) => `<th data-sort="${k}" ${sortKey === k ? `aria-sort="${sortDir > 0 ? 'ascending' : 'descending'}"` : ''} scope="col">${t}${sortKey === k ? (sortDir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr></thead><tbody>
  ${C.map(r => { const f = r.f, fl = flags(r); return `<tr class="tap" data-sym="${esc(r.sym)}"><td><b>${esc(r.sym)}</b></td><td>$${px(f.price)}</td><td class="${f.chg_pct >= 0 ? 'up' : 'dn'}">${pct(f.chg_pct)}</td>
    <td>${big(f.volume)}</td><td>${f.rvol != null ? f.rvol.toFixed(1) + 'x' : '–'}</td><td>${f.vwap_pos}${f.vwap_event ? ' · ' + f.vwap_event : ''}</td>
    <td>${f.spread_pct != null ? f.spread_pct.toFixed(2) + '%' : '–'}</td><td>${catCell(r.catalyst)}</td>
    <td title="${esc(fl.join('; '))}">${fl.length ? '<span style="color:#ff9f43">' + fl.length + ' ⚠</span> ' + esc(fl[0]).slice(0, 34) : '–'}</td><td>${etTime(f.t + 60)}${delayed() ? ' (delayed)' : ''}</td><td>${chip(r.status, r.status === 'watching' ? 0 : r.side)}</td><td>${r.score}</td></tr>` }).join('')}
  </tbody></table></div>`;
}

function vSetups(side) {
  if (RP.on) return vReplayFrame();
  if (!CITY || !CITY.candidates) return noData();
  const k = side > 0 ? 'long' : 'bear', order = ['confirmed', 'developing', 'extended', 'rejected'];
  const C = cands().filter(r => order.includes(r[k].status)).sort((a, b) => order.indexOf(a[k].status) - order.indexOf(b[k].status) || b.score - a.score);
  const P = (CITY.risk && CITY.risk.proposals) || [];
  const shortsOff = CITY.config && CITY.config.risk && !CITY.config.risk.allow_short_orders;
  const head = side > 0 ? '<p class="note">Breakouts need a close beyond the level, supporting volume for the time of day, a hold or retest, an acceptable spread, and VWAP/trend that don\'t contradict. Crossing VWAP, an EMA, a high or a low is never enough on its own.</p>'
    : `<p class="note">Breakdowns use the same confirmations, mirrored. ${shortsOff ? '<b>Short orders are off</b>, so bearish setups are warnings and watch candidates only.' : 'Short paper orders are ON in city_config.json.'}</p>`;
  if (!C.length) return head + `<div class="hq-empty">No ${side > 0 ? 'long' : 'bearish'} setups are developing right now.</div>`;
  return head + `<div class="hq-grid">${C.map(r => { const e = r[k], p = P.find(x => x.sym === r.sym && x.side === (side > 0 ? 'long' : 'bearish'));
    return `<div class="hq-card"><h4><span class="hq-sym" data-sym="${esc(r.sym)}">${esc(r.sym)}</span>${chip(e.status)}<span style="margin-left:auto">$${px(r.f.price)}</span></h4>
      ${e.level ? `<div class="hq-row"><span>Level</span><span>${esc((e.level_name || '').replace('_', ' '))} $${px(e.level)}</span></div>` : ''}
      ${e.stop ? `<div class="hq-row"><span>Invalidation / stop</span><span>$${px(e.stop)}</span></div><div class="hq-row"><span>Target</span><span>$${px(e.target)} (${CITY.config ? CITY.config.signals.target_r : 2}R)</span></div>` : ''}
      ${e.checks.length ? `<div class="hq-checks">${e.checks.map(c => `<div>${ok(c.ok)}<span>${esc(c.name)} <em>${esc(c.detail)}</em></span></div>`).join('')}</div>` : ''}
      ${e.warnings.map(w => `<div class="hq-warn">⚠ ${esc(w)}</div>`).join('')}
      ${(r.data_warnings || []).map(w => `<div class="hq-warn">⚠ ${esc(w)}</div>`).join('')}
      ${p ? decision(p) : `<div class="hq-dec hq-hold"><b>WAIT / NO TRADE</b><br>${esc(e.reasons.join('; ') || 'not confirmed')}</div>`}
    </div>` }).join('')}</div>`;
}
function decision(p) {
  const enter = p.decision === 'ENTER';
  return `<div class="hq-dec ${enter ? 'hq-go' : 'hq-hold'}"><b>${enter ? 'PAPER ORDER SENT' : 'WAIT / NO TRADE'}</b><br>
    <span class="hq-why">Thesis</span> ${esc(p.thesis)}<br>
    <span class="hq-why">Trigger</span> $${px(p.trigger)} · <span class="hq-why">limit</span> ${p.limit ? '$' + px(p.limit) : '–'} · <span class="hq-why">stop</span> $${px(p.stop)} · <span class="hq-why">target</span> $${px(p.target)} (${esc(p.target_logic)})<br>
    <span class="hq-why">Size</span> ${p.shares} shares · <span class="hq-why">risk</span> ${p.risk_dollars != null ? money(p.risk_dollars) : '–'} · <span class="hq-why">spread</span> ${p.spread_pct != null ? p.spread_pct.toFixed(2) + '%' : 'unknown'} · <span class="hq-why">data</span> ${etTime(p.data_time)}
    ${p.blocks && p.blocks.length ? '<br><span class="dn">Blocked: ' + p.blocks.map(esc).join('; ') + '</span>' : ''}
    ${p.order ? `<br>Broker: ${esc(p.order.status || '')} ${esc(p.order.message || '')}` : ''}</div>`;
}

function contextCard(compact) {
  const X = CITY && CITY.context; if (!X) return '';
  const idx = Object.entries(X.indexes || {}).map(([s, v]) => `<span><b>${s}</b> <span class="${v.chg_pct >= 0 ? 'up' : 'dn'}">${pct(v.chg_pct)}</span>${v.above_vwap == null ? '' : v.above_vwap ? ' ↑VWAP' : ' ↓VWAP'}</span>`).join(' · ');
  const br = X.breadth || {};
  const sec = (X.sectors || []);
  const mx = Math.max(0.5, ...sec.map(s => Math.abs(s[2])));
  return `<div class="hq-card" style="margin-bottom:8px"><h4>MARKET <span class="hq-chip" style="color:${X.direction === 'up' ? 'var(--call)' : X.direction === 'down' ? 'var(--put)' : 'var(--vwap)'}">${(X.direction || '–').toUpperCase()}</span></h4>
    <div class="hq-why" style="margin-bottom:4px">${idx}</div>
    <div class="hq-row"><span>Breadth (eligible stocks)</span><span><span class="up">${br.up || 0} up</span> · <span class="dn">${br.down || 0} down</span> · ${br.up_pct ?? '–'}% up</span></div>
    <div class="hq-row"><span>Volatility (${esc(X.volatility && X.volatility.proxy)})</span><span>${X.volatility && X.volatility.chg_pct != null ? pct(X.volatility.chg_pct) + ' · ' + X.volatility.state : 'unavailable'}</span></div>
    ${compact ? '' : `<div style="margin-top:6px">${sec.map(([s, n, c]) => `<div class="hq-sect"><span>${esc(n)}</span><span class="bar"><i style="${c >= 0 ? 'left:50%' : 'right:50%'};width:${Math.abs(c) / mx * 50}%;background:${c >= 0 ? 'var(--call)' : 'var(--put)'}"></i></span><span class="${c >= 0 ? 'up' : 'dn'}" style="text-align:right">${pct(c)}</span></div>`).join('')}</div>
    <div class="hq-why" style="margin-top:6px">Scheduled events: ${esc(X.events_note || 'unavailable')}.</div>`}
    <div class="hq-why">Index and sector data: ${delayed() ? '15-min delayed SIP' : 'real-time SIP'}, as of ${etTime(CITY.updated)}.</div></div>`;
}

function vNews() {
  if (RP.on) return vReplayFrame();
  let N = (NEWS && NEWS.items) || [];
  if (newsFilter === 'cat') N = N.filter(n => n.verified); else if (newsFilter === 'neg') N = N.filter(n => n.negative.length); else if (newsFilter === 'low') N = N.filter(n => n.confidence === 'low' || n.stale);
  return contextCard(false) + `<p class="note">Headlines from the only news source connected: ${esc((NEWS && NEWS.source) || 'Alpaca news')}. Repeats are grouped. Promotional, round-up, rumor and stale items are marked lower confidence. News is context, never an entry signal by itself.</p>
    <div class="hq-nav" role="group" aria-label="News filter">${[['all', 'All'], ['cat', 'Verified catalysts'], ['neg', 'Negative / dilutive'], ['low', 'Low confidence']].map(([k, t]) => `<button type="button" data-nf="${k}" aria-pressed="${newsFilter === k}">${t}</button>`).join('')}</div>
    <div class="hq-news">${N.slice(0, 120).map(n => { const low = n.confidence === 'low' || n.stale;
      return `<div class="n ${low ? 'low' : ''}"><div class="hq-why">${etFull(n.t)} · received ${etTime(n.received)}${n.received_note === 'at engine start' ? ' (engine start)' : ''} · ${esc((n.sources || [n.s]).join(', '))}${n.repeats ? ` · ${n.repeats + 1} versions` : ''}</div>
      ${n.u ? `<a href="${esc(n.u)}" target="_blank" rel="noopener">${esc(n.h)}</a>` : esc(n.h)}<div>
      ${(n.sy || []).slice(0, 6).map(s => `<span class="hq-tag" data-sym="${esc(s)}" style="cursor:pointer">${esc(s)}</span>`).join('')}
      ${n.types.filter(t => !n.negative.includes(t)).map(t => `<span class="hq-tag ${n.verified ? 'cat' : ''}">${esc(t)}</span>`).join('')}
      ${n.negative.map(t => `<span class="hq-tag neg">${esc(t.replace('_', ' '))}</span>`).join('')}
      ${n.promo ? '<span class="hq-tag low">PROMOTIONAL</span>' : ''}${n.roundup ? '<span class="hq-tag low">ROUND-UP</span>' : ''}${n.rumor ? '<span class="hq-tag low">RUMOR / UNCONFIRMED</span>' : ''}${n.stale ? '<span class="hq-tag low">STALE</span>' : ''}
      ${!n.types.length && !n.promo && !n.roundup ? '<span class="hq-tag">NO CATALYST TYPE</span>' : ''}</div></div>` }).join('') || '<div class="hq-empty">No headlines loaded.</div>'}</div>`;
}

function vPositions() {
  if (RP.on) return vReplayFrame();
  if (!CITY || !CITY.risk) return noData();
  const R = CITY.risk;
  const pos = R.open_positions || [], oo = R.open_orders || [], fills = R.fills || [];
  return `<p class="note">Paper account only. These are the City engine's own positions (orders tagged city-). The other Vantex bots trade the same paper account: they hold ${money(R.other_bots_exposure)} of stock.</p>
  <div class="hq-card"><h4>OPEN PAPER POSITIONS</h4>${pos.length ? pos.map(p => `<div class="hq-row"><span><b class="hq-sym" data-sym="${esc(p.sym)}">${esc(p.sym)}</b> ${p.qty > 0 ? 'long' : 'short'} ${Math.abs(p.qty)}</span><span>$${px(p.price)} · <span class="${p.unrealized >= 0 ? 'up' : 'dn'}">${money(p.unrealized)}</span></span></div>`).join('') : '<div class="hq-why">None.</div>'}</div>
  <div class="hq-card"><h4>WORKING ORDERS</h4>${oo.length ? oo.map(o => `<div class="hq-row"><span>${esc(o.sym)} ${esc(o.side)} ${esc(o.qty)} ${esc(o.type)}</span><span>${o.limit ? 'limit $' + esc(o.limit) : ''}${o.stop ? ' stop $' + esc(o.stop) : ''} · ${esc(o.status)}</span></div>`).join('') : '<div class="hq-why">None.</div>'}</div>
  <div class="hq-card"><h4>TODAY'S FILLS</h4>${fills.length ? fills.map(f => `<div class="hq-row"><span>${etTime(f.t)} ${esc(f.sym)} ${esc(f.side)} ${f.qty}</span><span>$${px(f.price)}</span></div>`).join('') : '<div class="hq-why">None.</div>'}</div>`;
}

function vRisk() {
  if (RP.on) return vReplayFrame();
  if (!CITY || !CITY.risk) return noData();
  const R = CITY.risk, L = R.limits || {}, used = Math.max(0, -(Math.min(R.city_pnl_today || 0, R.account_pnl_today || 0)));
  const blocks = R.entry_blocks || [];
  const edit = `https://github.com/${REPO}/edit/main/control.json`;
  return `<div class="hq-card"><h4>NEW ENTRIES <span class="hq-chip" style="color:${blocks.length ? 'var(--put)' : 'var(--call)'}">${blocks.length ? 'BLOCKED' : 'ALLOWED'}</span></h4>
    ${blocks.length ? blocks.map(b => `<div class="hq-warn">✗ ${esc(b)}</div>`).join('') : '<div class="hq-why">All account-level checks pass. Each setup still needs its own confirmations, quote and size.</div>'}</div>
  <div class="hq-card"><h4>PAUSE NEW ENTRIES</h4><div class="hq-row"><span>City control</span><b>${esc((CITY.control || 'on').toUpperCase())}</b></div>
    <p class="hq-why">The City reads <b>control.json</b> once a minute. This page is public and holds no keys, so the switch lives in your repo: open it and set <code>"city": "pause"</code> (no new entries, stops stay in place), <code>"city": "stop"</code> (close the City's paper positions) or <code>"city": "on"</code>. The other bots keep using <code>"trading"</code>.</p>
    <a class="hq-btn" style="display:inline-block;text-decoration:none" href="${edit}" target="_blank" rel="noopener">Open control.json to pause or resume ↗</a></div>
  <div class="hq-card"><h4>DAILY LOSS LOCKOUT</h4><div class="hq-row"><span>City P&L today</span><b class="${(R.city_pnl_today || 0) >= 0 ? 'up' : 'dn'}">${money(R.city_pnl_today)}</b></div>
    <div class="hq-row"><span>Whole paper account today</span><b class="${(R.account_pnl_today || 0) >= 0 ? 'up' : 'dn'}">${money(R.account_pnl_today)}</b></div>
    <div class="hq-meter"><i style="width:${Math.min(100, used / (R.daily_loss_limit || 1) * 100)}%;background:var(--put)"></i></div>
    <div class="hq-why">Entries lock at -${money(R.daily_loss_limit).replace('$', '$')} (${L.max_daily_loss_pct}% of start-of-day equity ${money(R.start_equity)}). ${R.locked ? '<b class="dn">LOCKED for today.</b>' : ''}</div></div>
  <div class="hq-card"><h4>LIMITS (city_config.json)</h4>
    ${[['Risk per trade', `${L.risk_per_trade_pct}% = ${money((R.start_equity || 0) * L.risk_per_trade_pct / 100)}`], ['Max daily loss', `${L.max_daily_loss_pct}%`], ['Max open positions', L.max_open_positions], ['Max exposure', `${L.max_exposure_pct}% of equity`],
      ['Max one position', `${L.max_position_pct}% of equity`], ['Entry hours (ET)', `${L.entries_from} – ${L.entries_until}`], ['Time stop', L.flat_at], ['Entry order', `limit at ask +${L.limit_offset_pct}%, cancelled after ${L.entry_timeout_s}s`],
      ['Short orders', L.allow_short_orders ? 'ON' : 'off (watch only)'], ['Day trades (5 days)', `${R.daytrade_count} of ${L.max_day_trades} allowed under $25K`],
      ['Sizing', 'shares = dollar risk ÷ stop distance; never from buying power; never larger after a loss'], ['Averaging down', 'never (one entry per stock per day)']].map(([a, b]) => `<div class="hq-row"><span>${a}</span><span style="text-align:right">${esc(b)}</span></div>`).join('')}</div>`;
}

function vHistory() {
  if (RP.on) return vReplayFrame();
  const T = ((HIST && HIST.trades) || []).slice().reverse();
  const E = ((EVENTS && EVENTS.events) || []).filter(e => ['order', 'no_trade', 'exit', 'order_cancel', 'trade_closed', 'control', 'engine_error', 'day_start'].includes(e.kind)).slice(-150).reverse();
  const tot = T.reduce((a, t) => a + t.pnl, 0);
  const line = e => e.kind === 'order' ? `<b class="up">ORDER</b> ${esc(e.side)} ${e.shares} ${esc(e.sym)} limit $${px(e.limit)} stop $${px(e.stop)} target $${px(e.target)} · ${esc(e.order && e.order.status || '')}`
    : e.kind === 'no_trade' ? `<b style="color:var(--vwap)">NO TRADE</b> ${esc(e.sym)} ${esc(e.side)}: ${esc((e.blocks || []).join('; '))}`
    : e.kind === 'exit' ? `<b>EXIT</b> ${esc(e.sym)} ${e.qty} (${esc(e.why)})` : e.kind === 'order_cancel' ? `<b class="dn">CANCEL</b> ${esc(e.sym)}: ${esc(e.reason)}, ${esc(e.result)}`
    : e.kind === 'trade_closed' ? `<b>CLOSED</b> ${esc(e.sym)} <span class="${e.pnl >= 0 ? 'up' : 'dn'}">${money(e.pnl)}</span>` : e.kind === 'day_start' ? `Day start: ${e.eligible} eligible of ${e.listed} listed · ${esc(e.feed && e.feed.label)}`
    : `${esc(e.kind)} ${esc(e.mode || e.error || '')}`;
  return `<div class="hq-card"><h4>CLOSED PAPER TRADES <span style="margin-left:auto" class="${tot >= 0 ? 'up' : 'dn'}">${money(tot)}</span></h4>
    ${T.length ? `<div class="hq-tablewrap"><table class="hq-table"><thead><tr><th>Day</th><th>Ticker</th><th>Side</th><th>Qty</th><th>Entry</th><th>Exit</th><th>Fees</th><th>P&L</th></tr></thead><tbody>
    ${T.map(t => `<tr><td>${t.day}</td><td>${esc(t.sym)}</td><td>${t.side}</td><td>${t.qty}</td><td>$${px(t.entry)}</td><td>$${px(t.exit)}</td><td>$${t.fees.toFixed(2)}</td><td class="${t.pnl >= 0 ? 'up' : 'dn'}">${money(t.pnl)}</td></tr>`).join('')}</tbody></table></div>` : '<div class="hq-why">No City paper trades yet.</div>'}</div>
  <div class="hq-card"><h4>TODAY'S DECISION LOG</h4><p class="hq-why">Every order, cancel, failed fill, exit and every confirmed setup that was not traded, with the reason.</p>
    ${E.length ? E.map(e => `<div class="hq-row" style="justify-content:flex-start"><span style="min-width:62px">${etTime(e.t)}</span><span>${line(e)}</span></div>`).join('') : '<div class="hq-why">Nothing logged yet today.</div>'}</div>`;
}

function vHealth() {
  if (RP.on) return vReplayFrame();
  if (!CITY) return noData();
  const H = CITY.health || {}, F = CITY.feed || {}, cv = CITY.coverage || {}, P = H.paper || {};
  const ex = cv.excluded_counts || {};
  return `<div class="hq-card"><h4>MARKET DATA</h4>
    ${[['Feed', F.label], ['Real time', F.realtime ? 'yes' : 'no: full-market prices are 15 minutes old'], ['Complete market', F.complete ? 'yes (all exchanges via SIP)' : 'no'],
      ['Spreads come from', F.realtime ? 'real-time SIP quotes' : 'IEX quotes only (one exchange, wider than the true market)'], ['Newest trade seen', H.data_age_s != null ? Math.round(H.data_age_s / 60) + ' min ago' : '–'],
      ['Stale', H.stale == null ? 'n/a (market closed)' : H.stale ? 'YES: new entries are off' : 'no'], ['Snapshot', H.snapshot ? `${H.snapshot.returned} of ${H.snapshot.requested} symbols (${H.snapshot.feed}), ${H.snapshot.no_data} without a price today` : '–'],
      ['Deep-scanned this minute', H.deep_scan], ['Cycle time', H.cycle_seconds != null ? H.cycle_seconds + 's' : '–'], ['Last update', CITY.updated ? etFull(CITY.updated) + ' (' + ago(CITY.updated) + ')' : '–']
    ].map(([a, b]) => `<div class="hq-row"><span>${a}</span><span style="text-align:right">${esc(b ?? '–')}</span></div>`).join('')}</div>
  <div class="hq-card"><h4>PAPER ACCOUNT CHECK</h4><div class="hq-row"><span>Verified paper account</span><b class="${P.verified ? 'up' : 'dn'}">${P.verified ? 'yes · …' + esc(P.account_suffix) : 'NO: ' + esc(P.reason || 'not checked')}</b></div>
    <div class="hq-why">Orders can only go to paper-api.alpaca.markets. The engine re-checks the paper account before every order.</div></div>
  <div class="hq-card"><h4>API CALLS / ERRORS</h4>${Object.entries(H.calls || {}).map(([k, v]) => `<div class="hq-row"><span>${esc(k)}</span><span>${v} calls · ${(H.errors || {})[k] || 0} errors · last ok ${H.last_ok && H.last_ok[k] ? etTime(H.last_ok[k]) : '–'}</span></div>`).join('')}
    ${(H.errors || {}).rate_limit ? `<div class="hq-warn">Rate-limited ${H.errors.rate_limit} times</div>` : ''}</div>
  <div class="hq-card"><h4>MARKET COVERAGE (${esc(cv.day || '')})</h4>
    <div class="hq-row"><span>Listed US equities at Alpaca</span><b>${(cv.listed || 0).toLocaleString()}</b></div><div class="hq-row"><span>Common stocks</span><b>${(cv.common_stocks || 0).toLocaleString()}</b></div>
    <div class="hq-row"><span>Eligible after filters</span><b>${(cv.eligible || 0).toLocaleString()}</b></div>
    ${Object.entries(ex).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<div class="hq-row"><span>Excluded: ${esc(k)}</span><span>${v.toLocaleString()}</span></div>`).join('')}
    <div style="margin-top:8px" class="hq-play"><input class="hq-in" id="hqWhy" placeholder="Why wasn't a stock scanned? e.g. AAPL" autocomplete="off" autocapitalize="characters" aria-label="Symbol to check"><button type="button" class="hq-btn" id="hqWhyGo">Check</button></div>
    <div id="hqWhyOut" class="hq-why" style="margin-top:6px"></div></div>
  <div class="hq-card"><h4>WHAT THE CITY SHOWS</h4><div class="hq-why">The Market HQ rotunda's beam is on only while the engine publishes fresh data: green = a long setup confirmed, red = a bearish setup confirmed or data stale, amber = setups developing, violet = scanning with nothing developing. The sky tint is market breadth (share of eligible stocks up on the day). The HQ sign flashes only when a new verified catalyst appears on a candidate. In replay, all of it follows the replayed session and the sign says REPLAY.</div></div>`;
}
async function whyScanned(sym) {
  sym = (sym || '').trim().toUpperCase(); const out = $('hqWhyOut'); if (!sym) return;
  if (!COV) COV = await getJSON('live-city/coverage.json');
  const ex = COV && COV.excluded && COV.excluded[sym];
  const c = (CITY.candidates || []).find(r => r.sym === sym);
  const lists = Object.entries(CITY.lists || {}).filter(([k, v]) => v.includes(sym)).map(([k]) => k.replace('_', ' '));
  out.innerHTML = ex ? `<b>${esc(sym)}</b> was excluded before scanning: ${esc(ex)}. (Data coverage or filter, see city_config.json.)`
    : c ? `<b>${esc(sym)}</b> is being deep-scanned right now: ${chip(c.status)} ${lists.length ? 'on lists: ' + esc(lists.join(', ')) : ''}`
    : lists.length ? `<b>${esc(sym)}</b> is a candidate (${esc(lists.join(', '))}) but ranked below the deep-scan cut this minute.`
    : COV && COV.excluded ? `<b>${esc(sym)}</b> is ${COV.excluded[sym] === undefined && !(CITY.coverage) ? 'unknown' : 'eligible and scanned every minute'}, but it is not moving or trading unusually enough to be a candidate right now. If it isn't listed at Alpaca at all, it can't be scanned.`
    : 'Coverage file not available yet.';
}

/* ---------------- replay ---------------- */
function vReplay() {
  const days = (RP.idx && RP.idx.days || []).slice().reverse();
  const ev = (E, t) => E ? `<div class="hq-card"><h4>EVALUATION · ${t}</h4><div class="hq-why" style="margin-bottom:6px">${esc(E.label)}</div>
    ${[['Sessions', E.sessions], ['Trades', E.trades], ['Net after costs', money(E.net_pnl)], ['Fees', money(E.fees)], ['Win rate', E.win_rate_pct != null ? E.win_rate_pct + '%' : '–'], ['Average R', E.avg_R],
      ['Max drawdown', money(E.max_drawdown)], ['Worst day', E.worst_day ? E.worst_day[0] + ' ' + money(E.worst_day[1]) : '–'], ['Worst 5 sessions', E.worst_5_sessions ? money(E.worst_5_sessions[0]) + ' from ' + E.worst_5_sessions[1] : '–'],
      ['Losing / winning days', `${E.losing_days} / ${E.winning_days}`], ['Avg position size', money(E.avg_exposure)]].map(([a, b]) => `<div class="hq-row"><span>${a}</span><span>${esc(b ?? '–')}</span></div>`).join('')}
    <div class="hq-why" style="margin-top:6px">By setup: ${Object.entries(E.by_setup || {}).map(([k, v]) => `${esc(k)} ${v.trades} trades ${money(v.pnl)}`).join(' · ') || '–'}</div>
    <div class="hq-why">R distribution: ${Object.entries(E.R_distribution || {}).map(([k, v]) => `${esc(k)} ${v}`).join(' · ') || '–'}</div>
    <div class="hq-why">Not traded: ${Object.entries(E.rejected_or_blocked || {}).slice(0, 8).map(([k, v]) => `${esc(k)} ${v}`).join(' · ') || '–'}</div>
    <div class="hq-warn">${esc(E.warning)} ${esc(E.note_pdt || '')}</div></div>` : '';
  return `<p class="note">Replay re-runs a past session minute by minute with the same rules as the live engine, using only what was known at each minute. Start a replay or an evaluation from GitHub Actions (Vantex City replay and evaluation).</p>
  <div class="hq-card"><h4>REPLAY A SESSION</h4>${days.length ? `<div class="hq-play"><select id="hqRpDay" aria-label="Session to replay">${days.map(d => `<option ${d === RP.day ? 'selected' : ''}>${d}</option>`).join('')}</select><button type="button" class="hq-btn" id="hqRpLoad">Load and watch</button></div>`
    : '<div class="hq-why">No replays yet. Run the workflow with mode = replay.</div>'}
    <a class="hq-btn" style="display:inline-block;text-decoration:none;margin-top:8px" href="https://github.com/${REPO}/actions/workflows/city-replay.yml" target="_blank" rel="noopener">Open the replay workflow ↗</a></div>
  ${ev(RP.evalDev, 'DEVELOPMENT PERIOD')}${ev(RP.evalTest, 'OUT-OF-SAMPLE')}`;
}
function vReplayFrame() {
  const D = RP.data, f = D && D.frames[RP.i]; if (!f) return '<div class="hq-empty">Loading replay…</div>';
  const evs = (D.events || []).filter(e => e.m <= f.m).slice(-12).reverse();
  const b = f.breadth || {};
  return `<div class="hq-card"><div class="hq-play"><button type="button" class="hq-btn" id="hqRpPlay">${RP.playing ? '❚❚ Pause' : '▶ Play'}</button>
    <select id="hqRpSpeed" aria-label="Replay speed">${[1, 2, 5, 15, 60].map(s => `<option value="${s}" ${s === RP.speed ? 'selected' : ''}>${s} min/sec</option>`).join('')}</select>
    <input type="range" id="hqRpPos" min="0" max="${D.frames.length - 1}" value="${RP.i}" aria-label="Replay position"><b>${mm(f.m)} ET</b></div>
    <div class="hq-row"><span>Breadth</span><span><span class="up">${b.up || 0} up</span> · <span class="dn">${b.down || 0} down</span></span></div>
    <div class="hq-row"><span>Candidate lists</span><span>${Object.entries(f.lists || {}).map(([k, v]) => `${k.replace('_', ' ')} ${v}`).join(' · ')}</span></div>
    <div class="hq-row"><span>Simulated P&L</span><b class="${f.pnl >= 0 ? 'up' : 'dn'}">${money(f.pnl)}</b></div>
    ${f.pos.map(p => `<div class="hq-row"><span>Position ${esc(p.sym)} ${p.side > 0 ? 'long' : 'short'} ${p.qty}</span><span>entry $${px(p.entry)} stop $${px(p.stop)}</span></div>`).join('')}</div>
  <div class="hq-tablewrap"><table class="hq-table"><thead><tr><th>Ticker</th><th>Price</th><th>Change</th><th>Rel vol</th><th>VWAP</th><th>Catalyst</th><th>Status</th><th>Why</th></tr></thead><tbody>
    ${f.top.map(r => `<tr class="tap" data-sym="${esc(r.sym)}"><td><b>${esc(r.sym)}</b></td><td>$${px(r.px)}</td><td class="${r.chg >= 0 ? 'up' : 'dn'}">${pct(r.chg)}</td><td>${r.rv != null ? r.rv.toFixed(1) + 'x' : '–'}</td><td>${r.vw}</td>
      <td>${r.cat && !r.neg.includes(r.cat) ? esc(r.cat) : r.neg.length ? '<span class="dn">' + esc(r.neg[0]) + '</span>' : '–'}</td><td>${chip(r.st, r.st === 'watching' ? 0 : r.side)}</td><td>${esc(r.why.join(' · '))}</td></tr>`).join('')}</tbody></table></div>
  <div class="hq-card" style="margin-top:8px"><h4>EVENTS SO FAR</h4>${evs.map(e => `<div class="hq-row" style="justify-content:flex-start"><span style="min-width:70px">${mm(e.m)}</span><span>${esc(e.kind)} ${esc(e.sym || '')} ${esc(e.side || e.why || '')} ${esc(e.status || '')} ${e.px ? '$' + px(e.px) : ''} ${e.pnl != null ? money(e.pnl) : ''} ${esc((e.reasons || []).join('; '))}</span></div>`).join('') || '<div class="hq-why">None yet.</div>'}</div>
  <div class="hq-card"><h4>NEWS KNOWN AT ${mm(f.m)}</h4>${(f.news || []).map(n => `<div class="hq-why">${etTime(n.t)} ${esc(n.h)} ${n.types.map(t => `<span class="hq-tag ${n.neg.includes(t) ? 'neg' : ''}">${esc(t)}</span>`).join('')}</div>`).join('') || '<div class="hq-why">None.</div>'}</div>`;
}
async function loadReplay(day) {
  const B = $('hqBody'); B.innerHTML = '<div class="hq-empty">Loading the replay…</div>';
  const d = await getJSON(`live-replay/replay/${day}.json`);
  if (!d || !d.frames || !d.frames.length) { B.innerHTML = '<div class="hq-empty">That replay could not be loaded.</div>'; return }
  RP.data = d; RP.day = day; RP.i = 0; RP.on = true; RP.playing = false; view = 'radar'; render(); paintCity();
}
function stopReplay() { RP.on = false; RP.playing = false; clearInterval(RP.timer); RP.timer = null; view = 'replay'; render(); paintCity() }
function tick() {
  if (!RP.on || !RP.playing) return;
  const f = RP.data.frames; const cur = f[RP.i].m, target = cur + RP.speed;
  let j = RP.i; while (j < f.length - 1 && f[j + 1].m <= target) j++;
  if (j === RP.i && RP.i < f.length - 1) j++;
  RP.i = j; if (RP.i >= f.length - 1) RP.playing = false;
  render(); paintCity(); if (chartSym) drawChart();
}
function setPlaying(p) { RP.playing = p; clearInterval(RP.timer); RP.timer = p ? setInterval(tick, 1000) : null; render() }

/* ---------------- events inside the pane ---------------- */
pane.addEventListener('click', e => {
  const s = e.target.closest('[data-sym]'); if (s) { openChart(s.dataset.sym); return }
  const th = e.target.closest('th[data-sort]'); if (th) { const k = th.dataset.sort; if (sortKey === k) sortDir = -sortDir; else { sortKey = k; sortDir = ['sym', 'spread', 'status', 'flags'].includes(k) ? 1 : -1 } store.set('sort', sortKey); store.set('dir', sortDir); render(); return }
  const sf = e.target.closest('[data-sf]'); if (sf) { statusFilter = sf.dataset.sf; render(); return }
  const nf = e.target.closest('[data-nf]'); if (nf) { newsFilter = nf.dataset.nf; render(); return }
  if (e.target.id === 'hqRpLoad') { loadReplay($('hqRpDay').value); return }
  if (e.target.id === 'hqRpPlay') { setPlaying(!RP.playing); return }
  if (e.target.id === 'hqWhyGo') { whyScanned($('hqWhy').value); return }
});
pane.addEventListener('change', e => {
  if (e.target.id === 'hqRpSpeed') { RP.speed = +e.target.value; return }
  if (e.target.id === 'hqRpPos') { RP.i = +e.target.value; render(); paintCity(); if (chartSym) drawChart() }
});
pane.addEventListener('input', e => { if (e.target.id === 'hqRpPos') { RP.i = +e.target.value; paintCity() } });
pane.addEventListener('keydown', e => {
  if (e.target.id === 'hqWhy' && e.key === 'Enter') whyScanned(e.target.value);
  const tr = e.target.closest && e.target.closest('tr.tap'); if (tr && e.key === 'Enter') openChart(tr.dataset.sym);
});

/* ---------------- ticker chart ---------------- */
async function openChart(sym) {
  chartSym = sym; drawer.hidden = false;
  if (!RP.on && (!CHARTS || !CHARTS.syms || !CHARTS.syms[sym] || Date.now() - (CHARTS._at || 0) > 55000)) { const c = await getJSON('live-city/charts.json'); if (c) { CHARTS = c; CHARTS._at = Date.now() } }
  if (!RP.on && !EVENTS) EVENTS = await getJSON('live-city/events.json');
  if (!emas) emas = (CITY && CITY.config && CITY.config.signals.chart_emas) || [9, 20];
  $('hqcE1').value = emas[0] || ''; $('hqcE2').value = emas[1] || '';
  drawChart(); drawer.querySelector('#hqcClose').focus();
}
function closeChart() { chartSym = null; drawer.hidden = true }
drawer.addEventListener('click', e => {
  if (e.target.id === 'hqcClose') closeChart();
  const t = e.target.closest('[data-tf]'); if (t) { tf = +t.dataset.tf; store.set('tf', tf); drawChart() }
  if (e.target.id === 'hqcRth') { rthOnly = !rthOnly; store.set('rth', rthOnly); drawChart() }
});
drawer.addEventListener('change', e => { if (e.target.id === 'hqcE1' || e.target.id === 'hqcE2') { emas = [+$('hqcE1').value || 0, +$('hqcE2').value || 0].filter(n => n > 1 && n < 400); store.set('emas', emas); drawChart() } });
addEventListener('keydown', e => { if (e.key === 'Escape' && !drawer.hidden) closeChart() });
const etMin = t => { const d = new Date(t * 1000); const p = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', minute: 'numeric', hourCycle: 'h23' }).formatToParts(d); return +p.find(x => x.type === 'hour').value * 60 + +p.find(x => x.type === 'minute').value };

function drawChart() {
  const sym = chartSym; if (!sym) return;
  let rows = null, row = null, frameM = null;
  if (RP.on && RP.data) { rows = (RP.data.charts || {})[sym]; const f = RP.data.frames[RP.i]; frameM = f && f.m; row = f && f.top.find(r => r.sym === sym) }
  else { rows = CHARTS && CHARTS.syms && CHARTS.syms[sym]; row = (CITY && CITY.candidates || []).find(r => r.sym === sym) }
  $('hqcSym').textContent = sym; $('hqcChip').innerHTML = row ? chip(row.status || row.st) : '';
  $('hqcName').textContent = RP.on ? `Replay ${RP.data.day}${frameM ? ' at ' + mm(frameM) + ' ET (bars after this minute hidden)' : ''}` : ((row && row.name) || '') + (CHARTS && CHARTS.delayed ? ' · chart data 15 minutes delayed' : '');
  drawer.querySelectorAll('[data-tf]').forEach(b => b.style.borderColor = +b.dataset.tf === tf ? 'var(--ema)' : '');
  $('hqcRth').style.borderColor = rthOnly ? 'var(--ema)' : '';
  const cv = $('hqCv'), dpr = Math.min(2, devicePixelRatio || 1), W = cv.clientWidth, H = cv.clientHeight;
  cv.width = W * dpr; cv.height = H * dpr; const g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
  if (!rows || !rows.length) { g.fillStyle = '#9a96cf'; g.font = '12px JetBrains Mono, monospace'; g.fillText(RP.on ? 'No chart saved for this stock in the replay.' : 'No chart data for this stock right now.', 12, 24); $('hqcInfo').innerHTML = info(sym, row); return }
  let B = rows.map(r => ({ t: r[0], m: etMin(r[0]), o: r[1], h: r[2], l: r[3], c: r[4], v: r[5] }));
  if (frameM != null) B = B.filter(b => b.m < frameM);
  if (rthOnly) B = B.filter(b => b.m >= 570 && b.m < 960);
  if (tf === 5) { const M = new Map(); B.forEach(b => { const k = Math.floor(b.m / 5) * 5, x = M.get(k); if (!x) M.set(k, { ...b, m: k }); else { x.h = Math.max(x.h, b.h); x.l = Math.min(x.l, b.l); x.c = b.c; x.v += b.v } }); B = [...M.values()] }
  if (!B.length) return;
  let pv = 0, vv = 0, ses = null; const vw = B.map(b => { const s = b.m >= 570 ? 'r' : 'p'; if (s !== ses) { pv = vv = 0; ses = s } pv += (b.h + b.l + b.c) / 3 * b.v; vv += b.v; return vv ? pv / vv : b.c });
  const emaL = (emas || []).map(n => { let e = null; const a = 2 / (n + 1); return B.map(b => e = e == null ? b.c : e + a * (b.c - e)) });
  const lv = row && row.f ? row.f.levels || {} : {};
  const ev = row && !RP.on ? [row.long, row.bear].filter(e => e && e.stop && ['confirmed', 'developing'].includes(e.status)) : [];
  let lo = Math.min(...B.map(b => b.l), ...ev.map(e => Math.min(e.stop, e.target))), hi = Math.max(...B.map(b => b.h), ...ev.map(e => Math.max(e.stop, e.target)));
  const pad = (hi - lo) * 0.08 || hi * 0.01; lo -= pad; hi += pad;
  const top = 8, ph = H * 0.72, vt = top + ph + 6, vh = H - vt - 14, left = 4, right = 52, cw = (W - left - right) / B.length;
  const y = p => top + (hi - p) / (hi - lo) * ph;
  g.strokeStyle = 'rgba(120,110,255,.12)'; g.fillStyle = '#9a96cf'; g.font = '10px JetBrains Mono, monospace'; g.lineWidth = 1;
  for (let k = 0; k <= 4; k++) { const p = lo + (hi - lo) * k / 4; g.beginPath(); g.moveTo(left, y(p)); g.lineTo(W - right, y(p)); g.stroke(); g.fillText(px(p), W - right + 4, y(p) + 3) }
  const vmax = Math.max(...B.map(b => b.v)) || 1;
  B.forEach((b, i) => { const x = left + i * cw + cw / 2, up = b.c >= b.o, col = up ? '#3dffa8' : '#ff3d71';
    g.fillStyle = up ? 'rgba(61,255,168,.35)' : 'rgba(255,61,113,.35)'; g.fillRect(x - Math.max(1, cw * 0.35), vt + vh - b.v / vmax * vh, Math.max(1, cw * 0.7), b.v / vmax * vh);
    g.strokeStyle = col; g.beginPath(); g.moveTo(x, y(b.h)); g.lineTo(x, y(b.l)); g.stroke();
    g.fillStyle = col; g.fillRect(x - Math.max(.5, cw * 0.35), Math.min(y(b.o), y(b.c)), Math.max(1, cw * 0.7), Math.max(1, Math.abs(y(b.o) - y(b.c)))) });
  const line = (arr, col, w, dash) => { g.strokeStyle = col; g.lineWidth = w; g.setLineDash(dash || []); g.beginPath(); arr.forEach((v, i) => { const x = left + i * cw + cw / 2; i ? g.lineTo(x, y(v)) : g.moveTo(x, y(v)) }); g.stroke(); g.setLineDash([]) };
  line(vw, '#ffc94d', 1.6); const ec = ['#4dd8ff', '#b88bff']; emaL.forEach((a, k) => line(a, ec[k % 2], 1.1, [5, 3]));
  const hline = (p, col, txt, dash) => { if (p == null || p < lo || p > hi) return; g.strokeStyle = col; g.setLineDash(dash || [2, 4]); g.lineWidth = 1; g.beginPath(); g.moveTo(left, y(p)); g.lineTo(W - right, y(p)); g.stroke(); g.setLineDash([]); g.fillStyle = col; g.fillText(txt, left + 4, y(p) - 3) };
  Object.entries(lv).forEach(([k, v]) => hline(v, 'rgba(233,231,255,.55)', k.replace('_', ' ')));
  ev.forEach(e => { hline(e.stop, '#ff3d71', 'stop', [6, 3]); hline(e.target, '#3dffa8', 'target', [6, 3]) });
  // signal annotations: when the engine logged a status change, an order or an exit for this stock
  const E = RP.on ? (RP.data.events || []).filter(e => e.sym === sym && e.m < (frameM || 9999)).map(e => ({ m: e.m, k: e.kind, s: e.status || e.side || e.why }))
    : ((EVENTS && EVENTS.events) || []).filter(e => e.sym === sym && ['signal', 'order', 'exit', 'no_trade'].includes(e.kind)).map(e => ({ m: etMin(new Date(e.t).getTime() / 1000), k: e.kind, s: e.status || e.decision || e.why }));
  E.forEach(e => { let i = B.findIndex(b => b.m >= (tf === 5 ? Math.floor(e.m / 5) * 5 : e.m - 1)); if (i < 0) return; const x = left + i * cw + cw / 2;
    const col = e.k === 'order' || e.k === 'entry' ? '#3dffa8' : e.k === 'exit' ? '#ffffff' : e.s === 'confirmed' ? '#4dd8ff' : e.k === 'no_trade' ? '#ffc94d' : '#ff9f43';
    g.fillStyle = col; g.beginPath(); g.moveTo(x, top + 2); g.lineTo(x - 4, top - 4 + 2); g.lineTo(x + 4, top - 4 + 2); g.fill(); g.strokeStyle = col; g.globalAlpha = .35; g.beginPath(); g.moveTo(x, top); g.lineTo(x, vt + vh); g.stroke(); g.globalAlpha = 1 });
  g.fillStyle = '#9a96cf'; [0, Math.floor(B.length / 2), B.length - 1].forEach(i => { const x = Math.min(W - right - 40, Math.max(left, left + i * cw - 14)); g.fillText(mm(B[i].m), x, H - 2) });
  $('hqcLeg').innerHTML = `<span><i style="background:#ffc94d"></i>VWAP</span>${(emas || []).map((n, k) => `<span><i style="background:${ec[k % 2]}"></i>EMA ${n}</span>`).join('')}<span><i style="background:rgba(233,231,255,.55)"></i>Key levels</span><span><i style="background:#ff3d71"></i>Stop</span><span><i style="background:#3dffa8"></i>Target / order</span><span>▼ signal / decision</span>`;
  $('hqcInfo').innerHTML = info(sym, row);
}
function info(sym, row) {
  if (!row) return '<p class="hq-why">Not in the current candidate list.</p>';
  if (RP.on) return `<div class="hq-why" style="margin-top:8px">${esc((row.why || []).join(' · '))}</div>`;
  const f = row.f, N = ((NEWS && NEWS.items) || []).filter(n => (n.sy || []).includes(sym)).slice(0, 6);
  const side = (e, t) => `<div class="hq-card"><h4>${t} ${chip(e.status)}</h4>${e.checks.map(c => `<div class="hq-checks"><div>${ok(c.ok)}<span>${esc(c.name)} <em>${esc(c.detail)}</em></span></div></div>`).join('')}${e.warnings.map(w => `<div class="hq-warn">⚠ ${esc(w)}</div>`).join('')}<div class="hq-why">${esc(e.reasons.join('; '))}</div></div>`;
  return `<div class="hq-card" style="margin-top:8px">${[['Price', '$' + px(f.price) + ' · ' + pct(f.chg_pct) + ' vs prior close $' + px(f.prior_close)], ['Premarket gap', pct(f.gap_pct)], ['Volume', big(f.volume) + ' shares · $' + big(f.dollar_volume)],
    ['Relative volume (time of day)', f.rvol != null ? f.rvol.toFixed(2) + 'x' : '–'], ['Spread', f.spread_pct != null ? f.spread_pct.toFixed(2) + '%' : 'no real-time quote'], ['VWAP', '$' + px(f.vwap) + ' · ' + f.vwap_pos + (f.vwap_event ? ' · ' + f.vwap_event : '') + ' · ' + f.vwap_ext_atr.toFixed(1) + ' ATR away'],
    ['Trend 1-min / 5-min', ['down', 'flat', 'up'][f.trend_1m + 1] + ' / ' + ['down', 'flat', 'up'][f.trend_5m + 1]], ['Opening range', f.or_high ? '$' + px(f.or_low) + ' – $' + px(f.or_high) : 'forms 9:30-9:35'], ['Day range', '$' + px(f.lod) + ' – $' + px(f.hod)],
    ['Volume with the move', f.vol_trend || '–'], ['Support / resistance', (f.support ? '$' + px(f.support) : '–') + ' / ' + (f.resistance ? '$' + px(f.resistance) : '–')], ['Market cap', row.market_cap ? '$' + big(row.market_cap) : 'unknown'], ['Data time', etFull(f.t + 60) + (CHARTS && CHARTS.delayed ? ' (delayed)' : '')]
  ].map(([a, b]) => `<div class="hq-row"><span>${a}</span><span style="text-align:right">${esc(b)}</span></div>`).join('')}</div>
  ${side(row.long, 'LONG')}${side(row.bear, 'BEARISH')}
  <div class="hq-card"><h4>NEWS</h4>${row.catalyst && row.catalyst.verified ? `<div class="hq-why"><span class="hq-tag cat">${esc(row.catalyst.types.join(', '))}</span>${esc(row.catalyst.headline)} · ${esc(row.catalyst.source)}</div>` : '<div class="hq-why">No verified catalyst found.</div>'}
    ${N.map(n => `<div class="hq-why">${etFull(n.t)} ${n.u ? `<a href="${esc(n.u)}" target="_blank" rel="noopener" style="color:var(--ink)">${esc(n.h)}</a>` : esc(n.h)} ${n.negative.map(t => `<span class="hq-tag neg">${esc(t)}</span>`).join('')}${n.confidence === 'low' ? '<span class="hq-tag low">LOW CONFIDENCE</span>' : ''}</div>`).join('')}</div>`;
}
new ResizeObserver(() => { if (chartSym) drawChart() }).observe(drawer);

/* ---------------- polling ---------------- */
loadCity(); setInterval(loadCity, 30000);
setInterval(async () => { if (open && !RP.on && ['news', 'history', 'positions'].includes(view)) { await loadFor(view); render() } if (chartSym && !RP.on) { const c = await getJSON('live-city/charts.json'); if (c) { CHARTS = c; CHARTS._at = Date.now(); drawChart() } } }, 60000);
setInterval(() => { if (!RP.on) paintCity(); if (open && !RP.on) strip() }, 15000);
})();
