import { Method } from '../../ui/method.js';
import { ui } from '../../ui/recipes.js';
import { json } from '../../lib/data.js';
import { esc, fd, n, pct, url } from '../../lib/format.js';
import { spark } from '../../lib/spark.js';
import { VIEW } from '../../lib/view.js';
import { latest, load, loading, nameOf, rows } from './scope.js';

/* Long-run interest: English Wikipedia views of each product's article (attention.json), ranked in the scope, its own trend and
   its change against its own prior window. Lagging, and only for products with an article. */
const LENSES = ['Top', 'Rising', 'Falling'];
let lens = 'Top',
  pick = null,
  shownNode = null;

function ids(A, D, scope, R) {
  if (R.products) {
    const got = R.products.map(p => p.id).filter(id => A.products[id] && A.products[id].last_4w != null);
    const by = { Top: p => -A.products[p].last_4w, Rising: p => -(A.products[p].change ?? -Infinity), Falling: p => A.products[p].change ?? Infinity };
    return got.sort((a, b) => by[lens](a) - by[lens](b));
  }
  let node = scope.kind === 'node' ? scope.id : pick && A.nodes[pick] ? pick : R.nodes.filter(id => A.nodes[id]).sort((a, b) => A.nodes[b].products - A.nodes[a].products)[0];
  while (node && !A.nodes[node]) node = D.nodes[node] && D.nodes[node].parent;
  pick = scope.kind === 'all' ? node : pick;
  shownNode = node;
  return node ? A.nodes[node][lens.toLowerCase()].filter(id => A.products[id]) : [];
}

const row = (A, D, id, i) => {
  const p = A.products[id],
    nm = (x => (x === id ? p.article : x))(nameOf(id, D)),
    P = A.source.params;
  return `<tr><td class="${ui.td} text-right ${ui.num} text-muted-foreground w-8 hidden sm:table-cell">${i + 1}</td>
    <td class="${ui.td} min-w-0"><a class="block max-w-[9rem] truncate sm:max-w-none text-foreground hover:underline underline-offset-2" href="#app=${encodeURIComponent(id)}">${esc(nm)}</a></td>
    <td class="${ui.td} text-right ${ui.num}">${n(p.last_4w)}</td>
    <td class="${ui.td} hidden sm:table-cell">${spark(p.views, A.weeks, `${nm}, English Wikipedia views`, { w: 96, h: 24, maxMissing: A.source.params.max_missing_share ?? 1 }) || ''}</td>
    <td class="${ui.td} text-right ${ui.num}">${p.change != null && p.prior_4w >= P.min_baseline ? pct(p.change * 100) : '<span class="text-muted-foreground" title="under the baseline or not recorded">·</span>'}</td>
    <td class="${ui.td} hidden md:table-cell"><a class="text-muted-foreground hover:text-foreground underline underline-offset-2" href="${url(p.url)}" target="_blank" rel="noopener noreferrer">${esc(p.article)}</a></td></tr>`;
};

export const panel = {
  id: 'interest',
  title: 'Long-run interest',
  note: 'English Wikipedia views of each product’s article. Lagging, and only for products with an article: a slow read of interest, not of use or day-to-day conversation.',
  controls: () =>
    `<div class="${ui.segmented}" role="group" aria-label="Order">${LENSES.map(l => `<button type="button" class="${ui.segment}" data-lens="${l}" aria-pressed="${l === lens}">${l}</button>`).join('')}</div>`,
  async render(scope, el) {
    const fresh = latest(el);
    el.className = 'flex flex-col gap-3 min-w-0';
    loading(el);
    const [A, D, R] = await Promise.all([json('attention.json'), load(), rows(scope)]);
    if (!fresh()) return;
    el.removeAttribute('aria-busy');
    const head = el.closest('[data-panel]');
    head._scope = scope; /* the handlers below are wired once: they read the scope of the latest render */
    if (!head._wired) {
      head._wired = true;
      head.addEventListener('click', e => {
        const b = e.target.closest('[data-lens]');
        if (!b) return;
        lens = b.dataset.lens;
        head.querySelectorAll('[data-lens]').forEach(x => x.setAttribute('aria-pressed', x === b));
        panel.render(head._scope, el);
      });
      head.addEventListener('change', e => {
        if (e.target.matches('[data-pick]')) (pick = e.target.value), panel.render(head._scope, el);
      });
    }
    const list = ids(A, D, scope, R),
      P = A.source.params,
      W = A.weeks,
      S = A.source;
    const picker =
      scope.kind === 'all'
        ? `<select data-pick class="h-8 rounded-md border border-border bg-background px-2 text-xs text-foreground" aria-label="Sector">${R.nodes
            .filter(id => A.nodes[id])
            .map(id => `<option value="${esc(id)}"${id === pick ? ' selected' : ''}>${esc(D.nodes[id].name)}</option>`)
            .join('')}</select>`
        : '';
    const moved = scope.kind === 'node' && shownNode && shownNode !== scope.id && D.nodes[scope.id];
    el.innerHTML = `${picker}${moved ? `<p class="${ui.panelNote}">Showing ${esc(D.nodes[shownNode].name)}: no product filed under ${esc(D.nodes[scope.id].name)} has a matched article.</p>` : ''}
      ${
        list.length
          ? `<div class="overflow-x-auto"><table class="${ui.table}"><thead><tr><th class="${ui.th} whitespace-nowrap text-right hidden sm:table-cell">#</th><th class="${ui.th} whitespace-nowrap">Product</th><th class="${ui.th} whitespace-nowrap text-right">Views<span class="hidden sm:inline">, ${P.window_weeks} weeks</span></th><th class="${ui.th} whitespace-nowrap hidden sm:table-cell">${P.weeks} weeks</th><th class="${ui.th} whitespace-nowrap text-right">vs prior<span class="hidden sm:inline"> ${P.window_weeks}</span></th><th class="${ui.th} whitespace-nowrap hidden md:table-cell">Article</th></tr></thead>
        <tbody>${list
          .slice(0, VIEW.attentionShown)
          .map((id, i) => row(A, D, id, i))
          .join('')}</tbody></table></div>`
          : `<p class="${ui.panelNote}">${lens === 'Top' ? 'No product here has a matched English Wikipedia article.' : `No product here is ${lens.toLowerCase()} by the rule below.`}</p>`
      }
      ${Method(`${n(Math.min(VIEW.attentionShown, list.length))} of ${n(list.length)} shown · weeks of ${fd(W[0])} to ${fd(W[W.length - 1])} · rising and falling need at least ${n(P.min_baseline)} views in the prior ${P.window_weeks} weeks · <a class="underline underline-offset-2 hover:text-foreground" href="${url(S.url)}" target="_blank" rel="noopener noreferrer">${esc(S.name)}</a>, ${esc(S.license)}, read ${fd(S.read)}`)}`;
  },
};
