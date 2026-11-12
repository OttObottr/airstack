/* How a panel's figures are measured: kept one click away, so the panel shows the reading and not its fine print. */
export const Method = (body, label = 'How this is measured') =>
  `<details class="inline-block"><summary class="inline-flex size-5 cursor-pointer list-none items-center justify-center rounded-full border border-border text-[11px] font-semibold leading-none text-subtle-foreground hover:text-foreground" aria-label="${label}" title="${label}">i</summary><div class="mt-2 max-w-prose text-xs leading-snug text-muted-foreground">${body}</div></details>`;
