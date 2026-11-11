import { $ } from '../lib/dom.js';
import { n } from '../lib/format.js';
import { stack, toggle } from '../lib/stack.js';
import { html, raw } from '../ui/html.js';
import { mono } from './avatar.js';

/* The rail's watchlist: the reader's stack, one link per product. It follows the stack as it changes. */
const ITEM = 'flex h-8 min-w-0 items-center gap-2.5 rounded-md px-2.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground';
function draw() {
  const s = stack();
  $('#railStackN').textContent = s.length ? n(s.length) : '';
  $('#railStack').innerHTML = String(
    s.length
      ? html`${s.map(x => html`<li class="group relative"><a class="${ITEM} pr-8" href="#app=${x.id}">${raw(mono(x, 's20'))}<span class="truncate">${x.name || x.id}</span></a><button class="absolute right-1 top-1 hidden size-6 items-center justify-center rounded text-subtle-foreground hover:bg-background hover:text-foreground group-hover:flex focus-visible:flex" type="button" data-unstack="${x.id}" aria-label="Remove ${x.name || x.id} from your stack">×</button></li>`)}`
      : html`<li class="px-2.5 text-xs leading-relaxed text-subtle-foreground">Save the tools you use to follow them here.</li>`
  );
}

export function mount() {
  $('#railAdd').addEventListener('click', () => $('#stackAdd').click());
  $('#railStack').addEventListener('click', e => {
    const b = e.target.closest('[data-unstack]');
    if (b) toggle({ id: b.dataset.unstack });
  });
  addEventListener('airstack:stack', draw);
  draw();
}
