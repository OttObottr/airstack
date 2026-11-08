/* Class recipes: every panel, chip, button, table and tile on the site uses these complete strings, so the compiled CSS
   finds them and every instance looks the same. Variants are lookups, never built from parts at runtime. */
export const ui = {
  panel: 'flex flex-col gap-4 rounded-lg border border-border bg-card p-4',
  panelHead: 'flex items-center justify-between gap-3 min-h-8',
  panelTitle: 'text-sm font-semibold text-foreground leading-none',
  panelNote: 'text-xs text-muted-foreground leading-snug',
  meta: 'text-xs text-muted-foreground leading-none',
  num: 'font-mono tabular-nums',
  chip: {
    base: 'inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full border border-border text-xs leading-none text-muted-foreground hover:text-foreground aria-pressed:bg-muted aria-pressed:text-foreground',
    quiet: 'inline-flex items-center gap-1.5 h-6 px-2 rounded-full bg-muted text-xs leading-none text-muted-foreground',
  },
  badge: {
    neutral: 'inline-flex items-center h-5 px-1.5 rounded-sm bg-muted text-[11px] font-medium leading-none text-muted-foreground',
    up: 'inline-flex items-center h-5 px-1.5 rounded-sm bg-up/12 text-[11px] font-medium leading-none text-up',
    down: 'inline-flex items-center h-5 px-1.5 rounded-sm bg-down/12 text-[11px] font-medium leading-none text-down',
    info: 'inline-flex items-center h-5 px-1.5 rounded-sm bg-info/12 text-[11px] font-medium leading-none text-info',
  },
  button: {
    primary: 'inline-flex items-center justify-center gap-2 h-9 px-4 rounded-md bg-primary text-primary-foreground text-sm font-medium leading-none hover:opacity-90',
    secondary: 'inline-flex items-center justify-center gap-2 h-9 px-4 rounded-md border border-border text-sm font-medium leading-none text-foreground hover:bg-muted',
    ghost: 'inline-flex items-center justify-center gap-2 h-8 px-2.5 rounded-md text-sm leading-none text-muted-foreground hover:bg-muted hover:text-foreground',
  },
  segmented: 'inline-flex items-center h-8 p-0.5 rounded-md border border-border bg-background',
  segment: 'inline-flex items-center h-full px-3 rounded-sm text-xs leading-none text-muted-foreground aria-pressed:bg-muted aria-pressed:text-foreground',
  table: 'w-full border-collapse text-sm',
  th: 'h-9 px-2 text-left align-middle text-xs font-medium text-muted-foreground border-b border-border',
  td: 'h-10 px-2 align-middle border-b border-border',
  tile: 'flex flex-col justify-between gap-2 rounded-lg border border-border bg-card p-4',
  tileLabel: 'text-xs text-muted-foreground leading-none',
  tileValue: 'font-mono tabular-nums text-2xl font-semibold leading-none text-foreground',
  delta: { up: 'inline-flex items-center gap-1 text-up', down: 'inline-flex items-center gap-1 text-down', flat: 'inline-flex items-center gap-1 text-muted-foreground' },
  sector: ['bg-sector-1', 'bg-sector-2', 'bg-sector-3', 'bg-sector-4', 'bg-sector-5', 'bg-sector-6', 'bg-sector-7', 'bg-sector-other'],
  grid: 'grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3',
};
