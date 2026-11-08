export const M = window.AIRSTACK_DATA;
if (!M) {
  document.body.insertAdjacentHTML(
    'afterbegin',
    '<p class="fail">Data failed to load. Reload the page.</p>'
  );
  throw new Error('site-data.js missing');
}
export const X = M.execution;
/* one request per file, shared by Home and the full views; a failure can be retried */
const got = {};
export const json = f =>
  (got[f] ||= fetch(f)
    .then(r => (r.ok ? r.json() : Promise.reject(new Error(`${f}: ${r.status}`))))
    .catch(e => {
      delete got[f];
      throw e;
    }));
