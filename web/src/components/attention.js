import { radios } from './chips.js';
import { M, PARAMS, fillParams, json } from '../lib/data.js';
import { $ } from '../lib/dom.js';
import { esc, fd, ic, n, pct, url } from '../lib/format.js';
import { spark } from '../lib/spark.js';
import { VIEW } from '../lib/view.js';

/* a ranked list per category: Wikipedia views of each product's article, its own trend, and its change against its own prior window (attention.json params) */
const LENSES = ['Top', 'Rising', 'Falling'],
  SHOWN = VIEW.attentionShown;
let A = null,
  T = {},
  now = null,
  lens = 'Top';
const NAMES = new Map(M.index.map(r => [r[0], r[1]]));
const nameOf = id => NAMES.get(id) || A.products[id].article;
const label = id => (T[id] && T[id][0]) || id;

function options() {
  const ids = Object.keys(A.nodes).filter(id => A.nodes[id].top.length);
  $('#tyPick').innerHTML = ids
    .sort((a, b) => label(a).localeCompare(label(b)))
    .map(id => `<option value="${esc(id)}">${esc(label(id))} · ${n(A.nodes[id].top.length)}</option>`)
    .join('');
  now = now && A.nodes[now] ? now : ids.sort((a, b) => A.nodes[b].top.length - A.nodes[a].top.length)[0];
  $('#tyPick').value = now;
}

function row(id, i) {
  const p = A.products[id],
    nm = nameOf(id),
    P = A.source.params;
  return `<tr><td data-l="#" class="r num">${i + 1}</td>
    <td data-l="Product"><a href="#app=${encodeURIComponent(id)}"><b>${esc(nm)}</b></a></td>
    <td data-l="Views, last ${P.window_weeks} weeks" class="r num">${p.last_4w != null ? n(p.last_4w) : '<span class="nobs">Not observed</span>'}</td>
    <td data-c="series" data-l="${P.weeks} weeks">${spark(p.views, A.weeks, `${nm}, English Wikipedia views`) || '<span class="nobs">Not observed</span>'}</td>
    <td data-l="vs its prior ${P.window_weeks} weeks" class="r num">${p.change != null ? pct(p.change * 100) : `<span class="nobs" title="${esc(A.source.note || '')}">Not observed</span>`}</td>
    <td data-l="Article"><a class="ext" href="${url(p.url)}" target="_blank" rel="noopener noreferrer">${esc(p.article)}${ic('out')}</a> <span class="meta">read ${fd(p.fetched)}</span></td></tr>`;
}

function draw() {
  const N = A.nodes[now];
  if (!N) return;
  const ids = (N[lens.toLowerCase()] || []).filter(id => A.products[id]);
  radios($('#atLens'), LENSES, lens, v => {
    lens = v;
    draw();
  });
  const body = $('#att tbody');
  body.setAttribute('aria-busy', 'false');
  body.innerHTML =
    ids.slice(0, SHOWN).map(row).join('') ||
    `<tr><td colspan="6" class="meta">${lens === 'Top' ? 'No product here has a matched English Wikipedia article.' : `No product here is ${lens.toLowerCase()} by the rule below.`}</td></tr>`;
  $('#tyPage').href = T[now] ? `/t/${now}/` : '/t/';
  const S = A.source,
    W = A.weeks;
  $('#tyNote').innerHTML =
    `${esc(label(now))}: ${n(Math.min(SHOWN, ids.length))} of ${n(ids.length)} shown · weeks of ${fd(W[0])} to ${fd(W[W.length - 1])} · source: <a class="ext" href="${url(S.url)}" target="_blank" rel="noopener noreferrer">${esc(S.name)}${ic('out')}</a>, ${esc(S.license)}, read ${fd(S.read)}. ${esc(S.note)}`;
}

export function mount() {
  const sel = $('#tyPick');
  if (!sel) return;
  Promise.all([json('attention.json'), json('t/map.json').catch(() => ({ nodes: {} }))])
    .then(([a, t]) => {
      A = a;
      PARAMS.attention = a.source.params;
      fillParams($('#types'));
      T = t.nodes || {};
      options();
      draw();
    })
    .catch(e => {
      console.error('attention:', e);
      $('#types').hidden = true; /* no attention data: the panel is left out */
    });
  sel.addEventListener('change', () => {
    now = sel.value;
    draw();
  });
}
