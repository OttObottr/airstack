import { json } from '../../lib/data.js';
import { esc, fd, n, tip, url } from '../../lib/format.js';
import { ui } from '../../ui/recipes.js';
import { MK } from '../../lib/market.js';
import { stack } from '../../lib/stack.js';
import { mono } from '../avatar.js';
import { IDX } from '../search/index.js';
import { loadDir } from '../search/directory.js';
import { latest, load, loading, sourceLine } from './scope.js';

/* A market's named field: the products filed under a taxonomy node (or a stack, or a maker's products), one row each, with
   what each published source says about it. Each column names its source; nothing is blended into a score, and a product a
   source does not cover shows a quiet dash, not zero. */

const DASH = '<span class="text-subtle-foreground" aria-hidden="true">—</span><span class="sr">not covered by this source</span>';
const ANNOUNCE = new Set(['release', 'changelog', 'blog']);
export const SUPPORT = new Set(['end of life', 'end of active support', 'end of extended support']);

/* every file a field reads, fetched once */
let FILES = null;
export const files = () =>
  (FILES ||= Promise.all([
    load(),
    json('taxonomy-index.json'),
    json('reach.json').catch(() => null),
    json('attention.json').catch(() => null),
    json('pricing.json').catch(() => null),
    json('events.json').catch(() => null),
  ]).then(([D, T, R, A, P, E]) => {
    const byProduct = new Map();
    for (const e of (E && E.events) || []) {
      if (!byProduct.has(e.id)) byProduct.set(e.id, []);
      byProduct.get(e.id).push(e);
    }
    return { D, T, R, A, P, E, byProduct };
  }));

const under = (D, node, id) => {
  for (let x = node; x; x = D.nodes[x] && D.nodes[x].parent) if (x === id) return true;
  return false;
};

/* the ids a scope stands for */
export async function idsOf(scope, F) {
  if (scope.kind === 'node') return Object.keys(F.T.products).filter(pid => F.T.products[pid].some(([node]) => under(F.D, node, scope.id)));
  if (scope.kind === 'stack') return stack().map(x => x.id);
  if (scope.ids) return scope.ids;
  if (scope.kind === 'maker') return ((await json('makers.json')).makers[scope.id] || {}).products || [];
  return [];
}

/* names: the catalog first, then the Wikidata directory (loaded once, the same file search uses) */
let NAMES = null;
const names = async () => {
  if (NAMES) return NAMES;
  await loadDir().catch(() => {});
  NAMES = new Map();
  for (const x of IDX) if (!NAMES.has(x.id)) NAMES.set(x.id, x);
  return NAMES;
};
export const nameOf = id => (NAMES && NAMES.get(id) ? NAMES.get(id).name : id);
export const ensureNames = names;

/* a price as published, read as a number only to find the lowest plan; plans in different currencies are not compared */
const amount = s => {
  const m = String(s || '').replace(/,/g, '').match(/(\d+(?:\.\d+)?)/);
  return m ? +m[1] : null;
};
const cur = s => (String(s || '').match(/US\$|[$€£¥]/) || [''])[0];
const PER = { month: '/mo', year: '/yr', 'one-time': ' once' };
export function entry(P, id) {
  const p = P && P[id];
  if (!p || !p.plans || !p.plans.length) return null;
  const priced = p.plans.map(pl => ({ ...pl, v: amount(pl.price), c: cur(pl.price) })).filter(pl => pl.v !== null);
  if (!priced.length) return null;
  if (priced.some(pl => pl.v === 0)) return { text: 'Free plan', v: 0, p };
  const c = priced[0].c,
    low = priced.filter(pl => pl.c === c).sort((a, b) => a.v - b.v)[0];
  const per = (PER[low.period] || '') + (low.unit === 'user' ? ' per user' : '');
  return { text: `From ${low.price.trim()}${per}`, v: low.v, p, plan: low.plan };
}

/* an announcement's title; a GitHub release published without one reads as its tag */
export const label = e => {
  const tag = /\/releases\/tag\/([^/?#]+)/.exec(e.url || '');
  return (!e.title || /^release$/i.test(e.title.trim())) && tag ? `Release ${decodeURIComponent(tag[1])}` : e.title;
};

/* a release published with only its tag says nothing about what changed: it is counted, never shown as news */
export const bare = e => e.kind === 'release' && (!e.title || /^release$/i.test(e.title.trim()) || !/\s/.test(e.title.trim()));
const announced = (F, id) => (F.byProduct.get(id) || []).filter(e => ANNOUNCE.has(e.kind) && e.status === 'observed').sort((a, b) => (a.at < b.at ? 1 : -1));
/* the latest thing a product announced on its own channels that says what changed; and its recent releases, by count */
export const lastNews = (F, id) => announced(F, id).find(e => !bare(e)) || null;
export const releases = (F, id, since) => announced(F, id).filter(e => e.kind === 'release' && e.at >= since);
/* did a product announce anything, a bare release included, since a date (events.json keeps a few per kind: a yes, not a count) */
export const activeSince = (F, id, since) => announced(F, id).some(e => e.at >= since);

const spark = views => {
  const v = (views || []).map(x => (x === null ? null : +x));
  const max = Math.max(1, ...v.filter(x => x !== null));
  const pts = v.map((x, i) => (x === null ? null : `${((i / Math.max(1, v.length - 1)) * 60).toFixed(1)},${(16 - (x / max) * 14).toFixed(1)}`)).filter(Boolean);
  return pts.length > 1
    ? `<svg class="inline-block align-middle text-muted-foreground" width="60" height="18" viewBox="0 0 60 18" aria-hidden="true"><polyline fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" points="${pts.join(' ')}"/></svg>`
    : '';
};

const BAND = [
  [1e3, 'Top 1,000'],
  [1e4, 'Top 10,000'],
  [1e5, 'Top 100,000'],
  [1e6, 'Top million'],
];

/* GitHub stars for the registry-tracked tools (market-data.js: the current count of the tool's own repository) */
const starsOf = () => {
  const out = new Map();
  for (const r of (MK && MK.movers && MK.movers.rows) || []) if (r.gh && r.gh.stars != null) out.set(r.id, r.gh);
  return out;
};

export function rowsOf(F, ids) {
  const R = (F.R && F.R.products) || {},
    A = (F.A && F.A.products) || {},
    G = starsOf();
  return [...new Set(ids)].map(id => {
    const x = NAMES && NAMES.get(id),
      r = R[id],
      a = A[id];
    return {
      id,
      name: nameOf(id),
      site: x && x.site,
      rank: r ? r[0] : null,
      domain: r ? r[1] : null,
      read: a && a.last_4w != null ? a.last_4w : null,
      stars: G.has(id) ? G.get(id).stars : null,
      gh: G.get(id) || null,
      att: a || null,
      news: lastNews(F, id),
      rel: releases(F, id, new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10)),
      price: entry(F.P, id),
      researched: !!(MK && MK.profiles && MK.profiles[id]),
    };
  });
}

export const SORTS = {
  stars: { label: 'GitHub stars', has: p => p.stars != null, by: (a, b) => (b.stars ?? -1) - (a.stars ?? -1) || (a.rank ?? 1e9) - (b.rank ?? 1e9) },
  reach: { label: 'Most-linked site', has: p => p.rank != null, by: (a, b) => (a.rank ?? 1e9) - (b.rank ?? 1e9) || (b.read ?? -1) - (a.read ?? -1) },
  read: { label: 'Most-read on Wikipedia', has: p => p.read != null, by: (a, b) => (b.read ?? -1) - (a.read ?? -1) || (a.rank ?? 1e9) - (b.rank ?? 1e9) },
  news: { label: 'Latest update', has: p => !!p.news || p.rel.length > 0, by: (a, b) => ((b.news && b.news.at) || '').localeCompare((a.news && a.news.at) || '') || (a.rank ?? 1e9) - (b.rank ?? 1e9) },
};
const SHOW = 20;
/* a field opens ordered by the size reading that covers most of its products, so a market of open-source tools is not led by
   the few that happen to own a front-page domain */
export const bestSort = rows => {
  const [k, c] = ['stars', 'reach', 'read'].map(k => [k, rows.filter(SORTS[k].has).length]).sort((a, b) => b[1] - a[1])[0];
  return c ? k : 'news';
};

const reachCell = p =>
  p.rank ? tip(BAND.find(b => p.rank <= b[0])[1], `${p.domain} is no. ${p.rank.toLocaleString('en')} of the million most-linked domains (Majestic Million, CC BY 3.0)`) : DASH;
const starCell = p => (p.stars != null ? `<a class="${ui.num} hover:underline underline-offset-2" href="${url(p.gh.url)}" target="_blank" rel="noopener noreferrer">★ ${n(p.stars)}</a>` : DASH);
const readCell = p => {
  if (p.read == null) return DASH;
  const ch = p.att.change,
    moved = p.att.prior_4w >= 2000 && ch != null && Math.abs(ch) >= 0.1;
  return `${spark(p.att.views)} <span class="${ui.num}">${n(p.read)}</span>${moved ? ` <span class="${ch > 0 ? ui.badge.up : ui.badge.down}">${ch > 0 ? '+' : ''}${Math.round(ch * 100)}%</span>` : ''}`;
};
const relLine = p =>
  p.rel.length
    ? `<a class="${ui.meta} hover:text-foreground hover:underline underline-offset-2" href="${url(p.rel[0].url.replace(/\/tag\/[^/]+$/, ''))}" target="_blank" rel="noopener noreferrer">Latest release ${esc(label(p.rel[0]).replace(/^Release /, ''))} · ${fd(p.rel[0].at)}</a>`
    : '';
const newsCell = p =>
  !p.news
    ? relLine(p) || DASH
    : `<a class="line-clamp-2 text-foreground hover:underline underline-offset-2" href="${url(p.news.url)}" target="_blank" rel="noopener noreferrer">${esc(label(p.news))}</a><span class="${ui.meta}">${esc(p.news.kind)} · ${fd(p.news.at)}</span>${relLine(p)}`;
const priceCell = p =>
  p.price
    ? `<a class="hover:underline underline-offset-2" href="${url(p.price.p.url)}" target="_blank" rel="noopener noreferrer">${esc(p.price.text)}</a><span class="${ui.meta}">read ${fd(p.price.p.checked)}</span>`
    : DASH;

const COLS = [
  ['GitHub stars', p => p.stars != null, p => `<td class="${ui.td} whitespace-nowrap text-sm">${starCell(p)}</td>`],
  ['Site reach', p => p.rank != null, p => `<td class="${ui.td} whitespace-nowrap text-sm">${reachCell(p)}</td>`],
  ['Wikipedia readers, 4 weeks', p => p.read != null, p => `<td class="${ui.td} whitespace-nowrap text-sm">${readCell(p)}</td>`],
  ['Latest update from the maker', p => !!p.news || p.rel.length > 0, p => `<td class="${ui.td} min-w-[14rem] py-2 text-sm"><div class="flex flex-col gap-0.5">${newsCell(p)}</div></td>`],
  ['Entry price', p => !!p.price, p => `<td class="${ui.td} min-w-[9rem] py-2 text-sm"><div class="flex flex-col gap-0.5">${priceCell(p)}</div></td>`],
];
const row = (p, cols) => `<tr class="hover:bg-muted/50">
  <td class="${ui.td} min-w-[11rem]"><a class="flex items-center gap-2 text-foreground hover:underline underline-offset-2" href="#app=${encodeURIComponent(p.id)}">${mono({ id: p.id, name: p.name, site: p.site }, 's20')}<span class="truncate">${esc(p.name)}</span></a></td>
  ${cols.map(c => c[2](p)).join('')}</tr>`;

export const field = {
  id: 'field',
  title: 'The field',
  note: 'Every product filed here, by name. Each column is one source’s reading; a dash means that source does not cover the product.',
  async render(scope, el) {
    const fresh = latest(el);
    el.className = 'flex flex-col gap-3 min-w-0';
    loading(el);
    const F = await files();
    await names();
    const ids = await idsOf(scope, F);
    if (!fresh()) return;
    el.removeAttribute('aria-busy');
    const all = rowsOf(F, ids);
    if (!all.length) {
      el.innerHTML = `<p class="${ui.panelNote}">${scope.kind === 'stack' ? 'Your stack is empty. Add software to see it measured here.' : 'No products are filed here yet.'}</p>`;
      return;
    }
    let sort = el.dataset.sort && SORTS[el.dataset.sort] ? el.dataset.sort : bestSort(all),
      open = false;
    const covered = (k, f) => all.filter(f).length;
    const cols = COLS.filter(c => all.some(c[1])); /* a source that covers none of the field is left out, not shown as a column of dashes */
    const draw = () => {
      const list = all.slice().sort(SORTS[sort].by),
        shown = open ? list : list.slice(0, SHOW);
      const pick = list.filter(p => p.researched).slice(0, 3);
      const cmp = (pick.length >= 2 ? pick : list.slice(0, 3)).map(p => p.id);
      el.innerHTML = `<div class="flex flex-wrap items-center justify-between gap-2">
        <div class="${ui.segmented}" role="group" aria-label="Order by">${Object.entries(SORTS)
          .filter(([, s]) => all.some(s.has))
          .map(([k, s]) => `<button type="button" class="${ui.segment}" data-sort="${k}" aria-pressed="${k === sort}">${s.label}</button>`)
          .join('')}</div>
        ${cmp.length >= 2 ? `<a class="${ui.button.secondary}" href="#compare=${cmp.map(encodeURIComponent).join(',')}">Compare ${esc(cmp.map(nameOf).join(' · '))}</a>` : ''}</div>
      <div class="relative overflow-x-auto"><table class="${ui.table}"><thead><tr><th class="${ui.th}">Product <span class="font-normal">(${n(all.length)})</span></th>
        ${cols.map(c => `<th class="${ui.th} whitespace-nowrap">${c[0]}</th>`).join('')}</tr></thead>
        <tbody>${shown.map(p => row(p, cols)).join('')}</tbody></table></div>
      ${list.length > SHOW ? `<button type="button" class="${ui.button.ghost} self-start" data-more>${open ? 'Show fewer' : `Show all ${n(list.length)}`}</button>` : ''}
      ${sourceLine(
        `${F.R && F.R.source ? `Site reach: the product’s own domain among the million most-linked, <a class="underline underline-offset-2" href="${url(F.R.source.url)}" target="_blank" rel="noopener noreferrer">Majestic Million</a> (CC BY 3.0), read ${fd(F.R.source.read)}. ` : ''}Covered: GitHub stars ${covered('g', p => p.stars != null)} of ${all.length} (the tool’s own repository, current count); site reach ${covered('r', p => p.rank)} of ${all.length} ; Wikipedia readers ${covered('a', p => p.read != null)} (Wikimedia pageviews, CC0: attention, not adoption; a change shows only on a base of 2,000 views); latest update ${covered('n', p => p.news || p.rel.length)} (the maker’s own feed or changelog in the past year, else its latest GitHub release in 30 days, by version and date); entry price ${covered('p', p => p.price)} (the maker’s pricing page as read; the lowest plan in its first listed currency).`,
        'taxonomy-index.json'
      )}`;
    };
    draw();
    el.onclick = e => {
      const s = e.target.closest('[data-sort]');
      if (s) {
        sort = el.dataset.sort = s.dataset.sort;
        draw();
      } else if (e.target.closest('[data-more]')) {
        open = !open;
        draw();
      }
    };
  },
};
