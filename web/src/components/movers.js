// spec: AS-112 AS-256 AS-326
import { here } from '../lib/router.js';
import { selectByName } from './app.js';
import { radios } from './chips.js';
import { M } from '../lib/data.js';
import { $, $$, reduce } from '../lib/dom.js';
import { esc, fd, ic, n, pct, sgn, url } from '../lib/format.js';
import { MK } from '../lib/market.js';
import { pview } from '../lib/profiles.js';

/* ---------- moving this week: registry and attention signals, each linked to the request that produced it ---------- */
export const MV = {
  lane: 'all',
  sort: 'dl',
  all: false,
  tok: 0,
  open: (/[#&]tool=([\w.-]+)/.exec(location.hash) || [])[1] || null,
};
const TOP = 12;
export function renderMovers() {
  const D = (MK && MK.movers) || M.moversTop;
  if (!D) {
    $('#movers').hidden = true;
    return;
  }
  const w = D.window;
  $('#moversSub').textContent =
    `${D.rows.length} tools · ${D.lanes.length} lanes · ${fd(w.last7[0])} to ${fd(w.last7[1])} vs the week before · fetched ${fd(D.generated)}`;
  radios(
    $('#lanes'),
    ['All'].concat(D.lanes.map(l => l.name)),
    MV.lane === 'all' ? 'All' : D.lanes.find(l => l.id === MV.lane).name,
    v => {
      MV.lane = v === 'All' ? 'all' : D.lanes.find(l => l.name === v).id;
      drawMovers();
    }
  );
  drawMovers();
}
const PH = () => matchMedia('(max-width:720px)').matches;
export function drawMovers() {
  const D = (MK && MK.movers) || M.moversTop;
  const weak = r =>
    r.dl.delta > 0 &&
    ((r.dl.vsBase != null && r.dl.vsBase < 0) ||
      r.dl.value < 5000); /* a rebound or a tiny base ranks below solid movers: still listed, labelled */
  const key = { dl: r => r.dl.delta, hn: r => r.hn.delta, stars: r => r.gh.stars }[MV.sort];
  const tier = r =>
    MV.sort === 'dl' && weak(r) ? 1 : 0; /* sorting by change: solid movers first, then rebounds and small bases */
  const all = D.rows
    .filter(r => MV.lane === 'all' || r.lane === MV.lane)
    .slice()
    .sort((a, b) => tier(a) - tier(b) || (key(b) ?? -Infinity) - (key(a) ?? -Infinity) || a.name.localeCompare(b.name));
  let rows = MV.all ? all : all.slice(0, TOP);
  const mxd = Math.max(1, ...all.map(r => (r.dl.delta == null ? 0 : Math.abs(r.dl.delta))));
  if (MV.open && !rows.some(r => r.id === MV.open)) {
    const o = all.find(r => r.id === MV.open);
    if (o) rows = rows.concat([o]);
  }
  const more = $('#mvMore'),
    n0 = D.partial ? D.total : all.length;
  more.hidden = n0 <= TOP;
  more.disabled = !!D.partial;
  more.textContent = MV.all ? `Show top ${TOP}` : `Show all ${n0}`;
  $$('#mvt th button').forEach(b => b.setAttribute('aria-pressed', b.dataset.s === MV.sort));
  const answered = new Set(M.tools.map(t => t.name));
  const why = (t, r) => `<span class="state-note" title="${esc(r || t)}">${t}</span>`;
  const ph = PH(); /* once per draw, not once per row */
  const html = rows.map(
    r => `<tr>
    <td data-l="Tool">${ph ? `<button type="button" class="rowtog" aria-expanded="false" data-rt="1"><b>${esc(r.name)}</b><br><span class="meta">${esc(r.laneName)}</span></button>` : `<b>${esc(r.name)}</b><br><span class="meta">${esc(r.laneName)}</span>`}</td>
    <td data-l="Downloads, 7 days" class="r">${r.dl.value !== null ? `${n(r.dl.value)} <span class="meta">${esc(r.dl.registry)}</span>${r.dl.url ? `<a class="src" href="${url(r.dl.url)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(r.dl.registry)} page for ${esc(r.name)}">${ic('out')}</a>` : ''}` : why('No registry record', r.dl.why)}</td>
    <td data-l="Change" class="r">${pct(r.dl.delta) !== null ? `${pct(r.dl.delta)}<span class="bar" aria-hidden="true"><i class="${r.dl.delta < 0 ? 'neg' : ''}" style="--w:${Math.max(2, (Math.abs(r.dl.delta) / mxd) * 100).toFixed(1)}%"></i></span>${weak(r) ? `<span class="meta"> ${r.dl.value < 5000 ? 'small base' : 'below its 4-week level'}</span>` : ''}` : why(r.dl.value !== null ? 'No prior week' : 'No weekly baseline', r.dl.why)}</td>
    <td data-l="HN stories, 7 days" class="r">${r.hn.value !== null ? `${n(r.hn.value)} <span class="meta">${sgn(r.hn.delta)}</span><a class="src" href="https://hn.algolia.com/?q=${encodeURIComponent((r.hn.query || '').replace(/"/g, ''))}" target="_blank" rel="noopener noreferrer" aria-label="Hacker News search for ${esc(r.name)}">${ic('out')}</a>` : why('No HN record', r.hn.why)}</td>
    <td data-l="GitHub stars" class="r">${r.gh.stars !== null && r.gh.stars !== undefined ? `${n(r.gh.stars)}<a class="src" href="${url(r.gh.url)}" target="_blank" rel="noopener noreferrer" aria-label="GitHub repository for ${esc(r.name)}">${ic('out')}</a>` : why('No GitHub record', r.gh.why)}</td>
    <td data-l="Last release">${r.gh.release ? `${esc(r.gh.release)} <span class="meta">${fd(r.gh.released)}</span>` : why('No release recorded', r.gh.why)}</td>
    <td data-l="AirStack">${
      answered.has(r.name)
        ? `<a class="ext" href="#check" data-app="${esc(r.name)}">Check yours</a>`
        : MK && MK.profiles && MK.profiles[r.id]
          ? `<button class="ghost pbtn" type="button" data-p="${esc(r.id)}" aria-expanded="${MV.open === r.id}" aria-controls="pr-${esc(r.id)}">Profile · ${MK.profiles[r.id].facts} facts</button>`
          : '<span class="state-note">Catalog only</span>'
    }</td></tr>
    ${MV.open === r.id && MK && MK.profiles[r.id] ? `<tr class="prow" id="pr-${esc(r.id)}"><td colspan="7">${pview(r, r.id, drawMovers)}</td></tr>` : ''}`
  );
  const tok = ++MV.tok,
    FIRST = 24;
  $('#mvt tbody').innerHTML = html.slice(0, FIRST).join('');
  if (html.length > FIRST)
    requestAnimationFrame(() => {
      if (tok === MV.tok) $('#mvt tbody').insertAdjacentHTML('beforeend', html.slice(FIRST).join(''));
    });
}

export function mount() {
  matchMedia('(max-width:720px)').addEventListener('change', () => {
    if (typeof drawMovers === 'function' && $('#mvt tbody')) drawMovers();
  });
  document.addEventListener('click', e => {
    const b = e.target.closest('#mvt th button');
    if (b) {
      MV.sort = b.dataset.s;
      drawMovers();
      return;
    }
    if (e.target.closest('#mvMore')) {
      MV.all = !MV.all;
      drawMovers();
      return;
    }
    const rt = e.target.closest('#mvt .rowtog');
    if (rt) {
      const tr = rt.closest('tr'),
        o = tr.classList.toggle('open');
      rt.setAttribute('aria-expanded', o);
      return;
    }
    const pb = e.target.closest('#mvt .pbtn');
    if (pb) {
      MV.open = MV.open === pb.dataset.p ? null : pb.dataset.p;
      history.replaceState(null, '', MV.open ? `#tool=${MV.open}` : here());
      drawMovers();
      return;
    }
    const a = e.target.closest('#mvt a[data-app]');
    if (a) {
      e.preventDefault();
      selectByName(a.dataset.app);
      $('#check').scrollIntoView({ block: 'start', behavior: reduce ? 'auto' : 'smooth' });
    }
  });
  renderMovers();
}
