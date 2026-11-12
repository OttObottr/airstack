import { $ } from '../../lib/dom.js';
import { esc, n } from '../../lib/format.js';
import { stack } from '../../lib/stack.js';
import { ALL, mount as mountPanel } from '../../ui/panel.js';
import { onMarket } from '../search/index.js';
import { panel as sectors } from './sectors.js';
import { landing } from './landing.js';
import { field } from './field.js';
import { changes, oss, support } from './changes.js';
import { load } from './scope.js';

/* The Markets view: pick a market, see the named field. With no market picked, the landing cards and what is ending soon
   everywhere; with one picked (or your stack), its products by name, what their makers announced, support ending, and its
   open-source projects. Panels a scope cannot fill are left out rather than shown empty. */
const WIDE = 'lg:col-span-2';
const layout = (scope, D) => {
  if (scope.kind === 'all') return [[landing, WIDE], [support, ''], [sectors, '']];
  const kids = scope.kind === 'node' && Object.keys(D.nodes).some(k => D.nodes[k].parent === scope.id);
  return [[field, WIDE], [changes, ''], [support, ''], ...(scope.kind === 'node' ? [[oss, '']] : []), ...(kids ? [[sectors, '']] : [])];
};
let scope = ALL;

export function mount() {
  const grid = $('#mkGrid'),
    pick = $('#mkScope');
  if (!grid) return;
  pick.style.maxWidth = '100%'; /* long market names must not widen the page on a phone */
  pick.style.minWidth = '0';
  let live = [];
  const draw = D => {
    const cells = layout(scope, D);
    grid.innerHTML = cells.map(([p, span]) => `<div class="min-w-0 ${span}"><section aria-label="${esc(p.title)}"></section></div>`).join('');
    live = cells.map(([p], i) => mountPanel(grid.children[i].firstElementChild, p, scope));
  };
  const path = (D, id) => {
    const out = [];
    for (let x = id; x && D.nodes[x]; x = D.nodes[x].parent) out.unshift(D.nodes[x].name);
    return out;
  };
  const options = D => {
    const N = D.nodes,
      tops = Object.keys(N)
        .filter(k => N[k].parent === null)
        .sort((a, b) => N[a].name.localeCompare(N[b].name));
    const below = top => Object.keys(N).filter(k => k !== top && N[k].listed && path(D, k)[0] === N[top].name);
    const st = stack();
    pick.innerHTML =
      `<option value="all">All markets</option>` +
      (st.length ? `<option value="stack">Your stack · ${st.length}</option>` : '') +
      tops
        .map(
          t => `<optgroup label="${esc(N[t].name)}"><option value="node:${esc(t)}">All of ${esc(N[t].name)} · ${n(N[t].listed)}</option>${below(t)
            .sort((a, b) => path(D, a).join(' › ').localeCompare(path(D, b).join(' › ')))
            .map(k => `<option value="node:${esc(k)}">${esc(path(D, k).slice(1).join(' › '))} · ${n(N[k].listed)}</option>`)
            .join('')}</optgroup>`
        )
        .join('');
    pick.value = scope.kind === 'all' ? 'all' : scope.kind === 'stack' ? 'stack' : `node:${scope.id}`;
  };
  const set = s => {
    scope = s;
    load().then(D => {
      options(D);
      draw(D);
      if (s.kind !== 'all') grid.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
  };
  load().then(D => {
    options(D);
    draw(D);
  });
  pick.addEventListener('change', () => {
    const v = pick.value;
    set(v === 'all' ? ALL : v === 'stack' ? { kind: 'stack', ids: stack().map(x => x.id) } : { kind: 'node', id: v.slice(5) });
  });
  grid.addEventListener('click', e => {
    const b = e.target.closest('button[data-node]');
    if (b) set({ kind: 'node', id: b.dataset.node });
  });
  addEventListener('airstack:stack', () => {
    if (scope.kind === 'stack') set({ kind: 'stack', ids: stack().map(x => x.id) });
    else load().then(options);
  });
  onMarket(() => live.forEach(m => m.update(scope))); /* researched marks arrive with the market file */
}
