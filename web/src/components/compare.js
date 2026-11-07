// spec: AS-256 AS-366
import { METRIC, STR, chainData, showVal } from './chain.js';
import { kindOf, mono } from './avatar.js';
import { amt, per } from './prices.js';
import { loadDir, researchedFacts } from './search/directory.js';
import { byId, rank } from './search/index.js';
import { M } from '../lib/data.js';
import { $, sr } from '../lib/dom.js';
import { esc, fd, ic, url } from '../lib/format.js';
import { PRICES, loadPrices } from '../lib/profiles.js';
import { show } from '../lib/router.js';

/* ---------- compare 2 to 5 products: what each one's OWN pages say, side by side ----------
   Every cell is the page's own words with the page it is on and the day it was found there, or "Not observed". Facts come from chain-data.json
   (each with its verbatim quote, found on the page by code); list prices from pricing.json, only where a price was read from a pricing page.
   The address is the comparison (#compare=a,b,c), so back and forward move through it and a link carries it. A saved one is kept in this browser
   only; it is current for the same 14 days an answer is, counted from the oldest fact it shows. */
const KEY = 'airstack.compare.v1',
  DAYS = 14,
  SHOWN = 8; /* the first items of a long list; the rest open under it */
let st = { ids: [] },
  onlyDiff = false,
  act = 0,
  hits = [],
  blurT,
  keep = ''; /* what to focus again after a redraw */
const nameOf = (id, D) =>
  (D && D.entities[id] && D.entities[id].name) || (M.index.find(x => x[0] === id) || [])[1] || id;
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
  /* the address changed (back, forward, a pasted link, the Compare button): show what it names */
  const c = parse(location.hash);
  if (c) st = c;
  else if (location.hash !== '#/compare') return;
  draw();
}

/* ---------- a cell ---------- */
const nobs = '<span class="nobs">Not observed</span>';
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
const src = (f, more) =>
  `<a class="ext" href="${url(f.url)}" target="_blank" rel="noopener noreferrer">${esc(f.host)}${ic('out')}</a> <span class="meta">found ${fd(f.verified)}</span>${more ? ` <span class="meta">· ${more} more page${more > 1 ? 's' : ''}</span>` : ''}`;
/* the facts of one product for one field: its own pages first, a list gathered across them */
function cellOf(F) {
  if (!F.length) return { html: nobs };
  const f = F[0],
    lists = Array.isArray(f.value),
    value = lists ? [...new Set(F.filter(x => Array.isArray(x.value)).flatMap(x => x.value))] : f.value,
    own = typeof f.value === 'string' && f.value === f.quote; /* a sentence IS its quote: shown once */
  const quotes = F.slice(0, 4)
    .map(
      x =>
        `<li><q>${esc(x.quote)}</q> <a class="ext" href="${url(x.url)}" target="_blank" rel="noopener noreferrer">${esc(x.host)}${ic('out')}</a> <span class="meta">${fd(x.verified)}</span></li>`
    )
    .join('');
  return {
    key: norm(value),
    date: f.verified,
    html: `<div class="cv">${own ? `<q>${esc(f.quote)}</q>` : `<b>${lists ? items(value) : esc(showVal(value))}</b>`}</div>
      <div class="cs">${src(f, F.length - 1)}</div>
      ${own ? '' : `<details class="qt"><summary title="${esc(f.quote)}">${F.length > 1 ? 'Quotes' : 'Quote'}</summary><ul>${quotes}</ul>${F.length > 4 ? `<p class="meta">and ${F.length - 4} more on the evidence chain</p>` : ''}</details>`}`,
  };
}
/* a list price counts only as the pricing page's own words: the lowest paid plan, and whether a free one is listed */
function priceOf(id) {
  const Q = PRICES[id];
  if (!Q || !Q.plans || !Q.plans.length) return { html: nobs };
  const paid = Q.plans.filter(p => amt(p) > 0).sort((a, b) => amt(a) - amt(b)),
    p = paid[0] || Q.plans[0],
    free = Q.plans.some(x => amt(x) === 0);
  return {
    date: Q.checked,
    html: `<div class="cv"><b>${free ? 'Free plan listed' : ''}${free && paid.length ? ' · ' : ''}${paid.length ? `from ${esc(p.price)}${esc(per(p))}` : ''}</b></div>
      <div class="cs"><a class="ext" href="${url(Q.url)}" target="_blank" rel="noopener noreferrer">${esc(Q.url.replace(/^https?:\/\/(www\.)?/, '').split('/')[0])}${ic('out')}</a> <span class="meta">found ${fd(Q.checked)}</span></div>
      <details class="qt"><summary title="${esc(p.quote)}">Quote</summary><ul><li><q>${esc(p.quote)}</q></li></ul></details>`,
  };
}

/* ---------- the screen ---------- */
async function draw() {
  const sub = $('#cmpSub'),
    out = $('#cmpOut');
  $('#cmpChips').innerHTML = '';
  sub.textContent = 'Loading the evidence…';
  let D;
  try {
    [D] = await Promise.all([chainData(), loadPrices()]);
  } catch {
    sub.textContent = 'The comparison needs a connection: the evidence is loaded on demand.';
    out.innerHTML = '';
    return;
  }
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
  /* rows: the price, then every field any of these products states, in the order the profile page uses */
  const rows = [
    { l: 'List price', cells: ids.map(priceOf) },
    ...Object.keys(METRIC).map(m => ({
      l: METRIC[m],
      one: STR.has(m),
      cells: ids.map(id => cellOf(facts(id, m))),
    })),
  ].filter(r => r.cells.some(c => c.date));
  for (const r of rows) {
    const seen = new Set(r.cells.filter(c => c.key != null).map(c => c.key));
    r.diff =
      !r.one &&
      r.l !== 'List price' &&
      seen.size > 1; /* observed values only: Not observed against a value is not a difference */
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
    ? `Scope: ${ids.length} products × ${rows.length} fields · Coverage: ${observed} of ${possible} cells sourced${nd ? ` · ${nd} fields differ` : ''}${oldest ? ` · Oldest source check ${fd(oldest)}` : ''}. Open Quote for the page’s exact words.`
    : ids.length
      ? 'Add at least one more product: a comparison is 2 to 5.'
      : 'Add 2 to 5 products. Every cell is what that product’s own page says, with the page and the day it was found there.';
  const eg = [
    ['notion', 'asana', 'linear'],
    ['cursor', 'cline', 'claude-code'],
    ['fireflies', 'otter', 'fathom'],
  ].filter(g => g.every(id => D.entities[id]));
  out.innerHTML = !ready
    ? `<div class="cmp-eg"><p class="meta">Try one</p>${eg.map(g => `<a class="cta" href="#compare=${g.join(',')}">${esc(g.map(id => nameOf(id, D)).join(' · '))}</a>`).join('')}</div>`
    : `<div class="cmp-bar"><button class="chip" type="button" id="cmpDiff" aria-pressed="${onlyDiff}"${nd ? '' : ' disabled'}>Only what differs</button></div>
  ${ids.length > 2 ? '<p class="cmp-swipe meta">Swipe the table to see every product <span aria-hidden="true">→</span></p>' : ''}
  <div class="scroll"><table class="t${ids.length === 2 ? ' two' : ''}" id="cmpTbl"><thead><tr><th scope="col"><span class="sr">Field</span></th>${ids
    .map(id => {
      const x = byId(id);
      return `<th scope="col"><a href="#app=${esc(id)}">${x ? `${mono(x, 's20')} ` : ''}${esc(nameOf(id, D))}</a>${x ? `<span class="meta">${esc(x.laneName)}</span>` : ''}</th>`;
    })
    .join('')}</tr></thead><tbody>${rows
    .filter(r => !onlyDiff || r.diff)
    .map(
      r =>
        `<tr${r.diff ? ' class="diff"' : ''}><th scope="row">${esc(r.l)}${r.diff ? '<span class="dtag">differs</span>' : ''}</th>${r.cells.map((c, i) => `<td data-l="${esc(nameOf(ids[i], D))}">${c.html}</td>`).join('')}</tr>`
    )
    .join('')}</tbody></table></div>
  ${blank.length ? `<p class="meta mt16">${esc(blank.map(id => nameOf(id, D)).join(', '))}: AirStack has read none of its pages yet, so there is nothing to show for it. Nothing is guessed.</p>` : ''}
  <p class="mt24"><button class="ghost" type="button" id="cmpSave">${same ? 'Saved' : 'Save this comparison'}</button> ${mine && !same ? '<button class="ghost" type="button" id="cmpOpen">Open the saved one</button> ' : ''}<button class="ghost" type="button" id="cmpCopy">Copy link</button></p>
  <p class="meta mt12" id="cmpExp">${same ? `Saved ${fd(mine.on)}. ` : ''}${ends ? (recheckDue ? `Recheck due since ${fd(ends)}. The oldest supporting source was checked ${fd(oldest)}; previous values remain visible as history until monitoring refreshes them.` : `Monitoring active through ${fd(ends)}. Next recheck is based on the oldest supporting source check (${fd(oldest)}).`) : 'Monitoring starts when the comparison has a dated source.'}</p>`;
  if (keep) {
    const k = $(keep);
    keep = '';
    if (k) k.focus({ preventScroll: true });
  }
}

/* ---------- adding a product: the search's own index and ranking ---------- */
const known = x =>
  researchedFacts(x) ? `researched · ${researchedFacts(x)} facts` : x.dir ? 'listed, not researched' : 'tracked';
function suggest() {
  const ta = $('#cmpTa'),
    v = $('#cmpQ').value;
  hits = v.trim() ? rank(v).filter(x => !x.org && !st.ids.includes(x.id)) : [];
  if (act >= hits.length) act = 0;
  ta.innerHTML = hits.length
    ? hits
        .map(
          (x, i) =>
            `<li role="option" id="cmpo${i}" aria-selected="${i === act}" data-i="${i}"><span class="who">${mono(x, 's20', kindOf(x) || 'none')}<span>${esc(x.name)}</span></span><span class="meta">${esc(x.laneName)} · ${known(x)}</span></li>`
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
    <div class="find big"><svg class="i si" aria-hidden="true"><use href="#i-search"/></svg><input id="cmpQ" role="combobox" aria-label="Add a product to compare" aria-expanded="false" aria-controls="cmpTa" aria-autocomplete="list" autocomplete="off" spellcheck="false" autocapitalize="off" placeholder="Add a product"><ul class="ta" id="cmpTa" role="listbox" aria-label="Matching products" hidden></ul></div>
    <p class="meta" id="cmpFull" hidden>Five is the most.</p></div><div id="cmpOut" aria-live="polite"></div>`;
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
  $('#cmpSec').addEventListener('click', async e => {
    const t = e.target.closest('button');
    if (!t) return;
    if (t.dataset.rm) {
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
    else if (t.id === 'cmpCopy') {
      const before = t.textContent;
      try {
        if (!navigator.clipboard) throw new Error('Clipboard unavailable');
        await navigator.clipboard.writeText(location.href);
        t.textContent = 'Link copied';
        sr('Comparison link copied');
      } catch {
        t.textContent = 'Copy the address';
        sr('Copy failed. The address bar carries this comparison.');
      }
      setTimeout(() => {
        if (t.isConnected) t.textContent = before;
      }, 1600);
    }
  });
}
mount();
