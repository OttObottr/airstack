/* Home's front page: what vendors announced, what was discussed (news.json) and what readers turned to (attention.json).
   A panel with more than one range opens on the shortest that fills it. */
import { json } from '../lib/data.js';
import { cn, esc, fd, n, pct, url } from '../lib/format.js';
import { Lines } from '../ui/lines.js';
import { mount as mountPanel } from '../ui/panel.js';
import { ui } from '../ui/recipes.js';
import { mono } from './avatar.js';
import { byId } from './search/index.js';

const SHOWN = 7,
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
  return perProduct(N.items.filter(i => kinds.includes(i.kind) && i.date.slice(0, 10) >= from && i.date.slice(0, 10) <= read), score)
    .filter(i => score(i) >= 0)
    .map(i => ({ ...who(i.id, i.name), href: url(i.url), ...line(i, days) }));
};
const when = (i, days) => (days === 1 ? i.date.slice(11, 16) : fd(i.date).replace(/ \d{4}$/, ''));

/* a vendor post that says something shipped, not a guide written for search engines */
const SHIPS = /\b(introduc|announc|launch|now available|generally available|general availability|beta|preview|releas|rolls? out|rolling out|unveil|now supports?|support for|what'?s new|new in|is here|now in)\w*/i,
  FILLER = /\b(guide|how to|what is|what are|why |tips|ideas|best |top \d+|\d+ (ways|best|tips|steps)|vs\.?|webinar|podcast|survey|case study|explained|checklist|template)\b|\?$/i;
const announced = i => i.kind === 'changelog' || (SHIPS.test(i.title) && !FILLER.test(i.title));

const PANELS = [
  {
    id: 'headlines',
    title: 'Announcements',
    note: 'What vendors shipped or announced this week.',
    ranges: [7],
    rows: fromNews(['blog', 'changelog'], i => (announced(i) ? Date.parse(i.date) : -1), (i, days) => ({ text: i.title, value: when(i, days) })),
  },
  {
    id: 'discussed',
    title: 'Most discussed',
    note: 'Hacker News threads, by points.',
    ranges: [7, 30],
    rows: fromNews(['hacker news'], i => (i.points >= HN_MIN ? i.points : -1), i => ({ text: 'Hacker News thread', value: `${n(i.points || 0)} pts` })),
  },
  {
    id: 'reading',
    title: 'Trending',
    note: 'Biggest rise in Wikipedia readers.',
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
const LABEL = { 1: 'Today', 7: 'This week', 30: 'This month' };

function open(host, P) {
  let days = null;
  const m = mountPanel(host, {
    id: P.id,
    title: P.title,
    note: P.note,
    controls: () =>
      P.ranges.length < 2
        ? ''
        : `<div class="${ui.segmented}" role="group" aria-label="${esc(P.title)}: range">${P.ranges.map(d => `<button class="${ui.segment}" type="button" data-days="${d}" aria-pressed="${d === days}">${LABEL[d]}</button>`).join('')}</div>`,
    async render(_, el) {
      const all = await Promise.all(P.ranges.map(P.rows));
      if (days == null) {
        days = P.ranges[Math.max(0, all.findIndex(r => r.length >= FULL))];
        host.querySelectorAll('[data-days]').forEach(b => b.setAttribute('aria-pressed', +b.dataset.days === days));
      }
      el.innerHTML = String(Lines({ rows: all[P.ranges.indexOf(days)].slice(0, SHOWN), empty: `Nothing ${days === 1 ? 'yet today' : LABEL[days].toLowerCase()}.` }));
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
