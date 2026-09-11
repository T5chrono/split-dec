# Supply-chain posture

What protects the code this app installs and deploys, what is deliberately
*not* protected, and where the controls live that no file in this repo can
show you. Written after an OWASP A03 (Software Supply Chain Failures) review in
September 2026, and extended after an A04 (Cryptographic Failures) review the
same month — which is where the secrets register and the data classification
below came from.

The point of the second half is that an accepted risk and an oversight look
identical from outside. Everything below the line was considered and declined,
with a reason and a trigger for revisiting it.

The register is not exhaustive, and the omission is deliberate. Where writing
the gap down would itself be the thing an attacker needs — a control that is
off, next to the reason it stays off — the entry is kept in the maintainer's
private security record instead of here. Everything a reader of this repo can
already derive from the code stays in this file.

## Controls in this repository

| Control | Where |
| --- | --- |
| Full transitive pins, both ecosystems | `package-lock.json` (v3, `sha512-` integrity on every entry, every resolve on registry.npmjs.org), `requirements.txt` / `requirements-dev.txt` (`uv pip compile`, `==` on everything) |
| Reproducible production install | `vercel.json` → `npm ci --ignore-scripts`, asserted by `tests/test_vercel_config.py` |
| No package install scripts run in CI or on Vercel | `--ignore-scripts` on both. Only two packages in the tree declare one: `@sentry/cli` (dev; its postinstall exits immediately because all eight `@sentry/cli-*` platform packages are in the lockfile) and `fsevents` (dev, darwin-only) |
| Advisory scanning | `ci.yml` → `audit` job: `npm audit --audit-level=high`, and `pypa/gh-action-pip-audit` over both Python locks |
| Production build path covered | `ci.yml` → `frontend` job builds a second time with a dummy `SENTRY_AUTH_TOKEN` and fails if any `.map` survives into `dist/` — both the upload failure and a surviving map are silent by design |
| Lock freshness | `ci.yml` → `locks` job: constrained recompile of each `.in`, diffed against its `.txt` |
| Actions pinned to commit SHAs | all three workflows; the `github-actions` Dependabot group bumps them |
| Least-privilege workflow tokens | `permissions:` declared in every workflow; `persist-credentials: false` on every checkout |
| Agent workflows gated | `claude.yml` runs only for the repository owner and only with an explicit `--allowed-tools` list; `claude-code-review.yml` likewise, and cannot report green having said nothing |
| Branch protection | ruleset `SplitDecMaster`: PR required, `backend` / `frontend` / `claude-review` must pass, force-push and deletion blocked, **no bypass actors** |
| Runtime pinning | Node 24 (`package.json` engines), Python 3.12 (`.python-version`, matched in CI and on Vercel) |
| Least-privilege database role | `splitdec_app`, not the project owner — see CLAUDE.md and `tests/test_grants_pg.py` |
| Verified TLS to the database | `api/_src/db.py` + `supabase_ca.py`; asyncpg's default accepts any certificate and falls back to plaintext. `tests/test_db_tls.py` |
| No client-side storage of API responses | `Cache-Control: no-store` middleware in `api/_src/main.py`, plus Workbox kept out of `/api/`. `tests/test_cache_headers.py` |

## Controls that live in a dashboard

Not in version control, not visible to CI, and therefore the ones that rot
quietly. Check these at each release.

| Setting | Expected | Where |
| --- | --- | --- |
| Dependency graph, Dependabot alerts, Dependabot security updates | all enabled | GitHub → Settings → Code security |
| Secret scanning + push protection | enabled (free on public repos) | GitHub → Settings → Code security |
| Workflow permissions | *Read repository contents*, and "allow Actions to create and approve pull requests" **off** | GitHub → Settings → Actions → General |
| Private vulnerability reporting | enabled — `SECURITY.md` points at it | GitHub → Settings → Code security |
| Firewall rule "CSP report flood limit" | `path equals /api/csp-report`, 100 req/60s per IP, deny 5m | Vercel project — inspect with `vercel firewall rules list` |
| Firewall rule for `/api/unsubscribe` | **none, and that is a gap** — the route has only its in-process 30/min bucket, which is a per-instance floor on a function that runs several. Unlike the CSP route it writes a row, though a forged token is refused before the database is touched and the primary key makes a replay idempotent. Add one if it ever sees traffic | Vercel project |
| Inbound mail aliases | `privacy@` and `support@` both forwarding, each as an **explicit alias** — a catch-all alone was observed not to deliver | ImprovMX (the domain's MX records point there) |
| `SENTRY_AUTH_TOKEN` | project-scoped, production only | Vercel env vars |
| Auth email templates | match `docs/auth-email-templates.md` | Supabase dashboard |
| Database grants | `AUDIT_DATABASE_URL=<production> pytest tests/test_grants_pg.py` | run per release |
| Refresh-token rotation + reuse detection | both enabled — confirmed 2026-09-08 | Supabase → Authentication → Sessions |
| Password minimum length | **8**, matching `MIN_PASSWORD_LENGTH` — must not be *lowered* to meet the client. Confirmed 2026-09-08 | Supabase → Authentication, password settings under the Email provider |
| `SUPABASE_JWT_SECRET` | **absent** — verified 2026-09-08 | Vercel env vars |
| Supabase pooler CA | `Supabase Root 2021 CA`, expires **2031-04-26** | `AUDIT_DATABASE_URL=<production> pytest tests/test_db_tls_pg.py` — a rotation arrives as a connection failure, not a warning |

Inbound mail is the one row above with no account to log into from CI at all,
and it fails silently in the direction that matters: a dead alias bounces or
swallows mail without anything here noticing. What the MX records say is at
least checkable from anywhere:

```bash
nslookup -type=MX split-dec.app   # expect mx1/mx2.improvmx.com
```

That confirms mail reaches the forwarder, not that a given alias exists behind
it. The only real test is sending to the address and seeing it arrive — worth
doing for `privacy@` in particular, which the Privacy Policy publishes as the
contact for GDPR requests, where silence is a compliance problem rather than an
inconvenience.

Verifying the GitHub half without clicking through the UI:

```bash
gh api repos/T5chrono/split-dec --jq .security_and_analysis
gh api repos/T5chrono/split-dec/actions/permissions/workflow
gh api repos/T5chrono/split-dec/dependabot/alerts --jq '[.[] | select(.state=="open")] | length'
```

## Secrets register

Names, blast radius and what should make you rotate one. No values: those live
in Vercel's environment, in Supabase, and nowhere else. Owner is the
maintainer for all of them, which is the point of writing it down — there is
nobody to escalate to, so the runbook has to exist before the day it is needed.

| Secret | Where it lives | What it is worth | Rotate when |
| --- | --- | --- | --- |
| `DATABASE_URL` (the `splitdec_app` password) | Vercel env, local `.env` | Read/write on the eight application tables. Not the owner role — no `auth` schema, no role administration, nothing outside `public` | Suspected exposure, a laptop lost, or a contractor's access ending. Not on a schedule |
| `RESEND_API_KEY` | Vercel env | Sending as the verified domain. The blast radius is the domain's reputation, which money cannot buy back | Suspected exposure; also the natural rehearsal target, see below |
| `HEALTH_PROBE_KEY` | Vercel env, local `.env` | Opening one pooler connection per call and reading its latency, plus the Sentry probe. Lowest value here | Suspected exposure. **Rotated 2026-09-08** — the previous value was unrecoverable, see below |
| `UNSUBSCRIBE_SECRET` | Vercel env, local `.env` | Signing the unsubscribe links in invitation email. Holding it lets you unsubscribe any address you can name — a denial of service against invitations, not a disclosure | Suspected exposure. **Rotating invalidates every link already in somebody's inbox**; the suppressions themselves survive, because the table is keyed by an unpeppered digest for exactly that reason (api/_src/unsubscribe.py) |
| `SENTRY_AUTH_TOKEN` | Vercel env, production build only | Uploading source maps to the `split-dec` Sentry org | Suspected exposure |
| `SENTRY_DSN` | Vercel env | Writing events into the `splitdec-api` Sentry project. Not public, unlike its browser twin | Suspected exposure |
| `SUPABASE_JWT_SECRET` | **should not be set** | A symmetric minting credential: anything holding it can *issue* valid tokens. `ALLOW_LEGACY_HS256` is off, so nothing reads it | If it is set anywhere, the action is to remove it, not to rotate it |
| `VITE_SUPABASE_ANON_KEY`, `VITE_SENTRY_DSN` | committed | Public by construction — they ship inside the bundle | Never; they are not secrets |

The other Vercel variables — `SUPABASE_URL`, `APP_URL`, `RESEND_FROM` — hold no
secret and are listed here only so the register can be read against the
dashboard and every name accounted for. Anything in Vercel that is not on one
of these two lists is something nobody has thought about.


**Every secret in the Vercel project is stored Sensitive, which means nobody
can read it back — including you.** The project has the sensitive-variables
setting on, so a value added there is write-only from that moment: the
dashboard shows `Hidden`, and `vercel env pull` writes the literal string
`[SENSITIVE]` rather than failing, which is a trap worth knowing because the
pulled file *looks* like it worked. There is no recovery path and no support
ticket that retrieves it. **The local `.env` is therefore the only copy of
`HEALTH_PROBE_KEY`**, and losing it means rotating again rather than looking it
up. That is exactly what happened on 2026-09-08: the key could not be read from
anywhere, so it was replaced (32 chars from `secrets.token_urlsafe`, set in
Vercel, production redeployed, `.env` updated) rather than recovered.

Two consequences for the others. `DATABASE_URL` is also unreadable, so the
`.env` copy is the only one — which raises the stakes on the rotation procedure
below rather than lowering them. And a secret that is *not* in `.env` and not in
a password manager is, in practice, already lost; the register above is the list
of things to check that against.

**Rotating `DATABASE_URL` is a short outage, and pretending otherwise is worse
than scheduling one.** The role has exactly one password: the moment
`ALTER ROLE splitdec_app PASSWORD …` runs, every new connection fails until the
Vercel variable is updated and a deploy picks it up, and with `NullPool` on a
serverless function *every* request opens a new connection. Budget a couple of
minutes and do it deliberately. The genuinely seamless version is a second role
— create `splitdec_app_next`, apply the same grants (`20260904100000` is the
list), cut the variable over, drop the old one — which is worth the trouble
only if the rotation is planned rather than urgent.

**Rehearse on `RESEND_API_KEY`, never on the database.** A rehearsal whose
failure mode is a production outage is not a control, it is a second incident.
Resend's key can be rotated in the dashboard, updated in Vercel, and verified
by sending one invitation; if it goes wrong the app falls back to a mailto
draft, which is the behaviour it already has without a key at all.

## Data classification

There is no encryption of individual columns, and there should not be. What the
database holds, and what protects it:

| Data | Where | Protection |
| --- | --- | --- |
| Email address, display name, avatar URL | `public.users` | Supabase's disk encryption; the `splitdec_app` role reaches nothing else; FastAPI is the only reader |
| Group and expense names, categories, dates | `public.groups`, `public.expenses` | same |
| Amounts and per-person splits | `NUMERIC(14,4)` columns | same |
| Invitation recipient addresses | `public.group_invitations` (plaintext, deleted with the account), `public.write_events.recipient_hash` (SHA-256, pruned after ~24h — see `ratelimit.recipient_key`) | same |

**Application-level column encryption is rejected, not deferred.**
`users.email` is UNIQUE and drives lowercased invitation matching, and the
amounts are summed inside the balances CTE — encrypting either breaks the
feature it belongs to. And a key held by the same function that holds
`DATABASE_URL` protects nothing against the compromise that matters, which is
the function itself.

So the at-rest control is the provider's, and the in-transit half is now real
on both legs: browser → function over HTTPS with HSTS, function → database with
a verified certificate (`api/_src/db.py`, which until September 2026 accepted
any certificate at all). `src/lib/legal.ts` still claims only the in-transit
half, which is incomplete rather than false; adding an at-rest sentence waits
on dated evidence from Supabase about disk and backup encryption, because an
unverified promise in a privacy policy is worse than a silence.

---

## Accepted risks

### No second reviewer

**Risk.** Required approvals on `master` are 0, so one person authors and
promotes to production.

**Why accepted.** There is one committer. GitHub does not allow self-approval,
so any number above 0 makes every PR unmergeable — the fix is unavailable, not
declined. A `CODEOWNERS` file has the same problem: at 0 required approvals it
is auto-satisfied by the author, so it would be routing documentation dressed
up as an approval boundary.

**Compensating controls.** Three required checks with no bypass actors, the
maintainer included; an automated Claude review on every PR and on every push
to one, which cannot report green having posted nothing.

**Revisit when.** A second committer joins — that day, set approvals to 1 and
add `CODEOWNERS` over `.github/**`, `vercel.json`, `package-lock.json` and
`requirements*.txt`.

### `.github/workflows/**` can be weakened in the PR that is then judged by it

**Risk.** `ci.yml` runs from the PR head on `pull_request`, so a PR could
weaken a required check and be accepted on the weakened version.

**Why accepted.** Same root cause as above: it is the 0-approval problem
restated, and the mitigations are the same. `claude-code-review.yml` at least
declines to run at all when it differs from the default branch, so that file
cannot be quietly rewritten.

**Revisit when.** As above.

### No hash pinning on the Python locks

**Risk.** `requirements.txt` pins versions but not artifact hashes, so CI and
the Vercel build accept whatever the index serves for a pinned version. The npm
side has `sha512-` integrity on all 594 entries; the Python side has nothing
equivalent.

**Why accepted (for now).** This is the one change in the set that can break a
production deploy. Hashes are all-or-nothing: once present, the installer
refuses anything unhashed. Vercel's Python builder is `uv` — inferred from
`UV_LINK_MODE` in `vercel.json`, so pip's documented hash-checking behaviour
does not apply — and whether it honours `UV_REQUIRE_HASHES` is untested. The
threat it closes is a compromised index or mirror serving a different artifact
for an existing version, on top of TLS, from the default PyPI index.

**Revisit when.** Doing it deliberately, gated on a preview deploy: regenerate
both locks with `--generate-hashes` (keeping the existing header flags), add
`UV_REQUIRE_HASHES` next to `UV_LINK_MODE`, prove the preview installs, then
keep the hashes but drop the flag if the builder rejects it.

### No SBOM and no build provenance attestation

**Risk.** Nothing ties the bytes served in production to a reviewed commit,
its lockfiles and a CI result.

**Why accepted.** Attestation in particular would be theatre here: Vercel
rebuilds from source per environment rather than promoting one immutable
artifact, so attesting CI's `dist/` attests bytes nobody serves. An SBOM is
cheap to produce but answers a question that `npm ls` and `git log` over the
lockfile already answer for a two-ecosystem, single-maintainer app.

**Revisit when.** The deployment model changes to promote a built artifact, or
someone asks for an SBOM.

### `TEST_DATABASE_URL` is available to `pull_request` runs

**Risk.** A real Postgres credential is exposed to the `backend` job on PRs, so
a holder of push access could move it.

**Why accepted.** GitHub withholds secrets from fork `pull_request` runs, so
reaching it requires write access to this repo already — at which point the
credential is the least of it. The database is disposable and holds no real
data. Removing it would strip the *required* `backend` check of
`tests/test_locks_pg.py` and `tests/test_balances_pg.py`, the only verification
of the row-lock protocol anywhere, since SQLite silently drops those clauses.

**Revisit when.** A second committer joins, or the test database stops being
disposable.

### Every merge to `master` deploys to 100% of users at once

**Risk.** No canary. `VitePWA({ registerType: "autoUpdate" })` additionally
pushes a new service worker to every installed PWA client at once, so a bad
dependency bump reaches everyone.

**Why accepted.** A canary needs traffic to split and somebody watching the
split; neither exists. `autoUpdate` is deliberate — the alternative strands
installed clients on an old app shell, which is the failure the chunk-load
reload in `main.tsx` exists to catch.

**Compensating controls.** Vercel instant rollback; a preview deployment on
every `develop` push and every PR. For dependency-bump PRs specifically, open
the preview before merging — those are the class that breaks at runtime rather
than at build time, so a green build proves less than usual.

### Dependabot PRs get no Claude review

**Risk.** The one PR class that changes the supply chain is the one class the
automated reviewer skips.

**Why accepted.** The reason is sound and documented in
`claude-code-review.yml`: for `pull_request` the workflow runs from the PR's own
head, and a Dependabot PR can edit `.github/workflows`, so restoring the review
would mean putting the OAuth token within reach of a branch nobody here wrote.

**Compensating controls.** The `audit` and `locks` jobs run on those PRs, and
are exactly the review a dependency bump needs.

### Production configuration lives in dashboards

**Risk.** The Vercel Firewall rule, Vercel env vars, the Supabase auth email
templates, the out-of-band `splitdec_app` role and hand-applied migrations are
all outside version control, PR review and CI.

**Why accepted.** Rebuilding them as infrastructure-as-code is a larger project
than the app. The migration files are already the stated source of truth; what
was missing was a way to notice drift, not a way to declare intent.

**Compensating controls.** The dashboard table above is the inventory, checked
per release; `tests/test_grants_pg.py` reads the live catalogs and is the only
thing that checks what the database actually says.

### `npm audit` has no per-advisory ignore

**Risk.** A high-severity advisory in a dev-only package with no fix available
turns the `audit` job red and keeps it red.

**Why accepted.** The job is deliberately **not** a required status check, so a
red `audit` informs rather than blocks. If one lands and cannot be fixed, the
levers are `--omit=dev`, raising `--audit-level`, or a wrapper such as
`audit-ci` — choose one, narrow it as far as it will go, and record it here
with a date.
