# SplitDec — Pre-Go-Live Checklist

Things to do before treating SplitDec as a real, publicly-usable product.
The app is fully functional today at https://split-dec.vercel.app; the items
below are about production-readiness, deliverability, security hardening, and
polish — not missing features.

Status legend: ☐ not started · ◐ partial · ☑ done

---

## 1. Email deliverability (invitations + auth emails) — ☑ done (2026-07-18)
Domain **`split-dec.app`** verified in Resend (DKIM/SPF/return-path live,
region eu-west-1). `RESEND_FROM=SplitDec <invites@split-dec.app>` and
`APP_URL=https://www.split-dec.app` set on Vercel production. Supabase custom
SMTP configured (smtp.resend.com:465, user `resend`, dedicated sending-only
API key, sender `auth@split-dec.app`) and **verified end-to-end**: a test
signup dispatched its confirmation email through Resend successfully
(Resend rejects recipients at reserved domains like example.com — use
`delivered@resend.dev` for tests). Custom SMTP also raised the auth email
rate limit to 30/hour. Auth email templates still use Supabase defaults
(EN-only) — bilingual PL+EN templates are a nice-to-have follow-up under
Authentication → Emails → Templates.

## 2. Google OAuth consent screen — ☐
- Confirm the Google Cloud OAuth app is **published** (not "Testing", which
  caps at 100 hand-added test users and shows an "unverified app" warning).
- Complete the OAuth consent screen (app name, logo, support email, privacy
  policy + terms URLs, authorized domains).
- Google verification may be required for the app to avoid the warning screen
  once published — plan for a few days' review.

## 3. Custom domain for the app — ◐ live, one auth-config gap
- ☑ **`https://www.split-dec.app` is the primary domain** (apex 308-redirects
  to www; `.vercel.app` still serves). App + same-origin API verified on the
  www origin. `APP_URL` points at www.
- ☐ **Supabase Auth → URL Configuration — the one remaining gap.** Verified
  empirically (2026-07-18): the allow-list has the apex entries but NOT www,
  and Site URL is still `https://split-dec.vercel.app`. Because the app runs
  on www, Google sign-in from www falls back to the vercel.app origin and
  breaks PKCE (this is the "why am I on vercel.app?" symptom). Fix: Site URL
  → `https://www.split-dec.app`; add `https://www.split-dec.app` and
  `https://www.split-dec.app/reset-password` to Redirect URLs (keep apex,
  vercel.app and localhost entries).
- ☐ Google OAuth consent screen: add `split-dec.app` to authorized domains
  (the OAuth callback itself stays on the Supabase domain — no redirect URI
  change needed).
- Note: previously installed PWAs pin the origin they were installed from —
  reinstall from www.split-dec.app to migrate.

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
  or at least periodic review of Vercel runtime logs.
- Add a lightweight uptime check on `/api/health`.

## 8. Legal / privacy — ☐
- The app stores names, emails, avatars, and financial split data. Before a
  public launch add a Privacy Policy and Terms (also required to publish the
  Google OAuth app). Link them from the login page footer.

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

## 10. Android app (Play Store) via TWA — ☐ (PWA prerequisite ☑)
The app is an installable PWA (manifest + service worker; Chrome → "Add to
Home Screen"). To turn it into a Play Store app:
1. `npx @bubblewrap/cli init --manifest https://split-dec.vercel.app/manifest.webmanifest`
   (Bubblewrap offers to install JDK/Android SDK; it generates a signing key).
2. Serve `/.well-known/assetlinks.json` with the signing key's SHA-256
   fingerprint (drop the file in `public/.well-known/`) so the TWA runs
   fullscreen without the browser bar.
3. `npx @bubblewrap/cli build` → sideload the `.apk` to test, or upload the
   `.aab` to Google Play ($25 one-time developer account; privacy policy from
   item 8 is required for the listing).

## 11. Nice-to-haves before launch — ☐
- Rate limiting on write endpoints (expense/settlement/invite creation).
- Empty-state polish and a 404 page.
- `robots.txt` / basic SEO meta if the marketing page is public.
- Bundle size: the SPA is a single ~570 kB chunk; consider route-level code
  splitting if load time matters.

---

_Last updated: 2026-07-17. Maintained alongside the develop → PR → master
workflow; update statuses as items land._
