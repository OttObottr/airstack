import { json } from '../lib/data.js';
import { $, reduce } from '../lib/dom.js';
import { mountScoped } from '../lib/scope.js';
import { panel as findings } from './findings.js';
import { esc, n } from '../lib/format.js';

let I = null,
  pop = 'categories';
const BANDS = 3,
  TOP = 2;
const POP = { categories: 'Products in the categories AirStack follows', all_listed: 'All listed software' };
const shown = () => I.map.points.filter(p => (pop === 'all_listed') === p[0].startsWith('Q'));
const hash = s => {
  let h = 2166136261;
  for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return (h >>> 0) / 4294967296;
};
const pct = (k, of) => (of ? Math.round((k / of) * 100) : null);
/* a category count: a {found, of} record, or a bare count out of the products read */
const cnt = (v, c) => (v && typeof v === 'object' ? v : { found: v, of: c.researched });

function drawMap() {
  const cv = $('#aimap'),
    box = cv && cv.parentElement;
  if (!I || !box) return;
  const W = box.clientWidth,
    H = W < 600 ? 300 : 380,
    dpr = Math.min(2, devicePixelRatio || 1);
  cv.width = W * dpr;
  cv.height = H * dpr;
  cv.style.height = H + 'px';
  const g = cv.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, W, H);
  const P = shown(),
    mx = Math.log10(1 + Math.max(...I.map.points.map(p => p[3]))),
    L = 8,
    R = 8,
    T = 6,
    B = 22,
    bh = (H - T - B) / BANDS;
  const X = v => L + (Math.log10(1 + v) / mx) * (W - L - R),
    Y = (band, id) => T + (TOP - band) * bh + 6 + hash(id) * (bh - 12);
  const css = getComputedStyle(document.documentElement),
    ink = css.getPropertyValue('--color-ink').trim() || '#F4F6F8';
  g.strokeStyle = css.getPropertyValue('--color-hair').trim() || 'rgba(255,255,255,.12)';
  g.lineWidth = 1;
  for (let b = 1; b < BANDS; b++) {
    g.beginPath();
    g.moveTo(L, T + b * bh + 0.5);
    g.lineTo(W - R, T + b * bh + 0.5);
    g.stroke();
  }
  const mid = X(Math.pow(10, mx / 2) - 1);
  g.setLineDash([2, 4]);
  g.beginPath();
  g.moveTo(mid + 0.5, T);
  g.lineTo(mid + 0.5, H - B);
  g.stroke();
  g.setLineDash([]);
  g.fillStyle = ink;
  g.globalAlpha = 0.5;
  const jit = (v, id) =>
    v +
    (hash(id + 'x') - 0.5) *
      0.7; /* page counts are whole numbers: jitter each within its own step */
  const pts = P.map(p => ({ p, x: X(jit(p[3], p[0])), y: Y(p[4], p[0]) }));
  for (const q of pts) {
    g.beginPath();
    g.arc(q.x, q.y, W < 600 ? 1.4 : 1.8, 0, 7);
    g.fill();
  }
  g.globalAlpha = 1;
  g.font = '500 11px Inter, system-ui, sans-serif';
  g.fillStyle = css.getPropertyValue('--color-ink-2').trim();
  for (const t of [0, 1, 3, 10, 30, 100, 300].filter(v => Math.log10(1 + v) <= mx)) {
    const x = X(t);
    g.fillText(String(t), Math.min(x + 2, W - R - 16), H - 6);
  }
  const taken = [];
  for (let b = 0; b < BANDS; b++) {
    let named = 0;
    for (const q of pts.filter(q => q.p[4] === b).sort((a, c) => c.p[3] - a.p[3])) {
      if (named === 3) break;
      const w = g.measureText(q.p[1]).width,
        left = q.x + 6 + w > W - R ? q.x - 6 - w : q.x + 6,
        box = [left - 2, q.y - 9, left + w + 2, q.y + 5];
      if (taken.some(t => box[0] < t[2] && t[0] < box[2] && box[1] < t[3] && t[1] < box[3])) continue;
      taken.push(box);
      named++;
      g.fillStyle = ink;
      g.beginPath();
      g.arc(q.x, q.y, 3, 0, 7);
      g.fill();
      g.fillText(q.p[1], left, q.y + 4);
    }
  }
  cv._pts = pts;
}

function mapView() {
  const P = shown(),
    by = [0, 1, 2].map(b => P.filter(p => p[4] === b).length),
    ax = I.map.axes,
    E = I.map.elsewhere;
  const top = b =>
    P.filter(p => p[4] === b)
      .sort((a, c) => c[3] - a[3])
      .slice(0, 6);
  const chips = Object.entries(POP)
    .map(
      ([k, l]) =>
        `<button class="chip" type="button" aria-pressed="${pop === k}" data-pop="${k}">${esc(l)} · ${n(I.map.populations[k].reduce((a, b) => a + b, 0))}</button>`
    )
    .join('');
  return `<div class="aipop" role="group" aria-label="Which products the map shows">${chips}</div><div class="ai2"><div class="aiy" aria-hidden="true">${[2, 1, 0].map(b => `<span>${esc(ax.y[b])}<b>${n(by[b])}</b></span>`).join('')}</div>
    <div class="aiplot"><canvas id="aimap" role="img" aria-label="${esc(`${n(P.length)} products. ${[2, 1, 0].map(b => `${ax.y[b]}: ${n(by[b])}`).join('. ')}. ${n(I.map.unplaced)} more miss an input and are not placed.`)}"></canvas>
      <p class="aitip meta" id="aitip" aria-live="polite">Point at a dot for the product; open it for its page.</p>
      <div class="aiq" aria-hidden="true"><span>Little documented</span><span>How widely documented → (${esc(ax.x)}, log scale)</span><span>Widely documented</span></div></div></div>
    <p class="ins-annotation mt12"><b>Read the split, not a score.</b> ${n(by[1])} show AI elsewhere on their pages: across all listed software, ${n(E.models)} name the models they use, ${n(E.providers)} integrate AI providers and ${n(E.plans)} name AI plans. ${pop === 'all_listed' ? 'Most listed software is general-purpose and long predates AI, so this population is mostly “No AI”. ' : ''}${n(P.length)} placed · ${n(I.map.unplaced)} not placed because an input is missing · x is how widely a product is documented, not market share · y is what its own pages say, not what it does.</p>
    <details class="mt12"><summary class="meta">The most documented in each band, as a list</summary><div class="aitop">${[
      2, 1, 0,
    ]
      .map(
        b =>
          `<div><p class="lab">${esc(ax.y[b])}</p><ol>${top(b)
            .map(
              p => `<li><a href="#app=${esc(p[0])}">${esc(p[1])}</a> <span class="meta">${n(p[3])} pages</span></li>`
            )
            .join('')}</ol></div>`
      )
      .join('')}</div></details>`;
}

function kpiView() {
  const K = I.kpis,
    order = I.departments;
  const C = Object.entries(I.categories)
    .filter(([, c]) => c.researched)
    .sort(
      (a, b) => order.indexOf(a[1].department) - order.indexOf(b[1].department) || b[1].researched - a[1].researched
    );
  const cell = ({ found, of }) => {
    const v = pct(found, of);
    return v == null
      ? '<td class="r"><span class="nobs">—</span></td>'
      : `<td class="r"><span class="kb" style="--v:${v / 100}">${v}%</span> <span class="meta d">${n(found)} found of ${n(of)}</span></td>`;
  };
  let last = null;
  const rows = C.map(
    ([, c]) =>
      `${c.department !== last ? `<tr class="dept"><th scope="colgroup" colspan="${K.length + 2}">${esc((last = c.department || 'Other'))}</th></tr>` : ''}<tr><th scope="row">${esc(c.name)}</th><td class="r num">${n(c.researched)} <span class="meta">of ${n(c.listed)}</span></td>${K.map(k => cell(cnt(c[k.key], c))).join('')}</tr>`
  ).join('');
  return `<div class="scroll mt16"><table class="t kpi"><thead><tr><th scope="col">Category</th><th scope="col" class="r">Products read</th>${K.map(k => `<th scope="col" class="r">${esc(k.label)}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>
    <p class="meta mt12">Grouped by the department each category serves. Each share counts the products whose own pages say so, out of those AirStack has read; “—” where none are read.</p>`;
}

function render() {
  $('#insBody').innerHTML = `<section class="ins-chapter"><p class="lab">01 · Positioning</p><h3 class="h3">Where does AI appear in vendors’ own words?</h3>${mapView()}</section>
    <section class="ins-chapter"><p class="lab">02 · Disclosure</p><h3 class="h3">What do categories consistently disclose?</h3>${kpiView()}</section>`;
  $('#insSub').textContent =
    `Computed from the stored facts: ${I.source.facts_from}; ${I.source.documentation_from}; ${I.source.prices_from}.`;
  requestAnimationFrame(drawMap);
}

function near(cv, e) {
  const r = cv.getBoundingClientRect(),
    x = e.clientX - r.left,
    y = e.clientY - r.top;
  let best = null,
    d = 64;
  for (const q of cv._pts || []) {
    const k = (q.x - x) ** 2 + (q.y - y) ** 2;
    if (k < d) {
      d = k;
      best = q;
    }
  }
  return best;
}

export function mount() {
  const sec = $('#insights');
  if (!sec) return;
  const load = () => {
    if (!$('#insFindings').dataset.panel) mountScoped($('#insFindings'), findings);
    return json('insights.json')
      .then(d => {
        I = d;
        $('#insBody').setAttribute('aria-busy', 'false');
        render();
      })
      .catch(e => {
        console.error('insights:', e);
        $('#insSub').textContent = 'The stored market measurements could not be loaded.';
        $('#insBody').setAttribute('aria-busy', 'false');
        $('#insBody').innerHTML =
          '<p class="load-error mt16" role="status">Check the connection and reload. No measurement is shown until its source file loads.</p>';
      });
  };
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(
      es => {
        if (es.some(e => e.isIntersecting)) {
          io.disconnect();
          load();
        }
      },
      { rootMargin: '600px' }
    );
    io.observe(sec);
  } else load();
  sec.addEventListener('pointermove', e => {
    const cv = e.target.closest('#aimap');
    if (!cv) return;
    const q = near(cv, e);
    cv.style.cursor = q ? 'pointer' : 'default';
    $('#aitip').textContent = q
      ? `${q.p[1]} · ${n(q.p[3])} Wikipedia and sister-site pages · ${I.map.axes.y[q.p[4]]}`
      : 'Point at a dot for the product; open it for its page.';
  });
  sec.addEventListener('click', e => {
    const c = e.target.closest('.aipop .chip');
    if (c) {
      pop = c.dataset.pop;
      render();
      return;
    }
    const cv = e.target.closest('#aimap');
    if (!cv) return;
    const q = near(cv, e);
    if (q) {
      location.hash = '#app=' + q.p[0];
      $('#check').scrollIntoView({ block: 'start', behavior: reduce ? 'auto' : 'smooth' });
    }
  });
  let t;
  addEventListener('resize', () => {
    clearTimeout(t);
    t = setTimeout(drawMap, 150);
  });
  addEventListener('airstack:view', e => {
    if (e.detail === 'insights') requestAnimationFrame(drawMap);
  });
}
