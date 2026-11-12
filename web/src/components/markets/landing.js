import { esc, n } from '../../lib/format.js';
import { ui } from '../../ui/recipes.js';
import { mono } from '../avatar.js';
import { latest, loading, sourceLine } from './scope.js';
import { SORTS, activeSince, bestSort, ensureNames, files, nameOf, rowsOf } from './field.js';

/* The Markets landing: one card per market, led by the products in it by name, ordered by how many of them announced
   something lately. Every category is reachable from "All markets", grouped by sector. */

const DAYS = 30,
  CARDS = 12;
const from = () => new Date(Date.now() - DAYS * 864e5).toISOString().slice(0, 10);

function markets(F) {
  const D = F.D,
    since = from();
  const members = new Map();
  for (const [pid, places] of Object.entries(F.T.products))
    for (const [node] of places) {
      if (!D.nodes[node] || D.nodes[node].parent === null) continue;
      if (!members.has(node)) members.set(node, new Set());
      members.get(node).add(pid);
    }
  return [...members]
    .map(([id, set]) => {
      const ps = [...set];
      const rows = rowsOf(F, ps),
        k = bestSort(rows),
        ranked = rows.filter(SORTS[k].has).sort(SORTS[k].by).map(r => r.id);
      const active = ps.filter(p => activeSince(F, p, since));
      return { id, ids: ps, name: D.nodes[id].name, sector: D.nodes[D.nodes[id].parent] ? D.nodes[D.nodes[id].parent].name : '', size: ps.length, top: ranked.slice(0, 3), active: active.length };
    })
    .filter(m => m.size >= 1);
}

const card = m => `<button type="button" data-node="${esc(m.id)}" class="flex flex-col gap-3 rounded-lg border border-border bg-background p-4 text-left hover:border-input hover:bg-muted/40">
  <span class="flex flex-col gap-1"><span class="text-sm font-semibold text-foreground">${esc(m.name)}</span><span class="${ui.meta}">${esc(m.sector)}</span></span>
  <span class="flex flex-col gap-1.5">${(m.top.length ? m.top : m.ids.slice(0, 3)).map(id => `<span class="flex items-center gap-2 text-sm text-muted-foreground">${mono({ id, name: nameOf(id) }, 's20')}<span class="truncate">${esc(nameOf(id))}</span></span>`).join('')}</span>
  <span class="${ui.meta} mt-auto">${n(m.size)} products${m.active ? ` · <span class="text-foreground">${n(m.active)} announced in ${DAYS} days</span>` : ''}</span></button>`;

export const landing = {
  id: 'landing',
  title: 'Pick a market',
  note: `Each card is a category of software, led by three of its products, by whichever size reading (GitHub stars, site reach or Wikipedia readers) covers most of it. Ordered by how many of them announced something on their own channels in the last ${DAYS} days.`,
  async render(scope, el) {
    const fresh = latest(el);
    el.className = 'flex flex-col gap-3 min-w-0';
    loading(el);
    const F = await files();
    await ensureNames();
    if (!fresh()) return;
    el.removeAttribute('aria-busy');
    const all = markets(F).sort((a, b) => b.active - a.active || b.top.length - a.top.length || b.size - a.size);
    const named = n => all.filter(m => m.top.length >= n);
    const lead = (named(2).length >= 3 ? named(2) : named(1).length ? named(1) : all).slice(0, CARDS); /* lead with markets whose products we can name */
    const bySector = new Map();
    for (const m of all.slice().sort((a, b) => a.name.localeCompare(b.name))) {
      if (!bySector.has(m.sector)) bySector.set(m.sector, []);
      bySector.get(m.sector).push(m);
    }
    el.innerHTML = `<div class="${ui.grid}">${lead.map(card).join('')}</div>
      <details class="group"><summary class="${ui.button.ghost} inline-flex cursor-pointer list-none">All ${n(all.length)} markets</summary>
      <div class="mt-3 grid gap-x-6 gap-y-4 grid-cols-1 sm:grid-cols-2 xl:grid-cols-3">${[...bySector]
        .sort((a, b) => a[0].localeCompare(b[0]))
        .map(
          ([s, ms]) => `<div class="flex flex-col gap-1"><span class="${ui.tileLabel} mb-1">${esc(s)}</span>${ms
            .map(m => `<button type="button" data-node="${esc(m.id)}" class="flex justify-between gap-2 text-left text-sm text-muted-foreground hover:text-foreground"><span class="truncate">${esc(m.name)}</span><span class="${ui.num} text-subtle-foreground">${n(m.size)}</span></button>`)
            .join('')}</div>`
        )
        .join('')}</div></details>
      ${sourceLine('Categories: AirStack’s taxonomy (CC BY 4.0). Site reach: Majestic Million (CC BY 3.0). Announcements: the makers’ own channels.', 'taxonomy-index.json')}`;
  },
};
