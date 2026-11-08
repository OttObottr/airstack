import { json } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { cn, esc, fd, host, ic, pct, url } from '../lib/format.js';
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
const tile = (lab, big, sub, chart = '') =>
  `<div class="tile"><p class="lab">${lab}</p><p class="big">${big}</p>${chart}<p class="meta">${sub}</p></div>`;

function tiles(x) {
  const r = rowMap()[x.id],
    a = ATT && ATT.products[x.id],
    today = EV && EV.source.built_for,
    mine = EV ? EV.events.filter(e => e.id === x.id) : [],
    out = [];
  if (r && r.dl.value != null) {
    const s = series(r);
    out.push(tile('Downloads · 7 days', cn(r.dl.value),
      `${esc(r.dl.registry)}${r.dl.vsBase != null ? ` · ${pct(r.dl.vsBase)} vs its own 4-week level` : ''}${r.dl.fetched ? ` · fetched ${fd(r.dl.fetched)}` : ''}${src(r.dl.url, `${r.dl.registry} page for ${x.name}`)}`,
      s ? spark(s[0], s[1], `${x.name}, ${r.dl.registry} downloads`) : ''));
  }
  if (a && a.last_4w != null)
    out.push(tile('Wikipedia views · 4 weeks', cn(a.last_4w),
      `${a.change != null ? `${pct(a.change * 100)} vs its prior 4 weeks · ` : ''}attention, not adoption · read ${fd(a.fetched)}${src(a.url, `Wikipedia article for ${x.name}`)}`,
      spark(a.views, ATT.weeks, `${x.name}, English Wikipedia views`)));
  const rel = r && r.gh.release ? { title: r.gh.release, at: r.gh.released, url: r.gh.url, from: 'GitHub' }
    : (e => e && { title: e.title, at: e.at, url: e.url, from: host(e.url || '') })(
        mine.filter(e => e.status === 'observed' && /release|changelog/.test(e.kind)).sort((p, q) => (p.at < q.at ? 1 : -1))[0]);
  if (rel && rel.at) out.push(tile('Latest release', fd(rel.at), `${esc(rel.title)} · ${esc(rel.from)}${src(rel.url, `Release record for ${x.name}`)}`));
  const next = mine.filter(e => e.status === 'scheduled' && /^end of/.test(e.kind) && e.at >= today).sort((p, q) => (p.at < q.at ? -1 : 1))[0];
  if (next) out.push(tile('Next support date', fd(next.at), `${esc(next.title)} · published schedule, ${esc(host(next.url || ''))} · read ${fd(EV.source.support_schedules.read || today)}${src(next.url, `Support schedule for ${x.name}`)}`));
  return out;
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
      }
    });
  return t.length || !ready
    ? `<div class="tiles" id="sigs" data-id="${esc(x.id)}" aria-label="Public signals for ${esc(x.name)}">${t.join('')}${ready ? '' : '<div class="tile skeleton" aria-hidden="true"></div>'}</div>`
    : '';
}
