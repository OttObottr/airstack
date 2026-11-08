import { profileView } from '../components/profile.js';

export let PROF = null;
let PROFP = null,
  PROFERR = false;
export let PRICES = {},
  OSS = null,
  GUIDES = null,
  HF = null,
  TAX = null,
  COMMUNITY = null,
  NEWS = null;
let TAXP = null;
export const loadTaxonomy = () =>
  TAXP ||
  (TAXP = fetch('taxonomy-index.json')
    .then(r => {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    })
    .then(T => (TAX = T)));
const loadProfiles = () =>
  PROFP ||
  (PROFP = Promise.all([
    fetch('profiles.json').then(r => {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }),
    fetch('pricing.json')
      .then(r => (r.ok ? r.json() : {}))
      .catch(() => ({})),
    fetch('oss.json')
      .then(r => (r.ok ? r.json() : null))
      .catch(() => null),
    fetch('category-guides.json')
      .then(r => (r.ok ? r.json() : null))
      .catch(() => null),
    fetch('hf.json')
      .then(r => (r.ok ? r.json() : null))
      .catch(() => null),
    fetch('community.json')
      .then(r => (r.ok ? r.json() : null))
      .catch(() => null),
    fetch('news.json')
      .then(r => (r.ok ? r.json() : null))
      .catch(() => null),
    loadTaxonomy(),
  ])
    .then(([P, Q, O, G, H, C, N]) => {
      PROF = P;
      PRICES = Q;
      OSS = O;
      GUIDES = G;
      HF = H;
      COMMUNITY = C;
      NEWS = N;
    })
    .catch(e => {
      PROFP = null;
      PROFERR = true;
      throw e;
    }));
/* the comparison needs only the prices, not every profile */
let PRICEP = null;
export const loadPrices = () =>
  PRICEP ||
  (PRICEP = fetch('pricing.json')
    .then(r => (r.ok ? r.json() : {}))
    .catch(() => ({}))
    .then(Q => {
      if (!Object.keys(PRICES).length) PRICES = Q;
    }));
export const pview = (r, id, redo) => {
  if (PROF) return PROF[id] ? profileView(r, PROF[id]) : '';
  if (PROFERR) return '<p class="meta">These facts could not be loaded. Check your connection and reload.</p>';
  loadProfiles().then(redo, redo);
  return '<p class="meta">Loading what its own pages say…</p>';
};
