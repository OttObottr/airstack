/* Insights: where a category breaks from the average (findings.js), and what each category's products state on their own pages. */
import { json } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { n } from '../lib/format.js';
import { mountScoped } from '../lib/scope.js';
import { html } from '../ui/html.js';
import { mount as mountPanel } from '../ui/panel.js';
import { ui } from '../ui/recipes.js';
import { panel as findings } from './findings.js';

const NUM = `${ui.td} text-right ${ui.num}`;
/* a share with its count, and a bar of the same share behind the reading */
const share = (found, of) => {
  const v = of ? Math.round((found / of) * 100) : null;
  return v == null
    ? html`<td class="${NUM} text-muted-foreground">—</td>`
    : html`<td class="${NUM}"><span class="flex items-center justify-end gap-3"><span class="text-xs text-muted-foreground">${n(found)} of ${n(of)}</span><span class="w-10 text-foreground">${v}%</span><span class="h-1.5 w-20 overflow-hidden rounded-full bg-muted max-sm:hidden"><span class="block h-full rounded-full bg-info" style="width:${v}%"></span></span></span></td>`;
};

const disclosure = {
  id: 'disclosure',
  title: 'What each category states',
  note: 'The share of products whose own pages say so, of the products read in that category.',
  async render(scope, el) {
    const I = await json('insights.json'),
      cats = Object.values(I.categories).filter(c => c.researched),
      of = (c, k) => (c.found_of && c.found_of[k]) || { found: c[k], of: c.researched },
      K = I.kpis.filter(k => cats.filter(c => of(c, k.key).found).length > 2) /* a column found in almost no category says nothing */,
      groups = I.departments.map(d => [d, cats.filter(c => c.department === d).sort((a, b) => b.researched - a.researched)]).filter(g => g[1].length);
    el.innerHTML = String(html`<div class="overflow-x-auto"><table class="${ui.table}">
      <thead><tr><th class="${ui.th}">Category</th><th class="${ui.th} text-right">Products read</th>${K.map(k => html`<th class="${ui.th} text-right">${k.label}</th>`)}</tr></thead>
      ${groups.map(([d, cs]) => html`<tbody><tr><th class="h-9 px-2 pt-3 text-left align-middle eyebrow" colspan="${K.length + 2}" scope="colgroup">${d}</th></tr>
        ${cs.map(c => html`<tr class="hover:bg-muted"><th class="${ui.td} text-left font-medium text-foreground" scope="row">${c.name}</th><td class="${NUM}">${n(c.researched)} <span class="text-xs text-muted-foreground">of ${n(c.listed)}</span></td>${K.map(k => share(of(c, k.key).found, of(c, k.key).of))}</tr>`)}</tbody>`)}
    </table></div>`);
  },
};

/* loaded when the view first opens (main.js) */
export function mount() {
  mountScoped($('#insFindings'), findings);
  mountPanel($('#insDisclosure'), disclosure);
}
