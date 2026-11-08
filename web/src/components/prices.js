import { esc, fd, host, ic, nobs, url } from '../lib/format.js';
import { PRICES } from '../lib/profiles.js';

export const per = p =>
  `${p.unit === 'user' ? ' per user' : p.unit === 'usage' ? ' per unit' : ''}${p.period === 'month' ? ' / month' : p.period === 'year' ? ' / year' : p.period === 'one-time' ? ' once' : ''}`;
export const amt = p => (typeof p.amount === 'number' ? p.amount : Infinity);
const priceLink = (Q, p) =>
  `<a class="ext" href="${url(Q.url)}" target="_blank" rel="noopener noreferrer" title="“${esc(p.quote)}”">${esc(p.price)}${ic('out')}</a><span class="meta">${per(p)}</span>`;
export function priceView(x) {
  const Q = PRICES[x.id];
  if (!Q || !Q.plans.length) return '';
  return `<h3 class="h2 mt48">Plans and list prices</h3><p class="meta">As written on ${esc(host(Q.url))}, read ${fd(Q.checked)}. Each price’s quote is on that page (hover a price to read it). Prices change: check before you buy.</p>
    <div class="scroll mt16"><table class="t prices"><thead><tr><th scope="col">Plan</th><th scope="col">List price</th></tr></thead><tbody>${Q.plans.map(p => `<tr><td>${esc(p.plan)}</td><td>${priceLink(Q, p)}</td></tr>`).join('')}</tbody></table></div>`;
}
export const startAt = id => {
  const Q = PRICES[id];
  if (!Q || !Q.plans.length) return nobs;
  const paid = Q.plans.filter(p => amt(p) > 0).sort((a, b) => amt(a) - amt(b));
  const free = Q.plans.some(p => amt(p) === 0);
  return `${free ? '<span class="meta">Free · </span>' : ''}${paid.length ? priceLink(Q, paid[0]) : ''}` || nobs;
};
