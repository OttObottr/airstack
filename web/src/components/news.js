// spec: AS-256 AS-265
import { mono } from './avatar.js';
import { $ } from '../lib/dom.js';
import { esc, fd, n, url } from '../lib/format.js';
import { stack } from '../lib/stack.js';

/* ---------- what changed: each vendor's own changelog, GitHub releases and Hacker News stories that link to the product's own site ----------
   Titles are the publishers' own words. Blog posts are marketing-heavy, so they sit behind a toggle. Nothing dated after the read is shown. */
let N = null,
  shown = 40;
const KINDS = [
  ['changelog', 'Changelogs'],
  ['release', 'Releases'],
  ['hacker news', 'Hacker News'],
  ['blog', 'Blogs'],
];
const on = new Set(['changelog', 'release', 'hacker news']);
let mine = false; /* only the tools in my stack (kept in this browser) */
const HN_MIN = 5; /* a story with fewer points is noise, not news */
const day = iso => iso.slice(0, 10);

function rows() {
  const read = N.source.read;
  const ids = mine ? new Set(stack().map(x => x.id)) : null;
  return N.items.filter(
    i =>
      on.has(i.kind) &&
      day(i.date) <= read &&
      (i.kind !== 'hacker news' || (i.points || 0) >= HN_MIN) &&
      (!ids || ids.has(i.id))
  );
}

const ORDER = {
  changelog: 0,
  'hacker news': 1,
  blog: 2,
  release: 3,
}; /* within a day: what a vendor says changed, then discussion, then version bumps */
function byDay(R) {
  /* each product once: under the day of its latest update, its earlier ones folded under it */
  const rank = (a, b) => ORDER[a.kind] - ORDER[b.kind] || (b.points || 0) - (a.points || 0);
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
    days.get(d).push({ ...xs[0], more: xs.slice(1) });
  }
  return [...days].sort((a, b) => b[0].localeCompare(a[0])).map(([d, xs]) => [d, xs.sort(rank)]);
}
const KIND = k => (k === 'hacker news' ? 'HN' : k);
const version = i => (i.version ? ` <span class="meta">${esc(i.version)}</span>` : '');
const tally = xs =>
  Object.entries(xs.reduce((m, x) => ((m[x.kind] = (m[x.kind] || 0) + 1), m), {}))
    .map(([k, c]) => `${c} ${KIND(k)}${c > 1 && k !== 'hacker news' ? 's' : ''}`)
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
    ).join('') +
    (stack().length
      ? `<button class="chip mine" type="button" aria-pressed="${mine}" data-mine="1">My stack only · ${stack().length}</button>`
      : '');
  $('#newsList').innerHTML = groups.length
    ? groups
        .map(
          ([d, items]) =>
            `<li class="nday"><h3 class="lab">${fd(d)}</h3><ol>${items
              .map(
                i => `<li class="nrow">
      <a class="who" href="#app=${esc(i.id)}">${mono({ name: i.name })}<b>${esc(i.name)}</b></a>
      <span class="nt"><a class="ext" href="${url(i.url)}" target="_blank" rel="noopener noreferrer">${esc(i.title)}</a>${version(i)}${i.more.length ? `<details class="nmore"><summary class="meta">and ${i.more.length} more · ${esc(tally(i.more))}</summary><ul>${i.more.map(m => `<li><span class="meta">${fd(day(m.date))}</span> <a class="ext" href="${url(m.url)}" target="_blank" rel="noopener noreferrer">${esc(m.title)}</a>${version(m)} <span class="meta">${esc(KIND(m.kind))}</span></li>`).join('')}</ul></details>` : ''}</span>
      <span class="nk">${esc(KIND(i.kind))}</span>
      ${i.kind === 'hacker news' && i.discussion ? `<a class="ext meta" href="${url(i.discussion)}" target="_blank" rel="noopener noreferrer">${n(i.points)} points · discussion</a>` : ''}</li>`
              )
              .join('')}</ol></li>`
        )
        .join('')
    : `<li class="meta">${mine ? 'Nothing from the tools in your stack in these feeds yet.' : 'Nothing in the selected feeds yet.'}</li>`;
  $('#newsMore').hidden = R.length <= shown;
  $('#newsSub').textContent =
    `Each product once, at its latest update, from each vendor’s own feed, substantive GitHub release notes, and Hacker News stories (${HN_MIN}+ points) that link to the product’s own site · ${n(R.length)} products, ${n(R.reduce((k, i) => k + 1 + i.more.length, 0))} updates in ${N.source.window_days} days · read ${fd(N.source.read)}. Headlines are the publishers’ own; bare version tags are omitted.`;
}

export function mount() {
  const sec = $('#news');
  if (!sec) return;
  addEventListener('airstack:stack', () => {
    if (N) render();
  });
  const load = () =>
    fetch('news.json')
      .then(r => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then(d => {
        N = d;
        sec.hidden = false; /* hidden in the markup: a loading strip that vanishes would shift the page */
        render();
      })
      .catch(() => {
        sec.hidden = true;
      });
  /* It sits below the first screen, so it waits: it loads on the first interaction, or after a few seconds. Never while someone is getting an
     answer: answering sends no request. */
  let started = false;
  const go = () => {
    if (started) return;
    started = true;
    load();
  };
  for (const type of ['pointerdown', 'keydown', 'focusin', 'scroll'])
    addEventListener(type, go, { once: true, passive: true });
  setTimeout(go, 7000);
  sec.addEventListener('click', e => {
    if (e.target.closest('#newsKinds .chip[data-mine]')) {
      mine = !mine;
      shown = 40;
      render();
      return;
    }
    const k = e.target.closest('#newsKinds .chip');
    if (k) {
      const v = k.dataset.kind;
      on.has(v) ? on.delete(v) : on.add(v);
      shown = 40;
      render();
      return;
    }
    if (e.target.closest('#newsMore')) {
      shown += 60;
      render();
    }
  });
}
