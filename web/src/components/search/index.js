import { clearTool, renderAll, selectTool } from '../app.js';
import { kindOf, mono } from '../avatar.js';
import { rowMap } from '../browse.js';
import { notFound } from '../cards/tool.js';
import { SLUGS, addr, loadDir, researchedFacts } from './directory.js';
import { M } from '../../lib/data.js';
import { $ } from '../../lib/dom.js';
import { esc, known, n, sq } from '../../lib/format.js';
import { MK } from '../../lib/market.js';

const CATS = M.cats || [];
const LANEN = id => (M.lanes.find(l => l.id === id) || CATS.find(c => c.id === id) || {}).name || id;
export const IDX = M.index.map(([id, name, lane, aliases]) => ({
  id,
  name,
  lane,
  laneName: LANEN(lane),
  k: sq(name),
  ak: (aliases || []).map(sq),
  cat: CATS.some(c => c.id === lane),
}));
export const byId = id => IDX.find(x => x.id === id),
  byName = nm => IDX.find(x => x.k === sq(nm));
export const q = $('#q'),
  ta = $('#ta'),
  BR = { type: null };
let hits = [],
  act = 0;
export const PENDING = [];
export const onMarket = fn => (MK ? fn() : PENDING.push(fn));
export const moverRows = () => ((MK && MK.movers) || M.moversTop).rows;
/* edit distance from a to b (swapped neighbours count as one), or Infinity past max */
const near = (a, b, max) => {
  if (Math.abs(a.length - b.length) > max) return Infinity;
  let older = null,
    prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const row = [i];
    let low = i;
    for (let j = 1; j <= b.length; j++) {
      let v = Math.min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      if (older && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) v = Math.min(v, older[j - 2] + 1);
      row.push(v);
      if (v < low) low = v;
    }
    if (low > max) return Infinity;
    older = prev;
    prev = row;
  }
  return prev[b.length] <= max ? prev[b.length] : Infinity;
};
export function rank(s) {
  const k = sq(s);
  if (!k) return [];
  const R = rowMap(),
    dl = x =>
      (R[x.id] && R[x.id].dl.value) ??
      -1;
  /* keep only the best 8, so a keystroke costs the same at any catalog size */
  const top = [],
    first = (a, b) =>
      b.sc - a.sc ||
      b.dl - a.dl ||
      !!a.x.listed - !!b.x.listed ||
      (b.x.links || 0) - (a.x.links || 0) ||
      a.x.name.localeCompare(b.x.name);
  const offer = (x, sc) => {
    if (x.listed && sc < (x.org ? 118 : 120))
      sc /= 10; /* a listing ranks below tracked tools unless it is the exact name */
    if (top.length === 8 && sc < top[7].sc) return;
    const r = { x, sc, dl: dl(x) };
    if (top.length === 8 && first(r, top[7]) >= 0) return;
    let i = top.length;
    while (i > 0 && first(r, top[i - 1]) < 0) i--;
    top.splice(i, 0, r);
    if (top.length > 8) top.pop();
  };
  let strong = 0,
    best = 0;
  const tracked = [],
    listed = [];
  for (const x of IDX) {
    const w =
        x.w ||
        (x.w = x.name
          .toLowerCase()
          .split(/[\s.\-/]+/)
          .map(sq)),
      lk = x.lk || (x.lk = sq(x.laneName));
    let sc = 0;
    if (x.k === k) sc = 120;
    else if (x.ak.includes(k)) sc = 118;
    else if (x.k.startsWith(k)) sc = 100;
    else if (x.ak.some(a => a.startsWith(k))) sc = 90;
    else if (w.some(v => v.startsWith(k))) sc = 70;
    else if (x.k.includes(k)) sc = 40;
    else if (lk.includes(k)) sc = 20;
    if (sc) {
      if (sc >= 40) strong++;
      if (sc > best) best = sc;
      offer(x, sc);
    } else (x.listed ? listed : tracked).push(x);
  }
  if (k.length >= 4 && strong < 3 && best < 90) {
    /* misspellings: within 1 edit (up to 6 letters) or 2, ranked below every real match */
    const max = k.length > 6 ? 2 : 1;
    /* a typo rarely changes both of a name's first two letters, so skip names sharing neither */
    const k0 = k[0],
      k1 = k[1],
      plausible = a => a[0] === k0 || a[1] === k1 || a[1] === k0 || a[0] === k1;
    const measure = list => {
      let hits = 0;
      for (const x of list) {
        let d = Infinity;
        if (plausible(x.k)) d = Math.min(near(k, x.k, max), near(k, x.k.slice(0, k.length), max) + 0.5);
        for (const a of x.ak)
          if (plausible(a)) d = Math.min(d, near(k, a, max), near(k, a.slice(0, k.length), max) + 0.5);
        if (d <= max) {
          offer(x, 30 - d);
          hits++;
        }
      }
      return hits;
    };
    /* the tracked tools first; the listings only when none was close */
    if (!measure(tracked)) measure(listed);
  }
  return top.map(r => r.x);
}
const related = (top, shown) => {
  if (!top || top.listed) return [];
  const R = rowMap(),
    dl = x => (R[x.id] && R[x.id].dl.value) ?? -1;
  return IDX.filter(x => x.lane === top.lane && !x.listed && !shown.includes(x))
    .sort((a, b) => dl(b) - dl(a) || researchedFacts(b) - researchedFacts(a) || a.name.localeCompare(b.name))
    .slice(0, 5);
};
export function showTA() {
  if (!q.value.trim()) {
    hits = [];
    hideTA();
    return;
  }
  const all = rank(q.value),
    products = all.filter(x => !x.org),
    orgs = all.filter(x => x.org),
    near = related(products[0], products);
  hits = [...products, ...near, ...orgs];
  if (act >= hits.length) act = 0;
  let i = 0;
  const row = x =>
    `<li role="option" id="o${i}" aria-selected="${i === act}" data-i="${i++}"><span class="who">${mono(x, 's20', kindOf(x) || 'none')}<span>${esc(x.name)}</span></span><span class="meta">${esc(x.laneName)} · ${known(x, researchedFacts(x))}</span></li>`;
  const group = (title, xs) => (xs.length ? `<li class="tah" role="presentation">${esc(title)}</li>${xs.map(row).join('')}` : '');
  ta.innerHTML = hits.length
    ? group('Products', products) + group(`Related in ${near.length ? products[0].laneName : ''}`, near) + group('Organizations', orgs)
    : `<li class="none" role="option" aria-disabled="true">We don’t track “${esc(q.value.trim().slice(0, 40))}” yet</li>`;
  ta.hidden = false;
  q.setAttribute('aria-expanded', 'true');
  q.setAttribute('aria-activedescendant', hits.length ? 'o' + act : '');
  if (hits.length) $(`#o${act}`).scrollIntoView({ block: 'nearest' });
}
export function hideTA() {
  ta.hidden = true;
  q.setAttribute('aria-expanded', 'false');
  q.removeAttribute('aria-activedescendant');
}
let blurT;
const openApp = (id, first) => {
  const x = byId(id);
  if (x) {
    selectTool(x, {
      push: false,
    }); /* also for the open tool: back and forward restore it from the address */
    return;
  }
  if (first) renderAll();
  if (!IDX.some(x => x.id === id))
    loadDir().then(
      () => {
        const y = byId(id) || byId(SLUGS.get(id));
        if (y) {
          selectTool(y, { push: false });
          history.replaceState(null, '', `#app=${addr(y)}`); /* an old id link tidies itself to the readable address */
        }
      },
      () => {}
    );
};

export function mount() {
  q.placeholder = `Search ${n(M.index.length + (M.dir ? M.dir.products : 0))} products + ${n((M.dir || {}).orgs || 0)} makers`;
  /* cancel a pending blur hide, so suggestions typed right after it stay open */
  q.addEventListener('input', () => {
    clearTimeout(blurT);
    act = 0;
    showTA();
  });
  q.addEventListener('focus', () => {
    clearTimeout(blurT);
    showTA();
    loadDir().catch(() => {});
  });
  q.addEventListener('blur', () => {
    blurT = setTimeout(hideTA, 120);
  });
  q.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (ta.hidden) showTA();
      else if (hits.length) {
        act = (act + (e.key === 'ArrowDown' ? 1 : -1) + hits.length) % hits.length;
        showTA();
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const v = q.value.trim();
      if (hits.length) selectTool(hits[act]);
      else if (v) notFound(v);
    } else if (e.key === 'Escape') {
      hideTA();
    }
  });
  ta.addEventListener('mousedown', e => {
    e.preventDefault();
    const l = e.target.closest('li[data-i]');
    if (l) selectTool(hits[+l.dataset.i]);
  });
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-pick]');
    if (b) {
      const x = byId(b.dataset.pick);
      if (x) selectTool(x);
      return;
    }
    if (e.target.closest('#change')) {
      BR.type = null; /* Change tool returns to the first screen, not to a taxonomy type */
      clearTool();
    }
  });
  addEventListener('hashchange', () => {
    const m = /[#&]app=([\w.-]+)/.exec(location.hash);
    if (m) openApp(m[1]);
  });
  {
    const m = /[#&]app=([\w.-]+)/.exec(location.hash);
    if (m) openApp(m[1], true);
    else renderAll();
  }
}
