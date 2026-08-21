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

## Workflow (mandatory)

Work on `develop`, never commit to `master` directly. Push → open PR to `master` → the
Claude GitHub Action auto-reviews every PR on open **and on every push to it**
(`.github/workflows/claude-code-review.yml`; `@claude` mentions work too, but those workflows
execute from `master`, the default branch) → address findings → merge on green CI → Vercel
auto-deploys `master` to production.
A green `claude-review` check is not by itself proof a review happened: the job reports success
even when it posts nothing (PR #29). Look for the tracking comment, not the tick.
After merging, sync: `git checkout develop && git merge master && git push`.
CI runs pytest, `npm test`, and the build on pushes to both branches and all PRs.
The develop → PR → master sequence is mandatory regardless of what the host enforces:
treat it as the gate, and do not push to `master` even when a shortcut is technically
available.

## Architecture

One Vercel project, path-routed same-origin (no CORS in production; dev-only CORS is gated
on `ENV=development`):

- **Frontend**: Vite/React SPA at repo root. `vercel.json` rewrites `/api/*` to the function,
  everything else to `index.html`, 308-redirects `www.split-dec.app` to the apex (the apex must
  stay the serving origin — installed PWAs pin their origin and a redirecting apex strands their
  service workers and breaks same-origin `/api` calls), pins `regions: ["cdg1"]` — the
  function is deliberately collocated with the database (Paris); moving it re-adds
  ~500ms/request — and sets the security headers (HSTS, nosniff, `frame-ancestors 'none'` +
  `X-Frame-Options: DENY`, referrer and permissions policy), asserted by
  `tests/test_vercel_config.py`. It also sets `installCommand: "npm install"`,
  which exists to *narrow* the inferred install step: Vercel would otherwise
  also install the root `requirements.txt` into the build container, where
  nothing uses it — the build command is `tsc -b && vite build`, and the
  function gets its own install from the Python runtime afterwards. Removing
  the override restores a wasted install and, with it, the Tailwind
  source-detection problem described under Frontend patterns.
  **The script-level CSP is staged**: the enforced
  `Content-Security-Policy` is still framing-only, while the full policy
  (`default-src 'self'`, hash-pinned `script-src`, `connect-src` limited to self +
  the Supabase project) ships alongside it as `Content-Security-Policy-Report-Only`
  until the flows it could break — OAuth, recovery, installed PWAs — have been
  exercised in production. Promoting it is a one-key rename; the tests read
  whichever header carries the policy, so they survive the flip. Two things there
  are load-bearing and non-obvious: `font-src` must allow `data:` (Vite inlines the
  smallest Manrope woff2 into the built CSS), and the one inline script in
  `index.html` — the pre-mount theme flip — is allowed **by hash**, because a nonce
  is impractical when a single static `index.html` is served through a rewrite. The
  test recomputes that hash from `index.html`, so editing that script fails CI
  rather than silently reverting the app to a light-mode flash.
  A host-scoped `X-Robots-Tag: noindex` keeps `split-dec.vercel.app` from competing
  with the apex in search — it has to be a header, because every route rewrites to one
  `index.html` and a `<link rel="canonical">` in it would also claim `/privacy` and
  `/terms` are copies of the landing page. `public/robots.txt` and `public/sitemap.xml`
  cover the three public routes; assets are left crawlable on purpose, since the
  landing page is client-rendered.
- **Backend**: FastAPI in `api/index.py` (single Vercel function; code lives in `api/_src/` —
  the underscore prevents Vercel treating those files as separate functions).
- **Database**: Supabase Postgres, project ref `kmlheefyzhhegxmtaovq`. Connection MUST use the
  transaction pooler (port 6543, `postgresql+asyncpg://`) with `NullPool` and
  `statement_cache_size=0` (`api/_src/db.py`) — never per-request engines, never the session pooler.
- **Auth**: Supabase Auth (PKCE) on the frontend — Google OAuth **plus email/password** (signup
  with confirmation required, forgot/reset flow); backend verifies JWTs statelessly
  (`auth.py`: ES256 via JWKS, HS256 fallback) and reads only the `sub` claim — provider-neutral.
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

Three rules any new quota must follow:

- **Count tombstones, not the rows you are protecting.** Soft-deleted rows
  keeping their `created_at` is not enough — the group above them can vanish.
- **Answer an idempotent replay *before* the quota.** A client retrying a
  request whose response it never saw has already spent its slot, and a 429
  there leaves it unable to discover whether the row exists — the one thing
  `Idempotency-Key` is for. Both create endpoints look the key up first.
- **Charge inside the endpoint's transaction.** `record_write` only adds to the
  session, so a validation failure or the idempotency-race rollback takes the
  charge with it and a replay is never charged twice.

`record_write` also opportunistically prunes the caller's rows that have aged
out of the window — a serverless function has nowhere to hang a cron — and
`delete_account` clears that user's outright, since nothing would ever prune
them again.

Deliberately **no global cap** on the ledger or group windows: a
deployment-wide ceiling would turn one abusive account into an outage for
everyone. Invitations do carry one, because the resource they burn — the
sending domain's reputation — is shared and cannot be bought back.

A second, narrower lock covers *membership creation* against account deletion:
`get_active_user(..., lock=)` locks the `users` row — `"shared"` in every endpoint that hands
the caller a new membership (group create, invitation accept), `"exclusive"` in
`delete_account`, taken **before** the group snapshot and held to commit. Otherwise a
membership committed mid-deletion escapes both the balance check and the unscoped delete, and
membership-gated routes don't re-check liveness. `"exclusive"` is `FOR NO KEY UPDATE`, not
`FOR UPDATE`, on purpose: `FOR UPDATE` conflicts with the `FOR KEY SHARE` that FK inserts take
on `users` rows, which deadlocks against an expense write already holding the group lock.

### API contracts worth knowing

- `POST .../expenses` and `.../settlements` require an `Idempotency-Key` UUID header; replays
  return 200 with the existing row, **scoped to the path group** (cross-group key reuse → 409).
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
  covers only `PENDING` rows so re-inviting still works.
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
  `advancedChunks`): React, React-DOM, the router, TanStack Query and
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

### Database migrations

Raw SQL files in `supabase/migrations/` are the source of truth, but they are applied to the
live database separately (Supabase MCP/dashboard) — when adding one, both write the file and
apply it, and keep the SQLAlchemy models in `api/_src/models.py` in sync (tests create schema
from the models on SQLite).

### Email

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

- **Launch checklist and security record are deliberately not in this repo.** Both are
  kept locally and untracked (`GO-LIVE.md`, `SECURITY.md` — see `.gitignore`). The repo is
  public, and while every individual fact in them is either public or derivable from this
  code, together they read as an inventory of where the app is weak and unmonitored. If you
  need either file and it is absent, it exists on the maintainer's machine — ask rather
  than reconstructing it here.
  Two rules survive that move, because they are about *this code* rather than the launch:
  adding a third-party script to the origin, or rendering user content as markup, both
  invalidate assumptions the security posture rests on and are review-scoped changes; and
  any new data retention also changes `src/lib/legal.ts`.
- `/api/health/db` — DB latency probe, gated by `HEALTH_PROBE_KEY` header outside development.
