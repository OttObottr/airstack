import { Method } from '../ui/method.js';
import { S } from '../lib/state.js';
import { clearTool } from './app.js';
import { mono } from './avatar.js';
import { DIR, KIDS, loadDir, orgName, researchedFacts } from './search/directory.js';
import { BR, IDX, moverRows } from './search/index.js';
import { M, PARAMS, json } from '../lib/data.js';
import { $, reduce } from '../lib/dom.js';
import { LISTED, cn, esc, fd, n, pct } from '../lib/format.js';
import { MK } from '../lib/market.js';
import { RankList } from '../ui/rank.js';

export const rowMap = () => Object.fromEntries(moverRows().map(r => [r.id, r]));
/* Momentum compares the latest week with the tool's own four-week level. */
const mom = r => (r && r.dl.vsBase != null ? r.dl.vsBase : null);
export const byGrowth = R => (a, b) => (mom(R[b.id]) ?? -1e9) - (mom(R[a.id]) ?? -1e9) || a.name.localeCompare(b.name);
export function lb(items, { cur = null, lane = true, dense = false } = {}) {
  const R = rowMap();
  return RankList({
    dense,
    missing: `no ${PARAMS.movers.base_weeks}-week level yet`,
    rows: items.map(x => {
      const r = R[x.id],
        d = mom(r),
        vol =
          r && r.dl.value != null
            ? `${cn(r.dl.value)} ${r.dl.registry} a week${r.dl.delta != null ? ` · ${pct(r.dl.delta)} on the week before` : ''}`
            : 'downloads not observed';
      return { id: x.id, avatar: mono(x), name: x.name, note: `${lane ? x.laneName + ' · ' : ''}${vol}`, value: d, label: d == null ? '' : pct(d), current: x.id === cur };
    }),
  });
}
export const vendorOf = x =>
  x.dir
    ? (x.devs || []).map(orgName).filter(Boolean).join(', ')
    : MK && MK.catalog && MK.catalog[x.id]
      ? MK.catalog[x.id].vendor || ''
      : '';
export const catList = items =>
  `<ol class="lb">${items
    .map((x, i) => {
      const n = researchedFacts(x),
        v = vendorOf(x);
      return `<li style="--i:${i}"><button type="button" data-pick="${esc(x.id)}"><span class="who">${mono(x)}<span><b>${esc(x.name)}</b><span class="meta">${v ? esc(v) + ' · ' : ''}${n ? `${n} quotes found on its pages` : LISTED}</span></span></span></button></li>`;
    })
    .join('')}</ol>`;
function typeView() {
  if (!DIR) {
    $('#trend').setAttribute('aria-busy', 'true');
    $('#trend').innerHTML = '<div class="skeleton skeleton-list mt-6" role="status" aria-label="Loading the directory"></div>';
    loadDir().then(drawBrowse, () => {
      $('#trend').setAttribute('aria-busy', 'false');
      $('#trend').innerHTML =
        '<p class="load-error mt-6" role="status">The directory could not be loaded. Check your connection and reload.</p>';
    });
    return;
  }
  const T = DIR.types,
    i = BR.type,
    path = [];
  for (let j = i; j != null && path.length < 12; j = T[j][2].length ? T[j][2][0] : null) path.unshift(j);
  const down = new Set([i]),
    todo = [i];
  while (todo.length)
    for (const c of KIDS[todo.pop()])
      if (!down.has(c)) {
        down.add(c);
        todo.push(c);
      }
  const items = IDX.filter(x => x.dir && down.has(x.t))
      .sort((a, b) => b.links - a.links)
      .slice(0, 24),
    kids = KIDS[i];
  $('#trend').innerHTML =
    `<p class="eyebrow mt-6 crumb">${path.map(j => (j === i ? esc(T[j][1]) : `<button type="button" data-type="${j}">${esc(T[j][1])}</button>`)).join(' › ')} · ${n(T[i][4])} products</p>
    ${
      kids.length
        ? `<div class="tl">${kids
            .slice(0, 60)
            .map(
              j =>
                `<button type="button" data-type="${j}">${esc(T[j][1])} <span class="meta">${n(T[j][4])}</span></button>`
            )
            .join('')}</div>${kids.length > 60 ? `<p class="meta mt-3">and ${kids.length - 60} smaller types</p>` : ''}`
        : ''
    }
    <p class="eyebrow mt-6">Best known</p>${catList(items)}
    <p class="meta mt-3">Types and products from Wikidata (CC0), read ${fd(DIR.source.fetched_at)}, ranked by how many Wikipedia and sister-site pages cover them.</p>`;
}
export function drawBrowse() {
  $('#trend').setAttribute('aria-busy', 'false');
  $('#mvH').textContent = BR.type != null ? 'Browse by type' : 'Most active this week';
  if (BR.type != null) return typeView();
  /* the products that announced most in the last week, counted from their own feeds, changelogs and releases (news.json) */
  json('news.json').then(N => {
    const from = new Date(Date.parse(N.source.read) - 6 * 864e5).toISOString().slice(0, 10),
      count = {};
    for (const i of N.items) if (i.date.slice(0, 10) >= from && i.date.slice(0, 10) <= N.source.read && i.signal !== 'other') count[i.id] = (count[i.id] || 0) + 1;
    const top = Object.entries(count)
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 5)
      .map(([id, k]) => {
        const x = IDX.find(y => y.id === id) || { id, name: (N.items.find(i => i.id === id) || {}).name || id };
        return { id, avatar: mono(x), name: x.name, note: x.laneName || '', value: k, label: `${k} ${k === 1 ? 'update' : 'updates'}` };
      });
    $('#trend').innerHTML = top.length
      ? `${RankList({ rows: top, dense: true })}<div class="mt-3">${Method(`Posts, changelog entries and releases each product published on its own channels, ${fd(from)} to ${fd(N.source.read)}.`)}</div>`
      : '<p class="meta mt-4">No announcements recorded this week.</p>';
  }, () => ($('#trend').innerHTML = '<p class="load-error">This could not be loaded. Check the connection and reload.</p>'));
}

export function mount() {
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-type]');
    if (b) {
      BR.type = +b.dataset.type;
      if (S.tool) clearTool();
      drawBrowse();
      $('#browse').scrollIntoView({ block: 'start', behavior: reduce ? 'auto' : 'smooth' });
    }
  });
}
