// spec: AS-102 AS-131 AS-242 AS-256 AS-346
import { coverMap, drawMap } from './coverage-map.js';
import {
  DEFAULT_PLAN,
  LINE,
  PLANS_OF,
  PLATFORMS,
  S,
  WORD,
  current,
  expired,
  factsReceipt,
  family,
  receipt,
} from './model.js';
import { needChips, withNeeds } from './needs.js';
import { radios } from '../chips.js';
import { renderProfile } from '../profile.js';
import { M } from '../../lib/data.js';
import { $, $$, reduce, sr } from '../../lib/dom.js';
import { esc, fd, ic, url } from '../../lib/format.js';

function keepInLink() {
  /* a shared link reopens the same scenario: plan, meeting, device and needs */
  if (!S.tool || !S.app || (S.assumed && !S.to) || !/^#app=/.test(location.hash)) return;
  const p = new URLSearchParams({ app: S.tool.id, plan: S.plan, use: S.use === 'Online' ? 'online' : 'in-person' });
  if (S.device) p.set('device', S.device);
  if (S.needs.size) p.set('needs', [...S.needs].join(','));
  if (S.to) p.set('to', S.to);
  if (S.to && S.side === 'Proposed') p.set('side', 'proposed');
  const h = '#' + p.toString();
  if (location.hash !== h)
    history.pushState(null, '', h); /* each change you make is a step back and forward return to */
}
let REAL = ''; /* the plan you have, while the answer is drawn for the proposed one */
export function renderAnswer() {
  /* Proposed draws the whole answer as if you had changed plan; nothing else about the scenario moves */
  REAL = S.plan;
  const prop = S.side === 'Proposed' && S.to && S.to !== S.plan && PLANS_OF(family(S.plan)).includes(S.to);
  if (prop) S.plan = S.to;
  try {
    draw(prop);
  } finally {
    S.plan = REAL;
  }
  keepInLink();
}
function draw(prop) {
  $('#answer').hidden = false;
  $('#profile').hidden = false;
  $('#nf').hidden = true;
  needChips();
  let { a, ex, fam } = current();
  a = withNeeds(a);
  if (expired(a))
    a = {
      ...a,
      action: 'unknown',
      stale: true,
      line: `Recheck due since ${fd(a.freshUntil)}.`,
      reason: `Last verified answer: ${WORD[a.action]}, ${fd(a.evaluatedAt)}. No current recommendation is shown until monitoring verifies it again.`,
    };
  {
    const st = $('#strip');
    st.hidden = false;
    st.innerHTML = `<b class="aw ${a.action}">${a.stale ? 'Recheck due' : WORD[a.action]}</b><span class="sl">${a.action === 'ask' ? 'Which device?' : esc(a.reason || a.line || '')}</span>`;
  }
  $('#qDevW').hidden = !(fam === 'Google' && S.use === 'In person');
  const quote =
    !a.needs && a.sources[0] && a.sources[0].quote
      ? `<div><dt>In their words</dt><dd><p class="quote">${esc(a.sources[0].quote.replace(/\s*\*+\s*$/, ''))}</p></dd></div>`
      : ''; // no quote, no row; a trailing footnote marker is not part of the words
  const links = a.sources.length
    ? a.sources
        .map(
          s =>
            `<a class="ext" href="${url(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.label)} · ${s.published ? `published ${fd(s.published)} · checked ` : ''}${fd(s.date)}${ic('out')}</a>`
        )
        .join('')
    : '<span class="nobs">Not observed</span>';
  const rk = a.action + '|' + (a.reason || ''),
    changed = $('#answer').dataset.rk !== rk;
  const ask = a.action === 'ask';
  $('#answer').innerHTML =
    `<div class="ahead"><p class="aw ${a.action}">${a.stale ? 'Recheck due' : WORD[a.action]}</p></div>
    <p class="aline"><span class="big">${esc(hero(a))}</span>${ask || a.line === LINE[a.action] ? '' : esc(a.line)}</p>${ask ? choices('Device', M.devices.map(d => `<button class="chip" type="button" data-dev="${esc(d)}">${esc(d)}</button>`).join('')) : ''}
    <p class="areason">${esc(a.reason)}</p>${a.action === 'potential' && !$('#qNeedW').hidden ? choices(`What else do you use ${S.app} for?`, $('#needs').innerHTML) : ''}
    ${
      ask
        ? ''
        : `<dl class="kv">
      <div><dt>This changes if</dt><dd>${esc(a.changesIf)}</dd></div>
      <div><dt>Sources</dt><dd class="srcs">${links}</dd></div>
    </dl><div class="when meta"><p>${when(a)}</p><p>${a.needs ? receipt(ex) : factsReceipt(a)}</p></div>
    <details class="how"${S.how ? ' open' : ''}><summary>How we decided</summary>
      <p class="meta">Each line is something ${esc(S.app)} does for you. A tick means ${esc(S.plan)} already does it; a cross means only ${esc(S.app)} does.</p>${swap(prop) + coverMap(a, fam)}
      ${a.basis && !a.stale ? `<dl class="kv"><div><dt>Basis</dt><dd>${esc(a.basis)}</dd></div>${quote}</dl>` : quote ? `<dl class="kv">${quote}</dl>` : ''}
    </details>
    <p class="mt16"><button class="ghost" type="button" id="copyBrief">Copy with sources</button> <button class="ghost" type="button" data-compare="${esc(S.tool.id)}">Compare with other tools</button></p><pre class="json" id="briefOut" hidden></pre>`
    }`;
  const A = $('#answer');
  A.dataset.rk = rk;
  A.classList.toggle('reveal', changed && !reduce); /* new coverage nodes animate without a layout-flush restart */
  if (changed && !reduce) {
    const play = (selector, frames, options) => {
      const el = $(selector, A);
      if (el && el.animate) el.animate(frames, { fill: 'both', ...options });
    };
    play('.aw', [{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'translateY(0)' }], {
      duration: 420,
      easing: 'cubic-bezier(.2,.7,.2,1)',
    });
    for (const selector of ['.aline', '.areason'])
      play(selector, [{ opacity: 0 }, { opacity: 1 }], { duration: 400, delay: 120, easing: 'ease' });
  } /* once per meaningful verdict change; no forced reflow, and reduced motion stays still */
  setup(prop, fam);
  BRIEF = a.action === 'ask' ? '' : brief(a, fam);
  requestAnimationFrame(drawMap);
  renderProfile();
}
function hero(a) {
  /* the verdict in plain words; the official word (Retire, Keep) stays as the label above it */
  if (a.stale) return 'Monitoring recheck due.';
  if (a.action === 'ask') return a.line;
  return (
    {
      retire: `You can stop paying for ${S.app}.`,
      potential: `You may be able to stop paying for ${S.app}.`,
      keep: `Keep paying for ${S.app}.`,
    }[a.action] || 'We can’t say yet.'
  );
}
function when(a) {
  /* the same two dates as before, framed as continuous monitoring; a due recheck never reads as current */
  if (!a.evaluatedAt || !a.freshUntil) return '';
  return a.stale
    ? `Recheck due since ${fd(a.freshUntil)}. Last verified ${fd(a.evaluatedAt)}; the previous answer remains as history until monitoring verifies it again.`
    : `Verified ${fd(a.evaluatedAt)}. Monitoring active; next recheck by ${fd(a.freshUntil)}.`;
}
const choices = (q, chips) =>
  `<div class="inq" role="group" aria-label="${esc(q)}"><p class="lab">${esc(q)}</p><div class="chips">${chips}</div></div>`;
function setup(prop, fam) {
  /* the choices behind the answer, as one line; Change shows the chips */
  const d = fam === 'Google' && S.use === 'In person' && S.device ? `, on ${S.device}` : '',
    picked = $$('#needs .chip[aria-pressed="true"]').map(c => c.textContent),
    n = S.needs.has('none') ? ', nothing else' : picked.length ? ', also ' + picked.join(', ') : '';
  $('#setup .sv').textContent =
    `${prop ? 'If you changed to ' : ''}${fam === 'Google' && S.plan !== 'No Google plan' ? 'Google ' : ''}${S.plan}, ${S.use === 'Online' ? 'online' : 'in person'}${d}${n}`;
  $('#setup .lab').textContent = S.assumed ? 'Assuming' : 'Your setup';
}
function swap(prop) {
  /* Current / Proposed: the same coverage before and after a change of plan on your platform */
  const opts = PLANS_OF(family(REAL)).filter(p => p !== REAL);
  return `<div class="swap" role="group" aria-label="Coverage before and after a change"><button class="chip" type="button" id="swCur" data-side="Current" aria-pressed="${!prop}">Current: ${esc(REAL)}</button><button class="chip" type="button" id="swProp" data-side="Proposed" aria-pressed="${!!prop}"${S.to ? '' : ' disabled'}>Proposed${S.to ? ': ' + esc(S.to) : ''}</button><label class="meta">Change to <select id="swTo"><option value="">Choose a plan</option>${opts.map(p => `<option${p === S.to ? ' selected' : ''}>${esc(p)}</option>`).join('')}</select></label></div>`;
}
export let BRIEF = '';
function brief(a, fam) {
  /* the answer as plain text for a note or a ticket, from the same object the card shows */
  const inPerson = S.use === 'In person',
    dev = fam === 'Google' && inPerson && S.device ? S.device : null;
  const picked = $$('#needs .chip[aria-pressed="true"]').map(c => c.textContent);
  const args = {
    app: S.app,
    plan: S.plan,
    meeting: inPerson ? 'in_person' : 'online',
    ...(dev ? { device: dev } : {}),
    ...(S.needs.has('none') ? { needs: ['nothing else'] } : {}),
  };
  const lines = [
    `AirStack · ${S.app}`,
    `${S.plan !== REAL ? 'If you changed to' : 'You have'}: ${fam === 'Google' && S.plan !== 'No Google plan' ? 'Google ' : ''}${S.plan}, ${inPerson ? 'in-person' : 'online'} meetings${dev ? `, recorded on ${dev}` : ''}`,
    ...(picked.length ? [`Also used for: ${picked.join(', ')}`] : []),
    `Answer: ${a.stale ? 'Recheck due' : WORD[a.action]}. ${a.reason}`,
    `This changes if: ${a.changesIf}`,
    a.stale
      ? `Recheck due since ${fd(a.freshUntil)}; last verified ${fd(a.evaluatedAt)}`
      : `Verified ${fd(a.evaluatedAt)}; monitoring active through ${fd(a.freshUntil)}`,
    'Sources:',
    ...a.sources.map(
      x => `- ${x.label}: ${x.url} (checked ${fd(x.date)}${x.published ? `, published ${fd(x.published)}` : ''})`
    ),
  ];
  if (!picked.length || S.needs.has('none'))
    lines.push(
      `Same recorded answer for local agents: assess ${JSON.stringify(args)}`
    ); /* only when the endpoint takes exactly this scenario */
  return lines.concat([`${location.origin}${location.pathname}${location.hash}`]).join('\n');
}
export const announce = () => sr(`${$('#answer .aw').textContent}: ${$('#answer .areason').textContent}`);
function plansUp() {
  radios($('#plans'), PLANS_OF(S.platform), S.plan, v => {
    S.plan = v;
    S.assumed = false;
    renderAnswer();
    announce();
  });
}
export function chipsUp() {
  S.platform = family(S.plan);
  radios($('#platforms'), PLATFORMS(), S.platform, v => {
    S.platform = v;
    S.plan = DEFAULT_PLAN()[v] || PLANS_OF(v)[0];
    S.assumed = false;
    plansUp();
    renderAnswer();
    announce();
  });
  plansUp();
  radios($('#uses'), ['Online', 'In person'], S.use, v => {
    S.use = v;
    S.assumed = false;
    renderAnswer();
    announce();
  });
  radios($('#devices'), M.devices, S.device, v => {
    S.device = v;
    S.assumed = false;
    renderAnswer();
    announce();
  });
}
