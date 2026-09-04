"""The deployment's own configuration, as pure functions.

Everything here decides something that cannot be observed from a request: which
environment the app believes it is in, and whether the token issuer it trusts is
the same project as the database it reads. Both used to be single `os.getenv`
calls with a permissive default, and both fail closed now — which is only worth
anything if the failing is tested, since the states being guarded against are by
definition ones nobody sets up on purpose.
"""

import pytest

from _src.config import project_ref, resolve_env, supabase_url_problem

PROD_REF = "kmlheefyzhhegxmtaovq"
PROD_URL = f"https://{PROD_REF}.supabase.co"
PROD_DSN = (
    f"postgresql+asyncpg://postgres.{PROD_REF}:pa55w0rd"
    "@aws-0-eu-west-3.pooler.supabase.com:6543/postgres"
)

APP_DSN = (
    f"postgresql+asyncpg://splitdec_app.{PROD_REF}:pa55w0rd"
    "@aws-0-eu-west-3.pooler.supabase.com:6543/postgres"
)


class TestResolveEnv:
    """`ENV` is ours and can say anything; `VERCEL_ENV` is the platform's."""

    def test_a_laptop_is_taken_at_its_word(self):
        # No VERCEL_ENV: nobody is claiming this is hosted.
        assert resolve_env("development", "") == "development"

    def test_production_stays_production(self):
        assert resolve_env("production", "") == "production"

    @pytest.mark.parametrize("vercel_env", ["production", "preview"])
    def test_a_hosted_deployment_cannot_be_talked_into_development(self, vercel_env):
        """The finding this exists for.

        `ENV=development` in the Vercel project's environment variables would
        have switched on the Swagger page — a third-party script from
        cdn.jsdelivr.net executing on the origin that holds the Supabase
        session — plus the CORS middleware and the unauthenticated database
        probe. Nothing cross-checked it against where the code was running.
        """
        assert resolve_env("development", vercel_env) == "production"

    def test_vercel_dev_is_still_development(self):
        """`vercel dev` runs on a laptop and sets VERCEL_ENV=development. It is
        the one hosted-looking state that is genuinely local."""
        assert resolve_env("development", "development") == "development"

    @pytest.mark.parametrize("vercel_env", ["staging", "Production", "unknown", "test"])
    def test_an_unrecognized_platform_state_fails_closed(self, vercel_env):
        """Same rule as `docs_urls`: the failure mode of a value nobody
        anticipated is a missing dev convenience, never an open one."""
        assert resolve_env("development", vercel_env) == "production"


class TestProjectRef:
    def test_a_project_url(self):
        assert project_ref(PROD_URL) == PROD_REF

    def test_a_project_url_with_a_trailing_slash(self):
        assert project_ref(f"{PROD_URL}/") == PROD_REF

    def test_a_pooler_dsn(self):
        assert project_ref(PROD_DSN) == PROD_REF

    def test_a_password_containing_an_at_sign_does_not_confuse_it(self):
        """The ref is read out of the username, before the password — so it
        cannot be moved by whatever the password happens to contain."""
        dsn = f"postgresql+asyncpg://postgres.{PROD_REF}:p@ss@host:6543/postgres"
        assert project_ref(dsn) == PROD_REF

    def test_a_pooler_dsn_for_a_role_other_than_postgres(self):
        """The app stopped connecting as `postgres` (20260904100000).

        The username half of a pooler DSN is `<role>.<ref>`, and the pattern
        used to hardcode the role. Nothing failed loudly when the role changed
        -- project_ref simply returned None, which every caller reads as "a
        local database, nothing to compare". The cross-check in
        supabase_url_problem would have gone dead the moment the production
        DSN was swapped.
        """
        assert project_ref(APP_DSN) == PROD_REF

    def test_a_dotted_hostname_is_not_mistaken_for_a_ref(self):
        """Why the role half of the pattern still refuses dots. Widened far
        enough, `//db.example.com:5432` reads as role `db`, ref `example` --
        and a ref invented out of a hostname produces a mismatch against a
        perfectly good SUPABASE_URL."""
        assert project_ref("postgresql+asyncpg://db.example.com:5432/splitdec") is None

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "not-a-url",
            "https://evil.example",
            # A host that merely *ends* in the right domain.
            "https://kmlheefyzhhegxmtaovq.supabase.co.attacker.example",
            # A local database has no project ref, and that is not an error.
            "postgresql+asyncpg://postgres:secret@localhost:5432/splitdec",
        ],
    )
    def test_anything_else_has_no_ref(self, value):
        assert project_ref(value) is None


class TestSupabaseUrlProblem:
    def test_a_matching_pair_is_fine(self):
        assert supabase_url_problem(PROD_URL, PROD_DSN) is None

    def test_an_unset_url_is_refused(self):
        """It used to default to the production project, so a deployment that
        forgot the variable silently trusted our issuer while reading somebody
        else's database."""
        assert supabase_url_problem("", PROD_DSN) == "SUPABASE_URL is not set"

    def test_a_url_that_is_not_a_project_url_is_refused(self):
        assert supabase_url_problem("https://evil.example", PROD_DSN)

    def test_a_mismatched_pair_is_refused(self):
        """The interesting failure: tokens checked against one project's keys
        while every `sub` in them is looked up in another project's tables."""
        other = "aaaaaaaaaaaaaaaaaaaa"
        problem = supabase_url_problem(f"https://{other}.supabase.co", PROD_DSN)
        assert problem is not None
        assert other in problem and PROD_REF in problem

    def test_a_database_url_with_no_ref_is_not_a_mismatch(self):
        """Local development against a plain Postgres. There is nothing to
        compare, which is an absence rather than a conflict."""
        local = "postgresql+asyncpg://postgres:secret@localhost:5432/splitdec"
        assert supabase_url_problem(PROD_URL, local) is None

    def test_the_app_role_dsn_matches(self):
        """The pair production actually runs after the F9 swap."""
        assert supabase_url_problem(PROD_URL, APP_DSN) is None

    def test_a_supabase_host_with_no_readable_ref_is_refused(self):
        """Fail closed on the shape of this check disabling itself.

        A local Postgres with no ref is an absence and stays fine (above). A
        *Supabase* host whose username the pattern cannot read is different:
        the only reason to be here is that the DSN's shape moved, and skipping
        the comparison is precisely the silent no-op that made the role swap
        dangerous. The role name here contains a dot, which no role name the
        pattern accepts may.
        """
        odd = (
            f"postgresql+asyncpg://weird.role.{PROD_REF}:pa55w0rd"
            "@aws-0-eu-west-3.pooler.supabase.com:6543/postgres"
        )
        assert project_ref(odd) is None  # precondition for what follows
        problem = supabase_url_problem(PROD_URL, odd)
        assert problem is not None
        assert "no project ref" in problem
