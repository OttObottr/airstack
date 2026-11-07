// spec: AS-134 AS-253 AS-256 AS-346
import { announce, renderAnswer } from './answer.js';
import { S } from './model.js';
import { $ } from '../../lib/dom.js';
import { esc, fd, ic, url } from '../../lib/format.js';

export function mapNeeds(a) {
  /* the needs the answer rests on; a rule-only answer rests on one */
  if (a.needs) return a.needs;
  const st = { retire: 'covered', potential: 'covered', keep: 'unmet', unknown: 'unknown' }[a.action] || 'unknown';
  return [{ label: S.use === 'Online' ? 'Notes in online meetings' : 'Notes in in-person meetings', status: st }];
}
function tip(x, a, i) {
  /* a line's own words and page; a line with no quote says so, and shows the pages behind the whole answer instead */
  const s = x.source || (!a.needs && a.sources[0]) || null,
    quote = s && s.quote && s.quote.replace(/\s*\*+\s*$/, ''),
    from = s ? [s] : a.sources,
    link = p =>
      `<a class="ext" href="${url(p.url)}" target="_blank" rel="noopener noreferrer">${esc(p.label || p.host)} · checked ${fd(p.date || p.checked)}${ic('out')}</a>`;
  const close =
    x.status === 'covered'
      ? ''
      : `<span class="close"><b>What would close it</b><ul>${[
          x.why,
          x.changesIf || a.changesIf,
          x.status === 'unknown' ? 'A page that states it, with its quote.' : '',
        ]
          .filter((t, j, all) => t && all.indexOf(t) === j)
          .map(t => `<li>${esc(t)}</li>`)
          .join('')}</ul></span>`;
  return `<span class="tip" role="tooltip" id="tip${i}">${quote ? `<q>${esc(quote)}</q>` : '<span class="nobs">Not observed</span> No quote is recorded for this line.'}${from.map(link).join('')}${close}</span>`;
}
export function coverMap(a, fam) {
  const N = mapNeeds(a),
    have =
      fam === 'Google' && S.plan !== 'No Google plan'
        ? 'Google Workspace'
        : fam === 'Microsoft'
          ? 'Microsoft 365'
          : fam;
  const by = x =>
    x.status === 'covered'
      ? `${esc(S.plan)} ${ic('check')}`
      : x.status === 'unmet'
        ? `only ${esc(S.app)}`
        : 'not known yet';
  return `<div class="cmap${a.stale ? ' stale' : ''}" role="group" aria-label="What each plan covers, line by line">
    <svg aria-hidden="true"></svg>
    <div class="cnode cl"><b>${esc(S.app)}</b><span>What you pay for</span></div>
    <ul class="needs">${N.map((x, i) => `<li class="${x.status}" data-s="${x.status}" style="--i:${i}"><button class="ln" type="button" aria-expanded="false" aria-describedby="tip${i}"><span class="mk ${x.status}">${ic({ covered: 'check', unmet: 'x', unknown: 'q' }[x.status])}</span>${esc(x.label)}<span class="by">${by(x)}</span></button>${tip(x, a, i)}</li>`).join('')}</ul>
    <div class="cnode cr"><b>${esc(S.plan)}</b><span>${esc(have)} · what you have</span></div></div>`;
}
export function drawMap() {
  /* lines from each need to what covers it, measured from the laid-out boxes */
  const m = $('#answer .cmap');
  if (!m) return;
  const svg = m.querySelector('svg'),
    R = m.getBoundingClientRect();
  if (!R.width || getComputedStyle(svg).display === 'none') return;
  const box = e => {
    const r = e.getBoundingClientRect();
    return { l: r.left - R.left, r: r.right - R.left, y: r.top - R.top + r.height / 2 };
  };
  const L = box(m.querySelector('.cnode.cl')),
    RT = box(m.querySelector('.cnode.cr'));
  svg.setAttribute('viewBox', `0 0 ${R.width.toFixed(1)} ${R.height.toFixed(1)}`);
  svg.innerHTML = [...m.querySelectorAll('.needs li')]
    .map((li, i) => {
      const b = box(li),
        s = li.dataset.s;
      if (s === 'covered') {
        const mx = (b.r + RT.l) / 2;
        return `<path pathLength="1" style="--i:${i}" d="M${b.r} ${b.y}C${mx} ${b.y} ${mx} ${RT.y} ${RT.l} ${RT.y}"/><circle cx="${RT.l}" cy="${RT.y}" r="3"/>`;
      }
      if (s === 'unmet') {
        const mx = (b.l + L.r) / 2;
        return `<path pathLength="1" style="--i:${i}" d="M${b.l} ${b.y}C${mx} ${b.y} ${mx} ${L.y} ${L.r} ${L.y}"/><circle cx="${L.r}" cy="${L.y}" r="3"/>`;
      }
      return `<path class="unknown" d="M${b.r} ${b.y}h28"/><circle class="hollow" cx="${b.r + 32}" cy="${b.y}" r="3.5"/>`;
    })
    .join('');
}
const unpin = () => {
  for (const x of document.querySelectorAll('.needs .ln[aria-expanded="true"]'))
    x.setAttribute('aria-expanded', 'false');
};
function change(set, id) {
  set();
  S.assumed = false;
  renderAnswer();
  announce();
  document.getElementById(id).focus();
}
export function mount() {
  /* a line shows its quote on hover and focus; opening it (click, Enter) pins it and, for a line not yet covered, lists what would close it */
  document.addEventListener('click', e => {
    const b = e.target.closest('.needs .ln'),
      on = b && b.getAttribute('aria-expanded') !== 'true';
    unpin();
    if (on) b.setAttribute('aria-expanded', 'true');
    const w = e.target.closest('#answer [data-side]');
    if (w && !w.disabled) change(() => (S.side = w.dataset.side), w.id);
  });
  document.addEventListener('change', e => {
    if (e.target.id === 'swTo')
      change(() => {
        S.to = e.target.value || null;
        S.side = S.to ? 'Proposed' : 'Current';
      }, 'swTo');
  });
  addEventListener('keydown', e => e.key === 'Escape' && unpin());
  document.addEventListener(
    'toggle',
    e => {
      if (e.target.matches('details.how')) {
        S.how = e.target.open;
        drawMap(); /* a closed box has no size: the lines are drawn when it opens */
      }
    },
    true
  );
  if (window.ResizeObserver)
    addEventListener('DOMContentLoaded', () => new ResizeObserver(() => drawMap()).observe($('#answer')));
}
