import { json } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { esc, fd, n } from '../lib/format.js';
import { announced } from '../lib/news.js';

const DAYS = 3 /* how far back an announcement still leads the page */,
  LOUD = 100; /* Hacker News points that make a thread worth the top line */

/* The top line: what a reader should not miss. The newest announcement of each product over the last few days, and the threads
   everyone is in. `only`: product ids to keep; resolves false when none of them has an item. */
export async function drawTape(only) {
  const N = await json('news.json').catch(() => null);
  if (!N) return void ($('#tapeW').hidden = true), false;
  const read = N.source.read,
    from = new Date(Date.parse(read) - (DAYS - 1) * 864e5).toISOString().slice(0, 10),
    week = new Date(Date.parse(read) - 6 * 864e5).toISOString().slice(0, 10),
    seen = new Set();
  const rows = N.items
    .filter(i => i.date.slice(0, 10) <= read && (!only || only.has(i.id)) && ((announced(i) && i.date.slice(0, 10) >= from) || (i.kind === 'hacker news' && i.points >= LOUD && i.date.slice(0, 10) >= week)))
    .sort((a, b) => announced(b) - announced(a) || (b.points || 0) - (a.points || 0) || (a.date < b.date ? 1 : -1)) /* what a vendor said first, then the loudest threads */
    .filter(i => !seen.has(i.id) && seen.add(i.id))
    .slice(0, 24);
  const item = i =>
    `<a href="#app=${esc(i.id)}"><b>${esc(i.name)}</b><span>${i.kind === 'hacker news' ? `${n(i.points)} points on Hacker News` : esc(i.title)}</span></a>`;
  const as = `<span class="as">${only ? 'your tools · ' : ''}latest · ${fd(read)}</span>`;
  if (rows.length) $('#tape').innerHTML = as + rows.map(item).join('') + as + rows.map(item).join('');
  else if (!only) $('#tapeW').hidden = true;
  return rows.length > 0;
}

export const mount = () => void drawTape();
