import { researchedFacts } from './search/directory.js';
import { esc, host } from '../lib/format.js';
import { MK } from '../lib/market.js';

/* the hue comes from the website or name, so a product looks the same everywhere */
export const mono = (x, sz = '', k = '') => {
  const nm = String(x.name || '')
      .replace(/[^\p{L}\p{N} ]/gu, ' ')
      .trim(),
    w = nm.split(/\s+/).filter(Boolean);
  const ini = (w.length > 1 ? w[0][0] + w[1][0] : (w[0] || '?')[0]).toUpperCase(),
    key = (
      host(x.site || x.homepage || ((MK && MK.catalog && MK.catalog[x.id]) || {}).homepage || '') || nm
    ).toLowerCase();
  let h = 2166136261;
  for (const c of key) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return `<i class="av${sz ? ' ' + sz : ''}" style="--h:${((h >>> 0) % 12) * 30 + 15}"${k ? ` data-k="${k}"` : ''} data-i="${esc(ini)}" aria-hidden="true"></i>`;
};
export const kindOf = x => (x.org ? 'org' : researchedFacts(x) ? 'res' : '');
