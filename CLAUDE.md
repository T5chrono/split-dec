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
`tests/test_grants_pg.py` is the exception: it reads catalogs only, takes `AUDIT_DATABASE_URL`,
and is *meant* for production (see Database migrations). All three connect through the
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
CI runs pytest, `npm test`, and the build on pushes to both branches and all PRs.
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
  support link is a `target="_blank"`. It also sets `installCommand: "npm install"`,
  which exists to *narrow* the inferred install step: Vercel would otherwise
  also install the root `requirements.txt` into the build container, where
  nothing uses it — the build command is `tsc -b && vite build`, and the
  function gets its own install from the Python runtime afterwards. Removing
  the override restores a wasted install and, with it, the Tailwind
  source-detection problem described under Frontend patterns.
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
  visitor's own console, where nobody collects it. It is the one route on
  the API reachable without a token, so it touches no database, stores
  nothing, and logs only the violation's shape: the directive, the blocked
  *origin*, the reporting host, and the route pattern folded exactly as
  `insightsRoute` folds it — a group id, an OAuth `?code=` or a recovery
  `#access_token=` must never reach a log line, and neither may a field
  forge one with a newline. Reports are dropped unless the document URL is
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
  (`src/lib/authErrors.ts`) must match the dashboard's minimum length; signup/reset responses
  stay deliberately enumeration-safe (don't distinguish existing emails). `/reset-password` is
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

**Every one of those windows counts `write_events`** — one append-only
tombstone per quota-consuming write, charged by `record_write()` — and not the
rows being created. That indirection is the whole point: deleting a group is a
*hard* delete that takes its expenses, settlements **and invitations** with it,
and any member may delete a settled group, so while the quotas counted real
rows, create → fill → delete → repeat reset all of them. Nothing cascades to
`write_events`.

The per-recipient invitation window is keyed by `recipient_key(email)`, a bare
SHA-256 — the window only ever needs equality, so the durable table never holds
a contactable address and account deletion can go on promising to erase it.
Unpeppered on purpose: whoever can read that column can already read
`public.users.email` in plaintext, so a pepper buys nothing real and adds a
secret whose rotation would silently reset every recipient window.

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

- `POST .../expenses` and `.../settlements` require an `Idempotency-Key` UUID header; replays
  return 200 with the existing row, **scoped to the path group** (cross-group key reuse → 409).
  The client side of that contract is `useIdempotencyKey`: one key per open form, resent on
  every attempt. A retry that mints a fresh key is not a retry — if the first request landed
  and only its response was lost, the second one records the entry a second time.
- `PATCH /expenses/{id}` is partial: metadata (description/category/expense_date) applies
  independently; the five split-affecting fields (split_type, total_amount, currency,
  paid_by_user_id, splits) are all-or-nothing and trigger a full splits rewrite. The frontend
  (`ExpenseFormModal.financialsUnchanged`) sends metadata-only bodies when financials are
  untouched — required because reconstructed percentages are rounded and must not be resubmitted.
- Membership is invitation-based (`group_invitations`, matched by lowercased email so people
  who sign up later see their invites). The direct add-member endpoint and `GET /users/search`
  were removed (the latter was an email-registration oracle — deliberate spec deviation).
  **The invite endpoint must stay uniform for the same reason**: same response shape, same
  email attempt, same latency whether or not the address has an account (anyone can create a
  group and invite arbitrary addresses). Never reintroduce `user_exists`/`email_sent`/
  `invited_user_id` in a response. Sending is quota-limited (per inviter / per recipient /
  global, 24h — counted from `write_events`, see above). Cancelling sets
  `status='CANCELLED'` rather than deleting: the quotas no longer depend on that, but the
  row is the group's record that the invitation happened, and the partial unique index
  covers only `PENDING` rows so re-inviting still works. Cancelling, accepting and declining
  are all conditional on the row still being `PENDING` and answer 404 when it is not (see the
  concurrency section).
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
  the next holder of the address would inherit them) and anonymizes the address on answered
  ones.
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
  cold. The signed-out catch-all renders `LoginPage`, **not** the 404: an
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
  money formatting is locale-aware via `setMoneyLocale`. Dark mode = Tailwind `dark:` variants
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
  fail to be mirrored and land with no profile row. `privacy@split-dec.app` is the contact
  address (`src/lib/legal.ts`); this one is not for handing out. It *is* visible — the
  members tab renders each member's address under their name.
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

Invitation emails go through Resend (`api/_src/emailer.py`), best-effort: without
`RESEND_API_KEY` (or on failure) the UI falls back to a mailto draft. User-controlled names are
HTML-escaped via `invitation_email_content`. Load any data the email needs **before**
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
  kept locally and untracked (`GO-LIVE.md`, `SECURITY.md`). The repo is public, and while
  every individual fact in them is either public or derivable from this code, together
  they read as an inventory of where the app is weak and unmonitored. If you need one and
  it is absent, it exists on the maintainer's machine — ask rather than reconstructing it
  here. `.gitignore` names one more of that kind, `DB-ROLE-PLAN.md`, which has served its
  purpose and been deleted; the entry stays so a working document of that shape cannot
  drift into the repo again, which it once nearly did. Two rules follow from all of this.
  **Do not cite an untracked file from a tracked one** — a comment pointing at a path
  nobody outside that machine can open is worse than no pointer at all; put the fact in
  the tracked file or point at a test. And **a local working document is not a home for
  anything durable**: what outlives it belongs here, in `SECURITY.md`, or in a test.
  `CLAUDE.local.md` is untracked for a different reason — the maintainer's own reporting
  preferences, not repo policy, so nothing here should depend on it.
  Two rules survive that move, because they are about *this code* rather than the launch:
  adding a third-party script to the origin, or rendering user content as markup, both
  invalidate assumptions the security posture rests on and are review-scoped changes; and
  any new data retention also changes `src/lib/legal.ts`.
- `/api/health/db` — DB latency probe, gated by `HEALTH_PROBE_KEY` header outside development.
