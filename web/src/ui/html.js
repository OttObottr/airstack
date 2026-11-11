/* html`…` builds markup from data: every interpolated value is escaped unless it is markup itself (another html`…`,
   an array of them, or raw(…) for a string that is already markup). null, undefined and false render nothing. */
import { esc } from '../lib/format.js';

class Markup {
  constructor(s) {
    this.s = s;
  }
  toString() {
    return this.s;
  }
}
export const raw = s => new Markup(String(s ?? ''));
const put = v =>
  v == null || v === false ? '' : v instanceof Markup ? v.s : Array.isArray(v) ? v.map(put).join('') : esc(String(v));
export const html = (parts, ...values) => new Markup(parts.reduce((out, part, i) => out + put(values[i - 1]) + part));
