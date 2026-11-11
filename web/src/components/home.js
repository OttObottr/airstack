/* Home: the pulse, the front page, what is coming up and the leading category insights, each a panel mounted when Home first opens. */
import { $ } from '../lib/dom.js';
import { mountScoped, wire } from '../lib/scope.js';
import { mount as mountPanel } from '../ui/panel.js';
import { panel as pulse, sectorPanel } from './pulse.js';
import { mount as mountFront } from './front.js';

export function mount() {
  wire();
  let charts = false,
    front = false;
  addEventListener('airstack:view', e => {
    if (!charts && ['overview', 'calendar'].includes(e.detail)) {
      charts = true; /* the year at a glance leads both Home and Calendar */
      mountScoped($('#pulsePanel'), pulse);
      mountPanel($('#sectorsHome'), sectorPanel);
    }
    if (front || e.detail !== 'overview') return;
    front = true;
    mountFront($('#front'));
  });
}
