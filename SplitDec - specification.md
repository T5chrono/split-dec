# Splitwise Clone: Full Technical Specification v6
**Target Audience for this document:** AI Code Generators (Claude Code, Cursor, etc.).
**Goal:** Implement a fully functional, production-ready Splitwise clone based on the exact parameters below. Do not deviate from these architectural decisions.

> **Revision note (v5 → v6):** fixed a missing `idempotency_key` column on `settlements`, made soft-delete filtering in the balance CTE explicit for both `expenses` and `settlements`, restored a dropped index on `group_members`, corrected the CORS instruction (no CORS is needed in production under Vercel Services; it's a local-dev-only concern), hardened the connection-pooling guidance (`NullPool` + verified `statement_cache_size` key), added `SECURITY DEFINER` and explicit field-extraction to the auth-sync trigger, clarified the multi-currency balance check on member removal, and pinned down decimal serialization in API responses.

---

## 1. System Architecture, Deployment & Infrastructure
*   **Deployment Platform:** Single-project monorepo using **Vercel Services** (colocating frontend and backend under a single domain).
    *   *Frontend:* React SPA deployed via Vercel's standard build.
    *   *Backend:* Python **FastAPI** (asynchronous) deployed as a Vercel Function (Serverless, Fluid compute).
    *   *Config:* Generate a `vercel.json` config setting `maxDuration` to 30 seconds for backend routes to prevent serverless timeouts during multi-currency graph simplification.

*   **CORS & Routing:** Because the frontend and backend are path-routed on the same Vercel project domain, **production traffic is same-origin and CORS is not applicable — do not add a permissive/wildcard `CORSMiddleware`.** CORS only matters for **local development**, where the frontend dev server (e.g. Vite on `localhost:5173`) and the FastAPI backend (`uvicorn` on `localhost:8000`) run on different ports and are therefore cross-origin. Configure `CORSMiddleware` to allow only `http://localhost:5173` (or your dev server's actual port), gated behind an environment check (e.g. `if ENV == "development"`), so it is never active in production.

*   **Database:** Supabase (PostgreSQL) using an async ORM (SQLAlchemy 2.0 with asyncpg or SQLModel).

*   **Connection Pooling (Serverless Optimized):** You MUST connect using the Supabase **Transaction Pooler** connection string (Port 6543), NOT the direct database port or the Session Pooler.
    *   *Prepared statements:* Transaction-mode pooling does not support server-side prepared statements. Disable them by passing `statement_cache_size=0` in `connect_args` — this is the officially documented asyncpg mechanism and is required. Additionally pass `prepared_statement_cache_size=0` as a secondary safeguard (a distinct, secondary statement cache asyncpg falls back to); this key is less consistently documented, so verify it has an effect against your pinned asyncpg version before relying on it — `statement_cache_size=0` is the load-bearing setting.
    *   *Double-pooling:* SQLAlchemy's own connection pool sitting in front of PgBouncer's pool causes connection exhaustion under concurrent serverless invocations. Set `poolclass=NullPool` on the async engine so SQLAlchemy does not maintain its own idle connections — let the Transaction Pooler do all the pooling.
    *   *Example:*
        ```python
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.pool import NullPool

        engine = create_async_engine(
            DATABASE_URL,  # postgresql+asyncpg://...@...pooler.supabase.com:6543/postgres
            poolclass=NullPool,
            connect_args={
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
            },
        )
        ```
    *   *Lifecycle:* Create the engine once at module scope (or in a FastAPI `lifespan` handler) and reuse it across warm invocations. Never construct a new engine per-request.

*   **Authentication & RLS:**
    *   *Frontend:* Supabase JS SDK handles Google OAuth (PKCE) login and token storage.
    *   *Backend Gatekeeper:* FastAPI uses dependency injection (`Depends(verify_jwt)`) to validate the `Authorization: Bearer <token>` header on all protected routes.
    *   *RLS Stance:* Row Level Security remains **disabled** on all `public` schema tables. The backend connects via a trusted Postgres role and the FastAPI layer is the sole authorization boundary — do not `ENABLE ROW LEVEL SECURITY` on any table without also authoring matching policies, as that would lock out the backend's own connection role.

---

## 2. Data Modeling & Database Constraints
Strictly normalized relational schema. All financial columns MUST use `NUMERIC(14, 4)` to safely handle multi-currency ledgers and prevent rounding leaks.

*   **`users`**: `id` (UUID, PK), `email` (String, Unique), `full_name` (String), `avatar_url` (String, Nullable), `created_at` (Timestamp).
*   **`groups`**: `id` (UUID, PK), `name` (String), `created_by` (UUID, FK -> users), `created_at` (Timestamp). *Note: 1-on-1 expenses are simply treated as 2-person groups.*
*   **`group_members`**: `group_id` (UUID, FK), `user_id` (UUID, FK), `joined_at` (Timestamp). *Constraint: Composite PK on (group_id, user_id).*
*   **`expenses`**:
    *   `id` (UUID, PK), `group_id` (UUID, FK), `description` (String),
    *   `category` (String, Validated against Backend Enum), `split_type` (String, Enum: 'EQUAL', 'EXACT', 'PERCENTAGE'),
    *   `total_amount` (NUMERIC(14,4)), `currency` (String, 3-char ISO),
    *   `paid_by_user_id` (UUID, FK), `idempotency_key` (UUID, Unique), `created_at` (Timestamp), `deleted_at` (Timestamp, Nullable).
*   **`expense_splits`**: `id` (UUID, PK), `expense_id` (UUID, FK), `user_id` (UUID, FK), `owed_amount` (NUMERIC(14,4)).
*   **`settlements`**:
    *   `id` (UUID, PK), `group_id` (UUID, FK), `paid_by_user_id` (UUID, FK), `paid_to_user_id` (UUID, FK),
    *   `amount` (NUMERIC(14,4)), `currency` (String, 3-char ISO), `idempotency_key` (UUID, Unique),
    *   `created_at` (Timestamp), `deleted_at` (Timestamp, Nullable).

### Database Migrations (Mandatory)
The generator MUST output raw SQL migrations implementing the following:

1.  **Auth Sync Trigger:** Create a PostgreSQL function and trigger listening `AFTER INSERT ON auth.users` that copies the new user into `public.users`. The function must be `SECURITY DEFINER` (owned by a role with insert rights on `public.users`) since triggers on `auth.users` do not otherwise inherit write access to the `public` schema. Extract named fields from the JSONB `raw_user_meta_data` explicitly rather than copying it wholesale — provider-populated keys vary, so fall back across common aliases:
    ```sql
    CREATE OR REPLACE FUNCTION public.handle_new_user()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    SECURITY DEFINER SET search_path = public
    AS $$
    BEGIN
      INSERT INTO public.users (id, email, full_name, avatar_url, created_at)
      VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name'),
        COALESCE(NEW.raw_user_meta_data->>'avatar_url', NEW.raw_user_meta_data->>'picture'),
        NOW()
      )
      ON CONFLICT (id) DO NOTHING;
      RETURN NEW;
    END;
    $$;

    CREATE TRIGGER on_auth_user_created
      AFTER INSERT ON auth.users
      FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
    ```

2.  **Constraints:**
    *   `UNIQUE(expense_id, user_id)` on `expense_splits`.
    *   `CHECK (total_amount > 0)` and `CHECK (currency ~ '^[A-Z]{3}$')` on `expenses`.
    *   `CHECK (amount > 0)` and `CHECK (currency ~ '^[A-Z]{3}$')` on `settlements`.
    *   `UNIQUE(idempotency_key)` on both `expenses` and `settlements` (already declared as column-level `Unique` above; ensure the migration actually creates the constraint).

3.  **Indexes:**
    *   `CREATE INDEX idx_expenses_group_deleted ON expenses(group_id, deleted_at);`
    *   `CREATE INDEX idx_expense_splits_user ON expense_splits(user_id);`
    *   `CREATE INDEX idx_settlements_group ON settlements(group_id, deleted_at);`
    *   `CREATE INDEX idx_group_members_user ON group_members(user_id);` — required because the composite PK on `group_members` is `(group_id, user_id)`; a lookup by `user_id` alone (used by `GET /groups`) can't use that index efficiently without this.

---

## 3. Business Logic & Constants

### General Authorization Rule
Any active member of a group has explicit permission to view, edit, or soft-delete any expense or settlement within that specific group.

### Categories (Stateless & Hardcoded)
Do not create a categories table. Validate inputs strictly via Python `StrEnum` on the backend. The React frontend will maintain an immutable dictionary mapping these exact string values to matching `lucide-react` UI icons.

*   **Entertainment:** Games, Movies, Music, Sports, Other Entertainment
*   **Food and drink:** Dining out, Groceries, Liquor, Other Food and drink
*   **Home:** Electronics, Furniture, Household supplies, Maintenance, Mortgage, Pets, Rent, Services, Other Home
*   **Life:** Childcare, Clothing, Education, Gifts, Insurance, Medical expenses, Taxes, Other Life
*   **Transportation:** Bicycle, Bus/train, Car, Gas/fuel, Hotel, Parking, Plane, Taxi, Other Transportation
*   **Utilities:** Cleaning, Electricity, Heat/gas, Trash, TV/Phone/Internet, Water, Other Utilities
*   **Subscriptions:** Software, Streaming, Memberships, Other Subscriptions
*   **Learning:** Tutor, Courses, Books, Other Learning
*   **AI Expenses:** LLM APIs, Copilots, Generation Tools, Other AI Expenses
*   **Uncategorized:** General

### Split Strategies & Currency Precision Math
1.  **Verification:** Equal (division across group/selected members), Exact (verify `sum(amounts) == total_amount`), Percentage (verify `sum(percentages) == 100`).
2.  **Currency Precision Lookup:** The backend MUST apply a precision lookup dictionary (e.g., JPY = 0 decimals, USD/EUR = 2 decimals, KWD = 3 decimals).
3.  **Rounding Rule:** Round base units using **Banker's Rounding** (round half to even) matching the specific currency's decimal precision. Distribute any remaining fractional units deterministically (1 smallest decimal unit at a time, starting with the paying user) until the sum of the splits perfectly equals the `total_amount`.

### Optimized On-The-Fly Debt Simplification
To prevent serverless out-of-memory errors and timeout limits, the `/balances` route must execute this exact path:

1.  **Database Aggregation (CTE):** Execute a single SQL statement using CTEs that computes net user balances entirely on the database engine.
    *   The query must compute: `Net Balance = (Total Paid as Payer in expenses) - (Total Owed as Borrower in expense_splits) + (Total amount received in settlements) - (Total amount sent in settlements)`.
    *   *Critical — soft deletes apply to BOTH source tables:* join `expense_splits` to `expenses` to inherit `currency`, and exclude rows where `expenses.deleted_at IS NOT NULL`. **Separately and just as strictly**, exclude rows where `settlements.deleted_at IS NOT NULL` in the received/sent CTEs. A deleted settlement must stop affecting balances — this is easy to miss because it's a second, independent filter on a different table, not a side effect of the expenses filter. Sketch:
        ```sql
        WITH paid AS (
          SELECT paid_by_user_id AS user_id, currency, SUM(total_amount) AS amt
          FROM expenses WHERE deleted_at IS NULL GROUP BY 1, 2
        ),
        owed AS (
          SELECT es.user_id, e.currency, SUM(es.owed_amount) AS amt
          FROM expense_splits es JOIN expenses e ON e.id = es.expense_id
          WHERE e.deleted_at IS NULL GROUP BY 1, 2
        ),
        received AS (
          SELECT paid_to_user_id AS user_id, currency, SUM(amount) AS amt
          FROM settlements WHERE deleted_at IS NULL GROUP BY 1, 2
        ),
        sent AS (
          SELECT paid_by_user_id AS user_id, currency, SUM(amount) AS amt
          FROM settlements WHERE deleted_at IS NULL GROUP BY 1, 2
        )
        -- combine paid - owed + received - sent per (user_id, currency)
        ```
2.  **Isolate Currencies:** Divide the aggregated database balances into clean, isolated currency buckets in Python memory.
3.  **Greedy Match (Per Currency Bucket):** For each currency bucket, isolate users into `Debtors` (net < 0) and `Creditors` (net > 0). Sort both lists by absolute value descending. Iteratively match the largest Debtor to the largest Creditor to produce a simplified transaction ledger until all balances resolve to 0. *(Note: this greedy heuristic always fully settles the group but is not guaranteed to produce the mathematically minimum number of transactions — that's an NP-hard optimization in general. Don't represent it as optimal in user-facing copy.)*

---

## 4. API Endpoints & Contract Design
*   **Errors:** Standardize all error schemas using FastAPI's native `HTTPException`. Responses must strictly format as JSON objects matching `{"detail": "Error message explanation"}`. Leverage standard HTTP statuses: `400` (Bad Request), `403` (Forbidden membership), `404` (Not Found), `422` (Validation failure).
*   **Monetary serialization:** All amount fields (`total_amount`, `owed_amount`, `amount` in balances) MUST serialize as **strings** in JSON responses (e.g. `"120.5000"`), not bare numbers — `NUMERIC(14,4)` precision is not safely representable as a JS float, and this spec goes out of its way elsewhere to avoid rounding leaks. The frontend formats each string for display using the same currency-precision lookup table as the backend.

**Users & Groups:**
*   `GET /users/search?email={email}` -> Lookup a user for group invites. Returns `id`, `full_name`, and `avatar_url`.
*   `GET /groups` -> List all groups the authenticated user is a member of.
*   `POST /groups` -> Create a new group and instantly append the creator to `group_members`.
*   `GET /groups/{id}` -> Fetch group metadata and the complete list of member objects.
*   `POST /groups/{id}/members` -> Add a user to the group by passing their `user_id` UUID. Fails if the caller is not an active group member.
*   `DELETE /groups/{id}/members/{user_id}` -> Remove a user from the group. Strictly fails if the target user has a non-zero net balance **in any currency** within that group — check every currency bucket for that user/group pair, not just a default currency.

**Expenses (Idempotent Lifecycle):**
*   `GET /groups/{id}/expenses?limit=20&offset=0` -> Returns a paginated list of active expenses, ordered by `created_at` DESC. Filter out all soft-deleted records.
*   `POST /groups/{id}/expenses` -> Create an expense and its associated `expense_splits` inside a single ACID database transaction block.
    *   *Idempotency Protection:* Requires an `Idempotency-Key` UUID HTTP header, stored in `expenses.idempotency_key`. If a Postgres unique constraint violation is triggered on this key, catch the error and return `200 OK` with the existing data payload.
*   `PATCH /expenses/{id}` -> Edit an expense and completely rewrite its `expense_splits` mappings inside a single database transaction block.
*   `DELETE /expenses/{id}` -> Soft delete an expense by flagging `deleted_at = current_timestamp`.

**Settlements & Balances:**
*   `GET /groups/{id}/settlements` -> List all historical, non-deleted settlements for a group.
*   `POST /groups/{id}/settlements` -> Record a manual payment transaction between two users, inside a single database transaction.
    *   *Idempotency Protection:* Requires an `Idempotency-Key` UUID HTTP header, stored in `settlements.idempotency_key`. If a Postgres unique constraint violation is triggered on this key, catch the error and return `200 OK` with the existing data payload (identical pattern to expense creation, now that the column exists to back it).
    *   *Frontend UX Rule:* Upon receiving a successful `201 Created` confirmation from this endpoint, the React frontend must immediately invalidate its local cache and re-fetch both `/balances` and `/expenses` to update the application layout smoothly.
*   `PUT /settlements/{id}` -> Modify an existing settlement record's amount or metadata.
*   `DELETE /settlements/{id}` -> Soft delete a settlement record (`deleted_at = current_timestamp`) — the `/balances` CTE must exclude it going forward, per section 3.
*   `GET /groups/{id}/balances` -> Executes the database-aggregated Greedy Simplification Match. Returns a dictionary schema grouped cleanly by currency code, with amounts as strings:
    ```json
    {
      "PLN": [
        { "from_user_id": "uuid-1", "to_user_id": "uuid-2", "amount": "120.5000" }
      ],
      "EUR": []
    }
    ```
