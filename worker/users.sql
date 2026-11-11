-- AirStack accounts: the one schema, applied as is (every statement can run again): a person (user), their ways in (account),
-- their sign-ins (session) and pending codes (verification).

CREATE TABLE IF NOT EXISTS "user" (
  id            TEXT PRIMARY KEY NOT NULL,
  name          TEXT NOT NULL,
  email         TEXT NOT NULL UNIQUE,
  emailVerified INTEGER NOT NULL DEFAULT 0,
  image         TEXT,
  createdAt     TEXT NOT NULL,
  updatedAt     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "account" (
  id                    TEXT PRIMARY KEY NOT NULL,
  accountId             TEXT NOT NULL,
  providerId            TEXT NOT NULL,
  userId                TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  accessToken           TEXT,
  refreshToken          TEXT,
  idToken               TEXT,
  accessTokenExpiresAt  TEXT,
  refreshTokenExpiresAt TEXT,
  scope                 TEXT,
  password              TEXT,
  createdAt             TEXT NOT NULL,
  updatedAt             TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS account_userId ON account(userId);
CREATE UNIQUE INDEX IF NOT EXISTS account_provider_unique ON account(providerId, accountId);

CREATE TABLE IF NOT EXISTS "session" (
  id        TEXT PRIMARY KEY NOT NULL,
  expiresAt TEXT NOT NULL,
  token     TEXT NOT NULL UNIQUE,   -- a hash of the cookie's value; the value itself is never stored
  createdAt TEXT NOT NULL,
  updatedAt TEXT NOT NULL,
  ipAddress TEXT,
  userAgent TEXT,
  userId    TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS session_userId ON session(userId);

CREATE TABLE IF NOT EXISTS "verification" (
  id         TEXT PRIMARY KEY NOT NULL,
  identifier TEXT NOT NULL,         -- 'email:' and a keyed hash of the address; the address itself is not stored here
  value      TEXT NOT NULL,         -- a keyed hash of the code, then '.' and the wrong tries so far
  expiresAt  TEXT NOT NULL,
  createdAt  TEXT,
  updatedAt  TEXT
);
CREATE INDEX IF NOT EXISTS verification_identifier ON verification(identifier, createdAt);

-- AirStack's own: a person's saved stack, and the counters every cap reads before anything is spent
CREATE TABLE IF NOT EXISTS stack (
  userId    TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  productId TEXT NOT NULL,
  name      TEXT NOT NULL,
  addedAt   TEXT NOT NULL,
  PRIMARY KEY (userId, productId)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS quota (
  name   TEXT NOT NULL,
  period TEXT NOT NULL,
  n      INTEGER NOT NULL,
  PRIMARY KEY (name, period)
) WITHOUT ROWID;
