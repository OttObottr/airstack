/* Home: the pulse, what is coming up and the leading category insights, each a workspace panel mounted when Home first opens. */
import { $ } from '../lib/dom.js';
import { mountScoped, wire } from '../lib/scope.js';
import { mount as mountPanel } from '../ui/panel.js';
import { panel as pulse } from './pulse.js';
import { briefPanel as agenda } from './calendar.js';
import { briefPanel as findings } from './findings.js';

export function mount() {
  wire();
  let done = false;
  addEventListener('airstack:view', e => {
    if (done || !['overview', 'calendar'].includes(e.detail)) return;
    done = true;
    mountScoped($('#pulsePanel'), pulse);
    mountPanel($('#upHome'), agenda);
    mountPanel($('#insHome'), findings);
  });
}
