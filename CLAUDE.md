# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SplitDec — a Splitwise clone (groups, multi-currency expenses, settlements, greedy debt
simplification). Built to `SplitDec - specification.md` (v6), **with deliberate deviations**
listed below. Production: https://split-dec.vercel.app (installable PWA).

## Commands

```powershell
# Backend (Python venv at .venv; local Python is 3.14, Vercel runs 3.12)
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
Claude GitHub Action auto-reviews every PR on open (`.github/workflows/claude-code-review.yml`;
`@claude` mentions work too, but those workflows execute from `master`, the default branch) →
address findings → merge on green CI → Vercel auto-deploys `master` to production.
After merging, sync: `git checkout develop && git merge master && git push`.
CI runs pytest, `npm test`, and the build on pushes to both branches and all PRs.
Branch protection is unavailable (free plan + private repo) — the gate is by convention.

## Architecture

One Vercel project, path-routed same-origin (no CORS in production; dev-only CORS is gated
on `ENV=development`):

- **Frontend**: Vite/React SPA at repo root. `vercel.json` rewrites `/api/*` to the function,
  everything else to `index.html`, and pins `regions: ["cdg1"]` — the function is deliberately
  collocated with the database (Paris); moving it re-adds ~500ms/request.
- **Backend**: FastAPI in `api/index.py` (single Vercel function; code lives in `api/_src/` —
  the underscore prevents Vercel treating those files as separate functions).
- **Database**: Supabase Postgres, project ref `kmlheefyzhhegxmtaovq`. Connection MUST use the
  transaction pooler (port 6543, `postgresql+asyncpg://`) with `NullPool` and
  `statement_cache_size=0` (`api/_src/db.py`) — never per-request engines, never the session pooler.
- **Auth**: Supabase Google OAuth (PKCE) on the frontend; backend verifies JWTs statelessly
  (`auth.py`: ES256 via JWKS, HS256 fallback). **RLS is intentionally disabled** — the FastAPI
  layer is the sole authorization boundary; the Data API's anon/authenticated grants were
  revoked by migration. Do not enable RLS and do not weaken the FastAPI checks.

### Money invariants (the core of this codebase)

- All money is `NUMERIC(14,4)` in Postgres, `Decimal` in Python, and **string** in JSON
  (`"120.5000"`). Money never passes through binary floats anywhere: frontend math uses
  integer minor units (`toMinorUnits`/`fromMinorUnits` in `src/lib/currency.ts`) or BigInt.
- Split computation (`api/_src/splits.py`): banker's rounding at the currency's precision
  (`currencies.py`: JPY=0, most=2, KWD=3), remainder distributed one smallest unit at a time
  starting with the payer, so splits always sum exactly to the total. Splits are non-negative
  (Pydantic + DB CHECK).
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
- Account deletion anonymizes `public.users` (email gets `DELETED_EMAIL_SUFFIX` from `deps.py`)
  and deletes the `auth.users` row; endpoints not gated by membership must call
  `get_active_user` because old JWTs stay valid until expiry.
- Expense splits rewrite pattern: clear the collection and `flush()` **before** assigning
  replacements, or `UNIQUE(expense_id, user_id)` fires (inserts flush before deletes).

### Frontend patterns

- Shared query definitions in `src/lib/queries.ts` — prefetchers and components must agree on
  keys. Query keys are NOT user-scoped; instead `useAuth` clears the whole cache when the
  authenticated user id changes. Keep both halves of that invariant.
- Opening a group prefetches all four tabs; deletes are optimistic with rollback; global
  `staleTime` 60s but balances override to 15s (other members' actions change it).
- Date-only strings (`expense_date`) must never round-trip through UTC
  (`new Date("YYYY-MM-DD")`/`toISOString` shift the calendar day) — use `src/lib/dates.ts`.
- All user-visible strings go through `src/lib/i18n.tsx` (EN + PL, including category names);
  money formatting is locale-aware via `setMoneyLocale`. Dark mode = Tailwind `dark:` variants
  on everything plus `color-scheme` on `.dark`.
- Custom pickers (`DatePicker`, `CategorySelect`) are keyboard-accessible by prior review
  mandate; category list order is user-specified (General first, list opens at top).
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
free Resend sender only delivers to the account owner until a domain is verified (see GO-LIVE.md).

## Other files

- `GO-LIVE.md` — pre-launch checklist (email domain, OAuth publishing, secret rotation,
  Supabase Pro, funding via buycoffee.to). Update statuses as items land.
- `/api/health/db` — DB latency probe, gated by `HEALTH_PROBE_KEY` header outside development.
