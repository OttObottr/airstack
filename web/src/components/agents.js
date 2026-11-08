import { X } from '../lib/data.js';
import { $, copy } from '../lib/dom.js';
import { fd, n } from '../lib/format.js';

export function mount() {
  const agent = $('#agents');
  if (!agent) return;
  const tools = X.mcp.tools;
  $('#agScope').textContent = `Scope: ${n(tools.length)} reviewed tools · snapshot verified ${fd(X.mcp.as_of)} · clone, start locally, then ask in plain language.`;
  $('#agToolSummary').textContent = `Tools · ${n(tools.length)}`;
  $('#agTools').textContent = tools.join(', ');
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-copy]');
    if (button) copy(button, $(button.dataset.copy).textContent, { select: button.dataset.copy });
  });
}
