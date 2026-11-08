export const M = window.AIRSTACK_DATA;
if (!M) {
  document.body.insertAdjacentHTML(
    'afterbegin',
    '<p class="fail">Data failed to load. Reload the page.</p>'
  );
  throw new Error('site-data.js missing');
}
export const X = M.execution;
