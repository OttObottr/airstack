/* How widely linked a product's own site is (reach.json: the Majestic Million, CC BY 3.0), and the year it began (markets.json,
   Wikidata): the two readings that say how big and how old a listed product is. Loaded once; absent data shows nothing. */
import { json } from './data.js';
import { esc, tip, url } from './format.js';

let R = null,
  B = null,
  asked = null;
/* resolves when both files have been tried, so a caller can draw again */
export const loadScale = () =>
  (asked ||= Promise.all([json('reach.json').then(d => (R = d), () => {}), json('markets.json').then(d => (B = d.products), () => {})]));
const BAND = [
  [1e3, 'Top 1,000'],
  [1e4, 'Top 10,000'],
  [1e5, 'Top 100,000'],
  [1e6, 'Top million'],
];
export const rankOf = id => (R && R.products[id] ? R.products[id][0] : null);
/* "Top 10,000" with the domain it is the rank of, or '' */
export const reach = id => {
  const r = R && R.products[id];
  return r ? tip(BAND.find(b => r[0] <= b[0])[1], `${r[1]} is no. ${r[0].toLocaleString('en')} of the million most-linked domains (Majestic Million, CC BY 3.0)`) : '';
};
export const since = id => (B && B[id] && B[id][2]) || null;
export const reachCredit = () =>
  R && R.source.read
    ? `Site reach: the product’s own domain among the million most-linked domains, <a class="ext" href="${url(R.source.url)}" target="_blank" rel="noopener noreferrer">Majestic Million</a> (CC BY 3.0), read ${esc(R.source.read)}. Since: the year Wikidata records it began.`
    : '';
