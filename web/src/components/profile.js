import { M } from '../lib/data.js';
import { esc, fd, ic, tip, url } from '../lib/format.js';
import { chainData, chainNow, checks } from './chain.js';

const srcs = c => {
  const x = c.sources[0],
    more = c.sources.length - 1;
  return `<a class="src" href="${url(x.url)}" target="_blank" rel="noopener noreferrer" aria-label="Source: ${esc(x.host)}, checked ${fd(x.checked)}">${ic('out')}</a>${
    more
      ? `<span class="src">${tip(`+${more}`, `also on ${c.sources.slice(1).map(s => s.host).join(', ')}`)}</span>`
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
  /* each value with a footnote to the page that states it */
  const foot = (k, l) =>
    ((D && D.entities[r.id] && D.entities[r.id].facts) || [])
      .filter(f => f.metric === k)
      .slice(0, 2)
      .map(f => checks(r.name, l, f))
      .join(' ');
  const rows = PF.filter(([k]) => p[k])
    .map(([k, l]) => `<div><dt>${l}</dt><dd>${esc(val(p[k]))} ${foot(k, l) || srcs(p[k])}</dd></div>`)
    .join('');
  return `<dl class="kv">${rows}</dl><p class="mt-2 meta">Vendor statements, quoted and dated; not verified by AirStack. Check with the vendor.</p>`;
}
