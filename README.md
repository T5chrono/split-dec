# SplitDec

A Splitwise clone: groups, multi-currency expenses with EQUAL / EXACT / PERCENTAGE
splits, settlements, and on-the-fly greedy debt simplification.
Built to `SplitDec - specification.md` (v6).

## Stack

- **Frontend:** React 19 + Vite + TypeScript, Tailwind CSS, TanStack Query,
  `lucide-react` category icons, Supabase JS (Google OAuth, PKCE).
- **Backend:** FastAPI (async) deployed as a Vercel Function
  ([api/index.py](api/index.py)), SQLAlchemy 2.0 + asyncpg.
- **Database:** Supabase Postgres (project `SplitDec`), schema in
  [supabase/migrations](supabase/migrations/20260702000000_initial_schema.sql)
  (already applied). RLS is intentionally disabled — the FastAPI layer is the
  sole authorization boundary, per spec.

## Key behaviors

- All money columns are `NUMERIC(14,4)`; API serializes amounts as **strings**
  (`"120.5000"`). The frontend formats them with the same ISO-4217
  minor-unit table the backend uses (JPY = 0, USD/EUR = 2, KWD = 3 decimals).
- Splits use banker's rounding at the currency's precision; leftover smallest
  units are distributed deterministically starting with the payer, so splits
  always sum exactly to the total.
- `POST /groups/{id}/expenses` and `POST /groups/{id}/settlements` require an
  `Idempotency-Key: <uuid>` header; replays return `200` with the existing row.
- Expenses and settlements are soft-deleted (`deleted_at`); the balance CTE
  filters both tables independently.
- `GET /groups/{id}/balances` aggregates net balances per currency in a single
  SQL CTE, then greedy-matches debtors to creditors per currency bucket.
- Members can only be removed when their net balance is zero in **every**
  currency of that group.

## Email invitations (optional)

Group membership is invitation-based: invitees accept or decline in-app.
When the invited email doesn't belong to a SplitDec user yet, the backend
tries to email them via [Resend](https://resend.com). Set `RESEND_API_KEY`
(and optionally `RESEND_FROM`, `APP_URL`) on Vercel to enable this; without
it, invitations are still recorded (they appear when the person signs up)
and the UI offers a pre-written mailto draft instead.

## Branch workflow

- `develop` is the working branch — push (or PR) feature work here; CI runs
  the test suite and the frontend build on every push.
- When `develop` is green, open a PR to `master` and request a review from
  Claude (mention `@claude` in the PR). Address comments, then merge.
- Merging to `master` runs CI again and Vercel auto-deploys `master` to
  production (https://split-dec.vercel.app). Pushes to `develop` get Vercel
  preview deployments.

## Tests

- `pip install -r requirements.txt -r requirements-dev.txt`, then `pytest`.
- Pure logic (split math, debt simplification) plus full API tests running
  against in-memory SQLite with the auth dependency overridden — no network.
- `tests/test_balances_pg.py` / `tests/test_locks_pg.py` additionally check
  the balance CTE and row-lock clauses against a real Postgres; both are
  skipped unless `TEST_DATABASE_URL` is set (use a disposable database — they
  roll back everything they write).
- Frontend: `npm test` (Vitest + React Testing Library, jsdom). Pure `lib/`
  functions (currency formatting, local-date handling) plus component tests
  — `../lib/api` and `../lib/supabase` are mocked so no network calls happen;
  `.env.test` supplies dummy Supabase env vars so importing `useAuth` doesn't
  throw outside a real build. The `ExpensesTab` suite exercises the
  optimistic-delete/rollback flow directly (row disappears before the mocked
  request resolves, reappears with the server's error message if it fails).
- CI (`.github/workflows/ci.yml`) runs pytest, `npm test`, and the frontend
  build on every push and PR.

## Local development

1. Copy `.env.example` to `.env` and fill in:
   - `DATABASE_URL` — Supabase **Transaction Pooler** string (port **6543**),
     with the `postgresql+asyncpg://` scheme and your database password.
   - `SUPABASE_JWT_SECRET` — Dashboard → Project Settings → API → JWT Secret
     (only if the project signs tokens with legacy HS256; with asymmetric
     signing keys the backend verifies against JWKS automatically).
2. Backend: `pip install -r requirements.txt`, then `npm run api`
   (uvicorn on `:8000`; CORS for `localhost:5173` is enabled because `ENV=development`).
3. Frontend: `npm install`, then `npm run dev` (Vite on `:5173`).

## One-time Supabase setup

- Enable the **Google** provider: Dashboard → Authentication → Providers →
  Google (create an OAuth client in Google Cloud Console, add the callback URL
  Supabase shows you).
- Add your app origins (e.g. `http://localhost:5173`, your Vercel domain) to
  Authentication → URL Configuration → Redirect URLs.

## Deploying to Vercel

Import the repo as a single Vercel project (Vite framework preset is picked up
from `vercel.json`; the FastAPI function gets `maxDuration: 30`). Set these
environment variables:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Transaction Pooler URL, `postgresql+asyncpg://…:6543/postgres` |
| `SUPABASE_URL` | `https://kmlheefyzhhegxmtaovq.supabase.co` |
| `SUPABASE_JWT_SECRET` | project JWT secret (HS256 projects only) |
| `VITE_SUPABASE_URL` | same as `SUPABASE_URL` |
| `VITE_SUPABASE_ANON_KEY` | project publishable/anon key |

Do **not** set `ENV=development` or `VITE_API_URL` in production — the SPA and
API are same-origin under one domain, so no CORS is needed or enabled.
