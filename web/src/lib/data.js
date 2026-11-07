// spec: AS-131 AS-256
export const M = window.AIRSTACK_DATA;
if (!M) {
  document.body.insertAdjacentHTML(
    'afterbegin',
    '<p class="fail">site-data.js did not load. Run backend/tools/build_site_data.py.</p>'
  );
  throw new Error('site-data.js missing');
}
export const LIVE = M.meta.live,
  MODEL = M.meta.model,
  X = M.execution;
