import { M } from '../lib/data.js';
import { esc, fd, ic, url } from '../lib/format.js';
import { ui } from '../ui/recipes.js';
import { STR, chainData, chainNow, checks, says } from './chain.js';

const srcs = c => {
  const x = c.sources[0],
    more = c.sources.length - 1;
  return `<a class="src" href="${url(x.url)}" target="_blank" rel="noopener noreferrer" aria-label="Source: ${esc(x.host)}, checked ${fd(x.checked)}">${ic('out')}</a>${
    more
      ? `<span class="src" title="${esc(
          c.sources
            .slice(1)
            .map(s => s.host)
            .join(', ')
        )}">+${more}</span>`
      : ''
  }`;
};
const PF = M.labels;
let asked = false;
export function profileView(r, p, redo) {
  const D = chainNow();
  if (!D && !asked && redo) {
    asked = true;
    chainData().then(redo, () => {});
  }
  const val = c => (Array.isArray(c.value) ? c.value.join(', ') : c.value === true ? 'Yes' : String(c.value));
  /* each value with the vendor's own words behind it, once the evidence has loaded */
  const quotes = (k, l) =>
    ((D && D.entities[r.id] && D.entities[r.id].facts) || [])
      .filter(f => f.metric === k)
      .slice(0, 2)
      .map(f => `<div class="${ui.panelNote} mt-1">${says(r.name, f)}</div><div class="mt-1">${checks(r.name, l, f)}</div>`)
      .join('');
  const rows = PF.filter(([k]) => p[k])
    .map(([k, l]) => {
      const q = quotes(k, l); /* where the value is the page's own words, the attributed quote alone says it */
      return `<div><dt>${l}</dt><dd>${q && STR.has(k) ? '' : esc(val(p[k]))}${q || srcs(p[k])}</dd></div>`;
    })
    .join('');
  const missing = PF.filter(([k]) => !p[k]).map(([, l]) => l.toLowerCase());
  return `<dl class="kv">${rows}${missing.length ? `<div><dt>Not observed</dt><dd><details class="nobsd"><summary class="nobs">${missing.length} field${missing.length > 1 ? 's' : ''} not on the pages read</summary><span class="nobs">${esc(missing.join(', '))}</span></details></dd></div>` : ''}</dl><p class="mt8 meta">Vendor statements, quoted and dated; not verified by AirStack. Check with the vendor. “Not observed” means the pages read didn’t say.</p><button class="ext" type="button" data-chain="${esc(r.id)}">Evidence chain · ${p.facts} facts</button>`;
}
