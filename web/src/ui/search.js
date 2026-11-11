/* A search field with its result list (a combobox). The shell's global search in index.html uses the same classes. */
import { html } from './html.js';

export const SearchField = ({ id, label, placeholder, listId, listLabel }) =>
  html`<div class="relative flex w-full min-w-0">
    <svg class="i pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" aria-hidden="true"><use href="#i-search"/></svg>
    <input class="h-10 w-full rounded-md border border-border bg-card pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:border-ring focus:outline-none" id="${id}" role="combobox" aria-label="${label}" aria-expanded="false" aria-controls="${listId}" aria-autocomplete="list" autocomplete="off" spellcheck="false" autocapitalize="off" placeholder="${placeholder}">
    <ul class="ta" id="${listId}" role="listbox" aria-label="${listLabel}" hidden></ul></div>`;
