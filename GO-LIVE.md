# SplitDec — Pre-Go-Live Checklist

Things to do before treating SplitDec as a real, publicly-usable product.
The app is fully functional today at https://split-dec.vercel.app; the items
below are about production-readiness, deliverability, security hardening, and
polish — not missing features.

Status legend: ☐ not started · ◐ partial · ☑ done

---

## 1. Email deliverability (invitations) — ◐ blocked on a domain
Invitation emails currently send from Resend's shared sandbox address
`onboarding@resend.dev`. Consequences today:
- Resend only **delivers to the account owner's own address** (`chrono5@wp.pl`);
  every other recipient is rejected with HTTP 403.
- Even to the owner, mail lands in **spam** (no SPF/DKIM tied to a real domain).

**To fix (requires a domain you own):**
1. Buy/choose a domain (e.g. `splitdec.app`).
2. In [resend.com/domains](https://resend.com/domains) → Add Domain → add the
   SPF/DKIM/return-path DNS records it shows at your registrar → wait for
   "Verified".
3. Set `RESEND_FROM` on Vercel to e.g. `SplitDec <invites@yourdomain.com>`
   (ping Claude to wire it, or `vercel env add RESEND_FROM production`).
4. Re-test: invite a non-owner address and confirm inbox delivery.

Until then: in-app invitations work for everyone (they appear on sign-in) and
the "Open email draft" button covers manual sends. Consider hiding the
auto-email path or messaging it as best-effort.

## 2. Google OAuth consent screen — ☐
- Confirm the Google Cloud OAuth app is **published** (not "Testing", which
  caps at 100 hand-added test users and shows an "unverified app" warning).
- Complete the OAuth consent screen (app name, logo, support email, privacy
  policy + terms URLs, authorized domains).
- Google verification may be required for the app to avoid the warning screen
  once published — plan for a few days' review.

## 3. Custom domain for the app — ☐ (optional but recommended)
- Point a domain at the Vercel project (Vercel → Project → Domains).
- Update Supabase Auth → URL Configuration (Site URL + Redirect URLs) and the
  Google OAuth redirect/authorized origins to the new domain.
- Update `APP_URL` (backend, used in invite emails) if set.

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

## 9. Nice-to-haves before launch — ☐
- Rate limiting on write endpoints (expense/settlement/invite creation).
- Empty-state polish and a 404 page.
- `robots.txt` / basic SEO meta if the marketing page is public.
- Bundle size: the SPA is a single ~570 kB chunk; consider route-level code
  splitting if load time matters.

---

_Last updated: 2026-07-05. Maintained alongside the develop → PR → master
workflow; update statuses as items land._
