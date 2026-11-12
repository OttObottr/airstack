import { json } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { esc, fd } from '../lib/format.js';
import { announced, lead, says } from '../lib/news.js';

const PACE = 50; /* the top line's speed, in pixels a second */
const DAYS = 3; /* how far back an announcement still leads the page */

/* The top line: what a reader should not miss. The newest announcement of each product over the last few days, most important first. `only`: product ids to keep; resolves false when none of them has an item. */
export async function drawTape(only) {
  const N = await json('news.json').catch(() => null);
  if (!N) return void ($('#tapeW').hidden = true), false;
  const read = N.source.read,
    from = new Date(Date.parse(read) - (DAYS - 1) * 864e5).toISOString().slice(0, 10),
    seen = new Set();
  const rows = N.items
    .filter(i => i.date.slice(0, 10) <= read && (!only || only.has(i.id)) && announced(i) && i.date.slice(0, 10) >= from)
    .sort((a, b) => lead(b) - lead(a))
    .filter(i => !seen.has(i.id) && seen.add(i.id))
    .slice(0, 10); /* a short loop: the ten that matter most */
  const item = i =>
    `<a href="#app=${esc(i.id)}"><b>${esc(i.name)}</b><span>${esc(says(i))}</span></a>`;
  const as = `<span class="as">${only ? 'your tools · ' : ''}latest · ${fd(read)} · AirStack summaries</span>`;
  if (rows.length) {
    const t = $('#tape');
    t.innerHTML = as + rows.map(item).join('') + `<span class="contents" aria-hidden="true" inert>${as}${rows.map(item).join('')}</span>`; /* the loop's second copy is for the eye only */
    t.style.animationDuration = `${Math.round(t.scrollWidth / 2 / PACE)}s`; /* a steady reading pace however long the lines are */
  }
  else if (!only) $('#tapeW').hidden = true;
  return rows.length > 0;
}

export const mount = () => void drawTape();

/* the strip moves on its own; it stops under the pointer and on keyboard focus, and it does not move on touch screens or with reduced
   motion (WCAG 2.2.2): landing.css */
