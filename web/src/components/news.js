import { Method } from '../ui/method.js';
import { mono } from './avatar.js';
import { json } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { esc, fd, host, n, stamp, url } from '../lib/format.js';
import { scopeControl, stackScope, stackToggle } from '../lib/scope.js';
import { FeedDay, FeedEmpty, FeedRow } from '../ui/feed.js';
import { html, raw } from '../ui/html.js';
import { ALL } from '../ui/panel.js';

const FIRST = 12;
let N = null,
  shown = FIRST;
const KINDS = [
  ['changelog', 'Changelogs'],
  ['blog', 'Blogs'],
];
const on = new Set(['changelog', 'blog']); /* releases that say only their version are not rows: they count in Most active */ /* a bare version number says nothing: releases are one tap away, not the default */
let scope = ALL; /* all products, or your stack */
const day = iso => iso.slice(0, 10);

function rows() {
  const read = N.source.read;
  const ids = scope.ids ? new Set(scope.ids) : null;
  const top = new Set(stories().map(i => i.url)); /* a story in Top stories is not repeated in the feed below it */
  return N.items.filter(
    i =>
      on.has(i.kind) &&
      !bare(i) &&
      !top.has(i.url) &&
      day(i.date) <= read &&
      (!ids || ids.has(i.id))
  );
}

const ORDER = {
  changelog: 0,
  blog: 2,
  release: 3,
}; /* within a day: what a vendor says changed, then discussion, then version bumps */
/* a release that says nothing but its version: shown only folded into its product's line as a count and its latest version */
const bare = i => i.kind === 'release' && !i.gist && !i.story && (!i.title || i.title === i.version || /^v?\d[\w.+-]*$/.test(String(i.title).trim()));
function byDay(R) {
  const rank = (a, b) => bare(a) - bare(b) || (b.weight || 0) - (a.weight || 0) || ORDER[a.kind] - ORDER[b.kind]; /* what says something first, then what matters most */
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
/* coverage.json: links to outlets' articles about a product, with outlet and date; no outlet wording is shown, only "Covered by" links */
let PRESS = [];
const version = i => (i.version && i.version !== i.title ? ` <span class="meta">${esc(i.version)}</span>` : ''); /* a bare release is its version: say it once */
const tally = xs =>
  Object.entries(xs.reduce((m, x) => ((m[x.kind] = (m[x.kind] || 0) + 1), m), {}))
    .map(([k, c]) => `${c} ${KIND(k)}${c > 1 ? 's' : ''}`)
    .join(', ');

/* Top stories: the vendors' own announcements (blog and changelog, AirStack's sentence checked against the vendor's page), the weightiest first,
   one per product, each with the outlets that covered the product around the same days */
const SIGNAL = { launch: 'Launch', feature: 'New feature', pricing: 'Pricing', company: 'Company', security: 'Security', incident: 'Incident' };
function stories() {
  const read = Date.parse(N.source.read), seen = new Set();
  const press = PRESS;
  return N.items
    .filter(i => (i.kind === 'blog' || i.kind === 'changelog') && i.gist && (i.weight || 1) >= 2 && read - Date.parse(i.date) <= 14 * 864e5)
    .sort((a, b) => !!b.story - !!a.story || (b.weight || 0) - (a.weight || 0) || b.date.localeCompare(a.date))
    .filter(i => !seen.has(i.id) && seen.add(i.id))
    .slice(0, 9)
    .map(i => ({ ...i, covered: press.filter(p => p.id === i.id && Math.abs(Date.parse(p.date) - Date.parse(i.date)) <= 3 * 864e5).slice(0, 3) }));
}
const BTN_MORE = 'mt-3 inline-flex h-9 items-center rounded-md border border-border px-3 text-sm hover:bg-muted';
let topAll = false,
  TAX = null; /* taxonomy-index.json: each product's category, so a card says what kind of software it is */
const category = id => {
  const node = TAX && TAX.products[id] && TAX.products[id][0] && TAX.products[id][0][0];
  return node && TAX.nodes[node] ? TAX.nodes[node].name : '';
}; /* Top stories show three until the reader asks for more */
function renderTop() {
  const all = stories(), S = topAll ? all : all.slice(0, 3), el = $('#newsTop');
  if (!el) return;
  el.innerHTML = S.length
    ? String(html`<h3 class="h-section mb-3">Top stories</h3><ul class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">${S.map(
        i => html`<li class="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
          <a class="flex items-center gap-3" href="#app=${i.id}">${raw(mono({ id: i.id, name: i.name }, 's44'))}<span class="flex flex-col"><b class="font-semibold">${i.name}</b><span class="text-xs text-muted-foreground">${category(i.id) ? html`<b class="font-medium text-foreground/80">${category(i.id)}</b> · ` : ''}${SIGNAL[i.signal] || 'Update'} · ${fd(i.date.slice(0, 10))}</span></span></a>
          <a class="text-lg font-semibold leading-snug text-foreground hover:underline underline-offset-2" href="${raw(url(i.url))}" target="_blank" rel="noopener noreferrer">${i.story ? i.story.headline : i.gist}</a>
          ${i.story ? html`<p class="clamp3 text-sm leading-relaxed text-muted-foreground">${i.story.summary}</p>${i.story.why ? html`<p class="text-sm leading-relaxed"><b class="font-medium text-foreground">Why it matters:</b> <span class="text-muted-foreground">${i.story.why}</span></p>` : ''}` : ''}
          <span class="text-xs text-muted-foreground">From ${host(i.url)} · written by AirStack from the vendor’s page</span>
          ${i.covered.length ? html`<span class="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">Covered by ${i.covered.map(p => html`<a class="chip ext" href="${raw(url(p.url))}" target="_blank" rel="noopener noreferrer">${p.outlet}</a>`)}</span>` : ''}
        </li>`
      )}</ul>${all.length > 3 ? html`<button class="${BTN_MORE}" type="button" data-top-more>${topAll ? 'Fewer top stories' : `More top stories (${all.length - 3})`}</button>` : ''}`)
    : '';
}

function render() {
  renderTop();
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
  const releases = i => 1 + i.others.filter(bare).length;
  const label = i => (i.others && bare(i) ? `${releases(i)} release${releases(i) > 1 ? 's' : ''} · latest ${i.version || i.title}` : i.gist || i.title);
  const link = (i, cls = '') => html`<a class="ext font-normal decoration-transparent hover:decoration-border ${cls}" href="${raw(url(i.url))}" target="_blank" rel="noopener noreferrer">${label(i)}</a>${raw(bare(i) ? '' : version(i))}${raw(i.more ? `<ul class="mt-1 flex list-disc flex-col gap-0.5 pl-4 text-sm leading-snug text-muted-foreground">${i.more.map(m => `<li>${esc(m)}</li>`).join('')}</ul>` : '')}`;
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
                more: i.others.filter(o => !(bare(i) && bare(o))).length && {
                  summary: `and ${i.others.filter(o => !(bare(i) && bare(o))).length} more · ${tally(i.others.filter(o => !(bare(i) && bare(o))))}`,
                  items: i.others.filter(o => !(bare(i) && bare(o))).map(m => html`<span class="text-xs text-muted-foreground">${raw(stamp(day(m.date), N.source.read))}</span> ${link(m)} <span class="text-xs text-muted-foreground">${KIND(m.kind)}</span>`),
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
    Method(`Each product once, at its latest update, from each vendor’s own feed and GitHub releases. A summary line is machine-written by AirStack and may contain errors; the linked page governs. Read ${fd(N.source.read)}. Vendor headlines are the vendors’ own.${PRESS.length ? ` “Covered by” links go to outlets that reported on the product around the same days, found through <a class=\"underline underline-offset-2\" href=\"https://www.gdeltproject.org/\">The GDELT Project</a>; AirStack shows none of their words.` : ''}`);
}

export function mount() {
  const sec = $('#news');
  if (!sec) return;
  addEventListener('airstack:stack', () => {
    if (scope.ids) scope = stackScope();
    if (N) render();
  });
  /* the same file Home's front page reads, so it is fetched once */
  Promise.all([json('news.json'), json('coverage.json').catch(() => null), json('taxonomy-index.json').catch(() => null)])
    .then(([d, c, t]) => {
      TAX = t;
      N = d;
      PRESS = c && c.items ? c.items : [];
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
  /* Top stories sit at the head of Home, outside this section */
  const top = $('#topSec');
  if (top)
    top.addEventListener('click', e => {
      if (!e.target.closest('[data-top-more]')) return;
      topAll = !topAll;
      renderTop();
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
