# Supply-chain posture

What protects the code this app installs and deploys, what is deliberately
*not* protected, and where the controls live that no file in this repo can
show you. Written after an OWASP A03 (Software Supply Chain Failures) review in
September 2026.

The point of the second half is that an accepted risk and an oversight look
identical from outside. Everything below the line was considered and declined,
with a reason and a trigger for revisiting it.

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
| `SENTRY_AUTH_TOKEN` | project-scoped, production only | Vercel env vars |
| Auth email templates | match `docs/auth-email-templates.md` | Supabase dashboard |
| Database grants | `AUDIT_DATABASE_URL=<production> pytest tests/test_grants_pg.py` | run per release |

Verifying the GitHub half without clicking through the UI:

```bash
gh api repos/T5chrono/split-dec --jq .security_and_analysis
gh api repos/T5chrono/split-dec/actions/permissions/workflow
gh api repos/T5chrono/split-dec/dependabot/alerts --jq '[.[] | select(.state=="open")] | length'
```

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
