# SplitDec — Pre-Go-Live Checklist

Things to do before treating SplitDec as a real, publicly-usable product.
The app is fully functional today at https://split-dec.app; the items below
are about production-readiness, deliverability, security hardening, and
polish — not missing features.

(Use the apex when linking to the app. `split-dec.vercel.app` still serves it,
but it now carries `X-Robots-Tag: noindex` so it cannot compete with the
canonical domain in search — item 11.)

Status legend: ☐ not started · ◐ partial · ☑ done

---

## Remaining before launch, in dependency order

An index into the items below — the detail stays in each section. The app
itself is feature-complete and green (137 backend tests, 153 frontend, build).
**Everything still outstanding is ops, config or legal** — dashboards, DNS,
billing and a lawyer's eye. The code-side work is done; item 6 is the only
entry with a code component left in it (wiring an error tracker).

**Critical path — these gate a public launch:**

1. **Inbound mail for `privacy@split-dec.app`** (item 8). It is the contact
   point published in both legal documents. Nothing else can be true until
   mail to it is delivered somewhere a human reads.
2. **Publish the Google OAuth consent screen** (items 2 + 3). Until then you
   are capped at 100 hand-added test users and everyone sees an "unverified
   app" warning. Needs the `/privacy` and `/terms` URLs (done, item 8) and
   `split-dec.app` added to authorized domains. **Longest lead time —
   verification can take days, so start it first once item 1 is done.**
3. **Rotate the secrets that passed through chat/tooling** (item 4) — Supabase
   DB password and the Resend API key.
4. **Supabase Pro** (item 5). The free tier pauses after ~1 week of inactivity
   and has **no point-in-time recovery**. This is the item with the worst
   failure mode: holding other people's shared ledgers with no backups.
5. **Bilingual PL+EN auth email templates** (item 1). SMTP is verified
   end-to-end; only the Supabase default templates remain.

**Should land before real traffic, but not blocking:**

6. Uptime check on `/api/health` and some error aggregation (item 7).
7. Branch protection, if the repo goes public or onto GitHub Pro (item 6).
8. Legal review of the text drafted in item 8.

**After launch:** buycoffee.to profile and its tax treatment (item 9) and the
TWA/Play Store path (item 10).

**Item 11 is fully closed.** Rate limiting, the 404 page and empty states, SEO
and route-level code splitting shipped earlier; the two follow-ups they left
behind — a tombstone so group deletion can't reset a write quota, and
vendor-chunk splitting — landed on 2026-08-13. One narrower gap of the same
shape is newly recorded there: the *invitation* quotas still count rows that a
group deletion cascades away.

---

## Verified in production — 2026-08-12

Checked against `https://split-dec.app` on commit `1ead6b2`, not inferred from
a green build:

- All six security headers present on the apex; `X-Robots-Tag: noindex,
  nofollow` present on `split-dec.vercel.app` and **absent** from the apex and
  its subpages, so the host scoping does what it was written for.
- `www` 308s to the apex on `/` and on a subpath, query string preserved.
- `robots.txt` (`text/plain`) and `sitemap.xml` (`application/xml`) serve, the
  sitemap listing exactly the three public routes.
- `/privacy` and `/terms` render with their `mailto:` contact live, and pull
  `LegalPage-*.js` as a separate chunk — code splitting confirmed on the wire.
- `/api/health` returns ok; `POST /api/groups` without a token returns 401.
- Signed-out `/groups/<id>` still serves the sign-in screen, so invitation deep
  links survive.
- Signed-in 404 confirmed by hand (it is behind auth, so no automated probe
  covers it).

One incidental finding worth keeping: the first browser load was served by an
**already-installed service worker** from an older deploy and reported a stale
bundle hash before auto-updating. Harmless here, but it is the exact stale-shell
scenario the `ErrorBoundary` in item 11 exists to catch, observed live. When
re-probing after any deploy, expect that and cache-bust.

---

## 1. Email deliverability (invitations + auth emails) — ◐ SMTP done, templates pending
Domain **`split-dec.app`** verified in Resend (DKIM/SPF/return-path live,
region eu-west-1). `RESEND_FROM=SplitDec <invites@split-dec.app>` and
`APP_URL=https://split-dec.app` set on Vercel production. Supabase custom
SMTP configured (smtp.resend.com:465, user `resend`, dedicated sending-only
API key, sender `auth@split-dec.app`) and **verified end-to-end**: a test
signup dispatched its confirmation email through Resend successfully
(Resend rejects recipients at reserved domains like example.com — use
`delivered@resend.dev` for tests). Custom SMTP also raised the auth email
rate limit to 30/hour.
- ☐ **Bilingual PL+EN email templates** (Authentication → Emails →
  Templates → "Confirm sign up" and "Reset password") — still Supabase's
  EN-only defaults; the dashboard Templates page was returning an internal
  error during a Supabase incident on 2026-07-18 (Site URL config on the same
  dashboard worked fine, so this looks incident-specific, not a lasting
  problem) — retry when the page loads. Suggested copy (subjects + bilingual
  HTML bodies, `{{ .ConfirmationURL }}` placeholder) was drafted in-session;
  ask Claude to regenerate it if not saved.

## 2. Google OAuth consent screen — ☐
- Confirm the Google Cloud OAuth app is **published** (not "Testing", which
  caps at 100 hand-added test users and shows an "unverified app" warning).
- Complete the OAuth consent screen (app name, logo, support email, privacy
  policy + terms URLs, authorized domains). The URLs now exist:
  `https://split-dec.app/privacy` and `https://split-dec.app/terms` (item 8).
- Google verification may be required for the app to avoid the warning screen
  once published — plan for a few days' review.

## 3. Custom domain for the app — ◐ apex is canonical and routing is closed
- ☑ **`https://split-dec.app` (apex) is the primary domain.** A brief
  www-primary configuration (2026-07-18) caused a production incident:
  service workers registered on the apex kept serving the app shell from
  cache while `/api/*` 308-redirected to www — a cross-origin hop the
  CORS-less API correctly refuses → "Failed to fetch". SW update fetches
  also reject redirects, so apex-origin installs could never self-heal.
  **Lesson: never turn a previously-serving origin into a redirect** —
  the PWA pins its install origin.
- ☑ www → apex 308 is enforced in `vercel.json` (host-conditional redirect,
  versioned in git — the dashboard-level redirect toggle did not persist).
  `APP_URL=https://split-dec.app`.
- ☑ **Supabase Auth → URL Configuration: Site URL fixed** to
  `https://split-dec.app` (was `https://split-dec.vercel.app`) — confirmed
  by probing the verify-endpoint fallback, which now lands on the apex.
- ☑ **Fixed and verified in production (PR #26, merged 2026-07-31) — the
  www→apex redirect did not fire for the bare root `/`, and it was a full
  outage, not a cosmetic one.** `/` served the
  SPA shell from www (200) while *every* other path — `/api/*`, `/sw.js`,
  `/manifest.webmanifest` — 308'd to the apex. So the app booted on www and
  its same-origin `/api/*` calls became a cross-origin hop; requests carry an
  `Authorization` header, so they preflight, and a redirected preflight is a
  hard network error. Anyone typing the domain and getting autocompleted to
  www loaded the UI, logged in, and hit "Failed to fetch" on the first data
  request (reported by a tester, 2026-07-31). The earlier "low severity,
  still gets a fully working app" note was wrong.
  - ☑ Explicit `/` redirect rule added ahead of `/:path*` in `vercel.json`
    (`/:path*` does not match the bare root on Vercel's router), asserted by
    `tests/test_vercel_config.py::test_www_redirect_covers_the_bare_root`.
  - ☑ Client-side backstop `src/lib/canonicalHost.ts`, called from
    `main.tsx` before the app mounts, in case edge routing still misses `/`.
  - Safe to redirect www because nothing was ever *installed* from it:
    `/sw.js` 308s cross-origin, so service-worker registration always failed
    there. No www-pinned PWA exists to strand (unlike the apex on 07-18).
  - ☑ Verified in production post-deploy: `https://www.split-dec.app/` now
    308s to the apex (query string preserved), as do `/groups/*`, `/api/*`
    and `/sw.js`; a real browser lands on `https://split-dec.app/` in one hop
    with no console errors. `split-dec.vercel.app` is untouched and still
    serves its own API same-origin. The domain-level redirect (Settings →
    Domains) was therefore not needed — `vercel.json` alone covers `/`.
    Note when re-probing: Vercel's CDN caches the old root response, so a
    stale `200` right after deploy is not proof of failure — cache-bust.
- ☐ Google OAuth consent screen: add `split-dec.app` to authorized domains
  (the OAuth callback itself stays on the Supabase domain — no redirect URI
  change needed).

## 4. Rotate secrets that passed through chat/tooling — ☐
These were shared during development and should be rotated before launch:
- **Supabase database password** (Project Settings → Database) → update
  `DATABASE_URL` on Vercel.
- **Resend API key** (Resend → API Keys) → update `RESEND_API_KEY` on Vercel.
- Review the Supabase publishable/anon key exposure (it is public by design,
  but confirm no service-role key is anywhere in the frontend or git history).

## 5. Supabase production readiness — ☐
- **RLS stays disabled by design** (the FastAPI layer is the sole authz
  boundary; Data API grants were revoked in migration
  `20260702000001_lock_down_data_api.sql`). Re-confirm no table is reachable
  via the anon key: a quick `curl` to the REST endpoint should 401/empty.
- Free tier **pauses the project after ~1 week of inactivity** and has no
  point-in-time recovery — upgrade to Pro for uptime + daily backups before
  real users depend on it.
- Confirm the DB connection uses the **Transaction Pooler (port 6543)** in
  production `DATABASE_URL` (it does today).
- Email/password auth: enable **leaked-password protection** (HaveIBeenPwned
  check, Pro-only) and review Auth rate limits once on Pro. Keep the dashboard
  minimum password length in sync with `MIN_PASSWORD_LENGTH` in
  `src/lib/authErrors.ts` (both 8 today).

## 6. Branch protection / CI gating — ☐
- Enforcing "CI green before merge to `master`" needs GitHub Pro on a private
  repo, or making the repo public. Today the gate is by convention.
- Optionally require the Claude review to pass / be acknowledged.

## 7. Observability & error handling — ◐
- The invitation emailer now logs send failures (no more silent swallow), but
  there's no aggregated error tracking. Consider Sentry (frontend + FastAPI)
  or at least periodic review of Vercel runtime logs. Failures are logged by
  invitation id with a status code only — recipient addresses and provider
  response bodies are deliberately kept out of the retained logs, so
  diagnosing a specific delivery means looking it up in Resend.
- Invitation sending is quota-limited in `api/_src/routers/invitations.py`
  (per inviter / per recipient / global, 24h windows). The numbers there are
  a guess at ordinary usage — revisit once there is real traffic, and note
  that a legitimate power user hitting a 429 has no self-service escape.
- Add a lightweight uptime check on `/api/health`.

## 8. Legal / privacy — ◐ pages live, contact mailbox + review pending
- ☑ **Privacy Policy at `/privacy` and Terms of Service at `/terms`**, bilingual
  EN+PL, in `src/lib/legal.ts` (document bodies) rendered by
  `src/pages/LegalPage.tsx`. Both routes are registered in **both** auth
  branches of `App.tsx` — like `/reset-password` — so they resolve for
  signed-out visitors instead of being swallowed by the catch-all, and they
  render identically whether or not you are signed in. Linked from the landing
  footer, the login screen and the account modal via `LegalLinks`.
- The documents assert facts that are checked against the implementation:
  processors and their regions (Supabase eu-west-3, Vercel cdg1, Resend
  eu-west-1, Google only for OAuth), what account deletion actually erases vs.
  anonymizes, what group members can see, and that no analytics/ad cookies
  exist. **If any of that changes, `src/lib/legal.ts` changes with it** — and
  bump `LEGAL_UPDATED`.
- ☐ **Make `privacy@split-dec.app` actually receive mail** before launch — it
  is the contact point in both documents and for GDPR requests. Resend inbound
  or a registrar-level forward to a real inbox. An address that bounces is
  worse than none.
- ☐ Have the text reviewed. It was drafted to be accurate about this specific
  app, not run past a lawyer; the liability, consumer-rights and governing-law
  clauses in particular are the ones worth a professional eye if usage grows
  beyond friends. Both documents state that the Polish version prevails.
- Note: these are SPA routes, so the served HTML is the app shell and the text
  is rendered by JS. Google's OAuth reviewers render pages, so this is normally
  fine — but if the review bounces on "policy not found", the fallback is a
  prerendered static `public/privacy.html` / `terms.html`.

## 9. Funding: buycoffee.to — ☐
SplitDec will be funded by voluntary payments via [buycoffee.to](https://buycoffee.to)
rather than subscriptions or ads.
- Create a **dedicated buycoffee.to profile for SplitDec** (not a personal
  account) — separate name/avatar/description, its own payout destination,
  and a clean transaction history if this ever needs accounting for.
- Check the tax treatment of received "coffees" before relying on this
  (Poland: occasional voluntary gifts vs. recurring/business-like income can
  be treated differently — worth a quick check with an accountant rather
  than assuming, since we're not qualified to give tax advice here).
- Once the profile exists, add a support link/button in the app (footer
  and/or the account menu) pointing at the SplitDec buycoffee.to page.
- Depends on item 8 (Privacy/Terms) if the link or its landing page collects
  any user data beyond what buycoffee.to itself handles.
- The Terms already carry a forward-compatible clause ("What SplitDec costs"):
  voluntary contributions buy no features, guarantees or priority, are not
  refundable, and are handled by the payment provider. Adding the link needs
  no Terms change — but if contributions ever unlock anything, that clause and
  the consumer-withdrawal position both have to be revisited.

## 10. Android app (Play Store) via TWA — ☐ (PWA prerequisite ☑)
The app is an installable PWA (manifest + service worker; Chrome → "Add to
Home Screen"). To turn it into a Play Store app:
1. `npx @bubblewrap/cli init --manifest https://split-dec.app/manifest.webmanifest`
   (Bubblewrap offers to install JDK/Android SDK; it generates a signing key).
   Use the **apex**, not `split-dec.vercel.app` — a TWA pins the origin it was
   built against, the same way an installed PWA does (item 3).
2. Serve `/.well-known/assetlinks.json` with the signing key's SHA-256
   fingerprint (drop the file in `public/.well-known/`) so the TWA runs
   fullscreen without the browser bar.
3. `npx @bubblewrap/cli build` → sideload the `.apk` to test, or upload the
   `.aab` to Google Play ($25 one-time developer account; privacy policy from
   item 8 is required for the listing).

## 11. Nice-to-haves before launch — ☑ all four shipped, follow-ups closed
The two limitations this item used to carry were closed on 2026-08-13; one
narrower gap of the same shape is recorded below and does not block a launch.
- ☑ **Rate limiting on write endpoints.** `api/_src/ratelimit.py`: expense and
  settlement creation share one 24h window (`MAX_LEDGER_WRITES_PER_CALLER`) and
  group creation has its own (`MAX_GROUPS_PER_CALLER`), both **per caller**, so
  neither limit can be sidestepped by making more groups. Invitations keep
  their own three windows and share the dialect-aware `window_cutoff` helper.
  - Counted from rows in the database, not process memory — the API is a
    serverless function with several instances and constant cold starts.
  - **Deliberately no global cap** on either window: it would turn one abusive
    account into an outage for everyone.
  - Replays are answered **before** the quota in both create endpoints: a
    client retrying a request whose response it never saw has already spent
    its slot, and a 429 there would leave it unable to discover whether the
    entry exists — the one thing `Idempotency-Key` is for.
  - ☑ **Both windows now survive a group deletion** (PR pending, 2026-08-13).
    They used to count the rows they protected, and deleting a group is a
    *hard* delete that takes its expenses and settlements with it, so
    create-group → fill → delete → repeat reset them — the brakes only stopped
    clients that were not trying. They now count `write_events`
    (`supabase/migrations/20260813000000_write_events.sql`): one append-only
    tombstone per charged write, keyed by the caller, that no cascade reaches.
    Note the `created_by`-column variant floated earlier does **not** work on
    its own — those rows die with the group too.
  - ☑ **The ledger window moved from per-group to per-caller** in the same
    change, which was the other half of the fix: a per-group window let one
    member consume everyone else's allowance. 300/caller/24h against a busy
    trip's ~50 leaves plenty of room.
  - `record_write` prunes the caller's aged-out rows opportunistically (no cron
    on a serverless function) and `delete_account` clears that user's, since
    nothing would prune them again.
  - **Remaining gap of the same shape: the invitation quotas.** They still
    count `group_invitations`, which `delete_group` cascades away, so an
    invite/delete-the-group loop resets all three windows. Not closed with the
    others because the per-recipient window is keyed by *email address*, and a
    table that outlives the group would retain addresses that account deletion
    is specifically required to anonymize (item 8) — it needs a retention
    decision, not just a migration. Resend's own sending limits are the
    backstop meanwhile.
  - The 429 `detail` reaches the UI as-is (English only), like the existing
    invitation quota message. Worth localizing if these start firing.
- ☑ **Empty-state polish and a 404 page.** Unmatched signed-in routes render
  `NotFoundPage` instead of redirecting to `/` — a stale or mistyped link used
  to look like it had worked. Signed-out unmatched routes still fall through to
  the login screen on purpose, so a deep link from an invitation email survives
  sign-in. The four "nothing here yet" cards now share `EmptyState`, and the
  groups/expenses ones offer the action that fills them (suppressed on the
  expenses tab when a payer filter is what emptied the list).
  Confirmed signed-in in production on 2026-08-12.
- ☑ **`robots.txt` / basic SEO meta.** `public/robots.txt` (assets left
  crawlable on purpose — the landing page is client-rendered, so a blocked JS
  bundle means an empty `<div id="root">`), `public/sitemap.xml` covering the
  only three public routes, and description/Open Graph/Twitter tags in
  `index.html`. **No `<link rel="canonical">`**: every route is rewritten to
  one `index.html`, so a static canonical would declare `/privacy` and
  `/terms` duplicates of the landing page. Cross-host duplication with
  `split-dec.vercel.app` is handled by a host-scoped `X-Robots-Tag: noindex`
  in `vercel.json` instead, asserted by `tests/test_vercel_config.py`.
  Neither file is service-worker precached (`globPatterns` covers no
  `.txt`/`.xml`), so crawlers always get the live copy.
- ☑ **Route-level code splitting.** The single ~670 kB chunk is now ~545 kB
  (~160 kB gzipped, down from ~195) with the rest split by auth branch, so a
  signed-in user never downloads the marketing page and a signed-out visitor
  never downloads the group screens: `LandingPage` (19 kB), `LegalPage`
  (32 kB), `ResetPasswordPage` (3 kB) and `GroupPage` (74 kB — all four tabs,
  both form modals, the pickers and the category icon table).
  - `LoginPage`, `GroupsPage`, `Layout` and `NotFoundPage` stay eager: they are
    on the first paint of one branch or the other, and a chunk request for the
    404 page would cost more than the page.
  - `GroupsPage` warms the `GroupPage` chunk from the same hover/focus intent
    that already prefetches group data, so opening a group never waits on it.
  - Splitting routes created a failure mode the single bundle could not have:
    a client on an old app shell whose next lazy import 404s after a deploy
    replaced the chunk hashes. `Suspense` covers a *pending* import, never a
    rejected one, so that would unmount the tree to a blank page. A top-level
    `ErrorBoundary` (`src/components/ErrorBoundary.tsx`, in `main.tsx`) reloads
    once on a chunk-load error — the thing that actually fixes a stale
    reference — with a cooldown so a genuinely missing chunk can't become a
    refresh loop, and a translated fallback otherwise. Ordinary render errors
    skip the reload; repeating a crash doesn't help.
  - ☑ **The vendor chunk was split out** (2026-08-13). `vite.config.ts`
    `manualChunks` pins React, React-DOM, the router, TanStack Query and
    supabase-js into `vendor` (488 kB / 141 kB gzipped), leaving the app's own
    entry chunk at 59 kB / 20 kB — so a deploy that only changes app code
    re-downloads ~20 kB instead of ~160 kB. Route chunks are unchanged
    (`GroupPage` 73.6 kB before and after).
  - The allow-list is explicit on purpose: sending *everything* in
    `node_modules` to `vendor` would hoist `lucide-react` out of the route
    chunks that tree-shake it, pushing `GroupPage`'s icon table into the
    bundle a signed-out visitor downloads. Verified on the wire against
    `npm run preview` over the built `dist/`, with the landing page and the
    lazy `/privacy` route both loading clean — `npm run dev` does not apply
    this chunking, so it cannot show you this.

---

_Last updated: 2026-08-13. Maintained alongside the develop → PR → master
workflow; update statuses as items land._
