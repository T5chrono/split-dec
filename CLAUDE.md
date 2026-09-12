# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SplitDec — a Splitwise clone (groups, multi-currency expenses, settlements, greedy debt
simplification). Built to `SplitDec - specification.md` (v6), **with deliberate deviations**
listed below. Production: https://split-dec.app (installable PWA) — the apex is the
canonical origin; `split-dec.vercel.app` still serves the app but is `noindex`.

## Commands

```powershell
# Backend (Python venv at .venv; local Python is 3.14, Vercel runs 3.12 —
# pinned in .python-version, which also matches CI; deleting it hands the
# choice back to Vercel's default, which moves)
.\.venv\Scripts\python -m pytest -q                     # all backend tests
.\.venv\Scripts\python -m pytest tests/test_api_expenses.py::test_create_expense  # one test
npm run api                                             # uvicorn on :8000 (needs .env)

# Frontend
npm run dev                                             # Vite on :5173
npm test                                                # vitest run (all)
npx vitest run src/components/ExpensesTab.test.tsx      # one file
npm run build                                           # tsc -b && vite build (type-check lives here)
```

`npm run api` boots uvicorn through `api/_src/dev_loop.py` (dev-only): it scrubs the
`SSLKEYLOGFILE` env var Norton injects (hard-crashes the uv Python's static OpenSSL) and
routes TLS verification through the Windows cert store via `truststore` (Norton MITMs
outbound HTTPS, e.g. the JWKS fetch). Details in that module's docstring.

There is no linter configured; `tsc` via `npm run build` is the frontend gate.
Backend Postgres-only integration tests (`tests/test_balances_pg.py`, `tests/test_locks_pg.py`)
skip unless `TEST_DATABASE_URL` is set — never point that at production.
`tests/test_grants_pg.py` and `tests/test_db_tls_pg.py` are the exceptions: they read
catalogs (or nothing at all), take `AUDIT_DATABASE_URL`, and are *meant* for production —
the second one opens a full-strength TLS handshake against the real pooler, and is the
gate in front of any change to `db.py` or `supabase_ca.py`, because a certificate the
context refuses is an outage rather than a failing test. All three connect through the
transaction pooler, so any engine they build needs `statement_cache_size=0` /
`prepared_statement_cache_size=0` exactly as `db.py` does — and on this machine they exit 1
with **no output at all** unless `SSLKEYLOGFILE` is popped and `truststore` injected first,
because the OpenSSL abort described under `npm run api` kills the process before pytest
prints anything.

## Workflow (mandatory)

Work on `develop`, never commit to `master` directly. Push → open PR to `master` → the
Claude GitHub Action auto-reviews every PR on open **and on every push to it**
(`.github/workflows/claude-code-review.yml`; `@claude` mentions work too, but those workflows
execute from `master`, the default branch) → address findings → merge on green CI → Vercel
auto-deploys `master` to production.
**`master` is protected** — ruleset `SplitDecMaster`, active since 2026-08-27: a pull
request is required, `backend` / `frontend` / `claude-review` must be green before the merge
button works, force-push and deletion are blocked, and **nobody holds a bypass**, maintainer
included. Required approvals are deliberately **0**: GitHub does not let you approve your own
PR, so on a sole-committer repo any higher number makes every PR unmergeable.
A green `claude-review` check now does mean a review was posted — the workflow's
`Fail if no review was posted` step turns the PR #29 failure mode (success having said
nothing) into a red check. The verdict is no longer hostage to the reviewer's own `gh`
call either: the action writes the whole run to disk, and a recovery step posts the final
message whenever no comment appeared, as `github-actions[bot]` with a marker the guard
matches on — author **and** marker, so pasting the marker into a comment buys nobody a
green check. That failure is not hypothetical: PR #74's reviewer spent 14 of its 24 turns
on denied tool calls and stopped without posting a verdict it had already written, and
only a re-run rescued it. Two gaps remain by design: a PR that edits
`claude-code-review.yml` passes with a warning, because the action refuses to run whenever
that file differs from the default branch, and Dependabot PRs skip the job on its `if:`
guard. In both cases the check is green with no review behind it, so read the comment there
rather than the tick.
After merging, sync: `git checkout develop && git merge master && git push`.
CI runs pytest, `npm test`, and the build on pushes to both branches and all PRs —
those are the `backend` and `frontend` jobs, and they are the two the ruleset requires.
Two more jobs run alongside them and are deliberately **not** required: `audit`
(`npm audit --audit-level=high` plus `pip-audit` over both Python locks) and `locks`
(recompiles each `requirements*.in` against its own `.txt` as a constraint and diffs, so
a package added to an `.in` without regenerating stops being silent). Neither blocks a
merge, because an unfixable advisory in a dev dependency holding every unrelated PR
hostage is the fastest way to train a solo maintainer to stop reading checks at all —
red there means read it and decide, and record the decision in `docs/supply-chain.md`.
Every workflow declares `permissions:` and passes `persist-credentials: false` to
checkout, and every action is pinned to a commit SHA; `claude.yml` additionally runs
only for the repository owner, because a public repo's issue body is otherwise an
unreviewed prompt handed to an agent holding a write-scoped token.
The develop → PR → master sequence is now enforced by the ruleset rather than by convention
alone — but treat it as the gate regardless of what any host or tool appears to allow.

## Architecture

One Vercel project, path-routed same-origin (no CORS in production; dev-only CORS is gated
on `ENV=development`):

- **Frontend**: Vite/React SPA at repo root. `vercel.json` rewrites `/api/*` to the function,
  everything else to `index.html`, 308-redirects `www.split-dec.app` to the apex (the apex must
  stay the serving origin — installed PWAs pin their origin and a redirecting apex strands their
  service workers and breaks same-origin `/api` calls), pins `regions: ["cdg1"]` — the
  function is deliberately collocated with the database (Paris); moving it re-adds
  ~500ms/request — and sets the security headers (HSTS, nosniff, `frame-ancestors 'none'` +
  `X-Frame-Options: DENY`, COOP `same-origin-allow-popups`, CORP `same-origin`,
  referrer and permissions policy), asserted by
  `tests/test_vercel_config.py`. COOP is deliberately the `-allow-popups` variant:
  the strict value also severs popups *we* open, and while supabase-js signs in by
  full-page redirect today, an OAuth popup is one config change away — plus the
  support link is a `target="_blank"`. It also sets
  `installCommand: "npm ci --ignore-scripts"`, which exists first to *narrow* the
  inferred install step: Vercel would otherwise also install the root
  `requirements.txt` into the build container, where nothing uses it — the build
  command is `tsc -b && vite build`, and the function gets its own install from
  the Python runtime afterwards. Removing the override restores a wasted install
  and, with it, the Tailwind source-detection problem described under Frontend
  patterns. The command itself carries two more rules, both asserted by
  `tests/test_vercel_config.py`. It was `npm install` until an OWASP A03 review
  in September 2026: every direct dependency is caret-ranged and `npm install`
  silently *repairs* a lock/manifest mismatch rather than failing, so the tree
  Vercel deployed was a different resolution event from the one CI tested and a
  green CI attested nothing about it. And `--ignore-scripts`, because this
  container holds `SENTRY_AUTH_TOKEN` and an install script is arbitrary code
  running next to it for no reason but being in the tree. Nothing is lost: the
  only install script that would run on Linux is `@sentry/cli`'s, and its
  `postinstall` `process.exit(0)`s the moment it resolves the platform binary,
  which arrives as a package — all eight `@sentry/cli-*` optional dependencies
  are in the lockfile. The download is its fallback for `--no-optional`
  installs, not its normal path.
  **The script-level CSP is enforced** (`default-src 'self'`, hash-pinned
  `script-src`, `connect-src` limited to self + the Supabase project + the
  Sentry ingest host). It shipped staged on `Content-Security-Policy-Report-Only`
  and was promoted once the policy had been checked against the actual build
  rather than against intentions: `dist/index.html` carries exactly one inline
  script (the theme flip, already hash-pinned), no inline `<style>` and no
  `style=` attributes, every script/stylesheet/manifest is same-origin, and the
  bundle contains no `eval`/`new Function`/`insertRule`. React's `style={{…}}`
  and the landing page's `el.style.transform` are CSSOM writes, which CSP does
  not govern — only markup `style=` attributes and `<style>` elements are. The
  one trap worth knowing: `@vercel/analytics` and `@vercel/speed-insights` both
  contain a `https://va.vercel-scripts.com` fallback, but it sits behind a
  build-time `"production"` constant, so the shipped bundle only ever requests
  the same-origin `/_vercel/...` paths. Verify a policy change the same way —
  serve `dist/` with the real headers (`npm run preview` applies none of them)
  and read the console; `upgrade-insecure-requests` has to be dropped for a
  localhost run or nothing loads. `tests/test_vercel_config.py` now reads the
  enforcing header only and fails if a report-only header reappears — a policy
  that merely reports blocks nothing. Reporting stays on so a directive that is
  wrong for an untested flow surfaces as a log line instead of a broken screen.
  Two things there are load-bearing and non-obvious: `font-src` must allow `data:` (Vite inlines the
  smallest Manrope woff2 into the built CSS), and the one inline script in
  `index.html` — the pre-mount theme flip — is allowed **by hash**, because a nonce
  is impractical when a single static `index.html` is served through a rewrite. The
  test recomputes that hash from `index.html`, so editing that script fails CI
  rather than silently reverting the app to a light-mode flash.
  Violations are collected by `POST /api/csp-report`
  (`routers/reports.py`) — without a destination a policy reports to each
  visitor's own console, where nobody collects it.
  **That route must answer a CORS preflight, and for its first year it did
  not.** Two things conspire, neither obvious. A policy carrying `report-to`
  makes Chromium ignore `report-uri` outright, so the same-origin legacy
  channel is switched off by the presence of the modern one. And a `report-to`
  delivery is preflighted *even though the endpoint is same-origin*, because
  the browser's reporting service sends it from outside the document and
  `application/reports+json` is not CORS-safelisted. With only a `POST`
  handler registered the route answered `OPTIONS` with 405, every preflight
  failed, no report was ever delivered, and the sole trace was a periodic
  `OPTIONS /api/csp-report 405` in the runtime log — a browser retrying the
  same report on a lengthening backoff. The headers are a wildcard on purpose:
  CORS governs what a browser lets a page *read back*, and this route answers
  204 with an empty body to everyone, while the control on whose reports are
  recorded is `fold_origin` on the body, which binds curl too. The actual POST
  carries them as well as the preflight — a delivery whose response has no
  `Access-Control-Allow-Origin` is a failed fetch, so the report returns to
  the retry queue having already been logged, and the endpoint looks alive
  while losing everything. It is the one route on
  the API reachable without a token, so it touches no database, stores
  nothing, and logs only the violation's shape: the directive, the blocked
  *origin*, the reporting host, and the route pattern folded exactly as
  `insightsRoute` folds it — a group id, an OAuth `?code=` or a recovery
  `#access_token=` must never reach a log line, and neither may a field
  forge one. **Every field is percent-encoded on the way out**
  (`log_value`) — the line is five `name=value` pairs separated by spaces,
  so a route of `/a route=x origin=evil` forges two more fields without a
  newline anywhere in it, and an authority does the same; stripping CR/LF
  was never the whole answer. The blocked origin is *rebuilt* from
  `.hostname`/`.port` rather than copied out of `netloc`, which would keep
  `user:password@`. A field over 512 encoded characters is dropped rather
  than truncated, and a log consumer splits on the field boundaries before
  decoding a value. Reports are dropped unless the document URL is
  a host we actually serve (apex, www, or the project's `*.vercel.app`),
  since a page we never served was never handed our policy.
  **The in-process limits are a floor, not a ceiling**: a content-type
  check, a 16 kB body cap, ten reports per request (a `report-to` POST is
  an *array*) and a 60/min token bucket. The bucket is per warm instance,
  and this is a serverless function with several of them — so it is a floor,
  never the ceiling. **The ceiling is a Vercel Firewall rule** ("CSP report
  flood limit": `path equals /api/csp-report`, 100 req/60s per IP, deny for
  5m), which lives in the Vercel project rather than this repo and is
  therefore invisible to CI — inspect it with `vercel firewall rules list`,
  and if the in-function numbers change, change it too. Same
  "the dashboard is what actually runs" trap as the auth email templates.
  Pointing the reports at a third-party collector would be a new processor,
  and a `src/lib/legal.ts` change with a `LEGAL_UPDATED` bump.
  A host-scoped `X-Robots-Tag: noindex` keeps `split-dec.vercel.app` from competing
  with the apex in search — it has to be a header, because every route rewrites to one
  `index.html` and a `<link rel="canonical">` in it would also claim `/privacy` and
  `/terms` are copies of the landing page. `public/robots.txt` and `public/sitemap.xml`
  cover the three public routes; assets are left crawlable on purpose, since the
  landing page is client-rendered.
- **Backend**: FastAPI in `api/index.py` (single Vercel function; code lives in `api/_src/` —
  the underscore prevents Vercel treating those files as separate functions).
  **`ENV=development` is not something a hosted deployment can ask for.** It switches on
  the Swagger page (a third-party script from cdn.jsdelivr.net on the origin holding the
  Supabase session), the CORS middleware and the open database probe, and nothing used to
  cross-check it against where the code was running. `config.resolve_env` does: `VERCEL_ENV`
  is set by the platform and cannot be overridden from project settings, so any value of it
  other than `development` forces production regardless of `ENV`. An unset `VERCEL_ENV` —
  a laptop, CI, pytest — is the only state where `development` is reachable, and an
  unrecognised one fails closed, exactly like `docs_urls`.
- **Database**: Supabase Postgres, project ref `kmlheefyzhhegxmtaovq`. Connection MUST use the
  transaction pooler (port 6543, `postgresql+asyncpg://`) with `NullPool` and
  `statement_cache_size=0` (`api/_src/db.py`) — never per-request engines, never the session pooler.
  **The server's certificate is verified, and that takes an explicit `SSLContext`.**
  asyncpg's default is `sslmode=prefer`: it drops to plaintext if something
  answers that the server does not do TLS, and when TLS *is* negotiated it uses
  `check_hostname=False` / `CERT_NONE`, so any certificate passes. Either way
  the pooler password and the whole ledger are readable from the path between
  Vercel and AWS. `sslmode=require` closes only the first half. Two traps make
  this less obvious than it sounds: `ssl="verify-full"` does **not** use the
  system trust store — asyncpg reads it as libpq does and looks for
  `~/.postgresql/root.crt` — and the pooler serves a certificate from
  *Supabase's own* 2021 CA, which no public bundle (certifi included) carries.
  So `db.tls_context()` builds `ssl.create_default_context()` and loads the
  Supabase root **on top of** the system roots: the root is what makes it work
  today, the system store is what stops a move to a publicly trusted
  certificate becoming an outage. The PEM is embedded in `supabase_ca.py` as a
  string, not shipped as a `.crt`, because a file the Python builder declines
  to bundle is a hard outage and a module cannot go missing.
  **`VERIFY_X509_STRICT` is cleared, deliberately**: Supabase's *intermediate*
  declares `CA:TRUE` with no `keyUsage` extension, which strict RFC 5280
  checking refuses, and Python 3.13 turned that flag on inside
  `create_default_context()` — so leaving it alone makes the app connect or not
  depending on the interpreter (fine on the 3.12 Vercel runs today, an outage
  the day `.python-version` moves). Signature, chain, expiry and hostname are
  all still checked. Verified against the live pooler: the context completes a
  TLS 1.3 handshake, public roots alone are refused, and a wrong hostname is
  refused. It is attached by
  a `do_connect` listener rather than `connect_args` because `connect_args` is
  evaluated at import, and building an `SSLContext` at import kills the test
  suite on the maintainer's machine (Norton's `SSLKEYLOGFILE`, same root cause
  as `dev_loop.py`). `tests/test_db_tls.py` pins all of it, the CA fingerprint
  included.
  **The app connects as `splitdec_app`, not as the project owner** (migration
  `20260904100000`). `postgres` owns all eight tables and additionally carries
  CREATEROLE, CREATEDB, BYPASSRLS, membership in anon/authenticated/service_role
  and SELECT/UPDATE/DELETE on `auth.users`, `auth.sessions` and
  `auth.refresh_tokens`; `splitdec_app` holds the four DML verbs on those eight
  tables, EXECUTE on one function, and nothing else in any schema. This changes
  no authorization — FastAPI is still the only boundary and RLS stays off — it
  only shrinks what a leaked `DATABASE_URL` is worth. Three things follow:
  - **The role is created out of band and lives in no migration.** The statement
    carries a password and `supabase/migrations/` is public. The migration only
    grants, and creates a **NOLOGIN** stand-in if the role is absent so a branch
    or a restore still applies. `postgres` is unchanged, still runs migrations,
    and is the rollback.
  - **Account deletion goes through `public.delete_auth_user`**, a
    `SECURITY DEFINER` wrapper, because `postgres` holds `DELETE` on `auth.users`
    *without* grant option and so cannot pass it on — the wrapper is mandatory,
    not stylistic. `routers/users.py` branches on the dialect (the SQLite suite
    fakes the `auth` schema and has no functions), which means **the production
    statement is not covered by the default test suite**; `tests/test_locks_pg.py`
    calls the wrapper as the app role, and that needs `TEST_DATABASE_URL`.
  - Anything new the app touches — a table, a sequence, a schema — needs a grant
    added here, or it is `permission denied` in production. `tests/test_grants_pg.py`
    checks both directions: every table reachable, and nothing held outside
    `public`, no role attributes, no memberships.
- **Auth**: Supabase Auth (PKCE) on the frontend — Google OAuth **plus email/password** (signup
  with confirmation required, forgot/reset flow); backend verifies JWTs statelessly
  (`auth.py`: ES256 via JWKS) and reads only the `sub` claim — provider-neutral.
  The `alg` header may only *select* from `SYMMETRIC_ALGORITHMS`/`ASYMMETRIC_ALGORITHMS`;
  anything else (including `none`) is refused before a key is fetched, because that header
  travels inside the token being checked. **HS256 is off unless `ALLOW_LEGACY_HS256`
  is set**: the project's JWKS serves a single ES256 key (checked, not assumed), so the
  symmetric path verified nothing the app issues while keeping a *symmetric* credential
  live — anything that can read a shared secret can mint tokens with it, where the JWKS
  key can only check them. Turning it back on takes the flag **and** the secret.
  `SUPABASE_URL` has no default for the same reason: it is the trust anchor, and the old
  fallback to the production project meant a preview or a fork trusted our issuer while
  reading someone else's database. It is cross-checked against `DATABASE_URL`'s project
  ref at first use, and a mismatch refuses to verify anything. The ref is read out of the
  pooler DSN's `<role>.<ref>` username, for **any** role — it used to say `postgres`
  literally, which meant the F9 role swap would have made `project_ref` return `None`,
  and no ref reads as "nothing to compare". A Supabase host whose ref cannot be read is
  now a refusal rather than a skip, because that is the shape this check takes when it
  quietly stops working.
  **`exp`, `aud` and `sub` are required claims, not merely checked ones**, and
  `iss` is pinned to `{SUPABASE_URL}/auth/v1` wherever that URL is known (always,
  on the asymmetric path). PyJWT honours a claim it finds and ignores one it does
  not, so a correctly signed token that simply omitted `exp` used to validate for
  ever. `issuer=` and `require` are independent — `issuer=` alone still accepts a
  token with no `iss` — which is why `auth.py` sets both. The issuer string was
  read off the project's own `/auth/v1/.well-known/openid-configuration`, not
  guessed; a wrong value there is a 401 for every user at once.
  **Signing keys are not cached individually.** PyJWT keeps two caches: the JWKS
  response, on by default and good for five minutes, and behind `cache_keys=True`
  an LRU of resolved keys with no expiry at all. That flag was set here for a year
  and bought nothing the response cache was not already giving, while a key
  Supabase revoked went on verifying tokens for as long as the instance stayed
  warm. Do not pass it again; `tests/test_auth.py::TestSigningKeyCache` pins both
  halves, since switching the response cache off instead would fetch the JWKS on
  every request.
  **A token claiming `is_anonymous` is refused**, absent and `false` both passing.
  An anonymous sign-in carries the same `aud` and `role` as a real one, so nothing
  else in `verify_jwt` separates them; the three things that actually stop such an
  account existing — the provider being off, every route needing a `public.users`
  row, and the mirroring trigger being unable to write one without an email
  address — all live elsewhere, and the last is a `NOT NULL` column rather than a
  decision.
  Unauthenticated failures answer generically ("Authentication is unavailable") and put
  the specifics in the log — an anonymous 500 naming an environment variable hands a
  stranger the deployment's shape for nothing.
  `tests/test_auth.py` is the only place the boundary
  is exercised for real — every other API test overrides `verify_jwt`, so a change here that
  breaks authentication will not show up anywhere else in the suite.
  **RLS is intentionally disabled** — the FastAPI layer is the sole authorization boundary; the
  Data API's anon/authenticated grants were revoked by migration. Do not enable RLS and do not
  weaken the FastAPI checks. Password-auth specifics: `signUp` must pass `full_name` in metadata
  (the `handle_new_user` trigger reads it); the client's `MIN_PASSWORD_LENGTH`
  (`src/lib/authErrors.ts`) must match the dashboard's minimum length, **12**, and
  that length is the whole policy — "Password Requirements" is deliberately left at
  "No required characters", because composition rules are satisfied predictably and
  NIST SP 800-63B tells verifiers not to impose them. The blocklist that guidance
  assumes in their place is Pro-only and this project is on free, which
  `docs/supply-chain.md` records as an accepted risk; `errWeakPassword` names a
  length and nothing else, so turning classes on later makes it untrue.
  **Setting a password revokes every other session** — `updatePassword` follows
  the update with `signOut({ scope: "others" })`, because Supabase does not: its
  `UpdateUser` writes the password and never touches the session table, so
  without this the one gesture somebody reaches for when they think another
  person is in their account would change nothing for that person. It signs
  their own other devices out too, which is the intent. The failure is reported
  and never thrown — the password has already changed by then.
  Signup/reset responses stay enumeration-safe, and **that no longer depends on the
  dashboard**: an address that already has an account is caught by
  `isEmailAlreadyRegistered` and shown the same check-your-email screen a new one
  gets, so Supabase's "Confirm email" toggle drifting off changes nothing here.
  **`/reset-password` can legitimately refuse.** "Secure password change" is on in
  the dashboard, so Supabase turns down a password change from a session older than
  24 hours unless the request carries an emailed one-time code, which we never
  send — that is the control against somebody who has taken a live session, since a
  check in our own form would be skipped by anyone calling supabase-js directly.
  Recovery sessions are exempt inside Supabase (`if !session.IsRecovery()`), so
  forgot-password is untouched, and `errReauthNeeded` says where a new password
  actually comes from. `docs/supply-chain.md` holds the setting itself.
  `/reset-password` is
  registered in **both** auth branches of `App.tsx` — the recovery link lands signed-out, the SDK
  exchanges the code, and the app re-renders signed-in on the same path (screen sits outside
  `Layout`). Production auth emails need Supabase custom SMTP via Resend.

### Money invariants (the core of this codebase)

- All money is `NUMERIC(14,4)` in Postgres, `Decimal` in Python, and **string** in JSON
  (`"120.5000"`). Money never passes through binary floats anywhere: frontend math uses
  integer minor units (`toMinorUnits`/`fromMinorUnits` in `src/lib/currency.ts`) or BigInt.
- Split computation (`api/_src/splits.py`): banker's rounding at the currency's precision
  (`currencies.py`: JPY=0, most=2, KWD=3), remainder distributed one smallest unit at a time
  starting with the payer, so splits always sum exactly to the total. Splits are non-negative
  (Pydantic + DB CHECK) — when the remainder is *removed*, participants whose share is
  already under one unit are skipped, or a 0%-share payer would go negative.
- Balances (`api/_src/balances.py`): one CTE statement built with SQLAlchemy Core (portable to
  SQLite for tests), then per-currency greedy matching in Python. **Deviation from spec v6**:
  the spec's settlement signs (`+received −sent`) are inverted; the code uses `+sent −received`
  (settling must reduce debt). Soft-deletes filter expenses and settlements independently.

### Concurrency protocol (group row locks)

Every ledger mutation (expense/settlement create, update, **and soft-delete**) takes a
`FOR SHARE` lock on the group row; member removal, group deletion, and account deletion take
`FOR UPDATE` and re-check zero balances while holding it. The lock rides on the authorization
query (`deps.py`: `require_membership`/`get_*_for_member` with `lock=`, `lock_groups_exclusive`
for multi-group in sorted order). Any new balance-changing endpoint must join this protocol.
SQLite silently drops these clauses — that's why `test_locks_pg.py` exists.

Answering an invitation stays **out** of that protocol on purpose. Accept, decline and cancel
each read a PENDING row and then write a different status, which without atomicity lets a
cancelled invitation still grant membership; the fix is a conditional update
(`invitations._resolve_invitation`: `status = 'PENDING'` in the `UPDATE`, `rowcount` decides,
404 for the loser), **not** `SELECT … FOR UPDATE`. Locking the invitation before the caller's
decision inverts the order `delete_group` takes — group row first, its invitations second —
and deadlocks against it. For the same reason `accept_invitation` flushes the new membership
before touching the invitation: the FK insert takes the group's `FOR KEY SHARE` first.

**That flush is also the one place a ledger race surfaces as an exception rather
than a rowcount**, so it is caught: the group can be deleted between the unlocked
read and the insert (the FK then finds no group row), and a concurrent accept of
the same invitation collides on the membership primary key. Both are an
`IntegrityError`, both mean the invitation is no longer there to answer, and both
answer **404** — the same thing the loser of either race would have been told a
moment later. Unhandled, they were a 500.

**Creating** one is the other way round and does join the protocol: `invite_to_group`
takes the group's `FOR SHARE`, because an invitation now outlives its inviter only until
they leave (`remove_member` and `delete_account` cancel what they issued), and that sweep
runs while holding the group's `FOR UPDATE`. Unlocked, the caller's own deletion could
commit between this endpoint's membership read and its insert, leaving a live invitation
issued by an account that no longer exists. Group row first, the quota's advisory lock
second — the order `create_expense` takes — and released by the commit that precedes the
Resend call, so it never spans the provider.

**A ledger mutation may not leave a non-member with a non-zero balance**
(`deps.ensure_no_outsider_debt`, called after the flush in expense/settlement update and
delete). Removal already requires a zero balance, but nothing kept it there: withdrawing an
expense a departed member paid for — or rewriting its splits without them, which is the only
thing a rewrite *can* do, since splits may name only current members — moves their net off
zero, and they cannot settle it or be settled with. The group then also fails the zero-balance
check that group deletion needs, so a single delete could strand it forever. The way out of
that state, and the reason the check is a flat refusal rather than a comparison, is to invite
the person back.

### Write quotas (`api/_src/ratelimit.py`)

Row-creating endpoints are volume-braked, counting rows in the database (never
process memory — the API is a serverless function with several instances and
constant cold starts). Expense/settlement creation (100) and group creation
(25) are capped **per caller** over a 24h window; invitations keep their own
three (per inviter / per recipient / global). All of them use the dialect-aware
`window_cutoff` helper, because SQLite (tests) stores naive UTC where Postgres
stores TIMESTAMPTZ.

**Changing a ledger row has its own window** (`MUTATION`, 300 per caller per
24h, migration `20260912000000`). Creating was capped and editing was not, and
an edit is not free: it revalidates the participants, recomputes every split
and re-reads the group's balances, so a caller who had spent their 100 creates
could still rewrite one expense in a loop indefinitely. Charged by both update
endpoints and both soft-deletes. A new `kind` value is a schema change — the
`write_events_kind_check` constraint enumerates them — so a fifth one needs a
migration too.

**That window charges for the work, not for the outcome, and it is the one
place this and the attribution record disagree on purpose.** A PATCH that
changes nothing is *not* recorded as an edit (see API contracts) because
pressing Save without editing must not accuse anybody — but it does spend a
slot, because the server did all of that work anyway. Charging only on a real
change would make no-op PATCHes free and unlimited, which is exactly the loop
the cap exists to close.

**Every one of those windows counts `write_events`** — one append-only
tombstone per quota-consuming write, charged by `record_write()` — and not the
rows being created. That indirection is the whole point: deleting a group is a
*hard* delete that takes its expenses, settlements **and invitations** with it,
and any member may delete a settled group, so while the quotas counted real
rows, create → fill → delete → repeat reset all of them. Nothing cascades to
`write_events`.

The per-recipient invitation window is keyed by `recipient_key(email)`, a bare
SHA-256 — the window only ever needs equality, so the address itself is never
written. That is **not** anonymisation and the docstring says so: an email is
guessable, so the digest is reversible by anyone who can read the column. It is
acceptable because that same reader can read `public.users.email` in plaintext
anyway, because `record_write` prunes the rows after about a day, and because
account deletion nulls the column on rows naming the departing address, so the
erasure promise does not rest on the digest. Unpeppered for the same reason: an
HMAC would cover only never-registered invitees, only for a day, at the price
of a secret that must exist everywhere, fail closed when it does not, and reset
every recipient window on rotation.

Four rules any new quota must follow:

- **Count tombstones, not the rows you are protecting.** Soft-deleted rows
  keeping their `created_at` is not enough — the group above them can vanish.
- **Answer an idempotent replay *before* the quota.** A client retrying a
  request whose response it never saw has already spent its slot, and a 429
  there leaves it unable to discover whether the row exists — the one thing
  `Idempotency-Key` is for. Both create endpoints look the key up first.
- **Charge inside the endpoint's transaction.** `record_write` only adds to the
  session, so a validation failure or the idempotency-race rollback takes the
  charge with it and a replay is never charged twice.
- **Serialize the count against the charge.** They are two statements, so
  without a lock N parallel requests all count the same N−1 rows and all
  insert. Each `enforce_*` opens with `_hold_window`, a
  `pg_advisory_xact_lock` released by the same commit that stores the event —
  keyed per caller for the per-caller windows, and to a constant for the
  invitation ones, whose recipient and global limits count rows written by
  *other* callers. Never the session-scoped variant: the connection goes back
  to the transaction pooler at commit with nobody left to release it.

`record_write` also opportunistically prunes rows that have aged out of every
window — a serverless function has nowhere to hang a cron. That sweep is
deployment-wide rather than per caller, with `SKIP LOCKED`, a deterministic
`id` order and a batch cap, so concurrent sweeps step over each other instead
of queueing or deadlocking. It has to be: `delete_account` keeps the caller's
`INVITE` tombstones (see below), and nobody would ever come back for them
under a caller-scoped sweep.

Deliberately **no global cap** on the ledger or group windows: a
deployment-wide ceiling would turn one abusive account into an outage for
everyone. Invitations do carry one, because the resource they burn — the
sending domain's reputation — is shared and cannot be bought back.

That shared resource is also why **account deletion does not clear the
`INVITE` tombstones**. The per-caller `LEDGER`/`GROUP` rows go (nothing else
counts them, and sign-in is revoked), but the invitation rows feed the global
and per-recipient windows, so dropping them would make deletion the reset
button: invite an address its three times, delete the account, sign up again,
repeat. Rows keyed to the *deleted* address as a recipient keep their slot but
lose their `recipient_hash`, which is the only thing left on file derived from
an address the users row no longer holds.

A second, narrower lock covers *membership creation* against account deletion:
`get_active_user(..., lock=)` locks the `users` row — `"shared"` in every endpoint that hands
the caller a new membership (group create, invitation accept), `"exclusive"` in
`delete_account`, taken **before** the group snapshot and held to commit. Otherwise a
membership committed mid-deletion escapes both the balance check and the unscoped delete, and
membership-gated routes don't re-check liveness. `"exclusive"` is `FOR NO KEY UPDATE`, not
`FOR UPDATE`, on purpose: `FOR UPDATE` conflicts with the `FOR KEY SHARE` that FK inserts take
on `users` rows, which deadlocks against an expense write already holding the group lock.

### Error monitoring (Sentry)

Two projects in the `split-dec` org, both in Sentry's **EU region**
(`de.sentry.io` — which is what lets `legal.ts` say Germany): `splitdec-frontend`
for the browser, `splitdec-api` for the function. **Errors only** — no tracing,
no session replay. Speed Insights already measures performance, and a replay of
this app is a recording of somebody's ledger.

**A missing DSN is the off switch.** `VITE_SENTRY_DSN` (browser) and `SENTRY_DSN`
(function) are read at init; nothing initialises without them, which is how dev,
vitest and CI stay out of the issue stream with no second flag to keep in sync.
The browser DSN is public by construction — it ships inside the bundle either
way — so it lives in `.env.production` next to the Supabase publishable key; the
API one is Vercel-only. The browser key carries a **100/hour** server-side rate
limit, because a public DSN is a public write endpoint.

**Nothing reaches Sentry unredacted** (`src/lib/monitoring.ts`,
`api/_src/monitoring.py`). Not defensive tidying — the SDK defaults collect
precisely what the rest of this codebase works to keep out of logs:

- `location.href` on the OAuth callback is `?code=<live authorization code>`,
  and on the recovery link `#access_token=`. Query and fragment are therefore
  dropped **whole**, never filtered per parameter — an allow-list of safe
  parameters is a list somebody has to maintain against every future endpoint.
- Click breadcrumbs serialize `aria-label`, `title`, `name` and `alt` off the
  clicked element (`_htmlElementAsString` in @sentry/core), and `ExpensesTab`
  puts the expense *description* in an aria-label. Attribute **values** are
  stripped from the selector; the structure stays.
- Server side, `include_local_variables=False` is the single most load-bearing
  option in the file: one frame up from any database error sits `DATABASE_URL`
  with the pooler password, and inside `auth.py` the caller's raw bearer token.
  `max_request_body_size="never"` for the same reason — an expense POST *is* the
  ledger. Headers are **allow-listed, not deny-listed**: `send_default_pii=False`
  covers `Authorization` and `Cookie`, but the SDK has never heard of
  `X-Health-Key`.
- **The error's own message**, which none of the above touches and which this
  codebase does not write. A unique violation on `users.email` arrives as
  `DETAIL: Key (email)=(someone@example.com) already exists`. Same for
  `logentry`: `LoggingIntegration` is on by default and `integrations=[...]`
  *adds* to the defaults rather than replacing them, so any future
  `logger.error()` becomes an event body. **Breadcrumb text is held to the same
  standard**, and that is the point rather than an extra: `logger.warning`
  becomes a breadcrumb where `logger.error` becomes an event body, and in the
  browser the default `console` integration puts `ErrorBoundary`'s own
  `console.error("Unhandled error", …)` there — so scrubbing only the loud door
  let the *level of a log call* decide whether an address shipped. All of them
  get UUID **and** email redaction; stack frames are left alone, because they
  name our own files and `include_local_variables=False` means they carry no
  values.

Identifiers are matched by **shape** — every id in `models.py` is a UUID — rather
than by route list, so a new route is covered without anyone remembering to come
back. That is a deliberate divergence from `insightsRoute` (src/App.tsx) and
`fold_route` (routers/reports.py), which fold *named* patterns because their
buckets have to line up with each other; nothing in monitoring has to line up
with anything, so it can afford the stricter rule.

The browser SDK costs **~29 kB gzip on the first-paint chunk** (measured: entry
went 20.8 → 49.9 kB gzip) and is deliberately **not** in the vendor allow-list.
Source maps are generated only when `SENTRY_AUTH_TOKEN` is set, emitted
`hidden`, and deleted from `dist/` after upload — a served `.map` is the whole
bundle, readable, on the origin holding the Supabase session. Two non-obvious
things guard that, both found by building with a deliberately invalid token:

- **The service worker's map is suppressed separately** (`workbox.sourcemap:
  false`). vite-plugin-pwa writes `sw.js` in `closeBundle`, *after* the Sentry
  plugin's `writeBundle` has swept `dist/` for `*.map`, so `sw.js.map` and
  `workbox-*.js.map` outlived the sweep and shipped. Not emitting them beats
  deleting them later and trusting the hook order never changes.
- **An upload failure must not fail the build.** The plugin throws by default
  ("stopping the bundling process", per its README), which would let an expired
  token or a Sentry outage block a deploy of the app itself — and a deploy is
  how this app recovers from its own incidents. `errorHandler` downgrades it to
  a build-log warning. The accepted cost is that a silently missing upload
  surfaces only as minified frames on the next crash.

**A failed delivery writes no log line, so an unreachable Sentry and a
blameless app look identical.** The transport records the lost event and
re-raises into `capture_internal_exceptions()`, which swallows it — there is no
"unable to send" anywhere. That is not hypothetical: for the first three months
the only event `splitdec-api` ever held was a smoke test run from a laptop,
while the function logged `SSLEOFError: UNEXPECTED_EOF_WHILE_READING` against
`/envelope/` every few minutes and never once said it had given up. Out of that
came `GET /api/health/sentry`, because "no events" needed to stop being
ambiguous: it measures the handshake itself rather than asking the SDK, which
is the one party that cannot tell you it failed. **Never read an empty issue
stream as good news without running it.**

**The cause is the freeze, and it took two attempts to find.** `keep_alive=True`
was the first, on the theory that a pooled connection dies idle across the
freeze; it is still set, because it is right for a connection idling while the
process *runs*, but it did not change the log and cannot — keep-alive probes
come from the guest kernel, which is frozen along with everything else. The
actual mechanism is one layer up: Sentry sends on a background thread, the
platform freezes the instance the moment the response is written, and the send
is caught mid-flight. It then advances only when the next request thaws the
instance, by which point the socket is gone. Proof is in the retry timing —
urllib3's backoff on that pool is zero, yet production showed a single chain
stepping `Retry(total=2)` → `1` → `0` across three invocations fifteen minutes
apart, one step per incoming request. After the third the event is dropped, in
silence.

Two changes close it, and the first is the surprising one. **Release health is
off** (`auto_session_tracking=False`): the SDK opened a session per request and
posted aggregates every 60s, so the Sentry uptime monitor's five-minute ping of
`/api/health` was manufacturing nearly all the Sentry traffic — and all the
retry warnings — for a feature nothing here reads. **And `flush_on_response`**
(`monitoring.py`, applied in `api/index.py`) waits for a captured event to
reach Sentry before the reply ends, which is what Sentry's own AWS Lambda and
GCP integrations do for the same reason. It **must** wrap the app object: the
Starlette integration patches `Starlette.__call__`, so `SentryAsgiMiddleware`
sits outside every middleware added with `add_middleware`, and a flush
installed the ordinary way would run before the capture and flush nothing. Only
requests that captured something wait, and never longer than `FLUSH_TIMEOUT` —
the transport's own timeout is 30s, which is not a number to add to a request
that has already answered.

That wrapper is also why `api/index.py` exports a plain `async def` taking
exactly `(scope, receive, send)`: Vercel picks ASGI over WSGI by checking
`inspect.iscoroutinefunction` and counting required positional parameters
(`vercel_runtime/resolver.py`), so an extra argument or a default would have
the app served as WSGI — a per-request runtime failure, not a build error.
`tests/test_monitoring.py` pins the shape, because the suite otherwise only
ever drives the unwrapped `_src.main.app`.

Delivery confirmed from production on 2026-09-08: `tls: "ok"` and six of six
probe events delivered, the first events `splitdec-api` has ever received from
the function rather than from a laptop.

`connect-src` in `vercel.json` carries the org's ingest host pinned exactly
(`https://o4512011830886400.ingest.de.sentry.io`); `*.ingest.sentry.io` would
admit every other tenant on the platform. Asserted in `tests/test_vercel_config.py`,
which also refuses any wildcard host in `connect-src`.

Sentry is a **processor**: adding it was a `src/lib/legal.ts` change with a
`LEGAL_UPDATED` bump. It receives the reporting IP and stores a **city-level
location** derived from it (observed, not assumed — `user.geo` on the first
event), which is why the policy discloses coarse location rather than claiming
anonymity. Turning on *Prevent Storing of IP Addresses* in the project's
Security & Privacy settings would narrow that; it is a dashboard-only toggle.

### API contracts worth knowing

- **Every API response carries `Cache-Control: no-store`** (`main.py`, one
  middleware). No header at all does not mean "do not cache" — it means the
  browser decides, and what it stores is a copy of somebody's ledger left in a
  disk cache that outlives the session. Shared caches were never the exposure
  (RFC 9111 §3.5 already bars them from storing a response to an
  `Authorization` request); the local disk is. `no-store` alone: `private`
  addresses only those already-excluded intermediaries, and `Pragma` is a
  request header with no meaning on a response. The service worker is a
  separate store that no header reaches, and is kept out of `/api/` in
  `vite.config.ts` — `tests/test_cache_headers.py` asserts both halves.

- `POST .../expenses` and `.../settlements` require an `Idempotency-Key` UUID header; replays
  return 200 with the existing row, **scoped to the path group** (cross-group key reuse → 409).
  The client side of that contract is `useIdempotencyKey`: one key per open form, resent on
  every attempt. A retry that mints a fresh key is not a retry — if the first request landed
  and only its response was lost, the second one records the entry a second time.
- **Ledger rows record who entered them and who last changed them**
  (`created_by` / `updated_by` / `updated_at` on `expenses` and `settlements`,
  migration `20260911010000`, stamped through `deps.record_edit`). Distinct from
  `paid_by_user_id`, which is a claim about money rather than a statement about
  authorship — any member may create, edit and withdraw any row in their group, and
  nothing used to record which of them did. Four things worth knowing:
  - **Every mutation stamps, including the soft-delete.** Withdrawing somebody
    else's expense is the most disputable act available, and it is the one stamp
    no screen ever shows — deleted rows are not rendered — so it only ever answers
    a question asked afterwards.
  - **`updated_by` is stored even when the author edits their own row.** The
    column records what happened; the UI decides what is worth saying, and shows
    it only when `updated_by` differs from `created_by`. Do not collapse those
    two decisions into one by leaving the column blank.
  - **A request that changes nothing is not an edit.** Both update endpoints
    compare against the stored row — the metadata fields, and for the financial
    branch the computed shares too — and stamp only on a real difference.
    Without that, Bob opening Alice's expense and pressing Save marks it
    "edited by Bob", which is a false positive on the one signal the record
    exists to give. A delete always qualifies.
  - **It is shown in the row's own view (`ExpenseFormModal`, `SettleUpModal`),
    not in the list.** The list is scanned rather than read, and most edits are somebody
    fixing their own typo, so a permanent badge on every one of them gives
    ordinary collaborative behaviour an auditing tone. The discovery path is a
    *balance* looking wrong, not a line in a list — and it ends with one expense
    open, which is where the answer is. The list placement was tried first and
    measured out: that row's secondary line has 117px at 375px wide, so even
    "Alice paid · edited by Bob" truncated and a Polish name pushed the notice
    off the row entirely.
  - **No backfill, deliberately.** Rows older than the migration have no author,
    and inferring one from the payer would invent a fact. A row with
    `created_by IS NULL` and a non-null `updated_by` still shows its edit — the
    change is known even though the authorship is not.
  - **A deleted account keeps its attribution.** `updated_by` points at
    `public.users`, which account deletion anonymizes rather than deletes, so the
    reference stays valid and renders as "Deleted user" exactly like the expenses
    that account took part in.
  There is deliberately **no version history** — these columns answer "who last
  touched this", not "what did it say before". An audit table is the answer to the
  second question and a much larger pile of retained personal data; it waits until
  somebody actually needs it.
- `PATCH /expenses/{id}` is partial: metadata (description/category/expense_date) applies
  independently; the five split-affecting fields (split_type, total_amount, currency,
  paid_by_user_id, splits) are all-or-nothing and trigger a full splits rewrite. The frontend
  (`ExpenseFormModal.financialsUnchanged`) sends metadata-only bodies when financials are
  untouched — required because reconstructed percentages are rounded and must not be resubmitted.
- Membership is invitation-based (`group_invitations`, matched by lowercased email so people
  who sign up later see their invites). The direct add-member endpoint and `GET /users/search`
  were removed (the latter was an email-registration oracle — deliberate spec deviation).
  **Answering is authorized by `invited_user_id` alone once that column is set**
  (`invitations.invitee_predicate`), and by the address only while it is NULL — the
  state an invitation sent to an address with no account yet sits in. It used to be an
  OR of the two, which meant whoever held the mailbox *next* could answer an invitation
  bound to somebody else: addresses change hands (a user edits theirs and the old one is
  free to register; a corporate address is reassigned) and nothing here expires, so the
  window was unbounded. Revocation keeps the OR on purpose — revoking a capability too
  widely is safe, granting one too widely is the bug.
  **An invitation is also revoked when the member who *issued* it leaves** — `remove_member`
  cancels it for that group, `delete_account` across all of them. Acceptance checks the
  invitee and never the inviter, so an invitation outlives the membership that authorized
  it: invite an address you control, get removed, accept afterwards, and the group readmits
  a stranger with nobody left in it having agreed to that. The authority to invite is
  membership, so it ends with the membership; an invitation still wanted is one a current
  member can send again.
  **The invite endpoint must stay uniform for the same reason**: same response shape, same
  email attempt, same latency whether or not the address has an account (anyone can create a
  group and invite arbitrary addresses). Never reintroduce `user_exists`/`email_sent`/
  `invited_user_id` in a response. Sending is quota-limited (per inviter / per recipient /
  global, 24h — counted from `write_events`, see above) and skipped entirely for an
  address that has unsubscribed (see Email) — which changes the send and nothing
  else: the row, its visibility and the sender's quota charge are all unaffected. Cancelling sets
  `status='CANCELLED'` rather than deleting: the quotas no longer depend on that, but the
  row is the group's record that the invitation happened, and the partial unique index
  covers only `PENDING` rows so re-inviting still works. Cancelling, accepting and declining
  are all conditional on the row still being `PENDING` and answer 404 when it is not (see the
  concurrency section).
- **The settlements list is paged** (`{items, limit, offset}`, 20 a page, same
  envelope as expenses). It used to return every settlement a group had ever
  recorded, on every load, and nothing caps how many accumulate — the ledger
  quota bounds the rate, not the total. It was the only list here that grows
  without a ceiling: pending invitations are held to one per address by the
  partial unique index, and a member list does not grow on its own, so both of
  those stay unpaged on purpose. The change from a bare array was breaking, and
  acceptable only because the sole client ships in the same deploy.
- **A group holds 100 people** (`deps.MAX_GROUP_MEMBERS`), and a **seat** is a member
  *or* a PENDING invitation. Two checks, and they count differently on purpose.
  `invite_to_group` counts both and refuses at 400 — a courtesy, so the refusal reaches
  the member who can act on it instead of the invitee, who would otherwise be turned
  away by a link they were sent. `accept_invitation` counts members only (the invitation
  being answered already holds a seat) and is the actual gate: two invitations racing for
  the last seat both pass the first check. Both sit behind `deps.hold_group_seats`, an
  advisory lock keyed to the group — count-then-insert is two statements, exactly like
  the write quotas, and without it N parallel joins all count the same N−1 seats.
  Deliberately **advisory rather than the group row lock**: `FOR UPDATE` here would make
  joining a group queue behind every expense write on it, and the reverse, for a count
  that has nothing to do with money. Its namespace is 5; `ratelimit._LOCK_SPACE` owns
  1–4. The accept path takes `FOR SHARE` on the group first so the order stays
  user → group → invitation, the one `delete_group` and `delete_account` take. Seats are
  counted **after** the replay check, like the send quota — a retried invitation must get
  its row back, not a 400 about a group it did not overfill. The number is a product
  decision, not a threshold: it is easier to raise than to lower, since lowering it
  strands groups already over the line. The client copy is `src/lib/limits.ts`, and
  `MembersTab` deliberately counts **members only** with it: the member list arrives
  with the group while the pending count arrives from a query, so counting both renders
  the invite form as available and withdraws it a moment later, and waiting for the
  query takes the button away from every group for the length of a fetch. The UI
  answers the half it knows synchronously; a group at 99 members with an invitation
  outstanding is offered the form and refused by the server.
- **A group is never left without members.** `remove_member` refuses to remove the last one
  (400, pointing at group deletion, which is the same gesture with a confirmation behind it);
  `delete_account` cannot refuse on the group's behalf, so it purges any group its departure
  empties. Every route into a group is membership-gated, so a memberless one can never again
  be read, settled or deleted by anybody. **`delete_account` does not count the SplitDec
  system user as somebody left** (see The welcome group): it never signs in, so a group whose
  only human has just left is as unreachable as an empty one.
- Account deletion anonymizes `public.users` (email gets `DELETED_EMAIL_SUFFIX` from `deps.py`)
  and deletes the `auth.users` row; endpoints not gated by membership must call
  `get_active_user` because old JWTs stay valid until expiry. It also drops pending
  invitations addressed to that email (they are unexpiring capabilities matched by email —
  the next holder of the address would inherit them), cancels the pending ones it *sent*
  (see above; CANCELLED rather than deleted, because the recipient is a third party and the
  row is still the group's record), and anonymizes the address on answered ones.
- Expense splits rewrite pattern: clear the collection and `flush()` **before** assigning
  replacements, or `UNIQUE(expense_id, user_id)` fires (inserts flush before deletes).

### Frontend patterns

- **Routes are code-split** (`App.tsx`): `LandingPage`, `LegalPage`,
  `ResetPasswordPage` and `GroupPage` are `lazy`, split along the auth branch so
  each user type downloads roughly its own half. `LoginPage`, `GroupsPage`,
  `Layout` and `NotFoundPage` stay eager — they are on one branch's first paint.
  Any new lazy route must sit inside one of the two `Suspense` boundaries, and
  `GroupsPage` warms the `GroupPage` chunk from the same hover/focus handler that
  prefetches group data (same import specifier, so Rolldown emits one chunk).
- **The vendor chunk is an explicit allow-list** (`vite.config.ts`
  `codeSplitting`, named `advancedChunks` before rolldown 1.2 — the old key
  still works but warns on every build): React, React-DOM, the router, TanStack Query and
  supabase-js — the runtime both auth branches need on first paint, so a
  deploy that only touches app code leaves ~470 kB cached. It is a rolldown
  group matched by regex, not the object form of `manualChunks` that vite 6
  took: vite 8 accepts only a function there and fails the build on an object
  ("Invalid type: Expected Function but received Object"). Do **not** widen it
  to "everything in `node_modules`": `lucide-react` is tree-shaken per route,
  and hoisting it would drag `GroupPage`'s icon table into the chunk a
  signed-out visitor downloads, undoing the route splitting above. The dev
  server applies none of this — check chunking with `npm run build` then
  `npm run preview` (which serves `dist/`), never `npm run dev`.
- **Tailwind's sources are declared, not auto-detected** (`src/index.css`):
  `@import "tailwindcss" source(none)` followed by `@source "../index.html"`
  and `@source "./"`. Do **not** restore the bare `@import "tailwindcss"`.
  Auto-detection scans the project for anything not gitignored, which on
  Vercel reached the Python packages the build had just installed and minted
  utilities out of their comments — `.[ticket:489]` from sqlalchemy's mysql
  dialect, `.[lower:upper]` from asyncpg's array codec. It never reproduced
  locally, where `.venv/` is gitignored, so production quietly served ~944
  bytes of CSS the local build did not generate. Two things there are
  load-bearing: the `@source` lines must sit **after** both `@import`s,
  because `@import` has to precede every other rule or the parser drops it and
  the second one is the Manrope font; and a new location holding class names
  has to be added to that list, or its classes silently never generate.
- **Measurement lives in `App.tsx`, inside both auth branches**:
  `<Analytics beforeSend={foldAnalyticsUrl} />` (Vercel Web Analytics) and
  `<SpeedInsights route={insightsRoute(...)} />`.
  Both must stay inside `App` rather than `main.tsx` — `main.tsx` renders
  nothing when `enforceCanonicalOrigin()` says we are leaving, and a beacon
  fired from a non-canonical origin is exactly what that guard exists to
  prevent. `insightsRoute` folds `/groups/<uuid>` to `/groups/[groupId]`;
  **a new dynamic route has to be added to it**, both so the busiest screen
  isn't split into one bucket per group and because the Privacy Policy states
  group identifiers never reach the measurement. Speed Insights takes its
  route as a prop, but Web Analytics reads `location.href` itself, so the same
  fold reaches it only through `foldAnalyticsUrl` — the `beforeSend` hook,
  which runs `insightsRoute` over the parsed pathname so a new dynamic route
  is still added in exactly one place, and returns `null` (dropping the event)
  rather than reporting a URL it could not parse. Neither product sets cookies,
  which is what lets the policy keep saying no consent banner is needed — see
  `src/lib/legal.ts`, whose header carries the rule that any change to
  processors, storage or retention changes that file and bumps
  `LEGAL_UPDATED`.
- **Checking the measurement is alive** cannot be done by curling the endpoints:
  the catch-all rewrite turns *any* unregistered `/_vercel/...` path into a 200
  `index.html`, so a dead collector and a live one both look like success. What
  discriminates them is a GET on the collector path — `/_vercel/insights/view`
  and `/_vercel/speed-insights/vitals` answer with Vercel's own
  `{"code":"not_found"}` JSON, because the route exists and only rejects the
  method, while a path the platform does not own falls through to the SPA and
  returns HTML. Ground truth is the data:
  `vercel metrics vercel.speed_insights.lcp_count --since 1d --prod` (names via
  `vercel metrics schema vercel.speed_insights`; needs a recent CLI). Two traps
  there. Ingestion lags a minute or two, so `No data found` straight after the
  traffic means nothing — the query that came back empty at 12:18 returned the
  same points at 12:19. And only TTFB is sent on load; LCP/FCP/CLS/INP wait for
  the page to be hidden, so a single foreground visit reads as a broken install.
  Query `vercel.analytics_pageview.count` first as a control: it shares the auth,
  scope, project and `--prod` filter, so if it has rows and Speed Insights has
  none, the difference is real rather than a mistake in the query.
- A top-level `ErrorBoundary` (`main.tsx`, inside `I18nProvider` so its fallback
  is translated) reloads **once** on a chunk-load error: a client on an old app
  shell 404s its next lazy import after a deploy rotates the chunk hashes, and
  `Suspense` only covers a *pending* import, not a rejected one. A
  `sessionStorage` cooldown stops a genuinely missing chunk becoming a refresh
  loop; ordinary render errors skip the reload.
- **Routing invariants that look like bugs but are not.** `/privacy` and
  `/terms` are registered in *both* auth branches (like `/reset-password`) so
  they resolve for signed-out visitors — Google's OAuth review fetches them
  cold. `/unsubscribe` is there for the sharper version of the same reason: the
  person following that link has, in the ordinary case, never had an account. The signed-out catch-all renders `LoginPage`, **not** the 404: an
  invitation deep link lands signed-out, and the focused sign-in screen is what
  carries the visitor to the original URL afterwards. Only the signed-in
  catch-all renders `NotFoundPage`.
- Empty states share `EmptyState`; pass `action` where there is an obvious next
  step (suppressed on the expenses tab when a payer filter is what emptied it).
- **`VITE_API_URL` is a dev-only escape hatch and is enforced as one.** `src/lib/api.ts`
  reads it behind `import.meta.env.DEV`, which Vite inlines as a literal, so a production
  build collapses to same-origin `"/api"` and the other branch is dropped — the variable's
  value cannot reach the bundle even if it is set. It is a *build-time* value attached to
  requests that carry the user's Supabase access token, so before the guard a `npm run build`
  on a laptop with `.env` present baked `http://localhost:8000/api` into the production
  bundle, and a Vercel env var could have redirected every authenticated request to an
  arbitrary host without showing up in a diff.
- Shared query definitions in `src/lib/queries.ts` — prefetchers and components must agree on
  keys. Query keys are NOT user-scoped; instead `useAuth` clears the whole cache when the
  authenticated user id changes. Keep both halves of that invariant.
- Opening a group prefetches all four tabs; deletes are optimistic with rollback; global
  `staleTime` 60s but balances override to 15s (other members' actions change it).
- Date-only strings (`expense_date`) must never round-trip through UTC
  (`new Date("YYYY-MM-DD")`/`toISOString` shift the calendar day) — use `src/lib/dates.ts`.
- The expense form guesses the category from the description (`src/lib/categoryGuess.ts`):
  a bilingual keyword-stem table, earliest matching word wins, longest stem wins within a
  word. It stops the moment the user picks a category themselves, and never touches an
  expense that already has one. Keep the table's category values in sync with
  `CATEGORY_GROUPS` — a test asserts that.
- All user-visible strings go through `src/lib/i18n.tsx` (EN + PL, including category names);
  money formatting is locale-aware via `setMoneyLocale`. **Values go in through
  `t("key", { name })`, never `t("key").replace("{name}", value)`** — that was
  the convention in six places and it is a footgun: `String.replace` gives
  `$&`, `` $` ``, `$'`, `$$` and `$<name>` special meaning in a *replacement
  string*, so any display name containing one came out garbled. Nothing unsafe
  (this is text, never markup), just silently wrong. `t` fills placeholders
  through a replacer function, where nothing is special, and leaves a
  placeholder it has no value for visible rather than blanking it. Dark mode = Tailwind `dark:` variants
  on everything plus `color-scheme` on `.dark`.
- Custom pickers (`DatePicker`, `CategorySelect`) are keyboard-accessible by prior review
  mandate; category list order is user-specified (General first, list opens at top).
  `DatePicker` weeks start on Monday in every language (user-specified, not locale-derived).
- `Modal` dismisses on a backdrop click by default; anything holding unsaved input
  (expense/settlement forms, group create, group settings) passes `dismissOnBackdrop={false}`
  so a stray click can't discard it. Renaming and deleting a group live in
  `GroupSettingsModal` behind the gear next to the group title — not in the members tab.
- `vitest.config.ts` is separate from `vite.config.ts` on purpose (the PWA plugin must not run
  in tests). `.env.test` holds dummy Supabase values so importing `useAuth` doesn't throw;
  tests mock `../lib/api` / `../lib/supabase` per-file.

### The welcome group

Every account is seeded once with a group holding one unsettled expense: SplitDec paid
10 PLN for a coffee, the new account owes it (`api/_src/welcome.py`). It doubles as a
working example — somewhere to open, settle and delete without inventing a trip — and as
the standing form of the ask in `SUPPORT_URL`.

**The counterparty is an ordinary `public.users` row, and it has to be.** A one-member
group cannot hold a debt: net balance is `paid − owed`, so a lone member pays themselves
and nets to zero, leaving nothing for `remove_member` and `delete_group` to refuse. The
"you cannot leave until you settle" behaviour is therefore not new code — it is the
zero-balance checks those two endpoints already had, finally having something to refuse.
Nothing in `balances.py`, the settle form or the greedy simplification knows this group
exists, and no `if is_welcome` may ever appear near the money.

Consequences worth keeping:

- **Nobody can sign in as SplitDec.** `public.users.id` has no FK to `auth.users`, so the
  row exists with no auth identity — no password, no session, nothing to reset. Its
  address (`support@split-dec.app`) is **reserved**: `handle_new_user` mirrors signups
  into `public.users` where `email` is UNIQUE, so a real account registered there would
  fail to be mirrored and land with no profile row. **It is also a real mailbox**, and has
  to be: the members tab renders every member's address under their name, so this one is
  on screen for every account in its first group, where it reads as the way to ask for
  help. It forwards to the maintainer through ImprovMX, as an explicit alias — the
  domain's catch-all was observed not to deliver on its own. `privacy@split-dec.app`
  remains the contact address the Privacy Policy publishes (`src/lib/legal.ts`); this one
  is what someone writes to when they have not read it.
- **Seeding is claimed, not checked.** `users.welcomed_at` is set by a conditional UPDATE
  (`... WHERE id = ? AND welcomed_at IS NULL`), so the row is its own lock and `rowcount`
  decides — parallel first requests, a retry and two open tabs cannot produce two groups.
  The column outlives the group on purpose: settle the coffee, delete the group, and you
  are not handed another. Same reasoning as the `write_events` tombstones.
- **`POST /users/me/welcome` takes the user lock `"exclusive"`, not the `"shared"` the
  other membership-creating endpoints take.** It also UPDATEs the caller's own `users`
  row, and two requests that each took the shared lock first would deadlock upgrading it.
- **Account deletion is never blocked by the coffee.** `delete_account` skips the
  zero-balance refusal for a group whose members are exactly the caller and SplitDec, and
  purges it. Refusing erasure over a debt owed to us would be an obstacle we invented. The
  exemption is deliberately that narrow: invite a real person into the welcome group and
  the ordinary rule comes back, because the debts in it are then between real people.
- **Nothing here is charged to a quota.** The quotas brake what a *caller* creates
  (`ratelimit.py`); this is the deployment seeding itself, exactly once per account, and
  spending the user's first group slot on a gift would be backwards.
- The group name and the expense description are **stored text fixed at creation**, so the
  client sends its current language and the backend keeps a two-entry EN/PL table.
  An unrecognised value falls back to English rather than 422 — no caller shows this
  request's errors.
- Migration `20260905000000` adds `welcomed_at` **without a backfill**, so accounts that
  existed before it are seeded on their next sign-in too. That is the intent on a
  just-launched app; backfilling `now()` is the one-line change that would limit it to new
  signups.

### Voluntary support link (buycoffee.to)

The app is funded by voluntary payments rather than ads or a paid tier. `SupportLink`
carries that link in the landing footer and in `AccountModal`; the destination lives in
**one constant** (`src/lib/support.ts`), because `legal.ts` names it too and a second copy
is a second thing to forget.

**Nothing is fetched from buycoffee.to.** The embed code their panel hands out hotlinks its
artwork from their server, which would make every render of the landing footer a request
carrying the visitor's IP and visit time to a third party — undisclosed view tracking, the
same reason the auth emails draw their logo in HTML instead of linking one. Their JS widget
would be worse: a buycoffee.to profile page loads Google Tag Manager and GA4, a Facebook
pixel, Hotjar, Microsoft Clarity **session recording** and DoubleClick remarketing behind a
Cookiebot banner, none of which may execute on the origin holding the Supabase session, and
all of which would falsify the Privacy Policy's claim that there is no tracking pixel here.

So the button is drawn here and only the **cup** is theirs — used unaltered, because they
publish it as a monochrome file in black and in white, and repainting someone else's mark is
the one thing their materials do not license. Which file shows follows the button's own text
colour, so both themes work off one rule. Their own green (`#00A862` / `#1E3932`) is not our
teal, and their service rules require no particular button, which is what makes drawing one
allowed at all.

Consequences worth keeping:

- **`img-src 'self'` is untouched, and that is the test.** If a change here starts needing
  `vercel.json` or `tests/test_vercel_config.py`, someone has reverted to the embed.
- **The link stays off `LoginPage`** — that is where an invitation deep link lands a
  signed-out visitor, and asking for money before someone can join the group they were
  invited to is the wrong first impression. A test asserts its absence; `LegalLinks` sits in
  all three places, `SupportLink` in two, which is why they are separate components.
- In `AccountModal` it goes **above** the danger zone, never under "delete account".
- The Terms clause "What SplitDec costs" names the provider and the Privacy Policy says the
  link leaves for a company with its own analytics, advertising and session recording, and
  that only the origin travels (thanks to `Referrer-Policy: strict-origin-when-cross-origin`) —
  never the page or the group. Changing any of that is a `LEGAL_UPDATED` bump.
- `.gitignore` carries **`/buycoffee/`, root-anchored**. Unanchored it also swallows
  `public/buycoffee/` and the artwork 404s in production. The ignored directory is the local
  working material for the profile itself (copy, cover art, decision notes), untracked for
  the same reason as `GO-LIVE.md`.

### Database migrations

Raw SQL files in `supabase/migrations/` are the source of truth, but they are applied to the
live database separately (Supabase MCP/dashboard) — when adding one, both write the file and
apply it, and keep the SQLAlchemy models in `api/_src/models.py` in sync (tests create schema
from the models on SQLite).

**A migration file is a statement of intent; `tests/test_grants_pg.py` is the only thing that
checks what the database actually says.** It reads catalogs only, is skipped unless
`AUDIT_DATABASE_URL` is set, and — unlike `TEST_DATABASE_URL`, which must never name
production — it is *meant* to be pointed at production, because the drift it looks for is
created by things that happen to the live project. Two variables so neither habit reaches the
wrong one. Run it after adding a table, after enabling a Supabase feature, and before a
release.

The rule it enforces has a mechanism behind it: an object inherits the grants of whichever
role created it. `20260702000001` locked down the postgres role's default privileges for
tables and sequences but not **functions**, which is why `handle_user_updated` arrived
`anon=X/postgres` a year later and why `20260901000000` had to fix one object where the class
of object was the problem. `20260904000000` closes it — all three default ACLs for the
postgres role now name postgres and service_role only. Supabase's parallel
`FOR ROLE supabase_admin` defaults still grant to anon/authenticated and **cannot be changed
from here**: `pg_has_role(current_user, 'supabase_admin', 'MEMBER')` and `rolsuper` both
return false on production, and `ALTER DEFAULT PRIVILEGES FOR ROLE` requires that membership.
They stay inert only while every object in `public` is created as postgres, which the test
asserts directly.

Two triggers on `auth.users` mirror it into `public.users`: `handle_new_user` on INSERT and
`handle_user_updated` on UPDATE (email or `raw_user_meta_data` only — that table is written on
every sign-in), with a one-off backfill alongside the second for drift that predates it.
Everything downstream reads the copy, invitation matching included, so without the second one
an address change desynchronizes them permanently. Neither trigger is represented in the
models or exercised by the test suite, which creates its schema from the models on SQLite —
changes there are verified against the database or not at all. The UPDATE trigger never
repopulates a row anonymized by account deletion, and never overwrites a value with NULL.

### Email

`APP_URL` (and its frontend twin `APP_ORIGIN` in `src/lib/canonicalHost.ts`, used by the
mailto fallback) must name the **apex**: an installed PWA pins the origin it was installed
from, so a link opening the `vercel.app` alias lands the reader outside their own app, and
that host is `noindex` besides.

**Every invitation email carries a way to stop it** (`api/_src/unsubscribe.py`,
`routers/unsubscribe.py`). Anyone with an account can invite any address, so the
recipient is in the general case somebody who has never used SplitDec — and the send
quotas bound how *often* that happens without ever stopping it. The only previous way
out was reporting the mail as spam, which works through the provider's complaint
suppression at the exact cost the global invitation quota exists to protect.

Four things there are load-bearing:

- **`POST /api/unsubscribe` is POST-only, and that is not a style choice.**
  `List-Unsubscribe-Post` (RFC 8058) means the mail provider POSTs that URL with no
  human involved, while link scanners prefetch every GET in a message — so a GET that
  unsubscribed would fire on delivery. The human-facing page is `/unsubscribe` in the
  SPA, which explains itself and then POSTs. It is the second route reachable without
  a token after `/api/csp-report`, and the first that writes.
- **Opting out suppresses the email and nothing else.** The invitation row is still
  created, still visible in the app if that address ever signs up, and **still charged
  to the sender's quota**. Refunding the slot would let a caller read their own
  remaining allowance to discover whether an address has unsubscribed — the
  registration oracle `GET /users/search` was removed for, rebuilt out of a rate limit.
  **The clock is the exception, and it is a known one**: the skipped provider call
  makes a suppressed address answer faster, so a caller who times the request learns
  that one bit. Not closable here — work that must happen has to happen before the
  response is written, because the platform freezes the instance at that moment (see
  Error monitoring), so on this route latency *is* the send. Tolerated because a probe
  costs an invitation slot and the answer "not suppressed" is delivered by emailing
  that person; `routers/invitations.py` carries the argument and the conditions that
  would reopen it. Do not let a comment anywhere claim the two cases are
  indistinguishable.
- **`email_suppressions` is keyed by the unpeppered digest (`ratelimit.recipient_key`)
  while the token is signed with `UNSUBSCRIBE_SECRET`.** Keying the table by an HMAC
  instead would make rotating that secret silently orphan every row and resume mailing
  people who opted out. Rotation therefore costs outstanding *links*, never the
  objections. This also makes `recipient_key` durable in a way `write_events` is not —
  that docstring's "the rows do not accumulate" now names the exception.
- **Account deletion leaves a suppression standing.** Erasing it would make signing up
  and deleting again the way to resume mail to an address that refused it; the row
  names a digest, not an address.

Without the secret the feature degrades to a `mailto:` `List-Unsubscribe` (RFC 2369,
no endpoint and no stored row) rather than to a forgeable link. The suppression table
is new retention, so adding it was a `src/lib/legal.ts` change with a `LEGAL_UPDATED`
bump.

Invitation emails go through Resend (`api/_src/emailer.py`), best-effort: without
`RESEND_API_KEY` (or on failure) the UI falls back to a mailto draft. User-controlled names are
HTML-escaped via `invitation_email_content`; the *subject* additionally drops control
and format characters (bidi overrides included) and line/paragraph separators, collapses
whitespace, and is bounded to 200 UTF-8 bytes. That bound is **ours**, not a verified
Resend or RFC requirement — the provider builds the MIME header and how it encodes what we
hand it is not visible from here, so this is defence in depth rather than a fix for a
demonstrated injection. The stored name and the escaped HTML body are untouched.
Load any data the email needs **before**
`db.commit()` — the provider call must never hold a checked-out pooler connection. Note: the
free Resend sender only delivers to the account owner until a domain is verified.

**Auth emails** (signup confirmation, password reset) are a different system: Supabase Auth
sends them through custom SMTP, and the templates live in the **dashboard**, not in the
codebase. `docs/auth-email-templates.md` is their source copy — bilingual PL+EN, the app's
teal from `SplitDec DesignSystem/tokens/colors.css`. **The dashboard is what actually sends
mail, so if one changes, change both**; an earlier draft was lost precisely because it existed
only in the dashboard. Two rules in that file are load-bearing. The brand is **teal**
(`#0d9488`) — an earlier revision used indigo that appears nowhere in the app, and nothing in
CI checks an email template, so drift here is silent. And **the logo is drawn in HTML rather
than linked as an image on purpose**: a hosted `<img>`, even first-party, turns every open into
a request carrying the reader's IP and read time, which is undisclosed open-tracking — so
converting it to a real image is a `src/lib/legal.ts` change with a `LEGAL_UPDATED` bump, not a
cosmetic one. (`data:` URIs and inline `<svg>` are refused or stripped by Gmail/Outlook anyway.)

## Other files

- **Launch checklist and security record are deliberately not in this repo.** They are
  kept locally and untracked (`GO-LIVE.md`, `SECURITY-NOTES.md`). The repo is public, and while
  every individual fact in them is either public or derivable from this code, together
  they read as an inventory of where the app is weak and unmonitored. If you need one and
  it is absent, it exists on the maintainer's machine — ask rather than reconstructing it
  here. `.gitignore` names one more of that kind, `DB-ROLE-PLAN.md`, which has served its
  purpose and been deleted; the entry stays so a working document of that shape cannot
  drift into the repo again, which it once nearly did. Two rules follow from all of this.
  **Do not cite an untracked file from a tracked one** — a comment pointing at a path
  nobody outside that machine can open is worse than no pointer at all; put the fact in
  the tracked file or point at a test. And **a local working document is not a home for
  anything durable**: what outlives it belongs here, in `SECURITY-NOTES.md`, or in a test.
  The record was called `SECURITY.md` until September 2026, which was the one name it
  could not have: that is the filename GitHub reserves for the *public*
  vulnerability-disclosure policy, so the repo advertised no reporting channel and a
  single `git add -f` would have published the inventory. `SECURITY.md` is now the public
  policy and is tracked; the `.gitignore` entry is root-anchored for the same reason
  `/buycoffee/` is. `docs/supply-chain.md` is the tracked companion to the private
  record — every accepted supply-chain risk with its reason and its revisit trigger, plus
  the inventory of settings that live only in the GitHub, Vercel and Supabase dashboards.
  `CLAUDE.local.md` is untracked for a different reason — the maintainer's own reporting
  preferences, not repo policy, so nothing here should depend on it.
  Two rules survive that move, because they are about *this code* rather than the launch:
  adding a third-party script to the origin, or rendering user content as markup, both
  invalidate assumptions the security posture rests on and are review-scoped changes; and
  any new data retention also changes `src/lib/legal.ts`.
- `/api/health/db` — DB latency probe, gated by `HEALTH_PROBE_KEY` header outside development.
- `/api/health/sentry` — same gate. Answers whether error reporting from *this
  function* reaches Sentry, which nothing else can: it reports the TLS
  handshake to the ingest host (measured directly, not via the SDK) and the
  `event_id` of a probe event it captures and flushes, for you to look up. See
  Error monitoring for why a route was needed at all.
