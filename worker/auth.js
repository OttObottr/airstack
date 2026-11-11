/* Accounts: sign in with Google, GitHub or a code sent by email; one person, any number of linked ways in; a saved stack.
   Tables follow bottr's (user, account, session, verification) so the two sites share one shape. Nothing a stranger sends can
   cost money past a cap: every write is counted against a daily ceiling first, and sign-in emails stop at a monthly cap. */

const DAY = 864e5;
const enc = new TextEncoder();
const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
const sha = async s => hex(await crypto.subtle.digest('SHA-256', enc.encode(s)));
const hmac = async (key, s) => {
  const k = await crypto.subtle.importKey('raw', enc.encode(key), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return hex(await crypto.subtle.sign('HMAC', k, enc.encode(s)));
};
const rand = n => hex(crypto.getRandomValues(new Uint8Array(n)));
const iso = t => new Date(t).toISOString();
const json = (body, status = 200, headers = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...headers } });
const EMAIL = /^[^\s@<>()[\]\\,;:"]{1,64}@[a-z0-9-]+(\.[a-z0-9-]+)+$/i;
const COOKIE = '__Host-as';
const FLOW = '__Host-asf';
const cookie = (req, name) => ((req.headers.get('cookie') || '').match(new RegExp(`(?:^|; )${name}=([^;]+)`)) || [])[1] || null;
const setCookie = (name, v, maxAge) => `${name}=${v}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`;

export const PROVIDERS = {
  google: {
    auth: 'https://accounts.google.com/o/oauth2/v2/auth',
    token: 'https://oauth2.googleapis.com/token',
    scope: 'openid email profile',
    id: 'GOOGLE_CLIENT_ID',
    secret: 'GOOGLE_CLIENT_SECRET',
    async profile(token, fetcher) {
      const r = await fetcher('https://openidconnect.googleapis.com/v1/userinfo', { headers: { authorization: `Bearer ${token}` } });
      const p = await r.json();
      return { accountId: p.sub, email: p.email_verified ? String(p.email).toLowerCase() : null, name: p.name || p.email };
    },
  },
  github: {
    auth: 'https://github.com/login/oauth/authorize',
    token: 'https://github.com/login/oauth/access_token',
    scope: 'read:user user:email',
    id: 'GITHUB_CLIENT_ID',
    secret: 'GITHUB_CLIENT_SECRET',
    async profile(token, fetcher) {
      const h = { authorization: `Bearer ${token}`, 'user-agent': 'airstack.bot', accept: 'application/vnd.github+json' };
      const [u, e] = await Promise.all([fetcher('https://api.github.com/user', { headers: h }).then(r => r.json()), fetcher('https://api.github.com/user/emails', { headers: h }).then(r => r.json())]);
      const primary = Array.isArray(e) ? e.find(x => x.primary && x.verified) : null;
      return { accountId: String(u.id), email: primary ? primary.email.toLowerCase() : null, name: u.name || u.login };
    },
  },
};

export function make(L, fetcher = (...a) => fetch(...a)) {
  /* count one unit of `name` in this period; false once the cap is reached (the count is read and written in one statement) */
  async function spend(db, name, period, cap) {
    const n = await db
      .prepare('INSERT INTO quota(name, period, n) VALUES (?, ?, 1) ON CONFLICT(name, period) DO UPDATE SET n = n + 1 WHERE n < ? RETURNING n')
      .bind(name, period, cap)
      .first('n');
    return n != null;
  }
  const busy = () => json({ error: 'busy', message: 'Sign-in is busy right now. Please try again later.' }, 429);

  async function session(req, db, now) {
    const t = cookie(req, COOKIE);
    if (!t) return null;
    const row = await db.prepare('SELECT s.id, s.userId, s.expiresAt, u.name, u.email FROM session s JOIN "user" u ON u.id = s.userId WHERE s.token = ?').bind(await sha(t)).first();
    return row && Date.parse(row.expiresAt) > now ? row : null;
  }
  async function open(db, userId, req, now) {
    const t = rand(32),
      at = iso(now);
    await db
      .prepare('INSERT INTO session(id, expiresAt, token, createdAt, updatedAt, ipAddress, userAgent, userId) VALUES (?, ?, ?, ?, ?, NULL, NULL, ?)')
      .bind(rand(16), iso(now + L.sessionDays * DAY), await sha(t), at, at, userId)
      .run();
    return setCookie(COOKIE, t, L.sessionDays * 86400);
  }
  async function newUser(db, email, name, now) {
    const id = rand(16),
      at = iso(now);
    await db.prepare('INSERT INTO "user"(id, name, email, emailVerified, image, createdAt, updatedAt) VALUES (?, ?, ?, 1, NULL, ?, ?)').bind(id, name || email, email, at, at).run();
    return id;
  }
  const addAccount = (db, userId, providerId, accountId, now) =>
    db
      .prepare('INSERT INTO account(id, accountId, providerId, userId, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?, ?)')
      .bind(rand(16), accountId, providerId, userId, iso(now), iso(now))
      .run();
  const accountOf = (db, providerId, accountId) => db.prepare('SELECT userId FROM account WHERE providerId = ? AND accountId = ?').bind(providerId, accountId).first('userId');

  /* sign a person in by one of their ways in: an existing way in opens its account; a new way in links to the signed-in account when
     asked, else starts a new account unless its address already belongs to one (then the person is asked to sign in that way first) */
  async function enter(db, req, now, providerId, accountId, email, name, link) {
    const me = await session(req, db, now),
      owner = await accountOf(db, providerId, accountId);
    if (owner) {
      if (link && me && me.userId !== owner) return { error: 'taken' };
      return { userId: owner };
    }
    if (link && me) {
      await addAccount(db, me.userId, providerId, accountId, now);
      return { userId: me.userId, linked: true };
    }
    if (email && (await db.prepare('SELECT id FROM "user" WHERE email = ?').bind(email).first('id'))) return { error: 'exists' };
    const userId = await newUser(db, email || `${providerId}:${accountId}`, name, now);
    await addAccount(db, userId, providerId, accountId, now);
    return { userId };
  }

  async function handle(req, env, now) {
    const url = new URL(req.url),
      db = env.USERS,
      p = url.pathname,
      today = iso(now).slice(0, 10);
    if (req.method === 'POST' && req.headers.get('origin') !== url.origin) return json({ error: 'origin' }, 403);
    if (!(await spend(db, 'writes', today, L.dayWrites))) return busy();
    const ip = await hmac(env.AUTH_SECRET, `${today}|${req.headers.get('cf-connecting-ip') || ''}`);
    const body = req.method === 'POST' ? await req.json().catch(() => ({})) : {};

    if (p === '/api/me') {
      const me = await session(req, db, now);
      const ways = { email: !!env.EMAIL, google: !!env.GOOGLE_CLIENT_ID, github: !!env.GITHUB_CLIENT_ID };
      if (!me) return json({ user: null, enabled: true, ways });
      const [methods, stack] = await Promise.all([
        db.prepare('SELECT providerId FROM account WHERE userId = ? ORDER BY createdAt').bind(me.userId).all(),
        db.prepare('SELECT productId AS id, name, addedAt AS added FROM stack WHERE userId = ? ORDER BY addedAt, productId').bind(me.userId).all(),
      ]);
      return json({ user: { name: me.name, email: me.email }, enabled: true, ways, methods: methods.results.map(r => r.providerId), stack: stack.results });
    }

    if (p === '/api/auth/email/start' && req.method === 'POST') {
      const email = String(body.email || '').trim().toLowerCase();
      if (!EMAIL.test(email) || email.length > 254) return json({ error: 'email' }, 400);
      const id = `email:${email}`;
      const recent = await db.prepare('SELECT COUNT(*) AS n FROM verification WHERE identifier = ? AND createdAt > ?').bind(id, iso(now - 15 * 60e3)).first('n');
      if (recent >= L.codesPer15Min) return busy();
      if (!(await spend(db, `ip:${ip}`, today, L.codesPerNetworkDay)) || !(await spend(db, `code:${email}`, today, L.codesPerAddressDay))) return busy();
      if (!(await spend(db, 'emails', today.slice(0, 7), L.emailsPerMonth))) return busy();
      const code = String(crypto.getRandomValues(new Uint32Array(1))[0] % 1e6).padStart(6, '0');
      await db
        .prepare('INSERT INTO verification(id, identifier, value, expiresAt, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?, ?)')
        .bind(rand(16), id, `${await hmac(env.AUTH_SECRET, `${email}|${code}`)}.0`, iso(now + 10 * 60e3), iso(now), iso(now))
        .run();
      try {
        await env.EMAIL.send({
          from: L.from,
          to: email,
          subject: `${code} is your AirStack sign-in code`,
          text: `Your AirStack sign-in code is ${code}. It works once, for 10 minutes.\n\nIf you didn't ask for it, ignore this email.`,
        });
      } catch (e) {
        return busy();
      }
      return json({ ok: true });
    }

    if (p === '/api/auth/email/verify' && req.method === 'POST') {
      const email = String(body.email || '').trim().toLowerCase(),
        code = String(body.code || '').trim();
      const row = await db
        .prepare('SELECT id, value FROM verification WHERE identifier = ? AND expiresAt > ? ORDER BY createdAt DESC LIMIT 1')
        .bind(`email:${email}`, iso(now))
        .first();
      if (!row || !/^\d{6}$/.test(code)) return json({ error: 'code' }, 400);
      const [want, tries] = row.value.split('.');
      if (+tries >= L.codeTries) return json({ error: 'code' }, 400);
      if ((await hmac(env.AUTH_SECRET, `${email}|${code}`)) !== want) {
        await db.prepare('UPDATE verification SET value = ? WHERE id = ?').bind(`${want}.${+tries + 1}`, row.id).run();
        return json({ error: 'code' }, 400);
      }
      await db.prepare('DELETE FROM verification WHERE identifier = ?').bind(`email:${email}`).run();
      const r = await enter(db, req, now, 'email', email, email, email.split('@')[0], !!body.link);
      if (r.error) return json({ error: r.error }, 409);
      return json({ ok: true }, 200, { 'set-cookie': await open(db, r.userId, req, now) });
    }

    const start = p.match(/^\/api\/auth\/(google|github)\/start$/);
    if (start && req.method === 'GET') {
      const P = PROVIDERS[start[1]];
      if (!env[P.id]) return json({ error: 'unavailable' }, 503);
      const state = rand(16),
        verifier = rand(32),
        challenge = btoa(String.fromCharCode(...new Uint8Array(await crypto.subtle.digest('SHA-256', enc.encode(verifier)))))
          .replace(/\+/g, '-')
          .replace(/\//g, '_')
          .replace(/=+$/, '');
      const q = new URLSearchParams({ client_id: env[P.id], redirect_uri: `${url.origin}/api/auth/${start[1]}/callback`, response_type: 'code', scope: P.scope, state, code_challenge: challenge, code_challenge_method: 'S256' });
      return new Response(null, { status: 302, headers: { location: `${P.auth}?${q}`, 'set-cookie': setCookie(FLOW, `${state}.${verifier}.${url.searchParams.get('link') ? 1 : 0}`, 600), 'cache-control': 'no-store' } });
    }

    const back = p.match(/^\/api\/auth\/(google|github)\/callback$/);
    if (back && req.method === 'GET') {
      const P = PROVIDERS[back[1]],
        [state, verifier, link] = (cookie(req, FLOW) || '..').split('.'),
        done = where => new Response(null, { status: 302, headers: { location: `/#${where}`, 'set-cookie': setCookie(FLOW, '', 0), 'cache-control': 'no-store' } });
      if (!state || url.searchParams.get('state') !== state || !url.searchParams.get('code')) return done('signin=failed');
      const t = await fetcher(P.token, {
        method: 'POST',
        headers: { accept: 'application/json', 'content-type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ client_id: env[P.id], client_secret: env[P.secret], code: url.searchParams.get('code'), redirect_uri: `${url.origin}/api/auth/${back[1]}/callback`, grant_type: 'authorization_code', code_verifier: verifier }),
      }).then(r => r.json(), () => ({}));
      if (!t.access_token) return done('signin=failed');
      const who = await P.profile(t.access_token, fetcher).catch(() => null);
      if (!who || !who.accountId) return done('signin=failed');
      const r = await enter(db, req, now, back[1], who.accountId, who.email, who.name, link === '1');
      if (r.error) return done(`signin=${r.error}`);
      const res = done(r.linked ? 'settings=linked' : 'signin=ok');
      res.headers.append('set-cookie', await open(db, r.userId, req, now));
      return res;
    }

    const me = await session(req, db, now);
    if (!me) return json({ error: 'signin' }, 401);

    if (p === '/api/stack' && req.method === 'POST') {
      const id = String(body.id || '').slice(0, 80);
      if (!/^[A-Za-z0-9][\w.:-]{0,79}$/.test(id)) return json({ error: 'id' }, 400);
      if (body.op === 'remove') await db.prepare('DELETE FROM stack WHERE userId = ? AND productId = ?').bind(me.userId, id).run();
      else {
        const n = await db.prepare('SELECT COUNT(*) AS n FROM stack WHERE userId = ?').bind(me.userId).first('n');
        if (n >= L.stackMax) return json({ error: 'full' }, 400);
        await db.prepare('INSERT OR IGNORE INTO stack(userId, productId, name, addedAt) VALUES (?, ?, ?, ?)').bind(me.userId, id, String(body.name || id).slice(0, 120), today).run();
      }
      return json({ ok: true });
    }
    if (p === '/api/auth/signout' && req.method === 'POST') {
      await db.prepare('DELETE FROM session WHERE id = ?').bind(me.id).run();
      return json({ ok: true }, 200, { 'set-cookie': setCookie(COOKIE, '', 0) });
    }
    if (p === '/api/auth/unlink' && req.method === 'POST') {
      const n = await db.prepare('SELECT COUNT(*) AS n FROM account WHERE userId = ?').bind(me.userId).first('n');
      if (n <= 1) return json({ error: 'last' }, 400);
      await db.prepare('DELETE FROM account WHERE userId = ? AND providerId = ?').bind(me.userId, String(body.provider || '')).run();
      return json({ ok: true });
    }
    if (p === '/api/account/delete' && req.method === 'POST') {
      await db.batch([
        db.prepare('DELETE FROM stack WHERE userId = ?').bind(me.userId),
        db.prepare('DELETE FROM session WHERE userId = ?').bind(me.userId),
        db.prepare('DELETE FROM account WHERE userId = ?').bind(me.userId),
        db.prepare('DELETE FROM "user" WHERE id = ?').bind(me.userId),
      ]);
      return json({ ok: true }, 200, { 'set-cookie': setCookie(COOKIE, '', 0) });
    }
    return json({ error: 'not found' }, 404);
  }
  return { handle };
}
