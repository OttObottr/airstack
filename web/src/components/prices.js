import { M } from '../lib/data.js';
import { esc, fd, host, url } from '../lib/format.js';
import { PRICES } from '../lib/profiles.js';
import { ui } from '../ui/recipes.js';

export const per = p =>
  `${p.unit === 'user' ? ' per user' : p.unit === 'usage' ? ' per unit' : ''}${p.period === 'month' ? ' / month' : p.period === 'year' ? ' / year' : p.period === 'one-time' ? ' once' : ''}`;
/* a list price is shown only while its last read is within the published policy's age */
export const listed = id => {
  const Q = PRICES[id],
    days = M.policy && M.policy.price_max_age_days;
  return Q && Q.plans.length && (!days || Date.now() - Date.parse(Q.checked) <= days * 864e5) ? Q : null;
};
export function priceView(x) {
  const Q = listed(x.id);
  if (!Q) return '';
  return `<h3 class="h-section mt-12">Plans and list prices</h3><p class="meta">Listed on ${fd(Q.checked)} on <a class="ext" href="${url(Q.url)}" target="_blank" rel="noopener noreferrer">${esc(host(Q.url))}</a>. Prices change: check with the vendor.</p>
    <div class="mt-4 max-w-2xl overflow-x-auto rounded-lg border border-border bg-card"><table class="tbl"><thead><tr><th scope="col">Plan</th><th scope="col">List price</th></tr></thead><tbody>${Q.plans
      .map(p => `<tr><td>${esc(p.plan)}</td><td>${esc(p.price)}<span class="meta">${per(p)}</span><div class="${ui.panelNote} mt-1 whitespace-normal">The pricing page says: “${esc(p.quote)}”</div></td></tr>`)
      .join('')}</tbody></table></div>`;
}
