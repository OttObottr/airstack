/* An open-source repository as a card: its name, the three figures a reader weighs first, then licence, age and any security score. */
import { html, raw } from './html.js';

const Stat = (value, label) => html`<span class="flex flex-col gap-1"><b class="font-mono text-base font-semibold tabular-nums leading-none text-foreground">${value}</b><span class="text-[11px] leading-none text-subtle-foreground">${label}</span></span>`;
const Tag = text => html`<span class="inline-flex h-5 items-center rounded-sm bg-muted px-1.5 text-[11px] font-medium leading-none text-muted-foreground">${text}</span>`;

/* stars, forks, issues: formatted strings or null; score: { text, href } or null; warn: a short reason or null */
export const RepoCard = ({ name, href, stars, forks, issues, licence, pushed, created, score, warn }) =>
  html`<li class="flex min-w-0 flex-col gap-4 rounded-lg border border-border bg-card p-4">
    <a class="truncate text-sm font-semibold text-foreground hover:underline underline-offset-4" href="${raw(href)}" target="_blank" rel="noopener noreferrer">${name}</a>
    <span class="grid grid-cols-3 gap-3">${Stat(stars ?? '—', 'stars')}${Stat(forks ?? '—', 'forks')}${Stat(issues ?? '—', 'open issues')}</span>
    <span class="flex flex-wrap items-center gap-1.5">${licence ? Tag(licence) : ''}${score ? html`<a class="inline-flex h-5 items-center rounded-sm bg-info/12 px-1.5 text-[11px] font-medium leading-none text-info hover:underline" href="${raw(score.href)}" target="_blank" rel="noopener noreferrer">${score.text}</a>` : ''}${warn ? html`<span class="inline-flex h-5 items-center rounded-sm bg-warn/12 px-1.5 text-[11px] font-medium leading-none text-warn">${warn}</span>` : ''}</span>
    <span class="text-xs text-muted-foreground">Updated ${pushed}${created ? html` · started ${created}` : ''}</span></li>`;
