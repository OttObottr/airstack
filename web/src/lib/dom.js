// spec: AS-256 AS-343
export const $ = (s, r = document) => r.querySelector(s),
  $$ = (s, r = document) => [...r.querySelectorAll(s)];
export const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
export const sr = t => {
  $('#sr').textContent = t;
};
