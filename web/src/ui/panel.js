import { esc } from '../lib/format.js';
import { ui } from './recipes.js';

/* The contract every workspace panel keeps.
   A panel module exports `panel = { id, title, note, render(scope, el), controls?(scope) }`.
   scope: { kind: 'all' | 'node' | 'stack' | 'maker', id?: string, ids?: string[] } — what the left rail has selected.
   render fills `el` (the panel body) for the scope and may be called again whenever the scope changes. */
export const ALL = Object.freeze({ kind: 'all' });

export function mount(host, p, scope = ALL) {
  host.className = ui.panel;
  host.dataset.panel = p.id;
  host.innerHTML = `<header class="${ui.panelHead}"><div class="flex flex-col gap-1"><h2 class="${ui.panelTitle}">${esc(p.title)}</h2>${p.note ? `<p class="${ui.panelNote}">${esc(p.note)}</p>` : ''}</div><div class="flex items-center gap-2" data-controls></div></header><div data-body></div>`;
  const body = host.querySelector('[data-body]'),
    controls = host.querySelector('[data-controls]');
  /* a panel whose data cannot be fetched says so instead of leaving its loader running */
  const fail = e => {
    console.error(`${p.id}:`, e);
    body.removeAttribute('aria-busy');
    body.innerHTML = `<p class="${ui.panelNote}" role="status">This could not be loaded. Check the connection and reload.</p>`;
  };
  const update = s => {
    if (p.controls) controls.innerHTML = p.controls(s);
    try {
      const done = p.render(s, body);
      if (done && done.catch) done.catch(fail);
      return done;
    } catch (e) {
      fail(e);
    }
  };
  update(scope);
  return { update };
}
