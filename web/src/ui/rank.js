/* A ranked list: who (avatar, name, note), a bar on one shared scale, and the value. Length carries the size and fill
   carries the sign (solid up, hollow down), so the ranking reads without colour. A row with no value shows a dash. */
import { html, raw } from './html.js';

const COLS = {
  wide: 'grid-cols-[minmax(0,1fr)_56px_72px] gap-x-4 md:grid-cols-[minmax(0,1fr)_minmax(48px,200px)_72px] md:gap-x-6',
  dense: 'grid-cols-[minmax(0,1fr)_40px_64px] gap-x-3',
};

const Bar = ({ share, negative, strong }) =>
  html`<span class="block h-1 overflow-hidden rounded-full bg-border ${share == null ? 'invisible' : ''}" aria-hidden="true">${
    share == null
      ? ''
      : html`<i class="block h-full rounded-full ${negative ? 'ring-1 ring-inset ring-muted-foreground' : strong ? 'bg-foreground' : 'bg-subtle-foreground'}" style="width:${Math.max(2, share * 100).toFixed(1)}%"></i>`
  }</span>`;

/* rows: [{ id, avatar (markup), name, note, value: number|null, label, current }]; missing: what a dash stands for */
export function RankList({ rows, dense = false, missing = 'not observed' }) {
  const max = Math.max(1, ...rows.filter(r => r.value != null).map(r => Math.abs(r.value))),
    marked = rows.some(r => r.current);
  return html`<ol class="mt-4 list-none border-t border-border">${rows.map(
    r => html`<li class="border-b border-border"><button type="button" data-pick="${r.id}"${r.current ? raw(' aria-current="true"') : ''}
      class="group grid ${dense ? COLS.dense : COLS.wide} -ml-3 min-h-16 w-[calc(100%+1.5rem)] items-center rounded-sm p-3 text-left transition-colors hover:bg-info/5">
      <span class="flex min-w-0 items-center gap-2.5">${raw(r.avatar)}<span class="min-w-0"><b class="block truncate font-semibold decoration-border underline-offset-4 group-hover:underline group-aria-[current=true]:underline group-aria-[current=true]:decoration-foreground">${r.name}</b><span class="block text-xs leading-normal text-muted-foreground [overflow-wrap:anywhere]">${r.note}</span></span></span>
      ${Bar({ share: r.value == null ? null : Math.abs(r.value) / max, negative: r.value < 0, strong: !marked || r.current })}
      <span class="text-right font-medium tabular-nums">${
        r.value == null ? html`<span class="text-subtle-foreground" title="${missing}"><span aria-hidden="true">—</span><span class="sr">${missing}</span></span>` : r.label
      }</span></button></li>`
  )}</ol>`;
}
