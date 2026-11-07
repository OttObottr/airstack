// spec: AS-100 AS-104 AS-248 AS-256 AS-326
import { S } from './answer/model.js';
import { clearTool } from './app.js';
import { mono } from './avatar.js';
import { DIR, KIDS, loadDir, orgName, researchedFacts } from './search/directory.js';
import { BR, IDX, moverRows } from './search/index.js';
import { $, reduce } from '../lib/dom.js';
import { cn, esc, fd, n, pct } from '../lib/format.js';
import { MK } from '../lib/market.js';

export const rowMap = () => Object.fromEntries(moverRows().map(r => [r.id, r]));
/* momentum is change against the tool's OWN 4-week level: a bounce back from a dip is not growth (OpenHands was +107% on the week and 52% below its level) */
const mom = r => (r && r.dl.vsBase != null ? r.dl.vsBase : null);
export const byGrowth = R => (a, b) => (mom(R[b.id]) ?? -1e9) - (mom(R[a.id]) ?? -1e9) || a.name.localeCompare(b.name);
/* a ranked list with a change bar per row; bars share one scale (the largest change shown) and say so beside the list */
export function lb(items, { cur = null, lane = true } = {}) {
  const R = rowMap(),
    ds = items.map(x => mom(R[x.id]));
  const mx = Math.max(1, ...ds.filter(v => v !== null).map(Math.abs));
  return `<ol class="lb${cur ? ' has-cur' : ''}">${items
    .map((x, i) => {
      const r = R[x.id],
        d = ds[i];
      const vol =
        r && r.dl.value != null
          ? `${cn(r.dl.value)} ${esc(r.dl.registry)} a week${r.dl.delta != null ? ` · ${pct(r.dl.delta)} on the week before` : ''}`
          : 'downloads not observed';
      return `<li style="--i:${i}"><button type="button" data-pick="${esc(x.id)}"${x.id === cur ? ' aria-current="true"' : ''}><span class="who">${mono(x)}<span><b>${esc(x.name)}</b><span class="meta">${lane ? esc(x.laneName) + ' · ' : ''}${vol}${x.assess ? ' · renewal verdict' : ''}</span></span></span><span class="bar" aria-hidden="true">${d !== null ? `<i class="${d < 0 ? 'neg' : ''}" style="--w:${Math.max(2, (Math.abs(d) / mx) * 100).toFixed(1)}%"></i>` : ''}</span><span class="d">${d !== null ? pct(d) : '<span class="nobs">no 4-week level</span>'}</span></button></li>`;
    })
    .join('')}</ol>`;
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
      return `<li style="--i:${i}"><button type="button" data-pick="${esc(x.id)}"><span class="who">${mono(x)}<span><b>${esc(x.name)}</b><span class="meta">${v ? esc(v) + ' · ' : ''}${n ? `${n} quotes found on its pages` : 'not researched yet'}</span></span></span></button></li>`;
    })
    .join('')}</ol>`;
function typeView() {
  /* the taxonomy: a type, the way up to "software", its subtypes and its best-known products */
  if (!DIR) {
    $('#trend').innerHTML = '<p class="meta mt24">Loading the directory…</p>';
    loadDir().then(drawBrowse, () => {
      $('#trend').innerHTML =
        '<p class="meta mt24">The directory could not be loaded. Check your connection and reload.</p>';
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
    `<p class="lab mt24 crumb">${path.map(j => (j === i ? esc(T[j][1]) : `<button type="button" data-type="${j}">${esc(T[j][1])}</button>`)).join(' › ')} · ${n(T[i][4])} products</p>
    ${
      kids.length
        ? `<div class="tl">${kids
            .slice(0, 60)
            .map(
              j =>
                `<button type="button" data-type="${j}">${esc(T[j][1])} <span class="meta">${n(T[j][4])}</span></button>`
            )
            .join('')}</div>${kids.length > 60 ? `<p class="meta mt12">and ${kids.length - 60} smaller types</p>` : ''}`
        : ''
    }
    <p class="lab mt24">Best known</p>${catList(items)}
    <p class="meta mt12">Types and products from Wikidata (CC0), read ${fd(DIR.source.fetched_at)}, ranked by how many Wikipedia and sister-site pages cover them. Listed, not researched: AirStack claims nothing about a product until it has read the product’s own pages.</p>`;
}
export function drawBrowse() {
  if (BR.type != null) return typeView();
  const R = rowMap(),
    list = IDX.filter(x => {
      const r = R[x.id];
      return r && r.dl.delta != null && r.dl.value >= 5000 && !(r.dl.vsBase != null && r.dl.vsBase < 0);
    })
      .sort(byGrowth(R))
      .slice(0, 5);
  $('#trend').innerHTML =
    `<h3 class="trh">Trending this week</h3>${lb(list)}<p class="meta mt12">Weekly registry downloads against each tool’s own 4-week level. Bars share one scale, the largest change shown. Only tools also above their own 4-week level are listed, and tools under 5,000 downloads a week are left out.</p>`;
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
