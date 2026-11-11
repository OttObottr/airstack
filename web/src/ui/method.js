/* How a panel's figures are measured: kept one click away, so the panel shows the reading and not its fine print. */
export const Method = (body, label = 'How this is measured') =>
  `<details><summary class="cursor-pointer text-xs text-subtle-foreground hover:text-foreground">${label}</summary><div class="mt-2 max-w-prose text-xs leading-snug text-muted-foreground">${body}</div></details>`;
