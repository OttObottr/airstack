/* Scope, one meaning everywhere: { kind: 'all' | 'node' | 'stack' | 'maker', id?, ids? } (ui/panel.js). A node scope holds everything
   filed under that taxonomy node; a stack or maker scope holds its product ids. This module also draws the one scope control
   ("All products | Your stack · N", Manage) and the add/remove-from-stack toggle, and mounts a panel so both work. */
import { json } from './data.js';
import { esc } from './format.js';
import { stack, toggle, tracked } from './stack.js';
import { ALL, mount } from '../ui/panel.js';
import { ui } from '../ui/recipes.js';

/* is a row (a product id, the taxonomy node it is filed under) inside the scope? tree: {node: [parent, name]} */
export function inScope(scope, row, tree) {
  if (!scope || scope.kind === 'all') return true;
  if (scope.ids) return scope.ids.includes(row.id);
  if (scope.kind === 'node') for (let n = row.node; n; n = tree && tree[n] ? tree[n][0] : null) if (n === scope.id) return true;
  return false;
}
/* the taxonomy node of each product, for rows that carry only an id (taxonomy-index.json, loaded once, on demand) */
let placed = null;
export const nodeOf = () => (placed ||= json('taxonomy-index.json').then(d => id => ((d.products || {})[id] || [[null]])[0][0]));

export const stackScope = () => (stack().length ? { kind: 'stack', ids: stack().map(x => x.id) } : ALL);
export const scopeName = (scope, tree) =>
  !scope || scope.kind === 'all' ? 'All products' : scope.kind === 'stack' ? 'Your stack' : (tree && tree[scope.id] && tree[scope.id][1]) || scope.id;

const LINK = 'text-xs leading-none text-muted-foreground underline underline-offset-4 decoration-border hover:text-foreground';
/* "All products | Your stack · N" and Manage; an empty stack says so and links to adding tools */
export function scopeControl(scope, what = 'changes') {
  const k = stack().length,
    mine = scope && scope.kind === 'stack';
  if (!k) return `<span class="${ui.meta}">Your stack is empty · <a class="${LINK}" href="#/" data-manage>Add tools to see only their ${esc(what)}</a></span>`;
  return `<div class="${ui.segmented}" role="group" aria-label="Which products"><button type="button" class="${ui.segment} whitespace-nowrap" aria-pressed="${!mine}" data-scope="all">All products</button><button type="button" class="${ui.segment} whitespace-nowrap" aria-pressed="${mine}" data-scope="stack">Your stack · ${k}</button></div><a class="${LINK} whitespace-nowrap" href="#/" data-manage>Manage</a>`;
}
/* a product row's add or remove control, in the same words everywhere */
export const stackToggle = (id, name) =>
  id
    ? `<button type="button" class="${ui.chip.base}" data-stack-toggle="${esc(id)}" data-name="${esc(name || id)}" aria-pressed="${tracked(id)}" aria-label="${tracked(id) ? 'Remove' : 'Add'} ${esc(name || id)} ${tracked(id) ? 'from' : 'to'} your stack">${tracked(id) ? '✓ In your stack' : '+ Your stack'}</button>`
    : '';

/* mount a panel whose scope control switches it between all products and your stack, and which follows the stack as it changes */
export function mountScoped(host, panel, scope = ALL) {
  let now = scope;
  const m = mount(host, panel, now),
    set = s => m.update((now = s));
  host.addEventListener('click', e => {
    const b = e.target.closest('[data-scope]');
    if (b && host.contains(b)) set(b.dataset.scope === 'stack' ? stackScope() : ALL);
  });
  addEventListener('airstack:stack', () => set(now.kind === 'stack' ? stackScope() : now));
  return { update: set, scope: () => now };
}

let wired = false;
export function wire() {
  if (wired) return;
  wired = true;
  document.addEventListener('click', e => {
    const t = e.target.closest('[data-stack-toggle]');
    if (t) {
      toggle({ id: t.dataset.stackToggle, name: t.dataset.name });
      return;
    }
    if (e.target.closest('[data-manage]')) {
      e.preventDefault();
      if (document.body.dataset.view !== 'overview') location.hash = '#/';
      requestAnimationFrame(() => document.getElementById('mystack')?.scrollIntoView({ block: 'start' }));
    }
  });
  addEventListener('airstack:stack', () => {
    for (const b of document.querySelectorAll('[data-stack-toggle]')) {
      const on = tracked(b.dataset.stackToggle);
      b.setAttribute('aria-pressed', on);
      b.textContent = on ? '✓ In your stack' : '+ Your stack';
      b.setAttribute('aria-label', `${on ? 'Remove' : 'Add'} ${b.dataset.name} ${on ? 'from' : 'to'} your stack`);
    }
  });
}
