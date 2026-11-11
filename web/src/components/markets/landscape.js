/* Two readings only AirStack's own record gives: how many products each sector produced in each year (the dated chronology behind
   the pulse), and what kind of news each sector is making now (every vendor post, read and classed). */
import { json } from '../../lib/data.js';
import { esc, n } from '../../lib/format.js';
import { ui } from '../../ui/recipes.js';
import { latest, load, loading, sourceLine, under } from './scope.js';

const SW = [...ui.sector, 'bg-sector-other/40'];
const NEW = new Set(['new', 'founded', 'launch', 'ga', 'general availability', 'beta', 'announced']); /* the record's own event types: a product arriving, not a version of one */
const KIND = [
  ['launch', 'bg-info'],
  ['feature', 'bg-sector-3'],
  ['security', 'bg-warn'],
  ['incident', 'bg-down'],
  ['pricing', 'bg-maker'],
  ['release', 'bg-sector-other'],
];
const key = (cls, label) => `<span class="inline-flex items-center gap-1.5"><i class="inline-block size-2.5 rounded-[2px] ${cls}" aria-hidden="true"></i>${esc(label)}</span>`;
const legend = items => `<p class="flex flex-wrap gap-x-4 gap-y-1 ${ui.panelNote}">${items.map(([c, l]) => key(c, l)).join('')}</p>`;

/* one floating note for every mark on the page: it follows the pointer's mark and moves nothing */
let tip;
function hover(el) {
  if (!tip) {
    tip = document.createElement('div');
    tip.className = 'pointer-events-none fixed z-50 hidden max-w-72 rounded-md border border-border bg-popover px-3 py-2 text-xs text-foreground shadow-lg';
    document.body.append(tip);
    addEventListener('scroll', () => tip.classList.add('hidden'), { passive: true });
  }
  if (el.dataset.tips) return;
  el.dataset.tips = '1';
  el.addEventListener('pointerover', e => {
    const m = e.target.closest('[data-tip]');
    if (!m) return void tip.classList.add('hidden');
    tip.innerHTML = m.dataset.tip;
    tip.classList.remove('hidden');
    const r = m.getBoundingClientRect();
    tip.style.left = `${Math.max(8, Math.min(innerWidth - tip.offsetWidth - 8, r.left + r.width / 2 - tip.offsetWidth / 2))}px`;
    tip.style.top = `${r.top > tip.offsetHeight + 16 ? r.top - tip.offsetHeight - 8 : r.bottom + 8}px`;
  });
  el.addEventListener('pointerleave', () => tip.classList.add('hidden'));
}

/* the pulse sector a taxonomy node belongs to: its top node where the pulse names it, otherwise "Other sectors" */
const sectorOf = (P, node) => {
  let x = node;
  while (x && P.tree[x] && P.tree[x][0]) x = P.tree[x][0];
  const j = P.sectors.findIndex(s => s.id === x);
  return j >= 0 ? j : P.sectors.findIndex(s => s.id === 'other');
};

export const arrivals = {
  id: 'arrivals',
  title: 'New products by year',
  note: 'Products launched, founded or first made available in each year, by sector, from dated records each checked against its own page.',
  async render(scope, el) {
    const fresh = latest(el);
    loading(el);
    const P = await json('pulse.json');
    if (!fresh()) return;
    el.removeAttribute('aria-busy');
    const only = scope.kind === 'node' ? sectorOf(P, scope.id) : null,
      mine = scope.kind === 'stack' ? new Set(scope.ids) : null,
      S = P.sectors.map((s, j) => j).filter(j => P.sectors[j].id !== 'unplaced' && (only == null || j === only)),
      by = new Map();
    for (const e of P.events) {
      if (e.via !== 'chronology' || !NEW.has(e.what) || (mine && !mine.has(e.id))) continue;
      const y = e.at.slice(0, 4);
      if (!by.has(y)) by.set(y, P.sectors.map(() => 0));
      by.get(y)[e.sector]++;
    }
    const years = [...by.keys()].sort().slice(-4), /* the years the record covers in depth */
      total = y => S.reduce((a, j) => a + by.get(y)[j], 0),
      top = Math.max(1, ...years.map(total));
    if (!years.some(total)) return void (el.innerHTML = `<p class="${ui.panelNote}">No dated arrivals in this scope yet.</p>`);
    el.className = 'flex flex-col gap-3 min-w-0';
    el.innerHTML = `${S.length > 1 ? legend(S.filter(j => years.some(y => by.get(y)[j])).map(j => [SW[j], P.sectors[j].name])) : ''}
      <div class="flex h-56 items-end gap-2 border-b border-border" role="img" aria-label="${esc(years.map(y => `${y}: ${total(y)}`).join(', '))}">${years
        .map(
          y => `<div class="flex h-full min-w-0 flex-1 flex-col justify-end gap-1"><span class="${ui.num} text-center text-xs text-muted-foreground">${n(total(y))}</span>
            <div class="flex flex-col-reverse gap-px" style="height:${((total(y) / top) * 88).toFixed(1)}%">${S.filter(j => by.get(y)[j])
              .map(j => `<i class="block w-full rounded-[3px] ${SW[j]}" style="flex:${by.get(y)[j]} 1 0" data-tip="${esc(`<b>${esc(P.sectors[j].name)}</b> · ${y}<br>${n(by.get(y)[j])} of ${n(total(y))} new products`)}"></i>`)
              .join('')}</div></div>`
        )
        .join('')}</div>
      <div class="flex gap-2 ${ui.num} text-xs text-muted-foreground">${years.map(y => `<span class="min-w-0 flex-1 text-center">${y}</span>`).join('')}</div>
      ${sourceLine('Counts are of the records AirStack holds, not of every product launched: later years are more fully covered.', 'pulse.json')}`;
    hover(el);
  },
};

export const mix = {
  id: 'news-mix',
  title: 'What the news is about',
  note: 'Vendor posts and releases in the window, classed by what they announce.',
  async render(scope, el) {
    const fresh = latest(el);
    loading(el);
    const [N, T, D] = await Promise.all([json('news.json'), json('taxonomy-index.json'), load()]);
    if (!fresh()) return;
    el.removeAttribute('aria-busy');
    const tops = Object.keys(D.nodes).filter(k => D.nodes[k].parent === (scope.kind === 'node' ? scope.id : null)),
      groups = tops.length ? tops : scope.kind === 'node' ? [scope.id] : [],
      mine = scope.kind === 'stack' ? new Set(scope.ids) : null,
      rows = new Map(mine ? [['stack', { name: 'Your stack', c: {} }]] : groups.map(g => [g, { name: D.nodes[g].name, c: {} }]));
    for (const i of N.items) {
      if (!i.signal || i.signal === 'other') continue;
      const node = T.products[i.id] && T.products[i.id][0][0],
        g = mine ? (mine.has(i.id) ? 'stack' : null) : groups.find(x => node && under(D, node, x));
      if (g) rows.get(g).c[i.signal] = (rows.get(g).c[i.signal] || 0) + 1;
    }
    const sum = r => KIND.reduce((a, [k]) => a + (r.c[k] || 0), 0),
      R = [...rows.values()].filter(sum).sort((a, b) => sum(b) - sum(a)),
      top = Math.max(1, ...R.map(sum));
    if (!R.length) return void (el.innerHTML = `<p class="${ui.panelNote}">No classed announcements in this scope in the last ${N.source.window_days} days.</p>`);
    el.className = 'flex flex-col gap-3 min-w-0';
    el.innerHTML = `${legend(KIND.filter(([k]) => R.some(r => r.c[k])).map(([k, c]) => [c, k]))}
      <div class="flex flex-col gap-2">${R.map(
        r => `<div class="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)_2.5rem] items-center gap-x-3"><span class="truncate text-sm text-muted-foreground">${esc(r.name)}</span>
          <span class="flex h-4 gap-0.5" style="width:${((sum(r) / top) * 100).toFixed(1)}%">${KIND.filter(([k]) => r.c[k])
            .map(([k, c]) => `<i class="block h-full rounded-[3px] ${c}" style="flex:${r.c[k]} 1 0" data-tip="${esc(`<b>${esc(r.name)}</b><br>${n(r.c[k])} ${k} of ${n(sum(r))}`)}"></i>`)
            .join('')}</span>
          <span class="${ui.num} text-right text-sm text-foreground">${n(sum(r))}</span></div>`
      ).join('')}</div>
      ${sourceLine(`Posts and releases from the last ${N.source.window_days} days of the products whose own channels AirStack reads; a feed keeps only its latest posts.`, 'news.json')}`;
    hover(el);
  },
};
