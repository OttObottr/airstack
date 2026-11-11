/* Sign in, and the account: Google, GitHub or a code by email; once signed in, the ways in can be linked or removed and the account
   deleted. Shown only when accounts are on. */
import { $ } from '../lib/dom.js';
import { esc } from '../lib/format.js';
import { A, deleteAccount, providerUrl, refresh, signOut, startEmail, unlink, verifyEmail } from '../lib/account.js';
import { ui } from '../ui/recipes.js';

const NAME = { google: 'Google', github: 'GitHub', email: 'Email' };
const BTN = 'btn btn-secondary w-full justify-center';
let step = { email: '', sent: false, msg: '', link: false };
/* Cloudflare Turnstile on the email form, only when the site turns it on: its script loads the first time the form shows */
let check = { token: '', widget: null, loading: null };
const turnstile = () =>
  (check.loading ||= new Promise((ok, no) => {
    const s = document.createElement('script');
    s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    s.async = true;
    s.onload = () => ok(window.turnstile);
    s.onerror = () => ((check.loading = null), no());
    document.head.append(s);
  }));
async function mountCheck() {
  const el = document.querySelector('#signin [data-check]');
  if (!el || !A.ways.check) return;
  check.token = '';
  const t = await turnstile().catch(() => null);
  if (t && el.isConnected) check.widget = t.render(el, { sitekey: A.ways.check, callback: v => (check.token = v), 'expired-callback': () => (check.token = '') });
}

const say = m => (step.msg = m || '');
const MSG = {
  busy: 'Sign-in is busy right now. Please try again later.',
  code: 'That code didn’t work. Check it, or ask for a new one.',
  email: 'Enter a valid email address.',
  exists: 'That email already has an account. Sign in the way you used before, then add this way in from your account.',
  taken: 'That sign-in already belongs to another account.',
  failed: 'Sign-in didn’t complete. Please try again.',
  last: 'Keep at least one way to sign in.',
  check: 'Please complete the check, then ask for the code again.',
};

function body() {
  if (A.user) {
    const others = Object.keys(NAME).filter(k => A.ways[k] && !A.methods.includes(k));
    return `<h2 class="h-section">Your account</h2><p class="${ui.panelNote}">${esc(A.user.email)}</p>
      <h3 class="mt-4 text-sm font-medium">Ways to sign in</h3>
      <ul class="mt-2 flex flex-col gap-2">${A.methods
        .map(m => `<li class="flex items-center justify-between gap-3 text-sm">${NAME[m] || esc(m)}${A.methods.length > 1 ? `<button class="${ui.button.ghost}" type="button" data-unlink="${esc(m)}">Remove</button>` : ''}</li>`)
        .join('')}</ul>
      ${others.length ? `<div class="mt-3 flex flex-col gap-2">${others.map(k => (k === 'email' ? `<button class="${BTN}" type="button" data-link-email>Add an email sign-in</button>` : `<a class="${BTN}" href="${providerUrl(k, true)}">Add ${NAME[k]}</a>`)).join('')}</div>` : ''}
      ${step.link ? emailForm() : ''}
      <div class="mt-6 flex flex-wrap gap-2"><button class="${ui.button.secondary}" type="button" data-signout>Sign out</button><button class="${ui.button.ghost}" type="button" data-delete>Delete account</button></div>`;
  }
  return `<h2 class="h-section">Sign in to save your stack</h2>
    <div class="mt-4 flex flex-col gap-2">${['google', 'github'].filter(k => A.ways[k]).map(k => `<a class="${BTN}" href="${providerUrl(k)}">Continue with ${NAME[k]}</a>`).join('')}</div>
    ${A.ways.email ? emailForm() : ''}
    <p class="mt-4 ${ui.panelNote}">By signing in you agree to the <a href="/legal/">terms and privacy notice</a>.</p>`;
}
const emailForm = () =>
  !step.sent
    ? `<form class="mt-4 flex flex-col gap-2" data-start><label class="text-sm" for="siEmail">Email</label><input class="h-9 rounded-md border border-input bg-background px-3 text-sm" id="siEmail" type="email" autocomplete="email" required value="${esc(step.email)}">${A.ways.check ? '<div data-check></div>' : ''}<button class="${ui.button.primary}" type="submit">Email me a code</button></form>`
    : `<form class="mt-4 flex flex-col gap-2" data-verify><label class="text-sm" for="siCode">Code sent to ${esc(step.email)}</label><input class="h-9 rounded-md border border-input bg-background px-3 text-sm tracking-widest" id="siCode" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" required><button class="${ui.button.primary}" type="submit">Sign in</button><button class="${ui.button.ghost}" type="button" data-again>Use a different email</button></form>`;

function draw() {
  const d = $('#signin');
  d.querySelector('[data-body]').innerHTML = body() + (step.msg ? `<p class="mt-3 text-sm text-down" role="alert">${esc(step.msg)}</p>` : '');
  const rail = $('#railAccount');
  rail.hidden = !A.enabled;
  rail.textContent = A.user ? A.user.email : 'Sign in';
  mountCheck();
}
const open = () => {
  draw();
  const d = $('#signin');
  if (!d.open) d.showModal();
};

export function mount() {
  const d = $('#signin');
  if (!d) return;
  addEventListener('airstack:account', draw);
  addEventListener('airstack:signin', open);
  $('#railAccount').addEventListener('click', open);
  d.addEventListener('click', async e => {
    if (e.target === d || e.target.closest('[data-close]')) return d.close();
    const t = e.target;
    if (t.closest('[data-again]')) return (step = { email: '', sent: false, msg: '', link: step.link }), draw();
    if (t.closest('[data-link-email]')) return (step = { email: '', sent: false, msg: '', link: true }), draw();
    if (t.closest('[data-signout]')) return signOut().then(() => d.close());
    const un = t.closest('[data-unlink]');
    if (un) {
      const r = await unlink(un.dataset.unlink);
      say(r && r.body && MSG[r.body.error]);
      return draw();
    }
    if (t.closest('[data-delete]')) {
      if (!t.closest('[data-delete]').dataset.sure) {
        t.closest('[data-delete]').dataset.sure = '1';
        t.closest('[data-delete]').textContent = 'Delete account and saved stack';
        return;
      }
      await deleteAccount();
      return d.close();
    }
  });
  d.addEventListener('submit', async e => {
    e.preventDefault();
    if (e.target.matches('[data-start]')) {
      step.email = $('#siEmail').value.trim();
      const r = await startEmail(step.email, check.token);
      step.sent = r.ok;
      say(r.ok ? '' : MSG[r.body.error] || MSG.busy);
    } else {
      const r = await verifyEmail(step.email, $('#siCode').value.trim(), step.link);
      say(r.ok ? '' : MSG[r.body.error] || MSG.busy);
      if (r.ok) {
        step = { email: '', sent: false, msg: '', link: false };
        await refresh();
        if (!A.user || !step.link) d.close();
      }
    }
    draw();
  });
  /* a sign-in that came back from Google or GitHub says how it went in the address */
  const m = location.hash.match(/(signin|settings)=(\w+)/);
  if (m) {
    say(m[2] === 'ok' || m[2] === 'linked' ? '' : MSG[m[2]] || MSG.failed);
    history.replaceState(null, '', location.pathname + location.search);
    refresh().then(() => step.msg && open());
  } else refresh();
}
