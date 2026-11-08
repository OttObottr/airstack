import { renderAll } from '../components/app.js';
import { openChain } from '../components/chain.js';
import { renderMovers } from '../components/movers.js';
import { PENDING } from '../components/search/index.js';
import { $ } from './dom.js';
import { fillBase } from './spark.js';

export let MK = null,
  MKERR = false;

export function mount() {
  /* the market file is large: it loads for a view or deep link that needs it, on first interaction, or after a few seconds */
  let started = false;
  const load = () => {
    if (started) return;
    started = true;
    const el = document.createElement('script');
    el.src = 'market-data.js';
    el.onload = () => {
      MK = window.AIRSTACK_MARKET || null;
      if (MK && MK.movers) fillBase(MK.movers.rows);
      renderAll();
      PENDING.splice(0).forEach(f => f());
      renderMovers();
      const m = /[#&]chain=([\w.-]+)/.exec(location.hash);
      if (m) openChain(m[1]);
    };
    el.onerror = () => {
      MKERR = true;
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
