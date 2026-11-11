/* Home's front page: what vendors announced, what was discussed (news.json) and what readers turned to (attention.json).
   A panel with more than one range opens on the shortest that fills it. */
import { json } from '../lib/data.js';
import { cn, esc, n, pct, url } from '../lib/format.js';
import { announced, lead, says } from '../lib/news.js';
import { Badge } from '../ui/badge.js';
import { Lines } from '../ui/lines.js';
import { mount as mountPanel } from '../ui/panel.js';
import { ui } from '../ui/recipes.js';
import { mono } from './avatar.js';
import { byId } from './search/index.js';

const SHOWN = 12,
  FULL = 4; /* rows that make a range worth opening on */
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

const PANELS = [
  {
    id: 'headlines',
    title: 'Announcements',
    note: 'What vendors shipped or announced this week, most important first.',
    ranges: [7],
    rows: fromNews(['blog', 'changelog', 'release'], i => (announced(i) ? lead(i) : -1), i => ({ text: says(i), value: Badge(i.signal) })),
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
