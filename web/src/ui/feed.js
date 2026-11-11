/* A dated feed: days, and under each day one row per entity. A row is who (and an action beside it), what was said
   (with anything older folded under it), and the kind of source. Below 768 px who takes its own line. */
import { html } from './html.js';

export const FeedDay = ({ heading, rows }) =>
  html`<li><h3 class="font-mono text-xs font-medium uppercase tracking-wider text-muted-foreground">${heading}</h3><ol class="mt-2 list-none border-t border-border">${rows}</ol></li>`;

/* who, action, title: markup; more: { summary, items: [markup] } or null */
export const FeedRow = ({ who, action, title, more, kind }) =>
  html`<li class="grid min-h-13 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 border-b border-border py-2 md:grid-cols-[minmax(0,300px)_minmax(0,1fr)_auto]">
    <span class="col-span-full flex min-w-0 items-center justify-between gap-2 md:col-span-1">${who}${action}</span>
    <span class="min-w-0">${title}${
      more
        ? html`<details class="mt-1"><summary class="min-h-6 cursor-pointer list-none text-xs text-muted-foreground hover:text-foreground">${more.summary}</summary><ul class="mt-1 grid list-none gap-0.5">${more.items.map(i => html`<li>${i}</li>`)}</ul></details>`
        : ''
    }</span>
    <span class="inline-flex h-6 items-center justify-self-start whitespace-nowrap rounded-full border border-border px-2 text-xs capitalize text-muted-foreground">${kind}</span></li>`;

export const FeedEmpty = text => html`<li class="text-xs text-muted-foreground">${text}</li>`;
