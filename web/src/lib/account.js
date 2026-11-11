/* The signed-in person, when accounts are on: who they are, how they can sign in, and their saved stack. While accounts are off
   (no server secret yet) the site keeps the stack in the browser exactly as before. */
export const A = { enabled: false, user: null, ways: {}, methods: [], stack: [] };

const call = (path, body) =>
  fetch(path, body ? { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body), credentials: 'same-origin' } : { credentials: 'same-origin' }).then(async r => ({
    ok: r.ok,
    status: r.status,
    body: await r.json().catch(() => ({})),
  }));

export async function refresh() {
  const r = await call('/api/me').catch(() => null);
  Object.assign(A, { enabled: false, user: null, ways: {}, methods: [], stack: [] }, (r && r.ok && r.body) || {});
  dispatchEvent(new CustomEvent('airstack:account'));
  return A;
}

export const startEmail = (email, check) => call('/api/auth/email/start', { email, check });
export const verifyEmail = (email, code, link = false) => call('/api/auth/email/verify', { email, code, link });
export const saveStack = (op, id, name) => call('/api/stack', { op, id, name });
export const signOut = () => call('/api/auth/signout', {}).then(refresh);
export const unlink = provider => call('/api/auth/unlink', { provider }).then(refresh);
export const deleteAccount = () => call('/api/account/delete', {}).then(refresh);
export const providerUrl = (p, link = false) => `/api/auth/${p}/start${link ? '?link=1' : ''}`;
