// spec: AS-256 AS-328
import { renderAll } from '../components/app.js';
import { openChain } from '../components/chain.js';
import { renderMarket } from '../components/market-table.js';
import { renderMovers } from '../components/movers.js';
import { PENDING } from '../components/search/index.js';
import { $ } from './dom.js';

/* ---------- check yours: a lookup into answers precomputed from the database; no request, no model call ---------- */
export let MK = null,
  MKERR = false;

export function mount() {
  /* The market file is large and only the lookups and the Markets view need it, so it waits: it loads at once for a deep link or a view that
     needs it, otherwise on the first interaction, or after a few seconds. The first screen never competes with it, on any phone. */
  let started = false;
  const load = () => {
    if (started) return;
    started = true;
    const el = document.createElement('script');
    el.src = 'market-data.js';
    el.onload = () => {
      MK = window.AIRSTACK_MARKET || null;
      renderAll();
      PENDING.splice(0).forEach(f => f());
      renderMarket();
      renderMovers();
      const m = /[#&]chain=([\w.-]+)/.exec(location.hash);
      if (m) openChain(m[1]);
    };
    el.onerror = () => {
      MKERR = true;
      $('#market').hidden = true;
      $('#movers').hidden = true;
      renderAll();
    };
    document.body.append(el);
  };
  if (/[#&](app|chain|tool|stack|q)=|^#\/(?!$)/.test(location.hash)) addEventListener('load', load);
  else {
    for (const type of ['pointerdown', 'keydown', 'focusin', 'hashchange', 'scroll'])
      addEventListener(type, load, { once: true, passive: true });
    setTimeout(load, 9000);
  }
}
