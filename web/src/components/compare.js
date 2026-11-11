import { METRIC, STR, chainData, checks, says, showVal } from './chain.js';
import { kindOf, mono } from './avatar.js';
import { listed, per } from './prices.js';
import { loadDir, researchedFacts } from './search/directory.js';
import { byId, rank } from './search/index.js';
import { M, json } from '../lib/data.js';
import { $, copy } from '../lib/dom.js';
import { esc, fd, host, ic, known, url } from '../lib/format.js';
import { PRICES, loadPrices } from '../lib/profiles.js';
import { send } from '../lib/beacon.js';
import { show } from '../lib/router.js';
import { VIEW } from '../lib/view.js';
import { SearchField } from '../ui/search.js';

const KEY = 'airstack.compare.v1',
  DAYS = VIEW.compareRecheckDays,
  SHOWN = VIEW.compareShown;
let st = { ids: [] },
  onlyDiff = false,
  act = 0,
  hits = [],
  blurT,
  keep = ''; /* what to focus again after a redraw */
const nameOf = (id, D) => (D && D.entities[id] && D.entities[id].name) || (byId(id) || {}).name || id;
const hash = () => `#compare=${st.ids.join(',')}`;
const saved = () => {
  try {
    return JSON.parse(localStorage.getItem(KEY));
  } catch {
    return null;
  }
};
const parse = h => {
  const p = new URLSearchParams(h.slice(1));
  return p.has('compare')
    ? {
        ids: (p.get('compare') || '')
          .split(',')
          .filter(x => /^[\w.-]{1,80}$/.test(x))
          .slice(0, 5),
      }
    : null;
};
function go(next) {
  if (next.ids.length > 1 && next.ids.length > st.ids.length) send('compare', { n: Math.min(next.ids.length, 5) });
  st = next;
  history.pushState(null, '', hash());
  draw();
}
export function openCompare(ids, opener) {
  go({ ids });
  show('compare');
  if (opener) $('#cmpT').focus({ preventScroll: true });
}
export function sync() {
  const c = parse(location.hash);
  if (c) {
    st = c;
    if (c.ids.length > 1) send('compare', { n: Math.min(c.ids.length, 5) });
  } else if (location.hash !== '#/compare') return;
  draw();
}

const nobs = '<span class="nobs">Not observed</span>';
const LABEL = { similar: 'Similar', rising: 'Rising' }; /* what each suggestion measured, never a rank */
let SUG = null;
const norm = v =>
  Array.isArray(v)
    ? [...v]
        .map(x => String(x).toLowerCase())
        .sort()
        .join('|')
    : String(v).toLowerCase();
const items = list =>
  list.length > SHOWN
    ? `${esc(list.slice(0, SHOWN).join(', '))}<details class="more"><summary>+${list.length - SHOWN} more</summary>${esc(list.slice(SHOWN).join(', '))}</details>`
    : esc(list.join(', '));
function cellOf(F, name, label) {
  if (!F.length) return { html: nobs };
  const f = F[0],
    lists = Array.isArray(f.value),
    value = lists ? [...new Set(F.filter(x => Array.isArray(x.value)).flatMap(x => x.value))] : f.value,
    own = typeof f.value === 'string' && f.value === f.quote;
  const quotes = F.filter((x, i) => F.findIndex(y => y.quote === x.quote) === i) /* one line per distinct quote */
    .slice(0, 4)
    .map(x => `<li>${says(name, x)}<div class="mt-1">${checks(name, label, x)}</div></li>`)
    .join('');
  return {
    key: norm(value),
    date: f.verified,
    html: `<div class="cv">${own ? says(name, f) : `<b>${lists ? items(value) : esc(showVal(value))}</b>`}</div>
      ${own ? `<div class="mt-1">${checks(name, label, f)}</div>` : ''}
      ${own ? '' : `<details class="qt"><summary title="${esc(f.quote)}">${F.length > 1 ? 'What the pages say' : 'What the page says'}</summary><ul>${quotes}</ul>${F.length > 4 ? `<p class="meta">and ${F.length - 4} more on the evidence chain</p>` : ''}</details>`}`,
  };
}
function priceOf(id) {
  const Q = listed(id);
  if (!Q) return { html: nobs };
  return {
    date: Q.checked,
    html: `<div class="cv"><b>${esc(Q.plans.map(p => p.plan).join(', '))}</b></div>
      <div class="cs"><a class="ext" href="${url(Q.url)}" target="_blank" rel="noopener noreferrer">${esc(host(Q.url))}${ic('out')}</a> <span class="meta">Listed on ${fd(Q.checked)}</span></div>
      <details class="qt"><summary>What the pricing page says</summary><ul>${Q.plans.map(p => `<li>${esc(p.plan)}: ${esc(p.price)}${esc(per(p))} <span class="meta">“${esc(p.quote)}”</span></li>`).join('')}</ul></details>`,
  };
}

async function draw() {
  const sub = $('#cmpSub'),
    out = $('#cmpOut');
  $('#cmpChips').innerHTML = '';
  sub.textContent = 'Loading the evidence…';
  out.setAttribute('aria-busy', 'true');
  out.innerHTML = `<div class="skeleton ${st.ids.length ? 'skeleton-table' : 'skeleton-pills'}" role="status" aria-label="Loading comparison evidence"></div>`;
  let D;
  try {
    [D, SUG] = await Promise.all([chainData(), json('suggestions.json').catch(() => null), loadPrices()]);
  } catch {
    sub.textContent = 'The comparison needs a connection: the evidence is loaded on demand.';
    out.setAttribute('aria-busy', 'false');
    out.innerHTML = '<p class="load-error" role="status">Check the connection and reload.</p>';
    return;
  }
  out.setAttribute('aria-busy', 'false');
  const ids = st.ids,
    full = ids.length >= 5,
    facts = (id, m) =>
      (D.entities[id] ? D.entities[id].facts : [])
        .filter(f => f.verified && f.metric === m)
        .sort((a, b) => (b.class === 'vendor') - (a.class === 'vendor')); /* its own site before a store listing */
  $('#cmpChips').innerHTML = ids
    .map(
      id =>
        `<span class="cpick">${esc(nameOf(id, D))}<button class="x" type="button" data-rm="${esc(id)}" aria-label="Remove ${esc(nameOf(id, D))}">${ic('x')}</button></span>`
    )
    .join('');
  const add = $('#cmpQ');
  add.disabled = full;
  add.placeholder = full ? 'Five is the most' : ids.length ? 'Add another product' : 'Add a product';
  $('#cmpFull').hidden = !full;
  /* up to three others for the product added last, each with its label, reason and source */
  const last = ids[ids.length - 1],
    sug = full || !SUG ? [] : (SUG[last] || []).filter(s => !ids.includes(s.id) && LABEL[s.label]).slice(0, 3);
  $('#cmpSug').innerHTML = sug.length
    ? `<p class="lab">Others to compare with ${esc(nameOf(last, D))}</p><ul class="cmp-sug">${sug
        .map(s => {
          const src = s.source && typeof s.source === 'object' ? s.source : { url: s.source };
          return `<li><button class="chip" type="button" data-add="${esc(s.id)}">Add ${esc(nameOf(s.id, D))}</button><span class="dtag">${LABEL[s.label]}</span><span class="meta">${esc(s.why)}${src.url ? ` · <a class="ext" href="${url(src.url)}" target="_blank" rel="noopener noreferrer">${esc(src.name && src.name !== 'source' ? src.name : host(src.url))}${ic('out')}</a>` : ''}${src.read ? ` · read ${fd(src.read)}` : ''}</span></li>`;
        })
        .join('')}</ul>`
    : '';
  const rows = [
    { l: 'Plans and list prices', cells: ids.map(priceOf) },
    ...Object.keys(METRIC).map(m => ({
      l: METRIC[m],
      one: STR.has(m),
      cells: ids.map(id => cellOf(facts(id, m), nameOf(id, D), METRIC[m])),
    })),
  ].filter(r => r.cells.some(c => c.date));
  for (const r of rows) {
    const seen = new Set(r.cells.filter(c => c.key != null).map(c => c.key));
    r.diff =
      !r.one &&
      r.l !== 'Plans and list prices' &&
      seen.size > 1; /* Not observed against a value is not a difference */
  }
  const dates = rows.flatMap(r => r.cells.map(c => c.date).filter(Boolean)).sort(),
    oldest = dates[0],
    ends = oldest && new Date(Date.parse(oldest) + DAYS * 864e5).toISOString().slice(0, 10),
    recheckDue = ends && Date.now() > Date.parse(ends + 'T23:59:59Z'),
    mine = saved(),
    same = mine && mine.ids.join() === ids.join(),
    ready = ids.length >= 2,
    nd = rows.filter(r => r.diff).length,
    observed = rows.reduce((sum, r) => sum + r.cells.filter(c => c.date).length, 0),
    possible = rows.length * ids.length,
    blank = ids.filter(id => !D.entities[id]);
  sub.textContent = ready
    ? `Scope: ${ids.length} products × ${rows.length} fields · Coverage: ${observed} of ${possible} cells sourced${nd ? ` · ${nd} fields differ` : ''}${oldest ? ` · Oldest source check ${fd(oldest)}` : ''}. Open a cell for the vendor’s exact words.`
    : ids.length
      ? 'Add at least one more product: a comparison is 2 to 5.'
      : 'Add 2 to 5 products. Every cell is what that product’s own page says, with the page and the day it was found there.';
  const groups = new Map();
  for (const [id, , lane] of M.index)
    if (D.entities[id]) groups.set(lane, [...(groups.get(lane) || []), id]);
  const eg = [...groups.values()].filter(group => group.length >= 3).slice(0, 3).map(group => group.slice(0, 3));
  out.innerHTML = !ready
    ? ids.length ? '' /* one picked: the suggestions above are the next step */ : `<div class="cmp-eg"><p class="meta">Try one</p>${eg.map(g => `<a class="cta" href="#compare=${g.join(',')}">${esc(g.map(id => nameOf(id, D)).join(' · '))}</a>`).join('')}</div>`
    : `<div class="cmp-bar"><button class="chip" type="button" id="cmpDiff" aria-pressed="${onlyDiff && nd > 0}"${nd ? '' : ' disabled'}>Only what differs</button></div>
  ${ids.length > 2 ? '<p class="cmp-swipe meta">Swipe the table to see every product <span aria-hidden="true">→</span></p>' : ''}
  <div class="scroll"><table class="t${ids.length === 2 ? ' two' : ''}" id="cmpTbl"><thead><tr><th scope="col"><span class="sr">Field</span></th>${ids
    .map(id => {
      const x = byId(id);
      return `<th scope="col"><a href="#app=${esc(id)}">${x ? `${mono(x, 's20')} ` : ''}${esc(nameOf(id, D))}</a>${x ? `<span class="meta">${esc(x.laneName)}</span>` : ''}</th>`;
    })
    .join('')}</tr></thead><tbody>${rows
    .filter(r => !(onlyDiff && nd) || r.diff)
    .map(
      r =>
        `<tr${r.diff ? ' class="diff"' : ''}><th scope="row">${esc(r.l)}${r.diff ? '<span class="dtag">differs</span>' : ''}</th>${r.cells.map((c, i) => `<td data-l="${esc(nameOf(ids[i], D))}">${c.html}</td>`).join('')}</tr>`
    )
    .join('')}</tbody></table></div>
  ${blank.length ? `<p class="meta mt16">${esc(blank.map(id => nameOf(id, D)).join(', '))}: AirStack has read none of its pages yet.</p>` : ''}
  <p class="mt24"><button class="ghost" type="button" id="cmpSave">${same ? 'Saved' : 'Save this comparison'}</button> ${mine && !same ? '<button class="ghost" type="button" id="cmpOpen">Open the saved one</button> ' : ''}<button class="ghost" type="button" id="cmpCopy">Copy link</button></p>
  <p class="meta mt12" id="cmpExp">${same ? `Saved ${fd(mine.on)}. ` : ''}${ends ? (recheckDue ? `Needs a second look: the oldest supporting source was checked ${fd(oldest)}; previous values remain visible as history.` : `The oldest supporting source was checked ${fd(oldest)}.`) : 'No dated source yet.'}</p>`;
  if (keep) {
    const k = $(keep);
    keep = '';
    if (k) k.focus({ preventScroll: true });
  }
}

function suggest() {
  const ta = $('#cmpTa'),
    v = $('#cmpQ').value;
  hits = v.trim() ? rank(v).filter(x => !x.org && !st.ids.includes(x.id)) : [];
  if (act >= hits.length) act = 0;
  ta.innerHTML = hits.length
    ? hits
        .map(
          (x, i) =>
            `<li role="option" id="cmpo${i}" aria-selected="${i === act}" data-i="${i}"><span class="who">${mono(x, 's20', kindOf(x) || 'none')}<span>${esc(x.name)}</span></span><span class="meta">${esc(x.laneName)} · ${known(x, researchedFacts(x))}</span></li>`
        )
        .join('')
    : v.trim()
      ? `<li class="none" role="option" aria-disabled="true">Nothing matches “${esc(v.trim().slice(0, 40))}”</li>`
      : '';
  ta.hidden = !v.trim();
  $('#cmpQ').setAttribute('aria-expanded', String(!ta.hidden));
  $('#cmpQ').setAttribute('aria-activedescendant', hits.length ? `cmpo${act}` : '');
}
function choose(x) {
  $('#cmpQ').value = '';
  suggest();
  keep = '#cmpQ';
  if (!st.ids.includes(x.id) && st.ids.length < 5) go({ ids: [...st.ids, x.id] });
}

function mount() {
  $('#cmpBody').innerHTML =
    `<div class="cmp-top"><div class="chips" id="cmpChips" aria-label="Products being compared"></div>
    ${SearchField({ id: 'cmpQ', label: 'Add a product to compare', placeholder: 'Add a product', listId: 'cmpTa', listLabel: 'Matching products' })}
    <p class="meta" id="cmpFull" hidden>Five is the most.</p><div id="cmpSug"></div></div><div id="cmpOut" aria-live="polite"></div>`;
  $('#cmpBody').setAttribute('aria-busy', 'false');
  const q = $('#cmpQ');
  q.addEventListener('focus', () => loadDir().then(suggest, () => {}));
  q.addEventListener('input', () => {
    clearTimeout(blurT);
    act = 0;
    suggest();
  });
  q.addEventListener('blur', () => {
    blurT = setTimeout(() => ($('#cmpTa').hidden = true), 120); /* a later focus or keystroke cancels it */
  });
  q.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (hits.length) act = (act + (e.key === 'ArrowDown' ? 1 : -1) + hits.length) % hits.length;
      suggest();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (hits[act]) choose(hits[act]);
    } else if (e.key === 'Escape') $('#cmpTa').hidden = true;
  });
  $('#cmpTa').addEventListener('mousedown', e => {
    e.preventDefault();
    const l = e.target.closest('li[data-i]');
    if (l) choose(hits[+l.dataset.i]);
  });
  $('#cmpSec').addEventListener('click', e => {
    const t = e.target.closest('button');
    if (!t) return;
    if (t.dataset.add) {
      keep = '#cmpQ';
      if (!st.ids.includes(t.dataset.add) && st.ids.length < 5) go({ ids: [...st.ids, t.dataset.add] });
    } else if (t.dataset.rm) {
      keep = '#cmpQ';
      go({ ids: st.ids.filter(x => x !== t.dataset.rm) });
    } else if (t.id === 'cmpDiff') {
      onlyDiff = !onlyDiff;
      keep = '#cmpDiff';
      draw();
    } else if (t.id === 'cmpSave') {
      try {
        localStorage.setItem(KEY, JSON.stringify({ ...st, on: new Date().toISOString().slice(0, 10) }));
      } catch {
        /* private mode: nothing is kept */
      }
      keep = '#cmpSave';
      draw();
    } else if (t.id === 'cmpOpen') go(saved());
    else if (t.id === 'cmpCopy') copy(t, location.href, { ok: 'Link copied', fail: 'Copy the address' });
  });
}
mount();
