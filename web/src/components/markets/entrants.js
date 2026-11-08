import { ui } from '../../ui/recipes.js';
import { esc, n } from '../../lib/format.js';
import { findings, latest, loading, peerName, rows, share, sourceLine, under } from './scope.js';

/* New entrants: products whose Wikidata inception year falls in the window, with the base that year is known for */
const SAY = {
  entrants: (o, p) =>
    `${n(o.entrants)} of ${n(o.dated)} dated products are new (${share(o.entrants, o.dated)}%), against ${share(p.entrants, p.dated)}% ${peerName(p)} (${n(p.entrants)} of ${n(p.dated)}).`,
};

export const panel = {
  id: 'entrants',
  title: 'New entrants',
  note: 'Products whose inception year on Wikidata is recent. Only a share of products has an inception year: the base is stated.',
  async render(scope, el) {
    const fresh = latest(el);
    el.className = 'flex flex-col gap-3 min-w-0';
    loading(el);
    const R = await rows(scope);
    if (!fresh()) return;
    const D = R.D;
    el.removeAttribute('aria-busy');
    const inScope = R.products
      ? D.entrants.filter(r => R.products.some(p => p.id === r[0]))
      : D.entrants.filter(r => R.nodes.some(id => under(D, r[3], id)));
    const base = R.products
      ? { dated: R.products.filter(p => p.rec && p.rec[2]).length, listed: R.products.length }
      : R.nodes.reduce((s, id) => ({ dated: s.dated + D.nodes[id].dated, listed: s.listed + D.nodes[id].listed }), { dated: 0, listed: 0 });
    const f = R.products ? [] : findings(D, R.nodes, R.peer, SAY);
    el.innerHTML = `<p class="text-sm"><span class="${ui.num} text-foreground">${n(inScope.length)}</span> <span class="text-muted-foreground">new since ${D.entrants_from}, of ${n(base.dated)} products with an inception year (${n(base.listed)} listed).</span></p>
      ${f.length ? `<ul class="flex flex-col gap-2">${f.join('')}</ul>` : R.products ? '' : `<p class="${ui.panelNote}">No share of new entrants here differs enough from its peers to report.</p>`}
      ${
        inScope.length
          ? `<ul class="flex flex-col">${inScope
              .map(
                ([id, name, year, node, q]) =>
                  `<li class="flex items-center justify-between gap-3 h-10 border-b border-border text-sm"><span class="min-w-0 truncate"><a class="text-foreground hover:underline underline-offset-2" href="#app=${encodeURIComponent(id)}">${esc(name)}</a> <span class="text-muted-foreground">${esc((D.nodes[node] || {}).name || '')}</span></span>
                  <a class="${ui.num} text-muted-foreground hover:text-foreground underline underline-offset-2" href="https://www.wikidata.org/wiki/${encodeURIComponent(q)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(name)}: inception ${year} on Wikidata">${year}</a></li>`
              )
              .join('')}</ul>`
          : ''
      }
      ${sourceLine(D.source.inception, 'markets.json')}`;
  },
};
