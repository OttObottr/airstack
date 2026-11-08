/* Coming up: launches and releases a source has dated ahead of today (events.json, status scheduled), each linked to that source.
   Support and end-of-life schedules are not shown. Workspace panels: `panel` (the agenda) and `briefPanel` (Home's next few). */
import { json } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { esc, fd, host, n, stamp, url } from '../lib/format.js';
import { inScope, mountScoped, nodeOf, scopeControl, stackToggle } from '../lib/scope.js';
import { VIEW } from '../lib/view.js';
import { ui } from '../ui/recipes.js';

const DAY = 864e5,
  LINK = 'underline underline-offset-4 decoration-border hover:text-foreground';
const launch = e => e.status === 'scheduled' && (e.kind === 'release' || e.kind === 'changelog'); /* not blog dates, support or end-of-life schedules */
let E = null,
  ofNode = null,
  loading = null;

const draw = (days, shown) => (scope, el) => {
  const today = E.source.built_for,
    end = new Date(Date.parse(today) + days * DAY).toISOString().slice(0, 10),
    seen = new Set();
  const ahead = E.events
    .filter(e => launch(e) && e.at >= today && e.at <= end && inScope(scope, { id: e.id, node: ofNode && ofNode(e.id) }))
    .sort((a, b) => (a.at < b.at ? -1 : 1))
    .filter(e => !seen.has(e.id || e.name) && seen.add(e.id || e.name));
  const xs = ahead.slice(0, shown);
  el.innerHTML = `<div class="flex flex-col gap-2">${
    xs.length
      ? `<ol class="flex flex-col">${xs
          .map(
            e => `<li class="grid grid-cols-[5.5rem_minmax(0,1fr)] items-start gap-3 py-2 border-b border-border last:border-b-0"><time class="${ui.num} text-xs text-muted-foreground leading-5" datetime="${esc(e.at)}">${fd(e.at)}</time>
          <span class="flex flex-col gap-1 min-w-0"><span class="flex flex-wrap items-center gap-2"><a class="text-sm font-medium text-foreground ${LINK}" href="#app=${esc(e.id)}">${esc(e.name)}</a>${stackToggle(e.id, e.name)}</span>
          <span class="${ui.panelNote}">${e.url ? `<a class="${LINK}" href="${url(e.url)}" target="_blank" rel="noopener noreferrer">${esc(e.title)}</a> · ${esc(host(e.url))}, read ${stamp(e.source_read, E.source.built_for)}` : esc(e.title)}</span></span></li>`
          )
          .join('')}</ol>`
      : `<p class="text-sm text-muted-foreground">Nothing dated in the next ${days} days${scope.kind === 'stack' ? ' for your stack' : ''}.</p>`
  }${xs.length ? `<p class="${ui.panelNote}">${n(xs.length)} of ${n(ahead.length)} products with a launch or release a source dates from ${fd(today)}.</p>` : ''}</div>`;
};
const render = (days, shown) => (scope, el) => {
  const go = () => draw(days, shown)(scope, el);
  if (E && (scope.kind !== 'node' || ofNode)) return go();
  if (!el.firstChild) el.innerHTML = '<div class="skeleton skeleton-list" role="status" aria-label="Loading upcoming launches"></div>';
  return Promise.all([(loading ||= json('events.json').then(d => (E = d))), scope.kind === 'node' ? nodeOf().then(f => (ofNode = f)) : null])
    .then(go)
    .catch(e => {
      console.error('agenda:', e);
      el.innerHTML = `<p class="${ui.panelNote}" role="status">Upcoming dates could not be loaded. Check the connection and reload.</p>`;
    });
};

export const panel = {
  id: 'agenda',
  title: 'Coming up',
  note: `Launches and releases a source dates in the next ${VIEW.calendarAgendaDays} days.`,
  controls: scope => scopeControl(scope, 'dates'),
  render: render(VIEW.calendarAgendaDays, Infinity),
};
export const briefPanel = {
  id: 'agenda-brief',
  title: 'Coming up',
  note: `Launches and releases dated in the next ${VIEW.homeAheadWeeks} weeks.`,
  controls: () => `<a class="${ui.button.ghost} shrink-0 whitespace-nowrap" href="#/calendar">All dates</a>`,
  render: render(VIEW.homeAheadWeeks * 7, VIEW.homeShown),
};

export function mount() {
  const el = $('#agendaPanel');
  if (el && !el.dataset.panel) mountScoped(el, panel);
}
