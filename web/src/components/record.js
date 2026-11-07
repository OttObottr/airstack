// spec: AS-066 AS-103 AS-131 AS-136 AS-242 AS-256 AS-306
import { BRIEF } from './answer/answer.js';
import { WORD, ans } from './answer/model.js';
import { M, X } from '../lib/data.js';
import { $, $$, sr } from '../lib/dom.js';
import { cap, esc, fd, host, ic, n, secs, url } from '../lib/format.js';

/* ---------- the record: sources, history, execution ---------- */
const hk = (k, v) => `${k}=${JSON.stringify(v)}`;
const SRC = M.sources;
const J = X.judge,
  jo = J.output || {};
const abSide = (set, side) =>
  set.runs
    .filter(r => r.side === side)
    .map(
      r =>
        `<li><span class="w">${r.answer ? cap(r.answer.action.toLowerCase()) : 'No answer'}</span>${esc(r.answer ? r.answer.reason : r.note)}${r.tool_calls.length ? `<br><span class="meta">Asked AirStack get_verdict → ${r.tool_calls.map(t => (t.verdict ? `${cap(t.verdict.action.toLowerCase())} · ${esc(t.verdict.status.toLowerCase())} · ${fd(t.verdict.issued_at)}` : 'error')).join(', ')}</span>` : ''}</li>`
    )
    .join('');
const ea = X.mcp.request.params.arguments,
  pa = ans('fireflies', ea.plan, ea.device);
function tabs() {
  const ts = $$('.tab');
  const sel = t => {
    ts.forEach(x => {
      const on = x === t;
      x.setAttribute('aria-selected', on);
      x.tabIndex = on ? 0 : -1;
      $('#' + x.getAttribute('aria-controls')).hidden = !on;
    });
  };
  ts.forEach(t => t.addEventListener('click', () => sel(t)));
  $('.tabs').addEventListener('keydown', e => {
    const d = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (!d) return;
    e.preventDefault();
    const i = (ts.indexOf(document.activeElement) + d + ts.length) % ts.length;
    ts[i].focus();
    sel(ts[i]);
  });
}
tabs();

export function mount() {
  const toolCount = X.mcp.tools.length;
  $('#agScope').textContent = `Scope: ${n(toolCount)} reviewed tools · Answer snapshot verified ${fd(X.mcp.as_of)} · Clone, start locally, then ask in plain language.`;
  $('#agToolSummary').textContent = `Reviewed tool contract · ${n(toolCount)} tools`;
  $('#agTools').textContent = X.mcp.tools.join(', '); /* generated from the local server's descriptions: the page cannot drift from tools/list */
  $('#p-sources').innerHTML =
    `<table class="t stack"><thead><tr><th scope="col">Fact</th><th scope="col">Source</th><th scope="col">Published</th><th scope="col">Checked</th><th scope="col">Fingerprint</th></tr></thead><tbody>
  ${SRC.map(
    s => `<tr class="${s.superseded ? 'old' : ''}"><td data-l="Fact">${esc(s.fact)}${s.superseded ? ' <span class="meta">(replaced)</span>' : ''}</td>
    <td data-l="Source"><a class="ext" href="https://${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.source)}${ic('out')}</a></td>
    <td data-l="Published" class="num">${s.published ? fd(s.published) : '—'}</td><td data-l="Checked" class="num">${fd(s.observed)}</td>
    <td data-l="Fingerprint"><span class="mono hv" data-hk="${esc(hk(s.key, s.value))}" data-eh="${esc(s.hash)}" title="sha256 of ${esc(s.key)}">${esc(s.hash)}</span></td></tr>`
  ).join('')}
  </tbody></table><p class="mt12 meta">Fingerprint: sha256(key=value), first 8 hex · ${ic('check')} your browser recomputed it and it matches the database. It shows the record is intact, not that the claim is true: the source is the evidence</p>`;
  $('#p-history').innerHTML = M.history
    .map(
      h => `<h3>${esc(h.label)}</h3><table class="t stack"><thead><tr><th scope="col">Date</th><th scope="col">Clock</th><th scope="col">Answer</th><th scope="col">Why</th></tr></thead><tbody>
  ${h.rows.map(r => `<tr><td data-l="Date" class="num">${esc(r.date)}</td><td data-l="Clock">${r.clock === 'live' ? 'Real time' : 'Replayed'}</td><td data-l="Answer">${esc(r.what)}</td><td data-l="Why">${esc(r.why)}</td></tr>`).join('')}</tbody></table>`
    )
    .join('');
  /* the stored answer the endpoint serves for exactly this request */
  $('#p-exec').innerHTML = `
  <h3>Muse Spark’s judgement · ${esc(M.history[0].label)}</h3>
  ${
    J.output
      ? `<dl class="kv"><div><dt>Answer</dt><dd>${cap(jo.action.toLowerCase())} · ${jo.confidence.toFixed(2)} confidence · verdict #${esc(J.verdictId)}</dd></div>
    <div><dt>Cited</dt><dd>${J.cited.map(c => `<a class="ext" href="${url(c.url)}" target="_blank" rel="noopener noreferrer">${esc(c.ref)} · ${esc(c.fact)}${ic('out')}</a>`).join('<br>')}</dd></div>
    <div><dt>In its words</dt><dd><p class="quote">${esc(jo.reason)}</p></dd></div></dl>`
      : '<p class="meta">No judge output stored.</p>'
  }
  <h3>The same question, without and with AirStack</h3>
  ${
    X.ab
      ? X.ab
          .map(
            set => `<p class="mt24 lab">${esc(set.label)}</p>
    <details><summary>The question, asked 3 times each way</summary><p class="quote">${esc(set.question)}</p></details>
    <div class="ab"><div><p class="lab">Without AirStack</p><ol>${abSide(set, 'without')}</ol></div><div><p class="lab">With AirStack (MCP get_verdict)</p><ol>${abSide(set, 'with')}</ol></div></div>
    <p class="mt8 meta">${esc(set.model)} · ${set.runs.length} runs · ${set.runs.reduce((s, r) => s + r.calls.length, 0)} calls</p>`
          )
          .join('')
      : '<p class="meta">No A/B runs are recorded for this question.</p>'
  }
  <h3>Evaluation audit trail</h3>
  <div class="scroll"><table class="t stack"><thead><tr><th scope="col">Role</th><th scope="col">Response id</th><th scope="col">Logged (UTC)</th><th scope="col" class="r">Tokens in → out</th><th scope="col" class="r">Time</th></tr></thead><tbody>
  ${X.rows
    .map(
      r => `<tr><td data-l="Role">${esc(r.role)}</td><td data-l="Id"><span class="mono">${esc(r.ref)}</span></td><td data-l="Logged" class="num">${esc(r.ts.replace('T', ' ').replace('Z', ''))}</td>
    <td data-l="Tokens" class="r">${n(r.tin)} → ${n(r.tout)}</td><td data-l="Time" class="r">${secs(r.ms)}</td></tr>`
    )
    .join('')}</tbody></table></div>
  <h3>What search returned</h3>
  <table class="t stack"><thead><tr><th scope="col">Title</th><th scope="col">Site</th><th scope="col">Seen</th></tr></thead><tbody>
  ${X.searched.map(s => `<tr><td data-l="Title">${esc(s.title)}</td><td data-l="Site"><a class="ext" href="${url(s.url)}" target="_blank" rel="noopener noreferrer">${esc(host(s.url))}${ic('out')}</a></td><td data-l="Seen" class="num">${fd(s.seen)}</td></tr>`).join('')}</tbody></table>
  <h3 id="mcp">A local agent gets the same recorded answer</h3>
  <p class="mt8 mono">Local MCP · ${esc(X.mcp.request.params.name)} ${esc(JSON.stringify(X.mcp.request.params.arguments))} · recorded ${fd(X.mcp.as_of)}</p>
  <p class="meta">The answer below is the reviewed snapshot. Local MCP reads the same record without invoking a hosted function or model.</p>
  <dl class="kv"><div><dt>Answer</dt><dd>${WORD[pa.action]} · next check by ${fd(pa.freshUntil)}</dd></div>
    <div><dt>Reason</dt><dd>${esc(pa.reason)}</dd></div>
    <div><dt>This changes if</dt><dd>${esc(pa.changesIf)}</dd></div>
    ${pa.needs ? `<div><dt>Requirements</dt><dd>${pa.needs.filter(x => x.status === 'covered').length} of ${pa.needs.length} covered</dd></div>` : ''}
    <div><dt>Sources</dt><dd>${pa.sources.length} pages, each with its link and check date</dd></div></dl>`;
  $('#mcpLink').addEventListener('click', () => {
    location.hash = '#/agents';
  });
  document.addEventListener('click', async e => {
    const c = e.target.closest('#copyBrief');
    if (!c || !BRIEF) return; /* the answer and its sources as plain text; say "Copied" only when it worked */
    try {
      await navigator.clipboard.writeText(BRIEF);
      c.textContent = 'Copied';
      sr('The answer and its sources are on the clipboard');
    } catch {
      const o = $('#briefOut');
      o.textContent = BRIEF;
      o.hidden = false;
      const r = document.createRange();
      r.selectNodeContents(o);
      const sl = getSelection();
      sl.removeAllRanges();
      sl.addRange(r);
      c.textContent = 'Selected below: press Ctrl or Cmd+C';
    }
    setTimeout(() => {
      c.textContent = 'Copy with sources';
    }, 1600);
  });
  document.addEventListener('click', async e => {
    const b = e.target.closest('[data-copy]');
    if (!b) return;
    const t = $(b.dataset.copy).textContent,
      was = b.textContent; /* copy, and say so only when it worked */
    try {
      await navigator.clipboard.writeText(t);
      b.textContent = 'Copied';
      sr('Copied to the clipboard');
    } catch {
      const r = document.createRange();
      r.selectNodeContents($(b.dataset.copy));
      const sl = getSelection();
      sl.removeAllRanges();
      sl.addRange(r);
      b.textContent = 'Selected: press Ctrl or Cmd+C';
    }
    setTimeout(() => {
      b.textContent = was;
    }, 1600);
  });
  (async () => {
    try {
      if (!(window.crypto && crypto.subtle)) return;
      const enc = new TextEncoder();
      await Promise.all(
        $$('.hv').map(async e => {
          const d = await crypto.subtle.digest('SHA-256', enc.encode(e.dataset.hk));
          const h = [...new Uint8Array(d)]
            .slice(0, 4)
            .map(b => b.toString(16).padStart(2, '0'))
            .join('');
          if (h === e.dataset.eh) e.classList.add('ok');
        })
      );
    } catch (e) {}
  })();
}
