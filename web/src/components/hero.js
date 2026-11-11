import { M, PARAMS } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { esc, fd, pct } from '../lib/format.js';
import { VIEW } from '../lib/view.js';

/* `only`: ids to show; returns false when none of them has a figure */
export function drawTape(only, all) {
  const rows = (all || (M.moversTop && M.moversTop.rows) || [])
    .filter(r => r.dl && r.dl.vsBase != null && (!only || only.has(r.id)))
    .sort((a, b) => b.dl.vsBase - a.dl.vsBase);
  const shown =
    rows.length > 2 * VIEW.tapeEnds && !only
      ? [...rows.slice(0, VIEW.tapeEnds), ...rows.slice(-VIEW.tapeEnds)]
      : rows;
  const item = r =>
    `<a href="#app=${esc(r.id)}"><b>${esc(r.name)}</b><span class="${r.dl.vsBase < 0 ? 'dn' : 'up'}"><i class="arw${r.dl.vsBase < 0 ? ' down' : ''}" aria-hidden="true"></i>${pct(r.dl.vsBase)}</span></a>`;
  const as = `<span class="as">${only ? 'your tools · ' : ''}${PARAMS.movers.base_weeks}-week momentum · registry downloads · ${fd(M.moversTop.generated || M.meta.checked_at)}</span>`;
  if (rows.length) $('#tape').innerHTML = as + shown.map(item).join('') + as + shown.map(item).join('');
  else if (!only) $('#tapeW').hidden = true;
  return rows.length > 0;
}

export function mount() {
  drawTape();
}
