export const $ = (s, r = document) => r.querySelector(s),
  $$ = (s, r = document) => [...r.querySelectorAll(s)];
export const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
export const sr = t => {
  $('#sr').textContent = t;
};
/* where the clipboard is refused, the `select` element is selected for copying by hand */
export async function copy(button, text, { ok = 'Copied', fail = 'Copy failed', select } = {}) {
  const was = button.textContent,
    node = select && $(select);
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = ok;
    sr(ok);
  } catch {
    if (node) {
      const range = document.createRange();
      range.selectNodeContents(node);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
    }
    button.textContent = node ? 'Selected: press Ctrl or Cmd+C' : fail;
    sr(button.textContent);
  }
  setTimeout(() => button.isConnected && (button.textContent = was), 1600);
}
