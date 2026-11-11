/* What kind of news an item is, as a quiet coloured tag: colour carries the meaning, so a security notice never looks like a release. */
import { html } from './html.js';

const TONE = {
  launch: 'bg-info/12 text-info',
  security: 'bg-warn/12 text-warn',
  incident: 'bg-down/12 text-down',
  pricing: 'bg-maker/12 text-maker',
};
export const Badge = kind =>
  kind ? html`<span class="inline-flex h-5 items-center rounded-sm px-1.5 text-[11px] font-medium leading-none ${TONE[kind] || 'bg-muted text-muted-foreground'}">${kind}</span>` : '';
