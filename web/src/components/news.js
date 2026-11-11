import { Method } from '../ui/method.js';
import { mono } from './avatar.js';
import { json } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { esc, fd, n, stamp, url } from '../lib/format.js';
import { scopeControl, stackScope, stackToggle } from '../lib/scope.js';
import { FeedDay, FeedEmpty, FeedRow } from '../ui/feed.js';
import { html, raw } from '../ui/html.js';
import { ALL } from '../ui/panel.js';

const FIRST = 12;
let N = null,
  shown = FIRST;
const KINDS = [
  ['changelog', 'Changelogs'],
  ['release', 'Releases'],
  ['blog', 'Blogs'],
];
const on = new Set(['changelog', 'release']); /* a bare version number says nothing: releases are one tap away, not the default */
let scope = ALL; /* all products, or your stack */
const day = iso => iso.slice(0, 10);

function rows() {
  const read = N.source.read;
  const ids = scope.ids ? new Set(scope.ids) : null;
  return N.items.filter(
    i =>
      on.has(i.kind) &&
      day(i.date) <= read &&
      (!ids || ids.has(i.id))
  );
}

const ORDER = {
  changelog: 0,
  blog: 2,
  release: 3,
}; /* within a day: what a vendor says changed, then discussion, then version bumps */
function byDay(R) {
  const rank = (a, b) => (b.weight || 0) - (a.weight || 0) || ORDER[a.kind] - ORDER[b.kind]; /* what matters most first */
  const by = new Map();
  for (const i of R) {
    if (!by.has(i.id)) by.set(i.id, []);
    by.get(i.id).push(i);
  }
  const days = new Map();
  for (const xs of by.values()) {
    xs.sort((a, b) => day(b.date).localeCompare(day(a.date)) || rank(a, b));
    const d = day(xs[0].date);
    if (!days.has(d)) days.set(d, []);
    days.get(d).push({ ...xs[0], others: xs.slice(1) });   /* the product's other updates that day; `more` is a release's own change list */
  }
  return [...days].sort((a, b) => b[0].localeCompare(a[0])).map(([d, xs]) => [d, xs.sort(rank)]);
}
const KIND = k => k;
const version = i => (i.version && i.version !== i.title ? ` <span class="meta">${esc(i.version)}</span>` : ''); /* a bare release is its version: say it once */
const tally = xs =>
  Object.entries(xs.reduce((m, x) => ((m[x.kind] = (m[x.kind] || 0) + 1), m), {}))
    .map(([k, c]) => `${c} ${KIND(k)}${c > 1 ? 's' : ''}`)
    .join(', ');

function render() {
  const all = byDay(rows()),
    groups = [];
  let left = shown;
  for (const [d, items] of all) {
    if (left <= 0) break;
    groups.push([d, items.slice(0, left)]);
    left -= items.length;
  }
  const R = all.flatMap(g => g[1]);
  $('#newsKinds').innerHTML =
    KINDS.map(
      ([k, label]) =>
        `<button class="chip" type="button" aria-pressed="${on.has(k)}" data-kind="${esc(k)}">${label}</button>`
    ).join('');
  $('#newsScope').innerHTML = scopeControl(scope, 'changes');
  const link = (i, cls = '') => html`<a class="ext font-normal decoration-transparent hover:decoration-border ${cls}" href="${raw(url(i.url))}" target="_blank" rel="noopener noreferrer">${i.gist || i.title}</a>${raw(version(i))}${raw(i.more ? `<ul class="mt-1 flex list-disc flex-col gap-0.5 pl-4 text-sm leading-snug text-muted-foreground">${i.more.map(m => `<li>${esc(m)}</li>`).join('')}</ul>` : '')}`;
  $('#newsList').innerHTML = String(
    groups.length
      ? html`${groups.map(([d, items]) =>
          FeedDay({
            heading: html`${raw(stamp(d, N.source.read))} · ${fd(d)}`,
            rows: items.map(i =>
              FeedRow({
                who: html`<a data-who class="flex min-h-11 min-w-0 flex-1 items-center gap-2.5" href="#app=${i.id}">${raw(mono({ id: i.id, name: i.name }))}<b class="truncate font-semibold">${i.name}</b></a>`,
                action: raw(stackToggle(i.id, i.name)),
                title: link(i),
                more: i.others.length && {
                  summary: `and ${i.others.length} more · ${tally(i.others)}`,
                  items: i.others.map(m => html`<span class="text-xs text-muted-foreground">${raw(stamp(day(m.date), N.source.read))}</span> ${link(m)} <span class="text-xs text-muted-foreground">${KIND(m.kind)}</span>`),
                },
                kind: KIND(i.kind),
              })
            ),
          })
        )}`
      : FeedEmpty(scope.ids ? 'Nothing from your stack in these feeds yet.' : 'Nothing in the selected feeds yet.')
  );
  $('#newsMore').hidden = R.length <= shown;
  $('#newsMore').disabled = false;
  $('#newsSub').innerHTML =
    `${n(R.length)} products, ${n(R.reduce((k, i) => k + 1 + i.others.length, 0))} updates in ${N.source.window_days} days.` +
    Method(`Each product once, at its latest update, from each vendor’s own feed and GitHub releases. A summary line is machine-written by AirStack and may contain errors; the linked page governs. Read ${fd(N.source.read)}. Vendor headlines are the vendors’ own.`);
}

export function mount() {
  const sec = $('#news');
  if (!sec) return;
  addEventListener('airstack:stack', () => {
    if (scope.ids) scope = stackScope();
    if (N) render();
  });
  /* the same file Home's front page reads, so it is fetched once */
  json('news.json')
    .then(d => {
      N = d;
      delete sec.dataset.loading;
      $('#newsList').setAttribute('aria-busy', 'false');
      render();
    })
    .catch(() => {
      delete sec.dataset.loading;
      $('#newsKinds').innerHTML = '';
      $('#newsSub').textContent = 'Sourced updates could not be loaded.';
      $('#newsMore').hidden = true;
      $('#newsList').setAttribute('aria-busy', 'false');
      $('#newsList').innerHTML = '<li class="load-error" role="status">Check the connection and reload.</li>';
    });
  sec.addEventListener('click', e => {
    const sc = e.target.closest('#newsScope [data-scope]');
    if (sc) {
      scope = sc.dataset.scope === 'stack' ? stackScope() : ALL;
      shown = FIRST;
      render();
      return;
    }
    const k = e.target.closest('#newsKinds .chip');
    if (k) {
      const v = k.dataset.kind;
      on.has(v) ? on.delete(v) : on.add(v);
      shown = FIRST;
      render();
      return;
    }
    if (e.target.closest('#newsMore')) {
      shown += 60;
      render();
    }
  });
}
