import { $ } from '../../lib/dom.js';
import { esc } from '../../lib/format.js';
import { stack } from '../../lib/stack.js';
import { ALL, mount as mountPanel } from '../../ui/panel.js';
import { onMarket } from '../search/index.js';
import { panel as sectors } from './sectors.js';
import { panel as announcements } from './announcements.js';
import { arrivals, mix } from './landscape.js';
import { load } from './scope.js';

/* The Markets view: a scope picker standing in for the workspace rail, and the panels in one grid */
const CELLS = [
  [arrivals, ''],
  [mix, ''],
  [announcements, ''],
  [sectors, ''],
];
let scope = ALL;

export function mount() {
  const grid = $('#mkGrid'),
    pick = $('#mkScope');
  if (!grid) return;
  grid.innerHTML = CELLS.map(([p, span]) => `<div class="min-w-0 ${span}"><section aria-label="${esc(p.title)}"></section></div>`).join('');
  const live = CELLS.map(([p], i) => mountPanel(grid.children[i].firstElementChild, p, scope));
  const set = s => {
    scope = s;
    live.forEach(m => m.update(scope));
  };
  const options = D => {
    const tops = Object.keys(D.nodes).filter(k => D.nodes[k].parent === null);
    const node = scope.kind === 'node' ? scope.id : null,
      extra = node && !tops.includes(node) ? [node] : [];
    const st = stack();
    pick.innerHTML =
      `<option value="all">All sectors</option>` +
      tops
        .sort((a, b) => D.nodes[a].name.localeCompare(D.nodes[b].name))
        .concat(extra)
        .map(id => `<option value="node:${esc(id)}">${extra.includes(id) ? `${esc(D.nodes[D.nodes[id].parent].name)} › ` : ''}${esc(D.nodes[id].name)}</option>`)
        .join('') +
      (st.length ? `<option value="stack">Your stack · ${st.length}</option>` : '');
    pick.value = scope.kind === 'all' ? 'all' : scope.kind === 'stack' ? 'stack' : `node:${scope.id}`;
  };
  load().then(options);
  pick.addEventListener('change', () => {
    const v = pick.value;
    set(v === 'all' ? ALL : v === 'stack' ? { kind: 'stack', ids: stack().map(x => x.id) } : { kind: 'node', id: v.slice(5) });
  });
  grid.addEventListener('click', e => {
    const b = e.target.closest('button[data-node]');
    if (!b) return;
    set({ kind: 'node', id: b.dataset.node });
    load().then(options);
  });
  addEventListener('airstack:stack', () => {
    load().then(options);
    if (scope.kind === 'stack') set({ kind: 'stack', ids: stack().map(x => x.id) });
  });
  onMarket(() => live.forEach(m => m.update(scope))); /* researched marks and the full download rows arrive with the market file */
}
