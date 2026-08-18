# SECURITY.md

The security record for SplitDec: the model it relies on, the controls that
ship today, the risks accepted deliberately, what to do when something goes
wrong, and what is queued for later.

**Why this file exists separately from `GO-LIVE.md`.** Security work outlived
the launch checklist. `GO-LIVE.md` is a list that ends — items close and the
file eventually stops mattering. This one does not: it carries standing
invariants, accepted-risk records that need re-reading on a schedule, and an
incident runbook that is worth nothing if it has to be found inside a launch
document. Anything security-related that is genuinely a *launch gate* stays in
`GO-LIVE.md` and is cross-referenced from here; everything else lives here.

Architecture and the reasoning behind the code live in `CLAUDE.md`. This file
does not duplicate it — it records the security-relevant consequences.

_Last reviewed: 2026-08-18. Next scheduled review: 2026-11-18 (see
[Review schedule](#review-schedule))._

---

## 1. The security model

Five invariants. Breaking any of them is a security change, not a refactor.

1. **FastAPI is the sole authorization boundary.** Row Level Security is
   **intentionally disabled**, and the Data API's `anon`/`authenticated` grants
   were revoked by migration (`20260702000001_lock_down_data_api.sql`). There is
   no second line of defence behind the API layer — every endpoint checks
   membership itself, via `deps.py`. Do not enable RLS as "extra safety" without
   redesigning the layer that currently owns the decision, and do not weaken a
   FastAPI check on the assumption that something downstream will catch it.

2. **Authentication is stateless.** `auth.py` verifies a Supabase-issued JWT
   (ES256 via JWKS, with an HS256 fallback for the legacy shared-secret mode)
   and reads only the `sub` claim. No session table exists. The practical
   consequence, which matters in an incident: **the application cannot revoke
   anything.** Revocation is a Supabase-side operation. See
   [§5.1](#51-a-session-token-is-stolen).

3. **The browser holds the session.** supabase-js persists the access *and*
   refresh token in `localStorage`. This is an accepted risk with a written
   justification — see [AR-1](#ar-1-session-tokens-live-in-localstorage).

4. **Production is same-origin.** One Vercel project path-routes `/api/*` to the
   function, so there is no CORS in production; the dev-only CORS middleware is
   gated on `ENV=development` and fails closed. The apex must remain the serving
   origin — installed PWAs pin theirs.

5. **Old tokens outlive account deletion.** Deletion anonymises `public.users`
   and removes the `auth.users` row, but a JWT already issued stays
   cryptographically valid until it expires. Any endpoint not gated by group
   membership must therefore call `get_active_user`.

---

## 2. Controls that ship today

### 2.1 Transport and response headers

Defined in `vercel.json`, asserted by `tests/test_vercel_config.py` — nothing
else in the suite exercises that file, so a dropped header would otherwise ship
silently.

| Control | Value |
| --- | --- |
| HSTS | `max-age=63072000; includeSubDomains; preload` |
| Framing | `frame-ancestors 'none'` **and** `X-Frame-Options: DENY` |
| MIME sniffing | `X-Content-Type-Options: nosniff` |
| Referrer | `strict-origin-when-cross-origin` |
| Permissions | `camera=(), microphone=(), geolocation=(), payment=()` |
| Script-level CSP | **Report-Only** — see [§2.2](#22-content-security-policy-staged) |

### 2.2 Content Security Policy (staged)

The enforcing `Content-Security-Policy` header still carries `frame-ancestors
'none'` alone. The full policy ships alongside it as
`Content-Security-Policy-Report-Only`:

```
default-src 'self';
script-src 'self' 'sha256-qLrhRjI+UdLfAR8XFet3vZ+XqJqzt1VDGNgo6lhuh6c=';
style-src 'self';
img-src 'self' https://googleusercontent.com https://*.googleusercontent.com;
font-src 'self' data:;
connect-src 'self' https://kmlheefyzhhegxmtaovq.supabase.co;
worker-src 'self'; manifest-src 'self';
base-uri 'none'; form-action 'self'; frame-ancestors 'none';
object-src 'none'; frame-src 'none';
upgrade-insecure-requests
```

Four things about this policy are load-bearing and non-obvious. All four were
established by building the app and serving `dist/` with the policy
**enforcing** in a real browser — not by reading source, which would have got
one of them wrong:

- **`font-src` must allow `data:`.** Vite inlines the smallest Manrope woff2
  subset as a base64 URI into the built CSS. `font-src 'self'` alone drops a
  font that is actually in use.
- **The inline theme script is allowed by hash, not nonce.** A single static
  `index.html` is served through a rewrite, which makes per-response nonces
  impractical. `tests/test_vercel_config.py` **recomputes the hash from
  `index.html`** rather than hard-coding it, so editing that script fails CI
  with the exact replacement string instead of silently reverting the app to a
  light-mode flash.
- **It is the only inline script.** `vite-plugin-pwa` emits its service-worker
  registration as an external `/registerSW.js`. If that ever changes, the policy
  needs a second hash or offline support breaks.
- **`style-src 'self'` is sufficient.** React's inline `style` prop writes
  through the CSSOM, which CSP does not police. No `'unsafe-inline'` is needed
  for styles, and none should be added.

Verified blocked under enforcement: off-origin `fetch()`, and `eval()`.
Verified still working: the hashed theme script, service-worker registration,
the Supabase auth origin, lazy route chunks, signed-out deep links.

**The tests read whichever header carries `script-src`**, so promoting the
policy is a one-key rename rather than a test rewrite — and a separate assertion
requires the *enforcing* header to keep `frame-ancestors`, so the flip cannot
quietly demote framing protection.

Promotion is [OA-1](#oa-1-finish-the-csp-soak-and-flip-to-enforcing).

### 2.3 Application controls

| Control | Where | What it stops |
| --- | --- | --- |
| API docs are development-only | `docs_urls(ENV)`, `api/_src/main.py` | Third-party CDN script executing on the session origin; endpoint enumeration via `/api/openapi.json`. Fails closed: the test is `== "development"`, so an unset `ENV` costs a dev convenience rather than exposing anything |
| Avatar URL allow-list | `src/lib/avatarUrl.ts` | Any group member pointing every other member's browser at a host they control (IP, rough location, presence). `https:` on `googleusercontent.com` or a subdomain only |
| Legal-link scheme allow-list | `renderLegalText`, `LegalPage.tsx` | `javascript:` hrefs the day those documents stop being repo-owned copy. Unknown schemes render as plain text rather than vanishing |
| `mailto` address encoding | `MembersTab.tsx` | An address containing `&` or `?` splicing extra fields into the draft |
| No user-search endpoint | removed deliberately | An email-registration oracle. `GET /users/search` and the direct add-member endpoint are gone and must not return |
| Uniform invitation responses | `api/_src/routers/invitations.py` | The same oracle by another route. Same response shape, same email attempt, same latency whether or not the address has an account. Never reintroduce `user_exists` / `email_sent` / `invited_user_id` |
| Write quotas | `api/_src/ratelimit.py` | Volume abuse. Counted from `write_events` tombstones, so create-fill-delete cannot reset a window |
| Group row locks | `deps.py` | Not a security control, but the reason concurrent ledger mutations cannot corrupt balances |
| Email HTML escaping | `invitation_email_content`, `api/_src/emailer.py` | Injection into mail sent under our own sending domain — the one place the codebase builds markup from user input |
| Invitation cleanup on deletion | `delete_account` | Pending invitations are unexpiring capabilities matched by email; the next holder of a recycled address would otherwise inherit them |

### 2.4 The XSS audit of 2026-08-15

Ran clean, and the finding is a *precondition* for several decisions below —
including the deferral in [§6.1](#61-phase-2-backend-owned-sessions). If a
future change breaks one of these properties, re-read that deferral, because its
justification no longer holds:

- **No HTML sinks exist in `src/`.** `dangerouslySetInnerHTML`, `innerHTML`,
  `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, `new Function`,
  string-form `setTimeout`, `srcDoc` and `postMessage` handlers are all absent.
  Every user-controlled string — group name, expense description, `full_name`,
  email — reaches the DOM as a JSX text child, so React escapes it.
- **`t()` returns a `string`, not markup** (`src/lib/i18n.tsx`).
- **`renderLegalText` emits React elements, not HTML.**
- **The backend serves JSON only.** No `HTMLResponse`, no templates; every
  `HTTPException` detail is a constant or interpolates an already-validated
  value.

The three findings it did produce were fixed the same week and are rows in
[§2.3](#23-application-controls): the Swagger CDN script, the unvalidated
avatar URL, and the legal-link scheme check.

### 2.5 Supabase posture

- Project `kmlheefyzhhegxmtaovq`, region `eu-west-3` (Paris), Postgres 17.
- Connections use the transaction pooler (6543) with `NullPool` and
  `statement_cache_size=0`. Never per-request engines, never the session pooler.
- **Advisor check, 2026-08-18:** one finding — *Leaked Password Protection
  Disabled* (`WARN`, external-facing). Tracked as
  [OA-3](#oa-3-enable-leaked-password-protection). Notably the advisor returned
  **no RLS findings**, which is the positive confirmation that the Data API
  grant revocation is holding: the tables are not reachable to lint.
- Signup and password-reset responses are deliberately enumeration-safe.
- `MIN_PASSWORD_LENGTH` in `src/lib/authErrors.ts` must stay in sync with the
  dashboard minimum (both 8 today).

---

## 3. Accepted risks

Each entry states what is accepted, why, what compensates for it, and when it
gets re-read. An accepted risk with no review date is not accepted — it is
forgotten.

### AR-1: Session tokens live in `localStorage`

**Accepted 2026-08-18. Review 2026-11-18.**

`src/lib/supabase.ts` sets `persistSession: true` with no custom storage, so
supabase-js keeps both the access token and the **refresh token** in
`localStorage`. `src/lib/api.ts` reads that session and sends the access token
as a bearer header. Any JavaScript executing in the page can read both.

**Why this is worse than a typical session cookie exposure:** the refresh token
survives the tab. A single successful injection yields durable account access,
not a session that dies when the page closes.

**Why it is accepted for now:**

- The 2026-08-15 audit found **no exploitable injection anywhere**, and the
  properties that make that true are written down in
  [§2.4](#24-the-xss-audit-of-2026-08-15) so a change that breaks one is
  visible at review time.
- No third-party script is served from the application origin. The one that was
  — the Swagger CDN bundle — was found and removed.
- The compensating control is the CSP in [§2.2](#22-content-security-policy-staged),
  which blocks the convenient exfiltration paths (`fetch`, beacons, `eval`).
- The alternative is a substantial architectural change with its own new risks;
  it is assessed in [§6.1](#61-phase-2-backend-owned-sessions) and has a fixed
  decision date rather than an open-ended one.

**What is honestly *not* covered.** Stated plainly so this acceptance is not
mistaken for a solved problem:

- CSP does **not** stop exfiltration by top-level navigation
  (`location = 'https://…/' + token`). No shipped CSP directive governs it.
- CSP does **not** stop an injected script acting as the user in-page against
  our own API — and neither would an HttpOnly cookie.
- Shortening the access-token lifetime ([OA-2](#oa-2-verify-supabase-token-lifetime-rotation-and-reuse-detection))
  reduces the value of a stolen access token but **not** of a stolen refresh
  token.

**Therefore the acceptance is conditional**, and the conditions are the
tripwires in [§6.1](#61-phase-2-backend-owned-sessions).

### AR-2: RLS is disabled

**Accepted (long-standing). Review 2026-11-18.**

The FastAPI layer is the sole authorization boundary. Accepted because the Data
API grants were revoked, so Postgres is not directly reachable by the anon key,
and because a second policy layer that disagrees with the first is its own class
of bug. Compensating control: every endpoint's membership check is centralised
in `deps.py` rather than repeated per route. Verification: the anon-key REST
probe in `GO-LIVE.md` item 5 (§A8), plus the advisor check in
[§2.5](#25-supabase-posture).

### AR-3: `master` is unprotected

**Accepted (pending decision). Review at launch.**

The `develop` → PR → `master` workflow is enforced by convention, not by branch
protection. Tracked as a launch decision in `GO-LIVE.md` item 6 — it stays there
because it is a launch gate, not because it is not a security control. Note the
trap recorded there: the `claude-review` check reports success even when it
posts nothing, so requiring it is weaker evidence than it looks.

---

## 4. Open actions

Ordered by expected risk reduction per unit of effort.

### OA-1: Finish the CSP soak and flip to enforcing

The policy is written, tested and shipping report-only. What remains is
exercising the flows a signed-out local probe cannot reach, then renaming one
key in `vercel.json`.

Soak checklist — run each against production with the browser console open, and
watch for `Refused to…` messages:

- [ ] Google OAuth round trip (sign-in and the callback landing)
- [ ] Password recovery link → `/reset-password` → signed-in re-render
- [ ] Email confirmation link from a fresh signup
- [ ] An **installed PWA** upgrading onto the deploy that carries the policy
- [ ] A signed-in session: group screens, all four tabs, avatars actually
      loading from `lh3.googleusercontent.com`

**Known limitation of the soak.** Report-only ships with **no collector**, so
violations appear in the browser console only — this is a deliberate manual
pass, not a self-reporting one. A `/api/csp-report` endpoint was considered and
declined: it is a public unauthenticated write surface on a function whose
write paths are otherwise all quota-braked. Revisit if the soak proves
impractical by hand ([§6.3](#63-a-csp-report-collector)).

Then: rename `Content-Security-Policy-Report-Only` → `Content-Security-Policy`
and drop the old framing-only entry. The tests follow the rename unedited.

**Expected side effect:** the Vercel preview toolbar (`vercel.live`) will be
blocked on preview deployments, since `script-src 'self'` does not allow it.
Production is unaffected.

### OA-2: Verify Supabase token lifetime, rotation and reuse detection

Not yet verified — the values below could not be read through tooling and must
be checked in the dashboard. Recorded as unknown rather than assumed.

In **Authentication → Sessions / Tokens**, confirm and record here:

| Setting | Target | Current |
| --- | --- | --- |
| Access token (JWT) expiry | 900–1800 s (down from the 3600 s default) | _unverified_ |
| Refresh token rotation | Enabled | _unverified_ |
| Reuse-detection interval | Enabled, short | _unverified_ |
| Time-boxed session length | Consider a fixed cap | _unverified_ |

**Why this matters given [AR-1](#ar-1-session-tokens-live-in-localstorage):** an
access token cannot be revoked once issued — it is a stateless JWT, valid until
`exp`. Its lifetime *is* the revocation delay. Rotation plus reuse detection is
what makes a stolen **refresh** token detectable: when the legitimate client
next presents the rotated-away token, Supabase can invalidate the whole family.

Shortening the access-token TTL trades a little latency (more refresh round
trips) for a proportionally shorter window on every stolen access token. It is
the cheapest meaningful mitigation available for AR-1.

### OA-3: Enable leaked-password protection

Flagged by the Supabase advisor on 2026-08-18 and relevant because the app has
email/password signup, not only OAuth. Checks candidate passwords against
HaveIBeenPwned. **Pro-gated**, so it lands with the plan upgrade — tracked as a
launch item in `GO-LIVE.md` §B2. Review Auth rate limits in the same pass.

### OA-4: Detection — error tracking and an uptime check

Cross-reference: `GO-LIVE.md` item 7 (§A5), where it stays because it is
launch-scoped code work.

Recorded here because it is a **security** gap, not only an ops one: there is
currently no aggregated error tracking, so **nothing would reveal an exploited
injection**, and nothing will reveal a CSP violation in the field once the
policy is enforcing. Every mitigation in this document is unobservable until
this lands.

### OA-5: Rotate the credentials that passed through chat and tooling

Cross-reference: `GO-LIVE.md` item 4 (§A3), where it stays because it is an
explicit pre-launch gate.

Supabase database password and the Resend API key. Git history was checked on
2026-08-14 and is clean — these reached chat and tooling, which is a different
exposure with the same fix. See [§5.2](#52-a-credential-leaks) for the runbook.

---

## 5. Incident response

The app has no session store and no durable audit log, so both facts shape every
runbook below. Read [§5.4](#54-what-evidence-actually-exists) before starting an
investigation, so you know what you can and cannot reconstruct.

### 5.1 A session token is stolen

Assume both the access and the refresh token are compromised — they are stored
together.

**Step 1 — Revoke the refresh tokens for the affected user.** This is a
Supabase-side action; the application has nothing to revoke.

- Dashboard: **Authentication → Users →** the user **→ sign the user out** (all
  sessions).
- Or the Auth admin API, with the **service-role** key, server-side only:
  ```
  POST {SUPABASE_URL}/auth/v1/admin/users/{user_id}/logout
  Authorization: Bearer {SERVICE_ROLE_KEY}
  ```
  Prefer a global scope so every device is signed out, not just one.

**Step 2 — Accept that the access token stays valid until it expires.** It is a
stateless JWT; `auth.py` verifies the signature and reads `sub`, and nothing
consults a revocation list. The exposure window is exactly the access-token
lifetime — which is why [OA-2](#oa-2-verify-supabase-token-lifetime-rotation-and-reuse-detection)
is not cosmetic. If that window is unacceptable in the moment, go to step 5.

**Step 3 — Force a credential change.** For password accounts, trigger a reset
and require it. For Google OAuth accounts the password path does not apply —
signing out all sessions is the control, plus advising the user to review their
Google account security if the compromise was on their side.

**Step 4 — Assess the damage.** See
[§5.4](#54-what-evidence-actually-exists) for what is actually recoverable.
Expenses and settlements are **soft-deleted**, so ledger tampering is usually
reconstructible; group deletion is a **hard** delete and is not.

**Step 5 — If the compromise is broad or the access-token window is too long:**
rotate the project's JWT signing key in Supabase. This invalidates *every*
outstanding access token and signs out **all** users. It is the only way to
shorten an already-issued token's life. Treat it as the nuclear option and
expect support load; note that `auth.py` accepts both ES256 (JWKS) and HS256, so
confirm which mode is live before rotating.

**Step 6 — Record it here** as a dated entry in [§7](#7-change-log), including
whether the tripwires in [§6.1](#61-phase-2-backend-owned-sessions) should now
be considered fired.

### 5.2 A credential leaks

Database password, `RESEND_API_KEY`, or the Supabase service-role key.

1. Rotate at the source (Supabase → Database / Settings; Resend → API Keys).
2. Update the corresponding environment variable on Vercel and redeploy.
3. **Any `VITE_`-prefixed variable is public** — Vite inlines it into the bundle
   every visitor downloads. If a real secret ever acquires that prefix, treat it
   as disclosed and rotate it, regardless of whether the repo is public.
4. For the service-role key specifically: it bypasses every check in this
   document. Confirm it appears in no committed file and no client bundle —
   `git log -S` across all branches found no occurrence on 2026-08-14.

### 5.3 An XSS is found

1. Fix the injection itself first; the CSP is blast-radius, not a fix.
2. Treat **every** active session as potentially compromised — AR-1 means an
   injection yields refresh tokens. Consider the global revocation in
   [§5.1 step 5](#51-a-session-token-is-stolen).
3. The tripwires in [§6.1](#61-phase-2-backend-owned-sessions) have fired by
   definition. Re-open the phase-2 decision immediately rather than waiting for
   the scheduled date.
4. Update [§2.4](#24-the-xss-audit-of-2026-08-15): the audit's central claim is
   no longer true, and several decisions in this file depend on it.

### 5.4 What evidence actually exists

Know this **before** an incident, not during one.

- **`write_events` is not an audit log.** It is a quota ledger. `record_write`
  opportunistically prunes rows that have aged out of the 24-hour window, and
  `delete_account` clears a user's rows outright. Useful for "what happened in
  the last day", useless for anything older. It also stores only a
  `recipient_hash` (bare SHA-256) for invitations, never an address.
- **Soft deletes preserve ledger history.** Expenses and settlements are
  soft-deleted and filtered independently, so tampering is generally
  reconstructible from the rows themselves.
- **Group deletion is a hard delete** and takes its expenses, settlements and
  invitations with it. That data is gone.
- **No point-in-time recovery on the Supabase free tier.** Until the Pro
  upgrade (`GO-LIVE.md` §B1), there is no database rollback.
- **Supabase Auth logs** carry sign-in events; retention depends on plan.
- **Vercel runtime logs** are short-retention on the current plan.

The gap is deliberate but worth naming: **there is no durable application-level
audit trail.** See [§6.4](#64-a-durable-audit-trail).

---

## 6. Future considerations

Not scheduled work. Each has a trigger or a date so nothing sits here
indefinitely.

### 6.1 Phase 2: backend-owned sessions

**Decision date: 2026-11-18.** Fixed, not trigger-dependent — the tripwires
below can only pull it *earlier*, never push it out. On that date the decision
gets made and recorded in [§7](#7-change-log), even if the outcome is "defer
again with a new date".

The proposal: move login, OAuth callback, confirmation, recovery, refresh and
logout behind FastAPI `/api/auth/*`, and hold the session in a `__Host-`
cookie — `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, no `Domain` — with only
its hash stored server-side, plus exact Origin validation and a session-bound
CSRF header on unsafe requests.

**What it buys.** It removes the credential from JavaScript entirely, which
closes token theft outright — including the navigation-based exfiltration that
CSP cannot stop. That is a real gain over the current posture.

**What it does not buy.** An injected script still transacts as the user through
a cookie it cannot read. Phase 2 converts *durable account takeover* into
*session-bounded abuse*, which is narrower than "removes browser-readable
credentials" suggests.

**What it costs here:**

- Auth becomes stateful on the hot path. Verification is currently a signature
  check with zero database round trips; an opaque session id adds a lookup per
  request, on a serverless function using `NullPool` against a transaction
  pooler, deliberately collocated with its database to control latency.
- It adds a secret — encrypted refresh material needs a key with a rotation
  story — to a project that has not yet executed its first rotation
  ([OA-5](#oa-5-rotate-the-credentials-that-passed-through-chat-and-tooling)).
- Auth-critical code moves in-house. Login, PKCE exchange, refresh rotation,
  reuse-detection handling and CSRF defence become ours. Replacing an audited
  dependency with bespoke code relocates risk rather than removing it.
- It reverses the stateless, provider-neutral invariant in
  [§1](#1-the-security-model), which warrants its own design record.

**A middle option worth evaluating on the same date:** an encrypted `HttpOnly`
cookie carrying the Supabase tokens, which the backend decrypts and forwards.
That removes JS readability with no session table and no per-request database
read, and leaves GoTrue as the auth authority. It forfeits server-side
revocation, must fit the 4 KB cookie limit, and still requires CSRF defence.

**Tripwires that pull the date forward.** Any of these fires → decide
immediately rather than waiting:

- Any third-party script served from the application origin.
- Any user-supplied content rendered as markup (markdown in descriptions, rich
  text in notes).
- Contributors beyond the single maintainer.
- Any confirmed XSS ([§5.3](#53-an-xss-is-found)).

The tripwires exist because the acceptance in
[AR-1](#ar-1-session-tokens-live-in-localstorage) rests on properties of the
code, not on usage — so the honest trigger is a code event a reviewer notices,
and the fixed date is what stops "no trigger yet" becoming "never looked again".

### 6.2 Remove the HS256 fallback

`auth.py` selects its verification algorithm from the token's **unverified**
header, falling back to HS256 with `SUPABASE_JWT_SECRET` when that is what the
header claims. This is deliberate — it supports the legacy shared-secret signing
mode — and it is **not a live vulnerability**: forging a token still requires
the shared secret, which is server-side.

It is worth closing anyway. Once the project is confirmed to be on asymmetric
signing keys only, drop the HS256 branch and unset the secret. That removes a
forgery path whose only barrier is a long-lived secret that is never rotated,
and it removes the algorithm-selection-from-attacker-input shape entirely.

**Trigger:** confirm the signing mode during
[OA-2](#oa-2-verify-supabase-token-lifetime-rotation-and-reuse-detection); if
asymmetric-only, this becomes a small, safe change.

### 6.3 A CSP report collector

Declined for now (see [OA-1](#oa-1-finish-the-csp-soak-and-flip-to-enforcing)).
Reconsider if the manual soak proves impractical, or once the policy is
enforcing and silent breakage in the field becomes the concern. Any endpoint
must be quota-braked like every other write path.

### 6.4 A durable audit trail

`write_events` is pruned and cannot serve as one
([§5.4](#54-what-evidence-actually-exists)). A genuine append-only log of
security-relevant events — sign-ins, permission changes, deletions — would make
[§5](#5-incident-response) materially more useful. Weigh against the privacy
posture: `src/lib/legal.ts` governs what may be retained, and any new retention
changes that file and bumps `LEGAL_UPDATED`.

### 6.5 Navigation-based exfiltration

No shipped CSP directive constrains top-level navigation, so the gap named in
[AR-1](#ar-1-session-tokens-live-in-localstorage) has no header-level fix
today. Nothing to do now; revisit if a widely-supported directive lands.

---

## Review schedule

| When | What |
| --- | --- |
| **2026-11-18** | Phase-2 decision ([§6.1](#61-phase-2-backend-owned-sessions)); re-read every accepted risk in [§3](#3-accepted-risks); re-confirm the [§2.4](#24-the-xss-audit-of-2026-08-15) properties still hold |
| At launch | [OA-3](#oa-3-enable-leaked-password-protection) with the Pro upgrade; the AR-3 branch-protection decision |
| Every PR | Does this change add a third-party script, render user content as markup, or touch `auth.py`, `deps.py`, `vercel.json` or `index.html`? If yes, this file is in scope for the review |
| On any incident | The relevant runbook in [§5](#5-incident-response), then a dated entry in [§7](#7-change-log) |

---

## 7. Change log

- **2026-08-18** — File created. Security content moved out of `GO-LIVE.md`
  (item 12 in full, plus the XSS-audit record). Full CSP shipped report-only
  (PR #47). [AR-1](#ar-1-session-tokens-live-in-localstorage) recorded as a
  conscious acceptance. Phase 2 given the fixed decision date 2026-11-18.
  Supabase advisor run: one finding
  ([OA-3](#oa-3-enable-leaked-password-protection)), no RLS findings.
- **2026-08-15** — XSS audit ran clean. Swagger UI closed in production; avatar
  URLs allow-listed; legal-link schemes checked; `mailto` address encoded.
- **2026-08-14** — Git history confirmed free of secrets across all branches.
- **2026-07-02** — Data API `anon`/`authenticated` grants revoked by migration.
