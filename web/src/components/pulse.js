/* The pulse: one column per week over the last year (WEEKS); its height the weighted launches and releases of that week, its bands each
   sector's share. Hover or focus a week for its headline; select it for its events by sector, each linked to its source.
   A workspace panel (ui/panel.js): render(scope, el) for scope all, a taxonomy node, your stack or a maker. */
import { json } from '../lib/data.js';
import { esc, fd, host, MON, n, stamp, url } from '../lib/format.js';
import { columns } from '../lib/charts.js';
import { inScope, scopeControl, scopeName, stackToggle } from '../lib/scope.js';
import { ui } from '../ui/recipes.js';

const DAY = 864e5,
  WEEKS = 52 /* a rolling year: long enough to see a season, short enough that every column is a week you can read */,
  LANE = 15; /* one landmark label row */
/* sector bands in the published order: seven sectors, other sectors, not placed */
const FILL = ['fill-sector-1', 'fill-sector-2', 'fill-sector-3', 'fill-sector-4', 'fill-sector-5', 'fill-sector-6', 'fill-sector-7', 'fill-sector-other', 'fill-sector-other/40'];
const SW = [...ui.sector, 'bg-sector-other/40'];
const swatch = j => `<i class="inline-block size-2.5 shrink-0 rounded-[2px] ${SW[j]}" aria-hidden="true"></i>`;
const LINK = 'underline underline-offset-4 decoration-border hover:text-foreground';
const week = iso => `Week of ${fd(iso)}`;
const when = e =>
  e.precision === 'day' ? fd(e.at) : e.precision === 'month' ? `${MON[+e.at.slice(5, 7) - 1]} ${e.at.slice(0, 4)}, month-level date` : `${e.at}, year-level date`;

let P = null;
const load = () => json('pulse.json').then(d => (P = d));
const state = new WeakMap();

/* the published headline rule, applied to whatever is in scope: the most-read exactly named product, else the strongest source,
   else the weight; only full-weight events headline a week that has one */
function headline(list) {
  const R = P.source.params,
    rank = v => (R.source_rank.includes(v) ? R.source_rank.indexOf(v) : R.source_rank.length),
    full = list.filter(([i]) => P.events[i].w >= R.headline_min_weight),
    key = i => [P.events[i].views ?? -1, -rank(P.events[i].via), P.events[i].w];
  let best = null;
  for (const [i] of full.length ? full : list) {
    const k = key(i);
    if (!best || k[0] > best[1][0] || (k[0] === best[1][0] && (k[1] > best[1][1] || (k[1] === best[1][1] && k[2] > best[1][2])))) best = [i, k];
  }
  return best ? best[0] : null;
}

/* what an event is called on screen: a bare "Release" becomes the product and its version tag; any other title leads with its product */
const bare = e => e.title === 'Release';
const label = e => (bare(e) && e.name && e.url ? `${e.name} ${decodeURIComponent(e.url.split('/').pop())}` : e.name && !e.title.toLowerCase().includes(e.name.toLowerCase()) ? `${e.name}: ${e.title}` : e.title);
/* one dated event: what happened (linked to its source), how it is dated and where it was read, and the product it belongs to */
const row = e => `<li class="grid gap-1 py-2 border-b border-border last:border-b-0 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:gap-x-4">
      <span class="flex flex-col gap-1 min-w-0"><span class="text-sm text-foreground">${e.url ? `<a class="${LINK}" href="${url(e.url)}" target="_blank" rel="noopener noreferrer">${esc(label(e))}</a>` : esc(label(e))}</span>
      ${e.gist ? `<span class="text-sm leading-snug text-muted-foreground">${esc(e.gist)}</span>` : ''}
      <span class="${ui.panelNote}">${esc(e.what || e.via)} · ${esc(when(e))} · ${e.read ? `${esc(host(e.url))}, read ${stamp(e.read, P.source.built_for)}` : esc(host(e.url || ''))}${e.note ? ` · ${esc(e.note)}` : ''}</span></span>
      ${e.id ? `<span class="flex items-center gap-2"><a class="text-xs text-muted-foreground ${LINK}" href="#app=${esc(e.id)}">${esc(e.name || e.id)}</a>${stackToggle(e.id, e.name)}</span>` : '<span></span>'}</li>`;

function weeksIn(scope) {
  const all = !scope || scope.kind === 'all';
  return P.weeks.slice(-WEEKS).map(o => {
    const e = all ? o.e : o.e.filter(([i]) => inScope(scope, P.events[i], P.tree)),
      s = all ? o.s : P.sectors.map(() => 0);
    if (!all) for (const [i, part] of e) s[P.events[i].sector] += part;
    return { w: o.w, e, s, v: s.reduce((a, b) => a + b, 0), h: headline(e) };
  });
}

function draw(st) {
  const { cols, box } = st,
    narrow = box.clientWidth < 600,
    colW = Math.max(narrow ? 2 : 1.5, box.clientWidth / cols.length),
    W = Math.round(colW * cols.length),
    BH = narrow ? 88 : 112,
    top = LANE * 2 + 6,
    H = top + BH + 20;
  const vs = cols.map(c => c.v).sort((a, b) => a - b),
    max = vs[Math.min(vs.length - 1, Math.floor(P.source.params.scale_quantile * vs.length))] || vs[vs.length - 1] || 1;
  const C = columns(cols, FILL, { width: W, top, height: BH, max });
  st.geo = { colW: C.colW, max };
  let axis = '';
  cols.forEach((c, k) => {
    const x = k * colW;
    if (k && c.w.slice(0, 7) !== cols[k - 1].w.slice(0, 7))
      axis += `<line x1="${x}" x2="${x}" y1="${top + BH}" y2="${top + BH + 4}" class="stroke-border"/><text x="${x + 3}" y="${H - 4}" class="fill-muted-foreground text-[10px]">${MON[+c.w.slice(5, 7) - 1]}${c.w.slice(5, 7) === '01' ? ` ${c.w.slice(0, 4)}` : ''}</text>`;
  });
  const feeds = P.source.feeds_from,
    fk = feeds ? cols.findIndex(c => Date.parse(c.w) + 7 * DAY > Date.parse(feeds)) : -1,
    rows = [[], []];
  if (fk >= 0) {
    const x = fk * colW;
    axis += `<line x1="${x}" x2="${x}" y1="${LANE}" y2="${top + BH}" stroke-dasharray="2 3" class="stroke-muted-foreground"/><text x="${x - 4}" y="${LANE - 3}" text-anchor="end" class="fill-muted-foreground text-[10px]">Vendor feeds from ${fd(feeds)}</text>`;
    rows[0].push([x - 160, x + 2]);
  }
  /* landmarks: the headlines of the weeks shown, most-read product first, on two label rows; a label that would overlap another is left out */
  let marks = '';
  const heads = cols.map((c, k) => [c.h, k]).filter(([h]) => h != null && P.events[h].w >= P.source.params.headline_min_weight);
  const named = new Set(); /* an event dated to a month headlines several weeks: name it once */
  for (const [i, k] of heads.sort((a, b) => (P.events[b[0]].views ?? 0) - (P.events[a[0]].views ?? 0))) {
    const e = P.events[i];
    if (named.has(i)) continue;
    named.add(i);
    const x = k * colW + colW / 2,
      label = e.title.length > 26 ? e.title.slice(0, 25) + '…' : e.title,
      w = label.length * 6 + 8,
      a = Math.min(Math.max(0, x - 3), W - w),
      r = [0, 1].find(r => rows[r].every(([l, rr]) => a + w < l || a > rr));
    if (r === undefined) continue;
    rows[r].push([a, a + w]);
    const y = LANE * (r + 1) - 3;
    marks += `<line x1="${x}" x2="${x}" y1="${y + 3}" y2="${top + BH}" class="stroke-muted-foreground/40"/><text x="${a}" y="${y}" class="fill-foreground text-[11px]">${esc(label)}</text>`;
  }
  const sel = st.sel != null ? `<rect x="${st.sel * colW - 1}" y="${top - 2}" width="${colW + 2}" height="${BH + 4}" class="fill-none stroke-foreground"/>` : '';
  st.svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  st.svg.setAttribute('width', W);
  st.svg.setAttribute('height', H);
  st.svg.innerHTML = `<line x1="0" x2="${W}" y1="${top + BH + 0.5}" y2="${top + BH + 0.5}" class="stroke-border"/>${axis}${C.svg}${marks}${sel}`;
}

function tip(st, k) {
  const c = st.cols[k],
    t = st.tip;
  if (!c) return void (t.hidden = true);
  const h = c.h != null ? P.events[c.h] : null,
    top = c.s
      .map((v, j) => [v, j])
      .filter(([v]) => v)
      .sort((a, b) => b[0] - a[0])
      .slice(0, 3);
  t.innerHTML = `<p class="${ui.meta}">${esc(week(c.w))} · ${n(c.e.length)} event${c.e.length === 1 ? '' : 's'}</p>${
    h
      ? `<p class="text-sm font-semibold text-foreground">${esc(h.title)}</p><p class="${ui.panelNote}">${esc(h.what || h.via)} · ${esc(when(h))}${h.views != null ? ` · ${n(h.views)} Wikipedia views of ${esc(h.name || h.title)}, ${esc(P.source.attention.replace(/^.*weeks /, 'weeks '))}` : ''}</p>`
      : `<p class="${ui.panelNote}">No dated launch or release recorded.</p>`
  }${top.length ? `<p class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">${top.map(([v, j]) => `<span class="inline-flex items-center gap-1.5">${swatch(j)}${esc(P.sectors[j].name)} ${n(Math.round(v * 10) / 10)}</span>`).join('')}</p>` : ''}${c.v > st.geo.max ? `<p class="${ui.panelNote}">Taller than the scale: clipped at its top.</p>` : ''}`;
  t.hidden = false;
  const x = (k + 0.5) * st.geo.colW - st.scroll.scrollLeft;
  /* beside the hovered week, on whichever side has room: the tip never covers the column it describes */
  const gap = st.geo.colW / 2 + 8,
    left = x + gap + t.offsetWidth <= st.box.clientWidth ? x + gap : x - gap - t.offsetWidth;
  t.style.left = `${Math.max(0, left)}px`;
}

function detail(st) {
  const c = st.cols[st.sel],
    D = st.detail;
  if (!c) return void (D.innerHTML = `<p class="${ui.panelNote}">Select a week to see its events.</p>`);
  const by = new Map();
  for (const [i] of c.e) {
    const e = P.events[i];
    if (!by.has(e.sector)) by.set(e.sector, []);
    by.get(e.sector).push(e);
  }
  const yr = (P.years[c.w.slice(0, 4)] || []).map(i => P.events[i]).filter(e => inScope(st.scope, e, P.tree));
  D.innerHTML = `<p class="${ui.panelTitle}">${esc(week(c.w))} · ${n(c.e.length)} event${c.e.length === 1 ? '' : 's'}${st.scope.kind !== 'all' ? ` · ${esc(scopeName(st.scope, P.tree))}` : ''}</p>${
    by.size
      ? [...by]
          .sort((a, b) => a[0] - b[0])
          .map(([j, xs]) => `<section class="flex flex-col gap-1"><p class="flex items-center gap-2 text-xs font-medium text-muted-foreground">${swatch(j)}${esc(P.sectors[j].name)}</p><ol class="flex flex-col">${xs.map(row).join('')}</ol></section>`)
          .join('')
      : `<p class="${ui.panelNote}">No dated launch or release this week in this scope.</p>`
  }${yr.length ? `<details><summary class="${ui.panelNote} cursor-pointer">${n(yr.length)} more dated to ${esc(c.w.slice(0, 4))} only, not placed in a week</summary><ol class="flex flex-col">${yr.map(row).join('')}</ol></details>` : ''}`;
}

function wire(st) {
  const at = e => Math.floor((e.clientX - st.svg.getBoundingClientRect().left) / st.geo.colW);
  const pick = k => {
    st.sel = k;
    draw(st);
    detail(st);
  };
  st.svg.addEventListener('pointermove', e => tip(st, at(e)));
  st.svg.addEventListener('pointerleave', () => (st.tip.hidden = true));
  st.svg.addEventListener('click', e => pick(st.sel === at(e) ? null : at(e)));
  st.scroll.addEventListener('keydown', e => {
    const last = st.cols.length - 1,
      k = st.sel ?? last + 1,
      to = { ArrowLeft: k - 1, ArrowRight: k + 1, Home: 0, End: last }[e.key];
    if (to != null) {
      e.preventDefault();
      pick(Math.max(0, Math.min(last, to)));
      tip(st, st.sel);
      const x = st.sel * st.geo.colW;
      if (x < st.scroll.scrollLeft || x > st.scroll.scrollLeft + st.scroll.clientWidth - 20) st.scroll.scrollLeft = x - st.scroll.clientWidth / 2;
    } else if (e.key === 'Escape') {
      st.tip.hidden = true;
      pick(null);
    }
  });
  st.scroll.addEventListener('blur', () => (st.tip.hidden = true));
  let t;
  new ResizeObserver(() => {
    clearTimeout(t);
    t = setTimeout(() => draw(st), 120);
  }).observe(st.box);
}

function paint(el, scope) {
  let st = state.get(el);
  if (!st || !el.contains(st.svg)) {
    const R = P.source.params.weights;
    el.innerHTML = `<div class="flex flex-col gap-3"><div class="relative" data-box>
        <div class="overflow-x-auto overscroll-x-contain rounded-md focus-visible:outline-2 focus-visible:outline-ring" tabindex="0" role="group" aria-roledescription="weekly chart" aria-label="Weeks: arrow keys move, Escape clears" data-scroll><svg class="block" role="img" data-chart="columns"></svg></div>
        <div class="absolute top-0 z-10 flex w-72 max-w-full flex-col gap-1.5 rounded-md border border-border bg-popover p-3 shadow-lg pointer-events-none" role="status" hidden data-tip></div></div>
      <ul class="flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted-foreground" aria-label="Sectors">${P.sectors.map((s, j) => `<li class="inline-flex items-center gap-1.5">${swatch(j)}${esc(s.name)}</li>`).join('')}</ul>
      <div class="flex flex-col gap-3 border-t border-border pt-3" aria-live="polite" data-day></div>
      <details><summary class="${ui.panelNote} cursor-pointer">How the columns are counted</summary><p class="${ui.panelNote} mt-2 max-w-prose">Height: a launch, beta, general availability or major release counts ${R.release_major}; a minor release ${R.release_minor}, a patch ${R.release_patch}, a changelog entry ${R.changelog}; blog posts and Hacker News stories are not counted. Until ${fd(P.source.feeds_from)} the columns hold a dated chronology of launches; from then they add vendor release feeds and changelogs, so the latest weeks are fuller. A month-level date is spread over its month’s weeks; a year-level date is listed with its year. Columns above the ${Math.round(P.source.params.scale_quantile * 100)}th percentile week are clipped and marked ▼. Headline: the event whose product has the most English Wikipedia views, else the strongest source.</p></details></div>`;
    st = { box: el.querySelector('[data-box]'), scroll: el.querySelector('[data-scroll]'), svg: el.querySelector('svg'), tip: el.querySelector('[data-tip]'), detail: el.querySelector('[data-day]'), sel: null };
    state.set(el, st);
    wire(st);
  }
  if (st.scope && JSON.stringify(st.scope) !== JSON.stringify(scope)) st.sel = null;
  st.scope = scope;
  st.cols = weeksIn(scope);
  st.svg.setAttribute('aria-label', `${scopeName(scope, P.tree)}: ${st.cols.length} weeks from ${fd(st.cols[0].w)} to ${fd(P.source.built_for)}; ${n(st.cols.reduce((a, c) => a + c.e.length, 0))} event placements. Select a week for its events.`);
  const end = st.scroll.scrollLeft >= st.scroll.scrollWidth - st.scroll.clientWidth - 2;
  draw(st);
  if (end) st.scroll.scrollLeft = st.scroll.scrollWidth; /* the latest weeks first; the past scrolls in from the left */
  detail(st);
}

export const panel = {
  id: 'pulse',
  title: 'The pulse',
  note: 'Launches and releases each week over the last year, by sector.',
  controls: scope => scopeControl(scope, 'events'),
  render(scope, el) {
    if (P) return paint(el, scope);
    if (!el.firstChild) el.innerHTML = '<div class="skeleton skeleton-chart" role="status" aria-label="Loading the pulse"></div>';
    return load()
      .then(() => paint(el, scope))
      .catch(e => {
        console.error('pulse:', e);
        el.innerHTML = `<p class="${ui.panelNote}" role="status">The pulse could not be loaded. Check the connection and reload.</p>`;
      });
  },
};

/* Sector activity: one row per sector, one square per week of the same year. A square's strength is that week against the sector's
   own busiest week, so a quiet sector still shows its rhythm; the figures beside it are its share of everything in the last four
   weeks, and the headline of those weeks. */
const RECENT = 4,
  LISTED = 8;
let picked = null; /* { j: sector, k: week } the reader chose; until then, the loudest sector's latest active week */
function grid(el) {
  const cols = weeksIn(),
    last = cols.slice(-RECENT),
    all = last.reduce((a, c) => a + c.v, 0) || 1;
  const rows = P.sectors
    .map((sec, j) => ({ sec, j, peak: Math.max(...cols.map(c => c.s[j])) || 1, loud: last.reduce((a, c) => a + c.s[j], 0) / all }))
    .filter(r => r.sec.id !== 'unplaced' && cols.some(c => c.s[r.j]))
    .sort((a, b) => b.loud - a.loud);
  if (!rows.length) return void (el.innerHTML = `<p class="${ui.panelNote}">No dated activity in the last year.</p>`);
  const sel = picked || { j: rows[0].j, k: cols.findLastIndex(c => c.s[rows[0].j]) },
    c = cols[sel.k],
    events = c.e
      .map(([i]) => P.events[i])
      .filter(e => e.sector === sel.j)
      .sort((a, b) => (b.weight || 0) - (a.weight || 0) || !!b.gist - !!a.gist || bare(a) - bare(b) || (b.views ?? 0) - (a.views ?? 0) || b.w - a.w); /* what matters most, then what we can describe, then version bumps */
  el.innerHTML = `<div class="flex flex-col gap-4"><div class="flex flex-col gap-1 overflow-x-auto">${rows
    .map(
      r => `<div class="grid min-w-[40rem] grid-cols-[minmax(0,13rem)_minmax(0,1fr)_3rem] items-center gap-x-3">
        <span class="truncate text-sm ${r.j === sel.j ? 'font-medium text-foreground' : 'text-muted-foreground'}">${esc(r.sec.name)}</span>
        <span class="grid grid-cols-[repeat(52,minmax(0,1fr))] gap-px">${cols
          .map((w, k) => {
            const v = w.s[r.j],
              on = r.j === sel.j && k === sel.k;
            return `<button type="button" class="h-4 rounded-[2px] ${v ? SW[r.j] : 'bg-muted'} ${on ? 'ring-2 ring-foreground ring-offset-1 ring-offset-card' : ''} disabled:cursor-default" style="opacity:${v ? (0.25 + 0.75 * (v / r.peak)).toFixed(2) : 1}" data-j="${r.j}" data-k="${k}"${v ? '' : ' disabled'} aria-label="${esc(`${r.sec.name}, ${week(w.w)}`)}" title="${esc(`${r.sec.name} · ${week(w.w)} · ${v} ${v === 1 ? 'item' : 'items'}`)}" aria-pressed="${on}"></button>`;
          })
          .join('')}</span>
        <span class="${ui.num} text-right text-sm text-foreground" title="Share of all activity in the last ${RECENT} weeks">${Math.round(r.loud * 100)}%</span></div>`
    )
    .join('')}</div>
    <section class="flex h-96 flex-col gap-1 overflow-y-auto border-t border-border pt-3" aria-live="polite"><p class="flex items-center gap-2 ${ui.panelTitle}">${swatch(sel.j)}${esc(P.sectors[sel.j].name)} · ${esc(week(c.w))} · ${n(events.length)} event${events.length === 1 ? '' : 's'}</p>
      <ol class="flex flex-col">${events.slice(0, LISTED).map(row).join('')}</ol>${events.length > LISTED ? `<p class="${ui.panelNote}">and ${n(events.length - LISTED)} more that week.</p>` : ''}</section></div>`;
}
export const sectorPanel = {
  id: 'sector-activity',
  title: 'Sector activity',
  note: `A square per week over the last year; the figure is each sector’s share of all activity in the last ${RECENT} weeks. Select a square to see what happened.`,
  render(_, el) {
    if (!el.dataset.wired) {
      el.dataset.wired = '1';
      const at = e => (b => b && !b.disabled && { j: +b.dataset.j, k: +b.dataset.k })(e.target.closest('button[data-k]'));
      el.addEventListener('click', e => {
        const s = at(e);
        if (s) grid(el, (picked = s)); /* only a click changes what is shown: the list never moves under the pointer */
      });
    }
    return P ? grid(el) : load().then(() => grid(el));
  },
};
