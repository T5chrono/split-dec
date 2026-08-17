# SplitDec — Pre-Go-Live Checklist

Things to do before treating SplitDec as a real, publicly-usable product.
The app is fully functional today at https://split-dec.app; the items below
are production-readiness, deliverability, security hardening and polish — not
missing features. The app itself is feature-complete and green (149 backend
tests, 179 frontend, build), so **almost everything outstanding is ops, config
or legal**. Two entries carry code: item 7 (wire an error tracker) and item 12
(security hardening — none of it a live vulnerability, all of it blast radius;
12.2, 12.3, 12.4 and 12.5 are done and only the CSP, 12.1, remains).

Status legend: ☐ not started · ◐ partial · ☑ done

(Use the apex when linking to the app. `split-dec.vercel.app` still serves it
but carries `X-Robots-Tag: noindex`, so it cannot compete with the canonical
domain in search — item 11.)

---

## Current phase: open but unannounced

Decided 2026-08-13. The app is live and anyone who finds the URL can use it;
nothing points at it yet. Two things "test mode" does **not** mean here — both
checked against production rather than assumed, and both deliberately left
alone:

- **The apex is indexable.** Only `split-dec.vercel.app` carries
  `X-Robots-Tag: noindex`; `split-dec.app` carries none, and `robots.txt`
  invites crawling of `/`, `/privacy` and `/terms` with a sitemap listing them.
- **Email/password signup is open to anyone.** `signUpWithPassword` goes
  straight to `supabase.auth.signUp` with no allowlist or invite gate. Google's
  "Testing" mode caps *Google* sign-in at 100 hand-added users; it does not
  gate the app, and it never did.

If the phase ever needs to become genuinely private, those are the two levers:
a host-scoped `X-Robots-Tag` on the apex in `vercel.json` (with its assertion
in `tests/test_vercel_config.py`), and Supabase → Authentication → "Allow new
users to sign up".

**Standing constraint for this phase: stay on free tiers.** That is the only
reason item 5 (Supabase Pro) sits in section B rather than section A.

---

## A. Do now — nothing here waits on anyone else

Ordered by lead time, longest first. The detail stays in the numbered sections.

1. **Google OAuth consent screen** (items 2 + 3) — ◐ **the domain-ownership
   prerequisite is done** (2026-08-14, see item 2); what remains is the consent
   screen itself: add `split-dec.app` to authorized domains, complete the form,
   publish, submit for verification. **Still the longest clock, and the wait
   runs in parallel with testing.** Publishing is not a launch; it removes the
   100-user cap and the "unverified app" warning. Its other prerequisites
   (`/privacy`, `/terms`) have been live since item 8. The outcome then sits in
   section C.
2. ☑ **Inbound mail for `privacy@split-dec.app`** (item 8) — done 2026-08-15.
   The contact point published in both legal documents now reaches a real
   inbox instead of bouncing.
3. **Rotate the secrets that passed through chat/tooling** (item 4) — Supabase
   DB password, Resend API key. Best done *now*, in a phase where a fumbled
   environment variable costs nothing.
4. **Bilingual PL+EN auth email templates** (item 1) — ◐ the copy is written
   and now lives in `docs/auth-email-templates.md` (2026-08-14); all that is
   left is pasting two subjects and two HTML bodies into the Supabase
   dashboard. Testers hit signup and reset emails, so they may as well test the
   real ones.
5. **Error tracking and an uptime check** (item 7) — now the only remaining
   code work. Testing without error aggregation wastes every bug a tester hits.
6. **buycoffee.to profile** (item 9) — moved ahead of launch by decision on
   2026-08-13; the tax question is worth asking an accountant during testing.
7. **Branch protection decision** (item 6) — **no longer blocked**: the repo is
   public, so protected branches are free (checked 2026-08-14, see item 6).
   `master` is unprotected today. This is now a ~5-minute settings change, not
   a purchase.
8. **Re-confirm the anon key cannot read tables** (item 5) — free, quick, and
   the one part of item 5 that is not gated on Pro.
9. ☑ **Analytics `beforeSend`** (item 11) — done 2026-08-14. Web Analytics no
   longer reports raw group UUIDs; it runs the same fold Speed Insights uses.
10. ☑ **Swagger UI closed in production** (item 12.2) — done 2026-08-15.
    `/api/docs`, `/api/redoc` and `/api/openapi.json` are now development-only,
    so no third-party script is served from the session origin.

## B. At launch — the switch-flip list

Short by design, because everything above is meant to be done already.

1. **Supabase Pro** (item 5). Deferred purely by the free-tier constraint, and
   it is the item with the worst failure mode: the free tier pauses after ~1
   week of inactivity and has **no point-in-time recovery**, so a bad day
   holding other people's shared ledgers is unrecoverable. Reconsider early if
   testers start entering data they would be upset to lose.
2. **Leaked-password protection** (item 5) — Pro-only, so it lands with the
   upgrade. Review Auth rate limits at the same time.
3. **Announce.** No `noindex` to remove and no signup toggle to flip: the
   current phase is unannounced, not hidden.

## C. Waiting on other people — lower priority

Real work, but the clock is not yours to run, so it should never block
section A.

1. **Legal review of the Privacy Policy and Terms** (item 8). Drafted to be
   accurate about this specific app, never read by a lawyer; the liability,
   consumer-rights and governing-law clauses are the ones worth a professional
   eye. It says considerably more since analytics and Speed Insights landed.
2. **Google's verification outcome** — follows the submission in A1. Days,
   sometimes longer.
3. **Play Store via TWA** (item 10) — depends on 12 testers staying opted in
   for 14 continuous days *and* a paid developer account, so it is both
   people-dependent and against the free-tier constraint. Deferred. **Verify
   the current requirement before planning around it** — Google's terms for
   new personal developer accounts have changed before.

## Decisions on record — 2026-08-13

- **Phase: open but unannounced.** Not hidden; see above.
- **Free tiers for the duration of testing.** Defers item 5 and item 10.
- **buycoffee.to moves before launch** (was: after).
- **Test data stays at launch.** Nothing gets purged, so whatever testers
  create becomes production data. Worth knowing: cleaning up later is
  constrained by design — account deletion refuses while any balance is
  non-zero, and a group cannot be deleted until it is settled.

**Item 11 is fully closed.** Rate limiting, the 404 page and empty states, SEO
and route-level code splitting shipped earlier; the two follow-ups they left
behind — a tombstone so group deletion can't reset a write quota, and
vendor-chunk splitting — landed on 2026-08-13, along with the same fix for the
invitation quotas, which turned out to have the identical hole.

---

## Done — 2026-08-15

- **§A2 closed — `privacy@split-dec.app` receives mail.** Details in item 8,
  including the two decisions worth not re-litigating: forwarding to a read
  inbox rather than Resend inbound, and **no SPF record at the apex**.
  Verified by an actual round-trip, not by the forwarder turning green.
- **XSS audit — clean, and item 12 opened for what it did find.** No exploitable
  injection anywhere: no HTML sinks in `src/`, an i18n layer that returns
  strings rather than markup, a JSON-only backend that reflects nothing, and the
  one HTML generator (invitation email) escaping properly. Everything recorded
  in item 12 is defence in depth — the CSP has no `script-src` (12.1), `/api/docs`
  was live in production pulling an unpinned CDN script onto the session origin
  (12.2), and `avatar_url` reaches an `<img src>` unvalidated (12.3, not XSS).
- **§A10 closed — Swagger UI is development-only** (item 12.2), the one finding
  from that audit worth fixing the same day. `docs_urls(ENV)` in
  `api/_src/main.py` now gates `/api/docs`, `/api/redoc` and
  `/api/openapi.json`; `redoc_url` came along because FastAPI's bare `/redoc`
  default sat outside the `/api` prefix and was unreachable in production only
  by routing luck. 149 backend tests (8 new in `tests/test_docs_exposure.py`,
  one of which skips on a machine with `ENV=development` — the docstring
  explains why that is deliberate). Frontend untouched. **Merged and confirmed
  live**: all three paths now return FastAPI's own `{"detail":"Not Found"}`,
  with `/api/health` probed alongside as the control.
- **One flaky test fixed on the way** (PR #45). `TestNoRegistrationOracle::
  test_response_identical_for_registered_and_unregistered` compared the two
  invitation responses without excluding `created_at`, so it passed only when
  both sequential creates landed inside the same wall-clock second — a coin
  flip that went red in CI that day. Excluding it loses nothing: the key-set
  assertion that actually guards the enumeration oracle **was already passing
  during the failure**, and a creation timestamp cannot reveal whether an
  address is registered. Worth knowing for the next reader: with today's schema
  the exclusions leave `status` alone, so that value comparison earns its keep
  forward, not now.

**What that leaves in section A**: the Google consent screen itself (A1,
prerequisite done), secret rotation (A3), pasting the email templates (A4, copy
already in the repo), error tracking and an uptime check (A5), buycoffee.to
(A6), the branch-protection decision (A7), and the anon-key REST probe (A8).
A5 is no longer the only code left — item 12 still carries 12.1 and 12.3.

Still unverified on the wire from yesterday: the analytics fold. The check is
at the end of the 2026-08-14 entry below.

---

## Done — 2026-08-14

A short session, deliberately split between work that needed a browser and work
that needed a repo, so both ran at once.

- **§A9 closed — Web Analytics no longer sees group ids** (PR #41, merged).
  `foldAnalyticsUrl` runs the existing `insightsRoute` over the parsed pathname
  in a `beforeSend` hook, so Web Analytics and Speed Insights now fold
  identically and a new dynamic route is still added in exactly one place. An
  unparseable URL returns `null`, dropping the event rather than reporting it
  raw. 159 frontend tests (3 new), build clean. **This was the last of item 11's
  follow-ups; item 7 is now the only checklist entry that carries any code.**
- **§A1's prerequisite closed — `split-dec.app` verified in Search Console.**
  Details in item 2, including the two traps: don't delete the TXT record, and
  the Search Console account must match the Google Cloud project's.
- **§A4 de-risked — the auth email copy is in the repo** (PR #42, merged), at
  `docs/auth-email-templates.md`. It was previously drafted in a chat session
  and lost; item 1 now points at the file instead of saying to regenerate it.
  Pasting into the Supabase dashboard is still outstanding.
- **Two stale assumptions corrected, both found incidentally:**
  - The repo is **public**, so branch protection is free — item 6 had recorded
    it as blocked on GitHub Pro. `master` is unprotected today.
  - Prompted by that, git history was checked for secrets and is **clean**
    (item 4). The one committed env file holds only public values.

**Not verified on the wire yet:** both PRs deployed to production READY, but
nobody has confirmed the analytics fold live. The check, for next session: load
a group page and inspect the `POST /_vercel/insights/view` payload — the `url`
should read `/groups/[groupId]`, not a UUID. **Cache-bust first.** Per the
stale-shell trap below, the first load after a deploy is routinely served by the
already-installed service worker, and old JS contains the old fold.

**Untouched today, still §A:** `privacy@split-dec.app` inbound mail (A2), secret
rotation (A3), error tracking (A5), buycoffee.to (A6), the branch-protection
decision (A7), and the anon-key REST probe (A8).

---

## Verified in production — 2026-08-13

Checked against `https://split-dec.app` on commit `28f05cc`, the last of the
day's four merges:

- The **vendor chunk split** behaves exactly as designed, observed rather than
  assumed. `vendor-B36xOpBl.js` held its hash through three consecutive
  production deploys while the app entry chunk rotated each time
  (`DiQXpFl5` → `vChPMxzE` → `BdXQ6JuT`), then rotated to `vendor-sAol5NOC.js`
  on the fourth — the deploy that bumped `react-router`, which is precisely
  when it *should* rotate.
- That last hash is also the proof the **`react-router` 7.18.2 patch is really
  live**: it is byte-identical to the local build's, and Rollup hashes are
  content-derived. `node_modules` is unaffected by the CRLF difference that
  makes app-code hashes diverge between a Windows checkout and Vercel's Linux
  builders, so vendor is the one chunk that can be compared across the two.
- **Web Analytics and Speed Insights both serve and fire**:
  `/_vercel/insights/script.js`, `/_vercel/speed-insights/script.js` and a
  `POST /_vercel/insights/view` beacon.
- **Cookie audit — no cookies, confirmed four ways.** `document.cookie` empty
  and `cookieStore.getAll()` zero *after* both beacons fired; no `Set-Cookie`
  on `/`, `/privacy`, `/api/health` or either measurement script (checked with
  `curl -I`, since `Set-Cookie` is a forbidden header for `fetch` to read);
  and no `document.cookie` anywhere in `src/`. Signed-out browser storage is
  exactly one key, `splitdec.theme`.
- Privacy Policy live in **both** languages with the analytics and performance
  disclosures and `LEGAL_UPDATED` 2026-08-13.
- `/api/health` 200. `write_events` exists and is empty — the quota path is
  deployed but no traffic has exercised it yet.

**The stale-shell trap bit three times in one day, every time looking like a
failed deploy.** After each deploy the first load came from the
*already-installed* service worker: old app shell, old chunk hash, and — the
alarming one — the **previous version of the Privacy Policy**. Every time, the
origin was already serving the new build. Before concluding anything about a deploy, unregister
the service worker and clear `caches`, or use a fresh private window. Note the
failure mode is self-consistent rather than dangerous: an old cached shell is
old JS, which contains no measurement code either, so nobody is ever measured
under a policy that does not disclose it.

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
  problem) — retry when the page loads. **The copy to paste is in
  `docs/auth-email-templates.md`** (subjects + bilingual HTML bodies,
  `{{ .ConfirmationURL }}` placeholder). It lives in the repo because the
  templates themselves live in a dashboard, and the first draft was lost that
  way; the dashboard is what sends mail, so if one changes, change both.

## 2. Google OAuth consent screen — ◐ domain ownership proved, screen still to do
- ☑ **`split-dec.app` is verified in Google Search Console** (2026-08-14),
  which is the gate on the consent screen's **Authorized domains** field —
  Google will not accept a domain it does not believe you own.
  - Method: **Domain property** (covers the apex, `www` and every subdomain in
    one go), proved with a DNS `TXT` record. Google reported the method as
    "Dostawca nazwy domeny" / domain-name provider.
  - The record lives in **Vercel's DNS**, not at a registrar — `split-dec.app`
    delegates to `ns1/ns2.vercel-dns.com`. Value confirmed live on the wire:
    `google-site-verification=JV4JystQ030adHtWsbhX46SCD3AgJM4RTXboRNL92oY`
    (a public DNS record; it is a proof of control, not a secret).
  - **Never delete that TXT record.** Google re-checks it, and removing it
    un-verifies the domain silently — which would drop it back out of
    Authorized domains long after anyone remembers why.
  - It was the first and only `TXT` record at the apex, so nothing collided.
    Resend's SPF/DKIM live on subdomains (`send.`, `resend._domainkey.`) and
    were untouched.
  - **The account matters:** verification only helps if Search Console and the
    Google Cloud OAuth project are owned by the same Google account. If the
    Authorized domains field still rejects `split-dec.app`, that mismatch is
    the first thing to check.
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
  change needed). **Unblocked on 2026-08-14**: the domain-ownership proof that
  gates this field is done, see item 2.

## 4. Rotate secrets that passed through chat/tooling — ☐
These were shared during development and should be rotated before launch:
- **Supabase database password** (Project Settings → Database) → update
  `DATABASE_URL` on Vercel.
- **Resend API key** (Resend → API Keys) → update `RESEND_API_KEY` on Vercel.
- ☑ **Git history checked for secrets (2026-08-14)** — and it matters more than
  it used to, because the repo is public (item 6). Nothing leaked:
  - `service_role` and `SUPABASE_SERVICE` appear **nowhere** in any commit on
    any branch (`git log -S`, `--all`).
  - `.env` and `.env.local` were never committed and are gitignored.
  - `.env.production` **is** committed, deliberately ("Add public production
    config for deployment") and holds exactly two variables:
    `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`. Both are public by
    design — Vite inlines them into the frontend bundle that every visitor
    downloads, so committing them exposes nothing that shipping the app does
    not. Keep it that way: **any `VITE_`-prefixed variable is public**, so a
    real secret must never take that prefix.
  - This does **not** discharge the rotation below. The DB password and Resend
    key never reached git; they reached chat and tooling, which is a different
    exposure with the same fix.

## 5. Supabase production readiness — ☐ (split: one part now, the rest at launch)
- **§A8 — do now, free:** **RLS stays disabled by design** (the FastAPI layer
  is the sole authz boundary; Data API grants were revoked in migration
  `20260702000001_lock_down_data_api.sql`). Re-confirm no table is reachable
  via the anon key: a quick `curl` to the REST endpoint should 401/empty. This
  is the only part of item 5 that is not gated on a paid plan.
- **§B1 — at launch:** free tier **pauses the project after ~1 week of
  inactivity** and has no point-in-time recovery. Deferred by the free-tier
  decision of 2026-08-13, which is a real bet: during testing the exposure is
  losing test data, and the decision was that test data now becomes production
  data at launch. **Revisit the moment a tester enters something they would be
  upset to lose** — the free tier has no way to get it back.
- Confirm the DB connection uses the **Transaction Pooler (port 6543)** in
  production `DATABASE_URL` (it does today).
- Email/password auth: enable **leaked-password protection** (HaveIBeenPwned
  check, Pro-only) and review Auth rate limits once on Pro. Keep the dashboard
  minimum password length in sync with `MIN_PASSWORD_LENGTH` in
  `src/lib/authErrors.ts` (both 8 today).

## 6. Branch protection / CI gating — ☐ (but the blocker turned out to be gone)
- **The repo is public** (`gh repo view` → `"visibility": "PUBLIC"`, checked
  2026-08-14), so protected branches cost nothing. The long-standing note that
  this "needs GitHub Pro on a private repo" was stale — that was the constraint
  when it was written, not now. `CLAUDE.md` said the same thing and has been
  corrected.
- `master` is **unprotected today** (`gh api .../branches/master/protection` →
  404 "Branch not protected"), so the develop → PR → master workflow is still
  enforced only by convention.
- Turning it on is a few minutes in Settings → Branches. Worth deciding
  deliberately rather than by default: a rule requiring PRs also applies to
  **you**, on a repo where you are the only committer, and the existing
  convention has held for 40+ PRs.
- Optionally require the Claude review to pass / be acknowledged. Note the
  known trap from PR #29: `claude-review` reports success even when it posts
  nothing, so requiring that check is weaker evidence than it looks.

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

## 8. Legal / privacy — ◐ pages live and contact mailbox works; only the review is left
- ☑ **Privacy Policy at `/privacy` and Terms of Service at `/terms`**, bilingual
  EN+PL, in `src/lib/legal.ts` (document bodies) rendered by
  `src/pages/LegalPage.tsx`. Both routes are registered in **both** auth
  branches of `App.tsx` — like `/reset-password` — so they resolve for
  signed-out visitors instead of being swallowed by the catch-all, and they
  render identically whether or not you are signed in. Linked from the landing
  footer, the login screen and the account modal via `LegalLinks`.
- The documents assert facts that are checked against the implementation:
  processors and their regions (Supabase eu-west-3, Vercel cdg1 for hosting
  **plus Vercel Web Analytics and Speed Insights**, Resend eu-west-1, Google
  only for OAuth), what
  account deletion actually erases vs. anonymizes, what group members can see,
  and that no ad or analytics **cookies** exist and no identifier follows you
  across sites. **If any of that changes, `src/lib/legal.ts` changes with it**
  — and bump `LEGAL_UPDATED`.
- Analytics went in on 2026-08-13 (PR #36), Speed Insights the same day
  (PR #37). The policy previously promised "no analytics product" outright;
  that sentence is gone, and the cookie/consent claim now rests on both Vercel
  products being **cookieless** rather than on there being no measurement at
  all. If either is ever swapped for something that sets cookies or
  fingerprints, the "you are never asked to accept any" line stops being true
  and a consent banner becomes the real requirement.
- Speed Insights is passed `insightsRoute(pathname)` from `App.tsx`, which
  folds `/groups/<uuid>` to `/groups/[groupId]`. Two reasons, and a new dynamic
  route must be added to it for both: bucketing by raw pathname would split the
  app's busiest screen into one single-visit row per group, and it would hand
  group ids to the measurement. The policy says the identifier is never part of
  it, so that helper is load-bearing for a claim in a legal document — there
  are tests on it in `src/App.test.tsx`.
  ☑ **The asymmetry with Web Analytics is closed** (2026-08-14). It used to
  report raw pathnames, so group ids reached it — consistent with what the
  policy discloses (the page address is recorded, and Vercel already sees every
  URL in its server logs), but pointless to hand to a second system. It now
  runs the same fold through `foldAnalyticsUrl`, the `beforeSend` hook, because
  unlike Speed Insights it reads `location.href` itself instead of taking a
  route prop. Both call `insightsRoute`, so a new dynamic route is still added
  in exactly one place; a URL that fails to parse drops the event rather than
  reporting it raw. No `LEGAL_UPDATED` bump — the documents get more accurate,
  not less, and nothing about processors, storage or retention changed.
- The "what the app stores in your browser" list said **three** things (session,
  language, theme) and missed a fourth: `splitdec.chunk-reload`, the
  `sessionStorage` timestamp `ErrorBoundary` writes to stop a missing chunk
  becoming a refresh loop. Trivial and non-personal, but the sentence
  enumerates, so it was wrong. Now four, in both languages. The lesson for the
  next audit: that paragraph is an **exhaustive** claim, so anything that
  touches `localStorage`/`sessionStorage` has to be added to it.
- ☑ **`privacy@split-dec.app` receives mail** (2026-08-15). It is the contact
  point in both documents and for GDPR requests, and it used to bounce.
  - **Forwarding, not a mailbox**: ImprovMX free tier catches mail for the
    address and forwards it to a personal inbox. Chosen over Resend inbound
    deliberately — Resend would deliver it to an API and a dashboard, and a
    contact address carrying a 30-day statutory reply deadline belongs
    somewhere already read daily, not somewhere that has to be remembered.
  - Two `MX` records at the apex, `mx1`/`mx2.improvmx.com` (priority 10/20),
    added in **Vercel's** DNS. The apex had no MX at all beforehand, so nothing
    collided.
  - **No SPF record was added, on purpose, and none should be.** ImprovMX
    offers one; forwarding does not need it, and it is the only step here that
    could disturb *outgoing* mail. The apex still carries exactly one TXT
    record — the Google verification string from item 2. Resend's own SPF and
    bounce path live on `send.split-dec.app` and were never touched.
  - Verified rather than assumed: `MX` and `TXT` both re-read from DNS
    afterwards, `send.split-dec.app` confirmed intact, and a real message sent
    to the address arrived in the destination inbox.
  - **Forwarding is one-way.** A reply goes out from the personal address
    unless Gmail's "Send mail as" is pointed at the existing Resend SMTP
    credentials. Not set up; worth doing the first time someone actually
    writes in.
- ☐ **§C1 — waiting on someone else, deliberately not a blocker.** Have the
  text reviewed. It was drafted to be accurate about this specific app, not run
  past a lawyer; the liability, consumer-rights and governing-law clauses in
  particular are the ones worth a professional eye if usage grows beyond
  friends. Both documents state that the Polish version prevails. It says
  considerably more since analytics and Speed Insights landed, so a review is
  worth more now than it would have been this morning.
- Note: these are SPA routes, so the served HTML is the app shell and the text
  is rendered by JS. Google's OAuth reviewers render pages, so this is normally
  fine — but if the review bounces on "policy not found", the fallback is a
  prerendered static `public/privacy.html` / `terms.html`.

## 9. Funding: buycoffee.to — ☐ (§A6 — moved before launch on 2026-08-13)
SplitDec will be funded by voluntary payments via [buycoffee.to](https://buycoffee.to)
rather than subscriptions or ads. Creating the profile and settling the tax
question are both self-contained, so they belong in the testing phase; only the
in-app link has to wait for a page worth linking to.
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

## 10. Android app (Play Store) via TWA — ☐ (§C3 — deferred)
Deferred twice over: it needs a paid developer account, against the free-tier
decision, and publishing from a new **personal** developer account has required
12 testers opted in for 14 continuous days — people-dependent, and a clock that
cannot be shortened. **Check Google's current requirement before planning
around it**; their terms for new personal accounts have changed before, and
this note is not a live source.

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
The limitations this item used to carry were all closed on 2026-08-13.
- ☑ **Rate limiting on write endpoints.** `api/_src/ratelimit.py`: expense and
  settlement creation share one 24h window (`MAX_LEDGER_WRITES_PER_CALLER`,
  100) and group creation has its own (`MAX_GROUPS_PER_CALLER`, 25), both
  **per caller**, so neither limit can be sidestepped by making more groups.
  Invitations keep their own three windows (per inviter / per recipient /
  global). All of them share the dialect-aware `window_cutoff` helper.
  - Counted from rows in the database, not process memory — the API is a
    serverless function with several instances and constant cold starts.
  - **Deliberately no global cap** on either window: it would turn one abusive
    account into an outage for everyone.
  - Replays are answered **before** the quota in both create endpoints: a
    client retrying a request whose response it never saw has already spent
    its slot, and a 429 there would leave it unable to discover whether the
    entry exists — the one thing `Idempotency-Key` is for.
  - ☑ **All six windows now survive a group deletion** (PR pending,
    2026-08-13). They used to count the rows they protected, and deleting a
    group is a *hard* delete that takes its expenses, settlements and
    invitations with it, so create-group → fill → delete → repeat reset every
    one of them — the brakes only stopped clients that were not trying. They
    now count `write_events`
    (`supabase/migrations/20260813000000_write_events.sql`): one append-only
    tombstone per charged write, keyed by the caller, that no cascade reaches.
    Note the `created_by`-column variant floated earlier does **not** work on
    its own — those rows die with the group too.
  - ☑ **The ledger window moved from per-group to per-caller** in the same
    change, which was the other half of the fix: a per-group window let one
    member consume everyone else's allowance. 100/caller/24h against a busy
    trip's ~50 still leaves roughly double the headroom a real user needs.
  - ☑ **The invitation quotas came along**, which needed one extra decision:
    the per-recipient window is keyed by *email address*, and a table that
    outlives the group would otherwise retain addresses that account deletion
    is required to anonymize (item 8). It stores `recipient_key(email)`, a bare
    SHA-256, because the window only ever needs equality — so nothing
    contactable is retained. Unpeppered deliberately: whoever can read that
    column can already read `public.users.email` in plaintext, so a pepper buys
    nothing real and its rotation would silently reset every recipient window.
    `delete_account` also clears rows keyed to the departing address.
  - `record_write` prunes the caller's aged-out rows opportunistically (no cron
    on a serverless function) and `delete_account` clears that user's, since
    nothing would prune them again. An invitation row is charged to its
    inviter, so it prunes on the inviter's next write — no row is keyed only to
    someone who never writes.
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

## 12. Security hardening (XSS defence in depth) — ◐ only 12.1 (the CSP) left
An XSS review on 2026-08-15 found **no exploitable injection anywhere in the
app**, and nothing in this item is a live vulnerability. It is a checklist entry
anyway because every sub-item is *blast radius*: these are the reasons an
injection bug, if one is ever introduced, would go from "a bug" to "account
takeover". Ordered by that leverage, not by effort.

**What the audit confirmed, and what the items below are protecting.** A future
change that breaks one of these is what would make this section urgent:
- **No HTML sinks exist.** `dangerouslySetInnerHTML`, `innerHTML`, `outerHTML`,
  `insertAdjacentHTML`, `document.write`, `eval`, `new Function`, string-form
  `setTimeout`, `srcDoc` and `postMessage` handlers are **absent from `src/`**.
  Every user-controlled string — group name, expense description, `full_name`,
  email — reaches the DOM as a JSX text child, so React escapes it.
- **`t()` returns a `string`, not markup** (`src/lib/i18n.tsx`). An i18n layer
  is the usual quiet place for this to go wrong; here the two `{email}` /
  `{group}` placeholders are `String.replace` results that land in a text node
  and inside `encodeURIComponent` respectively.
- **`renderLegalText` emits React elements, not HTML**, and runs only over
  repo-owned copy in `src/lib/legal.ts`.
- **The backend serves JSON only** — no `HTMLResponse`, no templates — and every
  `HTTPException` detail is a constant or interpolates an already-validated
  value (`currency` is `^[A-Z]{3}$`, `split_type` a `Literal`). Nothing reflects
  arbitrary input, and `X-Content-Type-Options: nosniff` means a JSON body could
  not be sniffed into HTML even if it did.
- **The one HTML generator escapes.** `invitation_email_content`
  (`api/_src/emailer.py`) is the only place the codebase builds markup from user
  input — a group named `<img src=x onerror=…>` would otherwise inject into mail
  sent under our own sending domain — and both fields go through `html.escape`.

### 12.1 A script-level CSP — worth more than everything else here combined
`vercel.json` sends `Content-Security-Policy: frame-ancestors 'none'` and
nothing more: no `default-src`, `script-src`, `object-src`, `base-uri` or
`form-action`. That is deliberate (see `CLAUDE.md`), and the reason is real —
a `default-src` policy needs the Supabase endpoints and the PWA's generated
service worker audited first. What the decision costs is worth writing down:
- Nothing would stop an injected script from executing or exfiltrating.
- No `base-uri` means an injected `<base>` could redirect every relative
  script load.
- **The session is in `localStorage`** (`persistSession: true` in
  `src/lib/supabase.ts` — the supabase-js default), so any XSS yields a
  stealable *refresh* token: full account takeover, not a session that dies
  with the tab. There is no clean fix for that in a static SPA — cookie-backed
  storage wants a server session — which is exactly why the CSP carries the
  weight instead.
- **The concrete blocker is the inline theme script** at `index.html:38`, which
  exists to avoid a light-mode flash before React mounts. A nonce is awkward
  when one static `index.html` is served through a rewrite, so the practical
  route is a hash — and it has to be regenerated if that script is ever edited.
- Add the assertion to `tests/test_vercel_config.py` alongside the existing
  header checks, or the policy can be reverted as silently as it was added.

### 12.2 ☑ Swagger UI closed in production (§A10) — done 2026-08-15
`https://split-dec.app/api/docs` was publicly reachable — verified on the wire,
not inferred. FastAPI's `get_swagger_ui_html` defaults to
`https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js`: an
unpinned floating major tag, no SRI. That was **third-party script executing on
the canonical origin**, the same origin holding the session in `localStorage`
(12.1) — not XSS, but sitting on exactly the boundary XSS attacks, and the
largest arbitrary-script-execution surface the app had. `/api/openapi.json` was
public alongside it, enumerating every endpoint and schema.

Fixed by `docs_urls(ENV)` in `api/_src/main.py`: gated on `ENV` like the CORS
middleware rather than deleted, because the docs are useful against a local
uvicorn. Three things worth not re-deriving:
- **It fails closed.** The test is `== "development"`, not `!= "production"`,
  so an unset or misspelled ENV costs a dev convenience instead of exposing a
  CDN script.
- **`redoc_url` had to go too, and it was the sneaky one.** FastAPI defaults it
  to bare `/redoc` — *outside* the `/api` prefix, so it was unreachable in
  production only because `vercel.json`'s catch-all rewrite sent it to the SPA
  first. That is routing luck, not a decision, and it would evaporate the day
  the rewrite changes. It is now `/api/redoc` in dev and absent otherwise.
- **`tests/test_docs_exposure.py` mostly asserts the helper, not the live app,
  on purpose** — and the module docstring says why: `app` is built at *import*
  time from the developer's `.env`, so conftest's `_hermetic_env` cannot reach
  back and rebuild it. A plain route-absence test passes in CI (no `.env` →
  production) and fails on any machine running `ENV=development`. The one
  whole-app assertion is therefore conditional; it is what CI actually runs,
  and it was confirmed locally by forcing `ENV=production`.

Verified on both branches by real requests through the ASGI transport, not just
by route registration: production 404s `/api/docs`, `/api/redoc`,
`/api/openapi.json`, `/redoc` and `/openapi.json`; development serves the three
`/api`-prefixed ones and nothing at FastAPI's bare defaults.

☑ **Confirmed live on `https://split-dec.app` after the PR #45 merge**
(2026-08-15), cache-busted. All three doc paths return **`{"detail":"Not
Found"}`** — note the body, because it is the part that proves the point: that
is FastAPI's own 404, so the request reached the function and the route is
genuinely unregistered. An HTML body would have meant the SPA catch-all
answered and told us nothing about the function. `/api/health` was probed in
the same pass as a control, returning 200: without it, three 404s are equally
consistent with the whole API being down.

### 12.3 ☑ `avatar_url` is allow-listed before it reaches `<img src>` — done 2026-08-15
`src/components/Avatar.tsx` renders `user.avatar_url` unvalidated, and that
value is attacker-influenceable: `handle_new_user` copies
`raw_user_meta_data->>'avatar_url'` (or `'picture'`) verbatim from client-supplied
signup metadata, which a crafted `signUp` call controls.
- **This is not XSS.** `javascript:` does not execute in `img src`, and SVG
  loaded through `<img>` cannot script. Do not treat it as one.
- What it is: any group member can make every other member's browser issue a
  request to a host of their choosing — IP address, rough location and
  presence disclosure. `referrerPolicy="no-referrer"` already caps the leak.
Fixed by `safeAvatarUrl` in `src/lib/avatarUrl.ts`, applied at all three render
sites. It accepts **only `https:` on `googleusercontent.com` or a subdomain**;
anything else returns null and the existing initials badge renders instead, so a
rejected avatar looks like an ordinary empty state rather than a broken image.
- **The host list was checked against the database, not guessed.** Every avatar
  in production is `https://lh3.googleusercontent.com/…`, so restricting to
  Google's CDN breaks nobody. Subdomains are allowed as a group because Google
  rotates the shard (`lh3`–`lh6` all appear in the wild).
- **The leading dot in the suffix test is load-bearing**, and there are tests
  for it: without it `evilgoogleusercontent.com` matches, and a suffix test is
  also what rejects `googleusercontent.com.attacker.example`.
- **Adding a second OAuth provider means adding its avatar host here**, or its
  users silently get initials. Deliberate trade: a cosmetic regression the new
  provider's first test login reveals, against leaving a request-to-anywhere
  open for every existing member.
- `Layout.tsx` and `AccountModal.tsx` read the *viewer's own* metadata and were
  never exposed, but they go through the same helper anyway — so "avatar URLs
  are filtered" has no exceptions to remember, and a future `img-src` cannot be
  widened by one component quietly disagreeing with the other two.

### 12.4 ☑ `renderLegalText` only links known schemes — done 2026-08-15
`LegalPage.tsx` passed the `href` parsed out of `[label](href)` straight to
`<a href>` with no scheme check. Safe as written, because the only input is the
static copy in `src/lib/legal.ts` — and a live XSS the day that copy comes from
anywhere else, since React 19 *warns* on `javascript:` URLs without blocking
them. The check went in now rather than being left as a note, because it costs
nothing and the future change that makes these documents dynamic is exactly the
change least likely to remember it.

`SAFE_HREF` allows `https:` and `mailto:`; in-app `/…` paths keep their own
branch and stay client-side `Link`s. Both documents together use exactly those
three shapes, so nothing needed rewriting. An unknown scheme renders as **plain
label text rather than vanishing** — silently dropping words from a legal
document is worse than showing them unlinked.

Verified in a browser against the real rendered document, not only in tests: all
nine links on `/privacy` still resolve (3 `mailto`, 4 `https` — every one of
them carrying `rel="noreferrer"` — and 2 in-app), with no leftover `](` or `**`
in the text and a clean console.

One incidental find, deliberately not chased: the href group is `[^)]+`, so a
parenthesised URL ends the match early and leaves a stray `)` in the text. That
is the minimal parser working as written, it cannot arise in the real documents,
and "deliberately not a markdown parser" is a decision worth keeping.

### 12.5 ☑ The address in `mailtoHref` is encoded — done 2026-08-15
`MembersTab.tsx` encoded the subject and body but interpolated the address raw.
Backend validation (`^[^@\s]+@[^@\s]+\.[^@\s]+$`) excludes whitespace but
permits `&` and `?`, so an address containing them ended the recipient and began
a new mailto field instead of staying part of it. Cosmetic — a confusing draft
in the user's own mail client, nothing more.

Now `encodeURIComponent(address)` with `%40` mapped back to `@`, which RFC 6068
permits literally in the address and which keeps the raw URI readable where the
mail client shows it.

---

_Last updated: 2026-08-15. Maintained alongside the develop → PR → master
workflow; update statuses as items land._
