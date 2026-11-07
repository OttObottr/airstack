// spec: AS-101 AS-256
import { LIVE, M } from '../lib/data.js';
import { $, $$, reduce, sr } from '../lib/dom.js';
import { cap, esc, fd, ic, url } from '../lib/format.js';

/* ---------- as it happened: the stored events, step by step; nothing here is computed on the page ---------- */
const L = M.life,
  NAMES = { before: 'Before', change: 'Google ships', reassessed: 'Re-checked', checked: 'Scheduled check' };
let cur = L.steps.length - 1,
  timer = null;
function showStep(i, announce) {
  cur = i;
  const s = L.steps[i];
  $$('.step').forEach((b, j) => {
    b.setAttribute('aria-selected', j === i);
    b.tabIndex = j === i ? 0 : -1;
  });
  const c = s.caption,
    src = c.source
      ? ` <a class="ext" href="${url(c.source.url)}" target="_blank" rel="noopener noreferrer">${esc(c.source.label)}${ic('out')}</a>`
      : '';
  $('#cap').innerHTML =
    `<span class="when">${esc(s.date)}${c.at ? ', ' + esc(c.at) : ''}</span><span>${esc(c.text)}</span>${src}`;
  $('#lt tbody').innerHTML = s.rows
    .map(
      (r, j) => `<tr><td data-l="Plan">${esc(L.labels[j])}</td>
    <td data-l="Answer"><span class="lw ${r.action}${r.state === 'lapsed' ? ' lapsed' : ''}">${cap(r.action)}</span></td>
    <td data-l="Status">${r.state === 'lapsed' ? 'Needs a second look' : 'Current'}</td>
    <td data-l="What">${esc(r.note)}</td></tr>`
    )
    .join('');
  if (announce)
    sr(
      `${NAMES[s.step]}, ${s.date}. ` +
        s.rows
          .map(
            (r, j) =>
              `${L.labels[j]}: ${r.state === 'lapsed' ? cap(r.action) + ', needs a second look' : cap(r.action)}`
          )
          .join('. ')
    );
}
function stop() {
  clearTimeout(timer);
  timer = null;
  $('#replay').textContent = 'Replay';
}
function replay() {
  /* steps through RECORDED events; labelled as a replay, never as work in progress */
  stop();
  let i = 0;
  showStep(0, true);
  $('#replay').textContent = 'Stop';
  const next = () => {
    if (++i < L.steps.length) {
      showStep(i, true);
      timer = setTimeout(next, 1400);
    } else stop();
  };
  timer = setTimeout(next, 1400);
}
const st = M.status;

export function mount() {
  $('#steps').innerHTML = L.steps
    .map(
      (s, i) =>
        `<button class="step" role="tab" type="button" id="st${i}" aria-controls="lifepanel" aria-selected="false" tabindex="-1"><span class="sl">${NAMES[s.step]}</span><span class="sd">${esc(s.date)}</span></button>`
    )
    .join('');
  $('#steps').addEventListener('click', e => {
    const b = e.target.closest('.step');
    if (b) {
      stop();
      showStep(+b.id.slice(2), true);
    }
  });
  $('#steps').addEventListener('keydown', e => {
    const d = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (!d) return;
    e.preventDefault();
    stop();
    const i = (cur + d + L.steps.length) % L.steps.length;
    showStep(i, true);
    $('#st' + i).focus();
  });
  $('#replay').addEventListener('click', () => (timer ? stop() : replay()));
  showStep(cur);
  if (!reduce)
    new IntersectionObserver(
      (es, io) => {
        if (es[0].isIntersecting) {
          io.disconnect();
          replay();
        }
      },
      { threshold: 0.6 }
    ).observe($('#lifepanel'));
  $('#stat').textContent =
    `This record, ${fd(M.meta.checked_at)}: ${st.changed} facts changed · ${st.lapsed} second looks · ${st.rejudged} re-checked · ${st.withheld} withheld · ${st.calls} ${LIVE ? 'Muse Spark' : 'recorded'} calls`;
}
