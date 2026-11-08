import { VIEW } from './view.js';
export const M = window.AIRSTACK_DATA;
if (!M) {
  document.body.insertAdjacentHTML(
    'afterbegin',
    '<p class="fail">Data failed to load. Reload the page.</p>'
  );
  throw new Error('site-data.js missing');
}
export const X = M.execution;
/* the windows each file was built with, as it publishes them: copy quotes these, never numbers of its own */
export const PARAMS = { movers: (M.moversTop && M.moversTop.params) || {}, attention: {}, view: VIEW };
const param = path => {
  const [f, k] = path.split('.');
  return (PARAMS[f] || {})[k];
};
/* static copy: <span data-p="movers.base_weeks"></span> and data-aria="… {movers.base_weeks}-week …" */
export function fillParams(root = document) {
  for (const el of root.querySelectorAll('[data-p]')) if (param(el.dataset.p) != null) el.textContent = param(el.dataset.p);
  for (const el of root.querySelectorAll('[data-aria]'))
    el.setAttribute('aria-label', el.dataset.aria.replace(/\{([\w.]+)\}/g, (m, p) => param(p) ?? m));
}
/* the one set of headline counts every view quotes */
const D0 = M.dir || {};
export const COUNTS = (M.meta && M.meta.counts) || {
  products: M.index.length + (D0.products || 0),
  organizations: D0.orgs || 0,
  researched_products: D0.researched || 0,
};
/* one request per file, shared by Home and the full views; a failure can be retried */
const got = {};
export const json = f =>
  (got[f] ||= fetch(f)
    .then(r => (r.ok ? r.json() : Promise.reject(new Error(`${f}: ${r.status}`))))
    .catch(e => {
      delete got[f];
      throw e;
    }));
