/* Home: the pulse and the sector panels, mounted when Home first opens; Top stories and the feed come from news.js. */
import { $ } from '../lib/dom.js';
import { mountScoped, wire } from '../lib/scope.js';
import { mount as mountPanel } from '../ui/panel.js';
import { panel as pulse, sectorPanel } from './pulse.js';
import { mount as mountMap } from './treemap.js';

export function mount() {
  wire();
  let charts = false;
  addEventListener('airstack:view', e => {
    if (!charts && e.detail === 'overview') {
      charts = true;
      mountScoped($('#pulsePanel'), pulse);
      mountPanel($('#sectorsHome'), sectorPanel);
      mountMap($('#weekMap'));
    }
  });
}
