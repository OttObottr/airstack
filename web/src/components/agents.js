import { X } from '../lib/data.js';
import { $, copy } from '../lib/dom.js';

export function mount() {
  if (!$('#agents')) return;
  $('#agTools').textContent = X.mcp.tools.map(t => t.replace(/_/g, ' ')).join(', ');
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-copy]');
    if (button) copy(button, $(button.dataset.copy).textContent, { select: button.dataset.copy });
  });
}
