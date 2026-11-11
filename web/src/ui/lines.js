/* A compact list: who, one line about them, and a figure at the right. The line may link out; who opens the product. */
import { html, raw } from './html.js';

/* rows: [{ id, avatar (markup), name, text, href, value }] */
export const Lines = ({ rows, empty }) =>
  rows.length
    ? html`<ol class="flex list-none flex-col">${rows.map(
        r => html`<li class="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 border-b border-border py-2 last:border-b-0">${raw(r.avatar)}
          <span class="flex min-w-0 flex-col gap-0.5"><a class="truncate text-sm font-medium text-foreground hover:underline underline-offset-4" href="#app=${r.id}">${r.name}</a>${
            r.href
              ? html`<a class="line-clamp-2 text-xs leading-snug text-muted-foreground hover:text-foreground" href="${raw(r.href)}" target="_blank" rel="noopener noreferrer">${r.text}</a>`
              : html`<span class="line-clamp-2 text-xs leading-snug text-muted-foreground">${r.text}</span>`
          }</span>
          <span class="whitespace-nowrap text-right font-mono text-xs tabular-nums text-muted-foreground">${r.value}</span></li>`
      )}</ol>`
    : html`<p class="text-sm text-muted-foreground">${empty}</p>`;
