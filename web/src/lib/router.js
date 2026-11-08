export const VIEWS = {
  overview: 'Overview',
  compare: 'Compare',
  markets: 'Markets',
  insights: 'Insights',
  calendar: 'Calendar',
  makers: 'Makers',
  agents: 'Agents',
};
const TITLE = 'AirStack · See the software market move';
let view = null;

function viewOf(hash) {
  const h = hash || '';
  const m = /^#\/([a-z]*)/.exec(h);
  if (m) return VIEWS[m[1]] ? m[1] : 'overview';
  if (/^#compare=/.test(h)) return 'compare';
  if (/[#&](app|q|stack)=/.test(h)) return 'overview';
  if (/[#&]tool=/.test(h)) return 'markets';
  if (/[#&]chain=/.test(h)) return null; /* the chain opens over whatever view you are on */
  return /^#[\w-]+$/.test(h) ? null : 'overview';
}

export function show(v, { scroll = true } = {}) {
  if (!VIEWS[v] || v === view) return; /* selecting a tool calls this every time */
  const was = view;
  view = v;
  document.body.dataset.view = v;
  for (const s of document.querySelectorAll('[data-views]'))
    s.classList.toggle('view-away', !s.dataset.views.split(' ').includes(v));
  let active = null;
  for (const a of document.querySelectorAll('.nav a[data-view]')) {
    if (a.dataset.view === v) {
      a.setAttribute('aria-current', 'page');
      active = a;
    } else a.removeAttribute('aria-current');
  }
  /* scroll the current tab into view only when an edge hides it */
  if (active)
    requestAnimationFrame(() => {
      const nav = active.closest('.nav'),
        FADE = 28,
        n = nav.getBoundingClientRect(),
        a = active.getBoundingClientRect();
      if (a.left < n.left + FADE) nav.scrollLeft -= n.left + FADE - a.left;
      else if (a.right > n.right - FADE) nav.scrollLeft += a.right - (n.right - FADE);
    });
  document.title = v === 'overview' ? TITLE : `${VIEWS[v]} · ${TITLE}`;
  if (was) {
    const top = document.querySelector('[data-views]:not(.view-away)');
    if (top) {
      top.classList.remove('view-enter');
      requestAnimationFrame(() => !top.classList.contains('view-away') && top.classList.add('view-enter'));
    }
  }
  if (scroll) scrollTo(0, 0);
  dispatchEvent(new CustomEvent('airstack:view', { detail: v })); /* views drawn while hidden (canvas, treemap) redraw at their real size */
}

export const here = () =>
  view && view !== 'overview' ? `#/${view}` : location.pathname + location.search;

export function mount() {
  const go = () => {
    const v = viewOf(location.hash);
    if (v) show(v);
  };
  addEventListener('hashchange', go);
  go();
  if (!view) show('overview', { scroll: false });
}
