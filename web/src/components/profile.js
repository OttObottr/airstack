import { M } from '../lib/data.js';
import { esc, fd, ic, url } from '../lib/format.js';

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
export function profileView(r, p) {
  const val = c => (Array.isArray(c.value) ? c.value.join(', ') : c.value === true ? 'Yes' : String(c.value));
  const rows = PF.filter(([k]) => p[k])
    .map(([k, l]) => `<div><dt>${l}</dt><dd>${esc(val(p[k]))}${srcs(p[k])}</dd></div>`)
    .join('');
  const missing = PF.filter(([k]) => !p[k]).map(([, l]) => l.toLowerCase());
  return `<dl class="kv">${rows}${missing.length ? `<div><dt>Not observed</dt><dd><details class="nobsd"><summary class="nobs">${missing.length} field${missing.length > 1 ? 's' : ''} not on the pages read</summary><span class="nobs">${esc(missing.join(', '))}</span></details></dd></div>` : ''}</dl><p class="mt8 meta">${p.facts} facts extracted from ${esc(r.name)}’s own pages; each quote found on its page. “Not observed” means the pages read didn’t say.</p><button class="ext" type="button" data-chain="${esc(r.id)}">Evidence chain · ${p.facts} facts</button>`;
}
