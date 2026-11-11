import { Method } from '../../ui/method.js';
import { ui } from '../../ui/recipes.js';
import { M, PARAMS, json } from '../../lib/data.js';
import { esc, fd, n, delta, url } from '../../lib/format.js';
import { MK } from '../../lib/market.js';
import { series, spark } from '../../lib/spark.js';
import { VIEW } from '../../lib/view.js';
import { latest, load, loading, under } from './scope.js';

/* A lens for developer packages only: npm and PyPI weekly downloads, each tool against its own earlier weeks */
const SORTS = { base: 'vs own weeks', delta: 'Week on week', value: 'Downloads' };
let sort = 'base',
  all = false;

export const panel = {
  id: 'downloads',
  title: 'Package downloads · developer tools only',
  note: 'npm and PyPI downloads exist only for software shipped as a package, so this lens covers developer tools and nothing else.',
  controls: () =>
    `<div class="${ui.segmented}" role="group" aria-label="Order">${Object.entries(SORTS)
      .map(([k, l]) => `<button type="button" class="${ui.segment}" data-sort="${k}" aria-pressed="${k === sort}">${l}</button>`)
      .join('')}</div>`,
  async render(scope, el) {
    const fresh = latest(el);
    el.className = 'flex flex-col gap-3 min-w-0';
    loading(el);
    const [D, P] = await Promise.all([load(), json('taxonomy-index.json').then(t => t.products)]);
    if (!fresh()) return;
    el.removeAttribute('aria-busy');
    const host = el.closest('[data-panel]');
    host._scope = scope; /* the handler below is wired once: it reads the scope of the latest render */
    if (!host._wired) {
      host._wired = true;
      host.addEventListener('click', e => {
        const b = e.target.closest('[data-sort],[data-more]');
        if (!b) return;
        if (b.dataset.sort) sort = b.dataset.sort;
        else all = !all;
        host.querySelectorAll('[data-sort]').forEach(x => x.setAttribute('aria-pressed', x.dataset.sort === sort));
        panel.render(host._scope, el);
      });
    }
    const Mv = (MK && MK.movers) || M.moversTop,
      B = Mv.params || PARAMS.movers;
    const node = id => P[id] && P[id][0][0];
    const rows = Mv.rows.filter(r =>
      r.dl.value != null && (scope.kind === 'all' || (scope.kind === 'node' ? under(D, node(r.id), scope.id) : (scope.ids || []).includes(r.id)))
    );
    const solid = r => r.dl.value >= B.solid_min_downloads;
    const key = { base: r => r.dl.vsBase, delta: r => r.dl.delta, value: r => r.dl.value }[sort];
    rows.sort((a, b) => solid(b) - solid(a) || (key(b) ?? -Infinity) - (key(a) ?? -Infinity) || a.name.localeCompare(b.name));
    const sectors = [...new Set(Mv.rows.map(r => node(r.id)).map(id => { let x = id; while (x && D.nodes[x] && D.nodes[x].parent) x = D.nodes[x].parent; return x && D.nodes[x] ? D.nodes[x].name : null; }).filter(Boolean))];
    const shown = all ? rows : rows.slice(0, VIEW.moversTop);
    const cell = v => delta(v);
    el.innerHTML = `<p class="text-xs text-muted-foreground leading-snug">${n(Mv.rows.length)} tools tracked, all in ${esc(sectors.length > 1 ? `${sectors.slice(0, -1).join(', ')} and ${sectors[sectors.length - 1]}` : sectors.join(''))}. ${rows.length ? '' : 'None of them is in this scope.'}</p>
      ${
        rows.length
          ? `<div class="overflow-x-auto"><table class="${ui.table}"><thead><tr><th class="${ui.th} whitespace-nowrap">Tool</th><th class="${ui.th} whitespace-nowrap text-right">Downloads<span class="hidden sm:inline">, 7 days</span></th><th class="${ui.th} whitespace-nowrap hidden sm:table-cell">${B.series_weeks} weeks</th><th class="${ui.th} whitespace-nowrap text-right">vs own<span class="hidden sm:inline"> ${B.base_weeks} weeks</span></th><th class="${ui.th} whitespace-nowrap text-right hidden sm:table-cell">Week on week</th></tr></thead><tbody>
        ${shown
          .map(r => {
            const s = series(r);
            return `<tr><td class="${ui.td} min-w-0"><span class="block max-w-[9rem] truncate sm:max-w-none "><a class="text-foreground hover:underline underline-offset-2" href="#app=${encodeURIComponent(r.id)}">${esc(r.name)}</a> <span class="hidden sm:inline text-xs text-muted-foreground">${esc(r.laneName)}</span></span></td>
            <td class="${ui.td} text-right ${ui.num} whitespace-nowrap">${n(r.dl.value)} ${r.dl.url ? `<a class="hidden sm:inline text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground" href="${url(r.dl.url)}" target="_blank" rel="noopener noreferrer">${esc(r.dl.registry)}</a>` : `<span class="hidden sm:inline text-xs text-muted-foreground">${esc(r.dl.registry)}</span>`}</td>
            <td class="${ui.td} hidden sm:table-cell">${(s && spark(s[0], s[1], `${r.name}, ${r.dl.registry} downloads`, { w: 96, h: 24 })) || ''}</td>
            <td class="${ui.td} text-right ${ui.num}">${solid(r) ? cell(r.dl.vsBase) : '<span class="text-xs text-muted-foreground">small base</span>'}</td>
            <td class="${ui.td} text-right ${ui.num} hidden sm:table-cell">${solid(r) ? cell(r.dl.delta) : ''}</td></tr>`;
          })
          .join('')}</tbody></table></div>
        ${rows.length > VIEW.moversTop ? `<button type="button" class="${ui.button.secondary} self-start" data-more>${all ? `Show top ${VIEW.moversTop}` : `Show all ${n(rows.length)}`}</button>` : ''}`
          : ''
      }
      ${Method(`Each registry’s own daily counts, ${fd(Mv.window.last7[0])} to ${fd(Mv.window.last7[1])}, fetched ${fd(Mv.generated)}. vs own weeks: the latest week against the tool’s own ${B.base_weeks}-week level. Changes are shown from ${n(B.solid_min_downloads)} downloads a week. npm and PyPI count different things: compare within a registry.`)}`;
  },
};
