// spec: AS-112 AS-256
import { $$ } from '../lib/dom.js';
import { esc } from '../lib/format.js';

/* ---------- radio chips: one pattern for app, plan and device ---------- */
export function radios(el, items, cur, pick) {
  el.innerHTML = items
    .map(
      v =>
        `<button class="chip" role="radio" type="button" aria-checked="${v === cur}" tabindex="${v === cur || (cur == null && v === items[0]) ? 0 : -1}" data-v="${esc(v)}">${esc(v)}</button>`
    )
    .join('');
  el.onclick = e => {
    const b = e.target.closest('.chip');
    if (b) choose(b);
  };
  el.onkeydown = e => {
    const bs = $$('.chip', el),
      i = bs.indexOf(document.activeElement);
    if (i < 0) return;
    const d = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!d) return;
    e.preventDefault();
    const b = bs[(i + d + bs.length) % bs.length];
    b.focus();
    choose(b);
  };
  function choose(b) {
    $$('.chip', el).forEach(x => {
      const on = x === b;
      x.setAttribute('aria-checked', on);
      x.tabIndex = on ? 0 : -1;
    });
    pick(b.dataset.v);
  }
}
