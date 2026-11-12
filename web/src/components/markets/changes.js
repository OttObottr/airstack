import { json } from '../../lib/data.js';
import { esc, fd, n, url } from '../../lib/format.js';
import { ui } from '../../ui/recipes.js';
import { mono } from '../avatar.js';
import { latest, loading, sourceLine } from './scope.js';
import { SUPPORT, bare, ensureNames, files, idsOf, label, nameOf } from './field.js';

/* What the makers in a scope announced lately, and the support dates coming up for their products. Only the makers' own channels
   and published support schedules: no press, no third-party wording about a named company. */

const DAYS = 30,
  AHEAD = 120,
  SHOW = 8;
const today = () => new Date().toISOString().slice(0, 10);
const shift = (iso, d) => new Date(Date.parse(iso) + d * 864e5).toISOString().slice(0, 10);

const scoped = async (scope, F) => (scope.kind === 'all' ? null : new Set(await idsOf(scope, F)));

/* a panel with nothing to show for a picked market steps out of the grid, so the page does not carry empty boxes */
const hideIfEmpty = (el, scope, empty) => {
  const cell = el.closest('[data-panel]') && el.closest('[data-panel]').parentElement;
  if (cell) cell.hidden = empty && scope.kind !== 'all';
};
const item = (e, extra = '') => `<li class="flex items-start gap-3 py-2 border-b border-border last:border-b-0">
  ${mono({ id: e.id, name: nameOf(e.id) || e.name }, 's20')}
  <div class="flex min-w-0 flex-col gap-0.5"><span class="text-sm"><a class="font-medium text-foreground hover:underline underline-offset-2" href="#app=${encodeURIComponent(e.id)}">${esc(nameOf(e.id) === e.id ? e.name : nameOf(e.id))}</a>
  <a class="text-muted-foreground hover:text-foreground hover:underline underline-offset-2" href="${url(e.url)}" target="_blank" rel="noopener noreferrer">${esc(label(e))}</a></span>
  <span class="${ui.meta}">${extra}${esc(e.kind)} · ${fd(e.at)}${e.more ? ` · and ${e.more} more that day` : ''}</span></div></li>`;

const list = (rows, el, empty, open) =>
  rows.length
    ? `<ul class="flex flex-col">${(open ? rows : rows.slice(0, SHOW)).map(r => r).join('')}</ul>${rows.length > SHOW ? `<button type="button" class="${ui.button.ghost} self-start" data-more>${open ? 'Show fewer' : `Show all ${n(rows.length)}`}</button>` : ''}`
    : `<p class="${ui.panelNote}">${empty}</p>`;

export const changes = {
  id: 'changes',
  title: 'What the makers announced',
  note: `Releases, changelog entries and posts on the makers’ own channels in the last ${DAYS} days, newest first.`,
  async render(scope, el) {
    const fresh = latest(el);
    el.className = 'flex flex-col gap-2 min-w-0';
    loading(el);
    const F = await files();
    await ensureNames();
    const ids = await scoped(scope, F);
    if (!fresh()) return;
    el.removeAttribute('aria-busy');
    const from = shift(today(), -DAYS);
    const recent = ((F.E && F.E.events) || []).filter(e => e.status === 'observed' && !SUPPORT.has(e.kind) && e.at >= from && (!ids || ids.has(e.id)));
    /* releases published with only a tag are counted per product, not listed: a version number alone says nothing */
    const tagged = new Map();
    for (const e of recent.filter(bare)) tagged.set(e.id, (tagged.get(e.id) || []).concat(e));
    const also = [...tagged]
      .sort((a, b) => b[1].length - a[1].length)
      .map(([id, es]) => `<a class="hover:text-foreground hover:underline underline-offset-2" href="${url(es[0].url.replace(/\/tag\/[^/]+$/, ''))}" target="_blank" rel="noopener noreferrer">${esc(nameOf(id) === id ? es[0].name : nameOf(id))} (${es.length})</a>`);
    const rows = recent
      .filter(e => !bare(e))
      .sort((a, b) => (a.at < b.at ? 1 : -1))
      .reduce((out, e) => {
        const last = out.find(x => x.id === e.id && x.at === e.at && x.kind === e.kind); /* one row per product, day and kind */
        if (last) last.more = (last.more || 0) + 1;
        else out.push({ ...e });
        return out;
      }, [])
      .map(e => item(e));
    hideIfEmpty(el, scope, !rows.length && !also.length);
    let open = false;
    const draw = () =>
      (el.innerHTML =
        list(rows, el, also.length ? 'No announcement here says what changed; only release numbers, listed below.' : ids && ids.size ? 'None of these products announced anything on the channels we read in this window. Most makers here are not watched yet: unknown, not quiet.' : 'Nothing to show.', open) +
        (also.length ? `<p class="${ui.panelNote}">Also released, without release notes on file yet: ${also.join(', ')}.</p>` : '') +
        sourceLine('The makers’ own feeds, changelogs and GitHub releases, read daily', 'events.json', F.E && F.E.source && F.E.source.built_for));
    draw();
    el.onclick = e => e.target.closest('[data-more]') && ((open = !open), draw());
  },
};

export const support = {
  id: 'support',
  title: 'Support ending soon',
  note: `End of life, of active support and of extended support in the next ${AHEAD} days, from published support schedules.`,
  async render(scope, el) {
    const fresh = latest(el);
    el.className = 'flex flex-col gap-2 min-w-0';
    loading(el);
    const F = await files();
    await ensureNames();
    const ids = await scoped(scope, F);
    if (!fresh()) return;
    el.removeAttribute('aria-busy');
    const t = today(),
      to = shift(t, AHEAD);
    const rows = ((F.E && F.E.events) || [])
      .filter(e => SUPPORT.has(e.kind) && e.status === 'scheduled' && e.at >= t && e.at <= to && (!ids || ids.has(e.id)))
      .sort((a, b) => (a.at > b.at ? 1 : -1))
      .map(e => {
        const days = Math.round((Date.parse(e.at) - Date.parse(t)) / 864e5);
        return item(e, `<span class="${days <= 30 ? ui.badge.down : ui.badge.neutral}">in ${days} day${days === 1 ? '' : 's'}</span> `);
      });
    hideIfEmpty(el, scope, !rows.length);
    let open = false;
    const src = F.E && F.E.source && F.E.source.support_schedules;
    const draw = () =>
      (el.innerHTML =
        list(rows, el, `No published support date ends in the next ${AHEAD} days for products here.`, open) +
        sourceLine(
          src ? `Support schedules from <a class="underline underline-offset-2" href="${url(src.url)}" target="_blank" rel="noopener noreferrer">${esc(src.name)}</a> (${esc(src.license)}); a date is the schedule’s, as published` : 'Published support schedules',
          'events.json',
          src && src.read
        ));
    draw();
    el.onclick = e => e.target.closest('[data-more]') && ((open = !open), draw());
  },
};

/* open-source projects GitHub files under the same category (oss.json): shown only for a category it covers */
export const oss = {
  id: 'oss',
  title: 'More on GitHub',
  note: 'Other repositories GitHub topics place in this category, by stars. Stars are attention on GitHub, not use or quality.',
  async render(scope, el) {
    const fresh = latest(el);
    el.className = 'flex flex-col gap-2 min-w-0';
    loading(el);
    const O = await json('oss.json').catch(() => null);
    if (!fresh()) return;
    el.removeAttribute('aria-busy');
    const repos = (O && scope.kind === 'node' && O.categories[scope.id]) || [];
    const top = repos.slice().sort((a, b) => b.stars - a.stars).slice(0, SHOW);
    hideIfEmpty(el, scope, !top.length);
    el.innerHTML = top.length
      ? `<ul class="flex flex-col">${top
          .map(
            r => `<li class="flex items-center justify-between gap-3 py-2 border-b border-border last:border-b-0"><div class="flex min-w-0 flex-col gap-0.5">
            <a class="truncate text-sm font-medium text-foreground hover:underline underline-offset-2" href="${url(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.repo)}</a>
            <span class="${ui.meta}">${esc(r.license || 'no licence stated')} · pushed ${fd(r.pushed)}</span></div>
            <span class="${ui.num} shrink-0 text-sm text-foreground">★ ${n(r.stars)}</span></li>`
          )
          .join('')}</ul>${sourceLine('GitHub search by topic, each row with the date of its own search', 'oss.json')}`
      : `<p class="${ui.panelNote}">GitHub topics do not cover this category.</p>`;
  },
};
