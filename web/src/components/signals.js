import { PARAMS, json } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { ago, cn, esc, fd, host, ic, pct, stamp, url } from '../lib/format.js';
import { ui } from '../ui/recipes.js';
import { series, spark } from '../lib/spark.js';
import { rowMap } from './browse.js';

/* a product's public signals, each with its source and date; a signal not observed is left out */
let ATT = null,
  EV = null,
  asked = null;
const load = () =>
  (asked ||= Promise.all([
    json('attention.json').then(a => (ATT = a), () => (ATT = false)),
    json('events.json').then(e => (EV = e), () => (EV = false)),
  ]));

const src = (u, l) =>
  u ? ` <a class="src" href="${url(u)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(l)}">${ic('out')}</a>` : '';
/* a signal tile on the strip's shared rows (label, value, chart, meta), so every tile's rows line up whatever it holds */
const tile = (lab, big, sub, chart = '') =>
  `<div class="grid grid-rows-subgrid row-span-4 min-w-0 rounded-lg border border-border bg-card p-4" data-tile><p class="${ui.tileLabel}">${lab}</p><p class="${ui.tileValue}">${big}</p><div class="min-h-7">${chart}</div><p class="${ui.panelNote} [overflow-wrap:anywhere]">${sub}</p></div>`;

function tiles(x) {
  const r = rowMap()[x.id],
    now = (EV && EV.source.built_for) || (ATT && ATT.source.read) || '', /* the build's day, never the viewer's clock */
    mine = EV ? EV.events.filter(e => e.id === x.id) : [],
    out = [];
  if (r && r.dl.value != null) {
    const s = series(r);
    out.push(tile('Downloads · 7 days', cn(r.dl.value),
      `${esc(r.dl.registry)}${r.dl.vsBase != null ? ` · ${pct(r.dl.vsBase)} vs its own ${PARAMS.movers.base_weeks}-week level` : ''}${r.dl.fetched ? ` · fetched ${stamp(r.dl.fetched, now)}` : ''}${src(r.dl.url, `${r.dl.registry} page for ${x.name}`)}`,
      s ? spark(s[0], s[1], `${x.name}, ${r.dl.registry} downloads`) : ''));
  }
  const rel = r && r.gh.release ? { title: r.gh.release, at: r.gh.released, url: r.gh.url, from: 'GitHub' }
    : (e => e && { title: e.title, at: e.at, url: e.url, from: host(e.url || '') })(
        mine.filter(e => e.status === 'observed' && /release|changelog/.test(e.kind)).sort((p, q) => (p.at < q.at ? 1 : -1))[0]);
  if (rel && rel.at) out.push(tile('Latest release', `<time datetime="${esc(rel.at.slice(0, 10))}" title="${fd(rel.at)}">${ago(rel.at, now)}</time>`, `${esc(rel.title)} · ${esc(rel.from)}${src(rel.url, `Release record for ${x.name}`)}`));
  return out;
}

/* a year of this product's own dated events, one square a week: releases, posts, threads and support dates as they were observed */
const WEEKS = 52,
  WEEK = 7 * 864e5;
function activity(x) {
  if (!EV) return '';
  const end = Date.parse(EV.source.built_for),
    n = Array(WEEKS).fill(0),
    mine = EV.events.filter(e => e.id === x.id && e.status === 'observed');
  for (const e of mine) {
    const k = WEEKS - 1 - Math.floor((end - Date.parse(e.at)) / WEEK);
    if (k >= 0 && k < WEEKS) n[k]++;
  }
  const total = n.reduce((a, b) => a + b, 0),
    peak = Math.max(...n);
  if (!total) return '';
  return `<div class="mt-4 flex flex-col gap-2 rounded-lg border border-border bg-card p-4"><p class="${ui.tileLabel}">Activity · ${WEEKS} weeks · ${total} dated event${total === 1 ? '' : 's'}</p>
    <span class="grid grid-cols-[repeat(52,minmax(0,1fr))] gap-px" role="img" aria-label="${esc(`${x.name}: ${total} dated events over ${WEEKS} weeks`)}">${n.map((v, k) => `<i class="h-4 rounded-[2px] ${v ? 'bg-info' : 'bg-muted'}" style="opacity:${v ? (0.3 + 0.7 * (v / peak)).toFixed(2) : 1}" title="${esc(`Week of ${fd(new Date(end - (WEEKS - 1 - k) * WEEK).toISOString())}: ${v}`)}"></i>`).join('')}</span></div>`;
}

/* the strip renders now from what is loaded, and fills in place once attention and events arrive */
export function strip(x) {
  const ready = ATT !== null && EV !== null,
    t = tiles(x);
  if (!ready)
    load().then(() => {
      const box = $('#sigs');
      if (box && box.dataset.id === x.id) {
        const u = tiles(x);
        if (u.length) box.innerHTML = u.join('');
        else box.remove();
        const act = $('#sigAct');
        if (act) act.innerHTML = activity(x);
      }
    });
  return t.length || !ready
    ? `<div class="mt-6 grid grid-cols-[repeat(auto-fit,minmax(min(100%,12rem),1fr))] gap-x-4 gap-y-2" id="sigs" data-id="${esc(x.id)}" aria-label="Public signals for ${esc(x.name)}">${t.join('')}${ready ? '' : '<div class="skeleton row-span-4 min-h-32 rounded-lg" aria-hidden="true"></div>'}</div><div id="sigAct">${activity(x)}</div>`
    : `<div id="sigAct">${activity(x)}</div>`;
}
