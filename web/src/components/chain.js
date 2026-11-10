import { M } from '../lib/data.js';
import { here } from '../lib/router.js';
import { addr } from './search/directory.js';
import { S } from '../lib/state.js';
import { $, reduce } from '../lib/dom.js';
import { esc, fd, ic, n, reportUrl, textFragment, url } from '../lib/format.js';
import { ui } from '../ui/recipes.js';

let CH = null,
  chainOpener = null,
  cmp = null;
const withCompare = f => (cmp ? Promise.resolve(cmp) : import('./compare.js').then(m => (cmp = m))).then(f);
const CMP = /[#&]compare=|^#\/compare/;
export const METRIC = Object.fromEntries(M.labels);
export const STR = new Set(['what_it_does', 'license', 'pricing_basis']);
/* One fact as the vendor's words, with the links and dates to check it: the quote highlighted on its page, an archived copy, a report. */
export const says = (name, f) => `${f.class === 'vendor' ? `${esc(name)}’s page` : esc(f.host)} says: “${esc(f.quote)}”`;
export const checks = (name, label, f) =>
  `<span class="${ui.meta} inline-flex flex-wrap gap-x-2 gap-y-1"><a class="ext" href="${url(textFragment(f.url, f.quote))}" target="_blank" rel="noopener noreferrer">See it on ${esc(f.host)}${ic('out')}</a>${
    f.archived ? `<a class="ext" href="${url(f.archived.url)}" target="_blank" rel="noopener noreferrer">Archived copy${ic('out')}</a>` : ''
  }${f.first_read ? `<span>First read ${fd(f.first_read)}</span>` : ''}${f.checked ? `<span>Re-checked ${fd(f.checked)}</span>` : ''}<a href="${url(reportUrl(name, label, f.url, f.quote))}" target="_blank" rel="noopener noreferrer">Report a problem</a></span>`;
export const chainNow = () => CH;
/* the fields chain-data.json's published policy lets a page show */
export const shown = (D, m) => !D.policy || D.policy.tiers.low.includes(m) || D.policy.tiers.medium.includes(m);
export const showVal = v =>
  Array.isArray(v)
    ? v.join(', ')
    : v === true
      ? 'Yes'
      : v === false
        ? 'No'
        : typeof v === 'number'
          ? n(v)
          : v && typeof v === 'object'
            ? `${v.rating}${v.count ? ` (${v.count})` : ''}`
            : String(v);
export async function chainData() {
  if (!CH) {
    const r = await fetch('chain-data.json');
    if (!r.ok) throw new Error(r.status);
    CH = await r.json();
  }
  return CH;
}
export async function openChain(id, opener) {
  chainOpener = opener || chainOpener;
  const sec = $('#chainSec');
  sec.hidden = false;
  $('#chainSub').textContent = 'Loading the chain…';
  $('#chainTbl tbody').innerHTML = '';
  $('#chainSum').textContent = '';
  $('#chainNote').textContent = '';
  if (location.hash !== `#chain=${id}`) history.replaceState(null, '', `#chain=${id}`);
  sec.scrollIntoView({ block: 'start', behavior: reduce ? 'auto' : 'smooth' });
  $('#chainT').focus({ preventScroll: true });
  let D, E;
  try {
    D = await chainData();
    E = D.entities[id];
  } catch (e) {
    $('#chainSub').textContent =
      'The evidence chain needs a connection: it is loaded on demand and isn’t available offline until it has been opened once.';
    return;
  }
  if (!E) {
    $('#chainSub').textContent = 'No verified facts are recorded for this tool yet.';
    return;
  }
  const F = E.facts.filter(f => shown(D, f.metric)),
    n = F.length,
    ver = F.filter(f => f.verified).length,
    rc = F.filter(f => f.recheck),
    un = rc.filter(f => f.recheck.outcome === 'unchanged' || f.recheck.outcome === 'changed_quotes_present').length;
  const pages = new Set(F.map(f => f.url)).size,
    indep = new Set(F.flatMap(f => f.agree_independent)).size,
    multi = F.filter(f => f.agree.length).length;
  $('#chainT').textContent = `Evidence chain · ${E.name}`;
  $('#chainSub').textContent =
    `${n} facts from ${pages} pages, each with the path it took from the page to this screen`;
  $('#chainSum').textContent =
    `${ver} of ${n} quotes found on their pages · ${rc.length} re-checked live (${un} still supported) · ${multi} stated on more than one page · independent sources: ${indep || 'none yet'}`;
  const cls = c => D.classes[c] || c;
  $('#chainTbl tbody').innerHTML = F.slice()
    .sort((a, b) => (a.metric > b.metric) - (a.metric < b.metric) || (a.host > b.host) - (a.host < b.host))
    .map(
      f => `<tr>
    <td data-l="Fact"><b>${esc(METRIC[f.metric] || f.metric.replace(/_/g, ' '))}</b>${STR.has(f.metric) ? '' : ' ' + esc(showVal(f.value))}<div class="meta">${says(E.name, f)}</div><div class="mt-1">${checks(E.name, METRIC[f.metric] || f.metric, f)}</div></td>
    <td data-l="Source"><a class="ext" href="${url(f.url)}" target="_blank" rel="noopener noreferrer">${esc(f.host)}${ic('out')}</a><div class="meta">${esc(cls(f.class))}</div></td>
    <td data-l="Retrieved" class="num">${fd(f.retrieved)}<div class="meta">HTTP ${f.status || '?'} · <span class="mono">${esc(f.hash.slice(0, 8))}</span></div></td>
    <td data-l="Extracted" class="num">${fd(f.extracted)}</td>
    <td data-l="Verified">${f.verified ? `${ic('check')} quote found on the page<div class="meta num">${fd(f.verified)}</div>` : '<span class="nobs">Not verified</span>'}</td>
    <td data-l="Re-checked">${f.recheck ? `${fd(f.recheck.at)}<div class="meta">${esc(f.recheck.note)}</div>` : f.checked ? fd(f.checked) : '<span class="nobs">Not re-checked yet</span>'}</td>
    <td data-l="Also on">${f.agree.length ? `${f.agree.length} other page${f.agree.length > 1 ? 's' : ''}: ${esc(f.agree.join(', '))}` : '<span class="nobs">Only this page</span>'}${f.agree_independent.length ? `<div class="meta">Independent: ${esc(f.agree_independent.join(', '))}</div>` : ''}</td></tr>`
    )
    .join('');
  $('#chainNote').textContent = indep
    ? 'Some facts are also stated by independent sources, listed per fact.'
    : 'Every source here is the vendor’s own site, a store listing it controls, or the platform maker’s own documentation. None is an independent party, so these are vendor-origin claims that code has confirmed the pages really make.';
}
function closeChain() {
  $('#chainSec').hidden = true;
  if (/#chain=/.test(location.hash)) history.replaceState(null, '', S.tool ? `#app=${addr(S.tool)}` : here());
  if (chainOpener) {
    chainOpener.focus();
    chainOpener = null;
  }
}

export function mount() {
  for (const ev of ['pointerover', 'focusin'])
    document.addEventListener(
      ev,
      e => {
        if (!CH && e.target.closest && e.target.closest('[data-chain]')) chainData().catch(() => {});
      },
      { passive: true }
    );
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-chain]');
    if (b) {
      openChain(b.dataset.chain, b);
      return;
    }
    if (e.target.closest('#chainX')) closeChain();
    const c = e.target.closest('[data-compare]');
    if (c) withCompare(m => m.openCompare([c.dataset.compare], c));
  });
  addEventListener('keydown', e => {
    if (e.key === 'Escape' && !$('#chainSec').hidden) closeChain();
  });
  addEventListener('hashchange', () => {
    const m = /[#&]chain=([\w.-]+)/.exec(location.hash);
    if (m) openChain(m[1]);
    else if (!$('#chainSec').hidden) $('#chainSec').hidden = true;
    if (cmp || CMP.test(location.hash)) withCompare(m => m.sync());
  });
  if (CMP.test(location.hash)) withCompare(m => m.sync());
}
