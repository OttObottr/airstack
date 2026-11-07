// spec: AS-120 AS-256 AS-260
import { mount as mountRouter } from './lib/router.js';
import * as mapView from './components/market-map.js';
import * as insightsView from './components/insights.js';
import * as calendarView from './components/calendar.js';
import * as methodView from './components/method.js';
import * as makersView from './components/makers.js';

import { mount as m0 } from './components/hero.js';
import { mount as m1 } from './lib/market.js';
import { mount as m2 } from './components/answer/needs.js';
import { mount as m3 } from './components/answer/coverage-map.js';
import { mount as m4 } from './components/chain.js';
import { mount as m5 } from './components/movers.js';
import { mount as mountNews } from './components/news.js';
import { mount as mountStack } from './components/stack.js';
import { mount as m6 } from './components/brief.js';
import { mount as m7 } from './components/search/index.js';
import { mount as m8 } from './components/browse.js';
import { mount as m9 } from './components/replay.js';
import { mount as m10 } from './components/record.js';
import { mount as mountKeys } from './components/keys.js';
import './lib/data.js';
import './lib/dom.js';
import './lib/format.js';
import './components/chips.js';
import './lib/profiles.js';
import './components/prices.js';
import './components/answer/model.js';
import './components/answer/answer.js';
import './components/profile.js';
import './components/market-table.js';
import './components/search/directory.js';
import './components/app.js';
import './components/avatar.js';
import './components/cards/catalog.js';
import './components/cards/directory.js';
import './components/cards/tool.js';

import { selectTool } from './components/app.js';
import { byId, byName } from './components/search/index.js';

/* each component has its own boundary: malformed or missing data in one view does not stop the rest of the app */
const start = mount => {
  try {
    mount();
  } catch (e) {
    console.error('AirStack: a component failed to start', e);
  }
};

/* views below the first screen start the first time they are opened: start-up runs Overview only */
const LAZY = { markets: mapView, insights: insightsView, calendar: calendarView, makers: makersView, how: methodView };
const opened = new Set();

/* start-up, in the order the page has always run it, a few components per task: the modules run after first paint, so no one task may hold
   the main thread long enough to delay a tap. The first group runs at once (lib/market.js listens for the page's load event). The search list, the
   components after it and the router start together, last, so the page is whole when the list appears; the router last of all, so a deep
   link opens on the view that holds it. */
const GROUPS = [
  [m0, m1, m2, m3, m4], // components/hero.js, lib/market.js, components/answer/needs.js, components/answer/coverage-map.js, components/chain.js
  [m5], // components/movers.js
  [mountNews, mountStack, m6], // components/news.js, components/stack.js, components/brief.js
  [
    m7,
    m8,
    m9,
    m10,
    mountKeys, // components/keys.js
    () => {
      // components/search/index.js, components/browse.js, components/replay.js (it also wires the copy buttons and steps on Overview)
      addEventListener('airstack:view', e => {
        const v = e.detail;
        if (LAZY[v] && !opened.has(v)) {
          opened.add(v);
          start(LAZY[v].mount);
        }
      });
      start(mountRouter); // lib/router.js
      window.__airstack = { selectTool, byId, byName }; // the three functions the interaction-budget journey times (JOURNEY/test_journeys.py); nothing else is on window
    },
  ],
];
const run = i => {
  GROUPS[i].forEach(start);
  if (i + 1 < GROUPS.length) setTimeout(run, 0, i + 1);
};
run(0);

if (
  'serviceWorker' in navigator &&
  (location.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(location.hostname))
)
  addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
