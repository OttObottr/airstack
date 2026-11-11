import { M } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { fd, n } from '../lib/format.js';
import { stack } from '../lib/stack.js';
import { html, raw } from '../ui/html.js';
import { mono } from './avatar.js';

/* The rail's watchlist: the reader's stack, one link per product. It follows the stack as it changes. */
const ITEM = 'flex h-8 min-w-0 items-center gap-2.5 rounded-md px-2.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground';
function draw() {
  const s = stack();
  $('#railStackN').textContent = s.length ? n(s.length) : '';
  $('#railStack').innerHTML = String(
    s.length
      ? html`${s.map(x => html`<li><a class="${ITEM}" href="#app=${x.id}">${raw(mono(x, 's20'))}<span class="truncate">${x.name || x.id}</span></a></li>`)}`
      : html`<li class="px-2.5 text-xs leading-relaxed text-subtle-foreground">Save the tools you use to follow them here.</li>`
  );
}

export function mount() {
  const read = M.meta && M.meta.checked_at,
    c = M.meta && M.meta.counts;
  if (read) {
    $('#freshness').textContent = `Data read ${fd(read)}`;
    $('#railFresh').textContent = `Data read ${fd(read)}${c ? ` · ${n(c.products)} products · ${n(c.researched_products)} researched` : ''}. Every fact is quoted from its own page.`;
  }
  $('#railAdd').addEventListener('click', () => $('#stackAdd').click());
  addEventListener('airstack:stack', draw);
  draw();
}
