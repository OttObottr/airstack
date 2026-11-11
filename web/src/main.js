import { mount as mountRouter } from './lib/router.js';
import { mount as mountHero } from './components/hero.js';
import { mount as mountMarket } from './lib/market.js';
import { mount as mountChain } from './components/chain.js';
import { mount as mountNews } from './components/news.js';
import { mount as mountStack } from './components/stack.js';
import { mount as mountSearch } from './components/search/index.js';
import { mount as mountBrowse } from './components/browse.js';
import { mount as mountHome } from './components/home.js';
import { mount as mountAgents } from './components/agents.js';
import { mount as mountKeys } from './components/keys.js';
import { mount as mountRail } from './components/rail.js';
import { mount as mountBeacon } from './lib/beacon.js';
import { stack } from './lib/stack.js';
import { fillParams } from './lib/data.js';

fillParams(); /* static copy quotes the windows the data was built with */

/* one view's bad data does not stop the rest */
const start = mount => {
  try {
    mount();
  } catch (e) {
    console.error('AirStack: a component failed to start', e);
  }
};

const LAZY = {
  markets: () => import('./components/markets/index.js'),
  insights: () => import('./components/insights.js'),
  calendar: () => import('./components/calendar.js'),
  makers: () => import('./components/makers.js'),
};
const opened = new Set();
const lazy = () =>
  addEventListener('airstack:view', ({ detail: v }) => {
    if (!LAZY[v] || opened.has(v)) return;
    opened.add(v);
    LAZY[v]().then(m => start(m.mount)).catch(e => console.error(`AirStack: ${v} failed to load`, e));
  });

/* a few components per task keeps taps responsive; search opens a deep-linked product, so it starts after every view listener, then the router */
const GROUPS = [
  [mountHero, mountMarket, mountChain],
  [mountNews, mountStack, mountRail],
  [mountBrowse, mountHome, mountAgents, mountKeys, lazy, () => mountBeacon(() => stack().length), mountSearch, mountRouter],
];
const run = i => {
  GROUPS[i].forEach(start);
  if (i + 1 < GROUPS.length) setTimeout(run, 0, i + 1);
};
run(0);

if ('serviceWorker' in navigator && (location.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(location.hostname)))
  addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
