import { ui } from '../../ui/recipes.js';
import { esc, n } from '../../lib/format.js';
import { MK } from '../../lib/market.js';
import { latest, loading, meter, ofCell, rows, share, sourceLine } from './scope.js';

/* Sector overview: every node measured the same way, whatever kind of software it holds */
const TH = `${ui.th} text-right whitespace-nowrap`,
  TD = `${ui.td} text-right ${ui.num}`;

const nodeRow = (D, id) => {
  const o = D.nodes[id],
    r = share(o.researched, o.listed);
  return `<tr class="hover:bg-muted">
    <td class="${ui.td} min-w-0"><button type="button" class="block max-w-[9rem] truncate sm:max-w-none text-left text-sm text-foreground hover:underline underline-offset-2" data-node="${esc(id)}">${esc(o.name)}</button></td>
    <td class="${TD}">${n(o.listed)}</td>
    <td class="${TD}"><span class="flex items-center gap-2"><span class="w-10 text-right">${r == null ? '' : `${r}%`}</span>${meter(r)}</span></td>
    <td class="${TD} hidden sm:table-cell">${ofCell(o.announced, o.watched)}</td>
    <td class="${TD} hidden md:table-cell">${ofCell(o.entrants, o.dated)}</td></tr>`;
};

const productRow = p => {
  const [items, stories, year] = p.rec || [];
  const researched = MK && MK.profiles ? (MK.profiles[p.id] ? 'Yes' : 'No') : '';
  return `<tr><td class="${ui.td}"><a class="text-foreground hover:underline underline-offset-2" href="#app=${encodeURIComponent(p.id)}">${esc(p.name)}</a></td>
    <td class="${TD}">${researched}</td><td class="${TD}">${p.rec && p.rec[3] ? n(items) : '<span class="text-muted-foreground">Not watched</span>'}</td>
    <td class="${TD} hidden sm:table-cell">${p.rec && p.rec[3] ? n(stories) : ''}</td><td class="${TD} hidden md:table-cell">${year || '<span class="text-muted-foreground">Not recorded</span>'}</td></tr>`;
};

export const panel = {
  id: 'sectors',
  title: 'Sectors',
  note: 'Every product we list, measured the same way: how many, how many we have researched, who announced something and who is new.',
  async render(scope, el) {
    const fresh = latest(el);
    el.className = 'flex flex-col gap-3 min-w-0';
    loading(el);
    const R = await rows(scope);
    if (!fresh()) return;
    const D = R.D,
      days = Math.round((Date.parse(D.window[1]) - Date.parse(D.window[0])) / 864e5);
    el.removeAttribute('aria-busy');
    if (R.products) {
      el.innerHTML = R.products.length
        ? `<div class="overflow-x-auto"><table class="${ui.table}"><thead><tr><th class="${ui.th}">Product</th><th class="${TH}">Researched</th><th class="${TH}">Announcements, ${days} days</th><th class="${TH} hidden sm:table-cell">Hacker News stories</th><th class="${TH} hidden md:table-cell">Inception</th></tr></thead><tbody>${R.products.map(productRow).join('')}</tbody></table></div>`
        : `<p class="${ui.panelNote}">Nothing here yet. Add products to your stack to see them measured.</p>`;
      return;
    }
    const total = R.nodes.reduce((s, id) => s + D.nodes[id].listed, 0);
    el.innerHTML = `<div class="overflow-x-auto"><table class="${ui.table}"><thead><tr><th class="${ui.th}">${R.peer.parent === undefined ? 'Sector' : 'Category'}</th><th class="${TH}">Listed</th><th class="${TH} w-1/4">Researched</th>
      <th class="${TH} hidden sm:table-cell">Announced, ${days} days <span class="font-normal">(of watched)</span></th><th class="${TH} hidden md:table-cell">New since ${D.entrants_from} <span class="font-normal">(of dated)</span></th></tr></thead>
      <tbody>${R.nodes
        .sort((a, b) => D.nodes[b].listed - D.nodes[a].listed)
        .map(id => nodeRow(D, id))
        .join('')}</tbody></table></div>
      ${sourceLine(`${n(total)} products placed in this scope. Researched: facts read from the product's own pages. Watched: products whose own feed, changelog or releases we read; for the rest an announcement is unknown, not zero. Dated: products with an inception year on Wikidata.`, 'markets.json')}`;
  },
};
