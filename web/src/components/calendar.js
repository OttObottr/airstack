/* Coming up: what a source has dated ahead of today (events.json, status scheduled): support and end-of-life deadlines and dated
   releases, each linked to that source. Workspace panels: `panel` (the agenda) and `briefPanel` (Home's next few). */
import { json } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { esc, fd, host, n, stamp, url } from '../lib/format.js';
import { inScope, mountScoped, nodeOf, scopeControl, stackToggle } from '../lib/scope.js';
import { VIEW } from '../lib/view.js';
import { ui } from '../ui/recipes.js';

const DAY = 864e5,
  LINK = 'underline underline-offset-4 decoration-border hover:text-foreground';
const dated = e => e.status === 'scheduled' && e.kind !== 'blog'; /* a post dated ahead is a webinar or a timezone, not a date to plan around */
let E = null,
  ofNode = null;

const draw = (days, shown) => (scope, el) => {
  const today = E.source.built_for,
    end = new Date(Date.parse(today) + days * DAY).toISOString().slice(0, 10),
    seen = new Set();
  const ahead = E.events
    .filter(e => dated(e) && e.at >= today && e.at <= end && inScope(scope, { id: e.id, node: ofNode && ofNode(e.id) }))
    .sort((a, b) => (a.at < b.at ? -1 : 1))
    .filter(e => !seen.has(e.title) && seen.add(e.title));
  const xs = ahead.slice(0, shown);
  el.innerHTML = `<div class="flex flex-col gap-2">${
    xs.length
      ? `<ol class="flex flex-col">${xs
          .map(
            e => `<li class="grid grid-cols-[5.5rem_minmax(0,1fr)] items-start gap-3 py-2 border-b border-border last:border-b-0"><time class="${ui.num} text-xs text-muted-foreground leading-5" datetime="${esc(e.at)}">${fd(e.at)}</time>
          <span class="flex flex-col gap-1 min-w-0"><span class="flex flex-wrap items-center gap-2"><a class="text-sm font-medium text-foreground ${LINK}" href="#app=${esc(e.id)}">${esc(e.title)}</a>${stackToggle(e.id, e.name)}</span>
          <span class="${ui.panelNote}">${e.url ? `<a class="${LINK}" href="${url(e.url)}" target="_blank" rel="noopener noreferrer">${esc(host(e.url))}</a>, read ${stamp(e.source_read, E.source.built_for)}` : ''}</span></span></li>`
          )
          .join('')}</ol>`
      : `<p class="text-sm text-muted-foreground">Nothing dated in the next ${days} days${scope.kind === 'stack' ? ' for your stack' : ''}.</p>`
  }${xs.length < ahead.length ? `<p class="${ui.panelNote}">${n(xs.length)} of ${n(ahead.length)} dates a source publishes from ${fd(today)}.</p>` : ''}</div>`;
};
const render = (days, shown) => (scope, el) => {
  const go = () => draw(days, shown)(scope, el);
  if (E && (scope.kind !== 'node' || ofNode)) return go();
  if (!el.firstChild) el.innerHTML = '<div class="skeleton skeleton-list" role="status" aria-label="Loading upcoming dates"></div>';
  return Promise.all([json('events.json').then(d => (E = d)), scope.kind === 'node' ? nodeOf().then(f => (ofNode = f)) : null])
    .then(go)
    .catch(e => {
      console.error('agenda:', e);
      el.innerHTML = `<p class="${ui.panelNote}" role="status">Upcoming dates could not be loaded. Check the connection and reload.</p>`;
    });
};

export const panel = {
  id: 'agenda',
  title: 'Coming up',
  note: `Support deadlines and dated releases in the next ${VIEW.calendarAgendaDays} days.`,
  controls: scope => scopeControl(scope, 'dates'),
  render: render(VIEW.calendarAgendaDays, Infinity),
};
export const briefPanel = {
  id: 'agenda-brief',
  title: 'Coming up',
  note: `Support deadlines and dated releases in the next ${VIEW.homeAheadWeeks} weeks.`,
  controls: () => `<a class="${ui.button.ghost} shrink-0 whitespace-nowrap" href="#/calendar">All dates</a>`,
  render: render(VIEW.homeAheadWeeks * 7, VIEW.homeShown),
};

export function mount() {
  const el = $('#agendaPanel');
  if (el && !el.dataset.panel) mountScoped(el, panel);
}
