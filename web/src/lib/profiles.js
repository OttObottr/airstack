// spec: AS-137 AS-250 AS-251 AS-256 AS-366
import { profileView } from '../components/profile.js';

/* the market (market-data.js, deferred); until it loads, Google only */
/* the facts in each profile (profiles.json) load with the first product page that shows them; market-data.js carries only their counts */
export let PROF = null;
let PROFP = null,
  PROFERR = false;
export let PRICES = {},
  OSS = null,
  GUIDES = null,
  HF = null,
  COMMUNITY = null,
  NEWS = null; /* public channel records and the retained update feed load with product intelligence */
/* list prices as written on each product's pricing page, each with its quote (pricing.json) */
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
/* only the list prices: the comparison needs these and not the 4 MB of profiles */
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
