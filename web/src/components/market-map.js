import { selectByName } from './app.js';
import { M, PARAMS } from '../lib/data.js';
import { $, reduce } from '../lib/dom.js';
import { esc, fd, n, pct } from '../lib/format.js';
import { MK } from '../lib/market.js';
import { onMarket } from './search/index.js';
import { squarify } from '../lib/treemap.js';
import { mount as mountTypes } from './attention.js';

const FLAT = 2,
  CLAMP = 50;
const tone = v =>
  v == null
    ? 'none'
    : Math.abs(v) < FLAT
      ? 'flat'
      : (v > 0 ? 'up' : 'dn') + Math.min(4, Math.max(1, Math.ceil((Math.min(Math.abs(v), CLAMP) / CLAMP) * 4)));
const lift = rows => {
  const m = rows.filter(r => r.dl.vsBase != null),
    w = m.reduce((s, r) => s + r.dl.value, 0);
  return w ? m.reduce((s, r) => s + r.dl.vsBase * r.dl.value, 0) / w : null;
};
const say = r =>
  `${r.name}: ${n(r.dl.value)} ${r.dl.registry} downloads in 7 days, ` +
  (r.dl.vsBase == null
    ? `no change shown (${r.dl.why || 'no usable earlier weeks'})`
    : `${pct(r.dl.vsBase)} against its own ${PARAMS.movers.base_weeks}-week level${r.dl.from ? ` (from its ${r.dl.from})` : ''}`);

function drawMarketMap() {
  const D = (MK && MK.movers) || M.moversTop,
    host = $('#mmap');
  if (!D || !host) return;
  const lanes = D.lanes.map(l => {
    const all = D.rows.filter(r => r.lane === l.id),
      rows = all.filter(r => r.dl && r.dl.value > 0);
    return {
      ...l,
      rows,
      unmeasured: all.length - rows.length,
      lift: lift(rows),
      based: rows.filter(r => r.dl.vsBase != null).length,
    };
  });
  const none = lanes
    .filter(l => !l.rows.length)
    .map(l => l.name);
  lanes.splice(0, lanes.length, ...lanes.filter(l => l.rows.length));
  host.setAttribute('aria-busy', 'false');
  host.innerHTML = lanes
    .map(
      l => `<section class="mlane" aria-label="${esc(l.name)}"><h3><span>${esc(l.name)}</span>${
        l.lift == null
          ? `<span class="state-note">Insufficient ${PARAMS.movers.base_weeks}-week baseline</span>`
          : `<span class="mlift ${tone(l.lift)}" title="Weighted by downloads across the ${l.based} of ${l.rows.length} tools with usable earlier weeks"><i class="arw${l.lift >= 0 ? '' : ' down'}" aria-hidden="true"></i>${pct(Math.abs(l.lift)).replace('+', '')}<span class="sr"> across ${l.based} of ${l.rows.length} tools</span></span>`
      }</h3>
    <div class="tm" data-lane="${esc(l.id)}"></div>${l.unmeasured ? `<p class="meta">+${l.unmeasured} without download counts</p>` : ''}</section>`
    )
    .join('');
  for (const l of lanes) {
    const box = host.querySelector(`.tm[data-lane="${CSS.escape(l.id)}"]`),
      W = box.clientWidth,
      H = box.clientHeight;
    if (!W || !H) continue;
    const rows = [...l.rows].sort((a, b) => b.dl.value - a.dl.value),
      at = squarify(
        rows.map(r => r.dl.value),
        W,
        H
      );
    box.innerHTML = rows
      .map((r, i) => {
        const [x0, y0, x1, y1] = at[i],
          w = x1 - x0,
          h = y1 - y0,
          v = r.dl.vsBase;
        const label =
          w >= 72 && h >= 26
            ? `<b>${esc(r.name)}</b>${w >= 96 && h >= 44 && v != null ? `<span>${pct(v)}</span>` : ''}`
            : '';
        const cls = `tile ${tone(v)}`,
          pos = `left:${x0}px;top:${y0}px;width:${w}px;height:${h}px;--i:${i}`;
        if (w < 24 || h < 24)
          /* too small to tap: reached through the table below */
          return `<i class="${cls}" style="${pos}" data-app="${esc(r.name)}" title="${esc(say(r))}" aria-hidden="true"></i>`;
        return `<button type="button" class="${cls}" style="${pos}" data-app="${esc(r.name)}" aria-label="${esc(say(r))}" title="${esc(say(r))}">${label}</button>`;
      })
      .join('');
  }
  const D0 = D.window;
  $('#mmapNote').textContent =
    `Area: downloads ${D0 ? `${fd(D0.last7[0])} to ${fd(D0.last7[1])}` : 'last 7 days'}, from each registry’s own counts · fetched ${fd(D.generated)}. Areas compare within a lane, not across (npm and PyPI count different things).${none.length ? ` Not drawn: ${none.join(' and ')}, whose products are not packages with download counts.` : ''}`;
}

export function mount() {
  if (!$('#mmap')) return;
  $('#mmap').addEventListener('click', e => {
    const b = e.target.closest('button.tile[data-app]');
    if (!b) return;
    selectByName(b.dataset.app);
    $('#check').scrollIntoView({ block: 'start', behavior: reduce ? 'auto' : 'smooth' });
  });
  $('#mmap').addEventListener('pointerover', e => {
    const b = e.target.closest('.tile');
    if (b) $('#mmapInfo').textContent = b.getAttribute('title');
  });
  $('#mmap').addEventListener('focusin', e => {
    const b = e.target.closest('.tile');
    if (b) $('#mmapInfo').textContent = b.getAttribute('aria-label');
  });
  let t;
  if (window.ResizeObserver)
    new ResizeObserver(() => {
      clearTimeout(t);
      t = setTimeout(drawMarketMap, 120);
    }).observe($('#mmap'));
  mountTypes();
  onMarket(drawMarketMap); /* the full market data arrives after first paint */
}
