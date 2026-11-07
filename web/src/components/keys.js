// spec: AS-256 AS-341
/* ---------- keyboard: `/` or Cmd/Ctrl-K opens the palette (loaded on first use, never at start-up); `j` and `k` move through a list ---------- */
const typing = () => {
  const a = document.activeElement;
  return !!a && (/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName) || a.isContentEditable);
};
/* the lists j and k walk: each row, and the container that holds its list */
const ROWS = '#trend [data-pick], #mvt tbody tr, #mkList tr, #newsList li, #calAhead li, #stackList li';
const LISTS = '#trend, #mvt, #mkList, #newsList, #calAhead, #stackList';
const visible = el => el.offsetParent !== null; /* a hidden view's rows have no box */

export function step(dir) {
  const here = document.activeElement && document.activeElement.closest(ROWS),
    box = here ? here.closest(LISTS) : null,
    rows = [...(box || document).querySelectorAll(ROWS)].filter(visible);
  if (!rows.length) return false;
  const i = here ? rows.indexOf(here) : -1,
    to = rows[Math.min(rows.length - 1, Math.max(0, i + dir))];
  const el = to.matches('a,button') ? to : to.querySelector('a[href],button') || to;
  if (el === to && !to.matches('a,button')) to.tabIndex = -1;
  el.focus();
  return true;
}

export function mount() {
  addEventListener('keydown', e => {
    if (e.defaultPrevented || document.querySelector('dialog[open]')) return;
    const mod = e.metaKey || e.ctrlKey;
    if (mod && !e.altKey && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      import('./palette.js').then(p => p.open());
    } else if (!mod && !e.altKey && !typing()) {
      if (e.key === '/') {
        e.preventDefault();
        import('./palette.js').then(p => p.open());
      } else if (e.key === 'j' || e.key === 'k') step(e.key === 'j' ? 1 : -1);
    }
  });
}
