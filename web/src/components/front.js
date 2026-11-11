/* Home's front page: what vendors posted, what was discussed, what shipped (news.json) and what readers turned to
   (attention.json), each over a range the reader picks. A panel opens on the shortest range that fills it. */
import { json } from '../lib/data.js';
import { cn, esc, fd, n, pct, url } from '../lib/format.js';
import { Lines } from '../ui/lines.js';
import { mount as mountPanel } from '../ui/panel.js';
import { ui } from '../ui/recipes.js';
import { mono } from './avatar.js';
import { byId } from './search/index.js';

const SHOWN = 6,
  FULL = 4 /* rows that make a range worth opening on */,
  HN_MIN = 5; /* a thread with fewer points is noise, not news */
const who = (id, name) => ({ id, name, avatar: mono(byId(id) || { id, name }, 's20') });
const since = (read, days) => new Date(Date.parse(read) - (days - 1) * 864e5).toISOString().slice(0, 10);
/* the newest (or best, by `score`) item of each product inside the range */
const perProduct = (items, score) => {
  const by = new Map();
  for (const i of items) if (!by.has(i.id) || score(i) > score(by.get(i.id))) by.set(i.id, i);
  return [...by.values()].sort((a, b) => score(b) - score(a));
};
const fromNews = (kinds, score, line) => async days => {
  const N = await json('news.json'),
    read = N.source.read,
    from = since(read, days);
  if (read !== clock()) LABEL[1] = fd(read).replace(/ \d{4}$/, ''); /* data older than the clock is named by its date, never called today */
  return perProduct(N.items.filter(i => kinds.includes(i.kind) && i.date.slice(0, 10) >= from && i.date.slice(0, 10) <= read), score)
    .filter(i => score(i) >= 0)
    .map(i => ({ ...who(i.id, i.name), href: url(i.url), ...line(i, days) }));
};
const when = (i, days) => (days === 1 ? i.date.slice(11, 16) : fd(i.date).replace(/ \d{4}$/, ''));

const PANELS = [
  {
    id: 'headlines',
    title: 'Headlines',
    note: 'What vendors posted on their own blogs and changelogs.',
    ranges: [1, 7],
    rows: fromNews(['blog', 'changelog'], i => Date.parse(i.date), (i, days) => ({ text: i.title, value: when(i, days) })),
  },
  {
    id: 'discussed',
    title: 'Most discussed',
    note: 'Hacker News threads that link to a product’s own site, by points.',
    ranges: [1, 7, 30],
    rows: fromNews(['hacker news'], i => (i.points >= HN_MIN ? i.points : -1), i => ({ text: 'Hacker News thread', value: `${n(i.points || 0)} pts` })),
  },
  {
    id: 'shipped',
    title: 'Just shipped',
    note: 'The latest release each product published.',
    ranges: [1, 7],
    rows: fromNews(['release'], i => Date.parse(i.date), (i, days) => ({ text: i.version || i.title, value: when(i, days) })),
  },
  {
    id: 'reading',
    title: 'Trending',
    note: 'Products whose Wikipedia article drew the largest rise in readers.',
    ranges: [7, 30],
    rows: async days => {
      const A = await json('attention.json'),
        floor = A.source.params.min_baseline,
        of = p => (days === 7 ? p.views.slice(-2) : [p.prior_4w, p.last_4w]);
      return Object.entries(A.products)
        .map(([id, p]) => ({ id, p, was: of(p)[0], now: of(p)[1] }))
        .filter(x => x.was >= floor && x.now != null)
        .sort((a, b) => b.now / b.was - a.now / a.was)
        .map(x => ({ ...who(x.id, (byId(x.id) || {}).name || x.p.article), href: url(x.p.url), text: `${cn(x.now)} views, was ${cn(x.was)}`, value: pct((x.now / x.was - 1) * 100) }));
    },
  },
];
const LABEL = { 1: 'Today', 7: '7 days', 30: '30 days' };
const clock = () => new Date().toISOString().slice(0, 10);

function open(host, P) {
  let days = null;
  const m = mountPanel(host, {
    id: P.id,
    title: P.title,
    note: P.note,
    controls: () =>
      `<div class="${ui.segmented}" role="group" aria-label="${esc(P.title)}: range">${P.ranges.map(d => `<button class="${ui.segment}" type="button" data-days="${d}" aria-pressed="${d === days}">${LABEL[d]}</button>`).join('')}</div>`,
    async render(_, el) {
      const all = await Promise.all(P.ranges.map(P.rows));
      if (days == null) {
        days = P.ranges[Math.max(0, all.findIndex(r => r.length >= FULL))];
        host.querySelectorAll('[data-days]').forEach(b => {
          b.setAttribute('aria-pressed', +b.dataset.days === days);
          b.textContent = LABEL[b.dataset.days];
        });
      }
      el.innerHTML = String(Lines({ rows: all[P.ranges.indexOf(days)].slice(0, SHOWN), empty: `Nothing ${days === 1 && LABEL[1] === 'Today' ? 'yet today' : `in ${LABEL[days]}`}.` }));
    },
  });
  host.addEventListener('click', e => {
    const b = e.target.closest('[data-days]');
    if (!b) return;
    days = +b.dataset.days;
    m.update();
  });
}

export const mount = root => PANELS.forEach(P => open(root.querySelector(`[data-front="${P.id}"]`), P));
