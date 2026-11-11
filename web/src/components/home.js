/* Home: the pulse, the front page, what is coming up and the leading category insights, each a panel mounted when Home first opens. */
import { $ } from '../lib/dom.js';
import { mountScoped, wire } from '../lib/scope.js';
import { mount as mountPanel } from '../ui/panel.js';
import { panel as pulse, sectorPanel } from './pulse.js';
import { briefPanel as agenda } from './calendar.js';
import { briefPanel as findings } from './findings.js';
import { mount as mountFront } from './front.js';

export function mount() {
  wire();
  let done = false;
  addEventListener('airstack:view', e => {
    if (done || e.detail !== 'overview') return;
    done = true;
    mountScoped($('#pulsePanel'), pulse);
    mountPanel($('#sectorsHome'), sectorPanel);
    mountFront($('#front'));
    mountPanel($('#upHome'), agenda);
    mountPanel($('#insHome'), findings);
  });
}
