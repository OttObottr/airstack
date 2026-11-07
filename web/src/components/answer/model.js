// spec: AS-066 AS-102 AS-106 AS-131 AS-134 AS-256 AS-346
import { M, MODEL } from '../../lib/data.js';
import { esc, fd, n, secs } from '../../lib/format.js';
import { MK } from '../../lib/market.js';

export const S = {
  tool: null,
  app: null,
  platform: 'Google',
  plan: M.default[0],
  use: 'Online',
  device: null,
  needs: new Set(),
  to: null /* a proposed plan on the same platform, and which side of the change is shown */,
  side: 'Current',
  assumed: true,
  how: false /* the 'How we decided' disclosure stays as you left it across answers */,
};
/* nothing is preselected for the user; a device is asked only for in-person meetings */
export const DEFAULT_PLAN = () => ({
  Google: M.default[0],
  Zoom: 'Zoom Workplace paid plan',
  Microsoft: 'Teams Premium',
});
export const PLATFORMS = () => ['Google'].concat(MK ? Object.keys(MK.platforms).filter(f => f !== 'Google') : []);
export const PLANS_OF = f => (f === 'Google' ? M.plans : MK && MK.platforms[f] ? Object.keys(MK.platforms[f]) : []);
export const LINE = {
  retire: 'You can stop paying for this.',
  keep: 'Nothing you already have does this yet.',
  unknown: 'Not enough evidence yet.',
};
export const WORD = {
  retire: 'Retire',
  keep: 'Keep',
  unknown: 'Not known yet',
  potential: 'Notes covered',
  ask: 'One more question',
};
const keyOf = name => (M.tools.find(t => t.name === name) || M.tools[0]).key;
export const ans = (k, p, d) => {
  const i = M.answers[k] && M.answers[k][p] && M.answers[k][p][d];
  return i === undefined ? null : M.pool[i];
};
/* read-time freshness (review C02): the client clock can only take validity away, never extend it */
export const expired = a => {
  const f = a && a.freshUntil;
  return !!f && Date.now() > Date.parse(f.length === 10 ? f + 'T23:59:59Z' : f);
};
export function receipt(ex) {
  const ck = fd(M.meta.checked_at);
  if (!ex) return `<span class="receipt">Rules only · no model call · ${ck}</span>`;
  const cost = `${ex.calls} call${ex.calls > 1 ? 's' : ''} · ${n(ex.tokens)} tokens · ${secs(ex.ms)}`;
  if (ex.kind === 'judged')
    return `<span class="receipt">Judged by ${MODEL} · ${cost} · ${fd(ex.on)}</span><br><span class="meta">Next check by ${fd(ex.recheckBy)}</span>`;
  if (ex.kind === 'reverified')
    return `<span class="receipt">Re-checked by ${MODEL} · ${cost} · ${fd(ex.on)}</span><br><span class="meta">Next check by ${fd(ex.recheckBy)}</span>`;
  return `<span class="receipt">Stored evaluation · no model call · ${fd(ex.on)}</span>`;
}
export function family(plan) {
  if (M.plans.includes(plan)) return 'Google';
  for (const f in MK ? MK.platforms : {}) if (f !== 'Google' && MK.platforms[f][plan]) return f;
  return 'Google';
}
export function fromRule(r) {
  /* a platform rule over a verified quote, turned into an answer */
  const action = { covered: 'retire', unmet: 'keep', limited: 'keep', unknown: 'unknown' }[r.status];
  const line = r.status === 'limited' ? 'What you already have only partly does this.' : LINE[action];
  const src = r.source
    ? [{ label: r.source.host, date: r.source.checked, url: r.source.url, quote: r.source.quote, call: r.source.call }]
    : [];
  return {
    action,
    line,
    reason: r.why,
    changesIf: r.changesIf,
    sources: src,
    needs: null,
    evaluatedAt: r.evaluatedAt,
    freshUntil: r.freshUntil,
  };
}
export function current() {
  const fam = family(S.plan);
  const k = keyOf(S.app);
  if (fam === 'Google' && S.use === 'In person' && !S.device)
    /* in-person notes roll out by device: do not guess one */
    return {
      a: {
        action: 'ask',
        line: 'Which device do you record on?',
        reason: 'In-person notes are rolling out device by device, so the answer depends on yours.',
        changesIf: 'You tell us the device.',
        sources: [],
        needs: null,
        basis: null,
      },
      ex: null,
      fam,
    };
  if (fam === 'Google' && S.use === 'In person')
    return { a: ans(k, S.plan, S.device), ex: M.examples[`${k}|${S.plan}|${S.device}`], fam };
  const rule =
    fam === 'Google'
      ? MK.platforms.Google[S.plan].online
      : MK.platforms[fam][S.plan][S.use === 'Online' ? 'online' : 'in_person'];
  return { a: fromRule(rule), ex: null, fam };
}
export function factsReceipt(a) {
  const s = a.sources[0];
  if (!s) return '<span class="receipt">No verified fact yet · nothing to judge</span>';
  return s.call
    ? `<span class="receipt">Fact extracted from ${esc(s.label)}, quote found on the page · ${fd(s.date)}</span>`
    : `<span class="receipt">Rules over ${esc(s.label)} · no model call · ${fd(s.date)}</span>`;
}
