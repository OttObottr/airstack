import { researchedFacts } from './search/directory.js';
import { esc, host } from '../lib/format.js';
import { MK } from '../lib/market.js';

/* licensed logos (logos.json: id -> logos/<hash>.png, Wikimedia Commons; credits at /legal/logos.html), shown in place of initials
   once loaded; avatars drawn before then are filled in */
let LOGO = null;
const NAMED = /^logos\/[0-9a-f]{16}\.(png|jpg)$/;
const logoOf = id => (LOGO && id && NAMED.test(LOGO[id] || '') ? LOGO[id] : '');
fetch('logos.json')
  .then(r => (r.ok ? r.json() : null))
  .then(j => {
    if (!j || !j.logos) return;
    LOGO = j.logos;
    for (const el of document.querySelectorAll('i.av[data-id]')) {
      const p = logoOf(el.dataset.id);
      if (p) el.classList.add('lg'), (el.style.backgroundImage = `url(${p})`);
    }
  })
  .catch(() => {});

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
  const logo = logoOf(x.id);
  return `<i class="av${sz ? ' ' + sz : ''}${logo ? ' lg' : ''}" style="--h:${((h >>> 0) % 12) * 30 + 15}${logo ? `;background-image:url(${logo})` : ''}"${x.id ? ` data-id="${esc(x.id)}"` : ''}${k ? ` data-k="${k}"` : ''} data-i="${esc(ini)}" aria-hidden="true"></i>`;
};
export const kindOf = x => (x.org ? 'org' : researchedFacts(x) ? 'res' : '');
