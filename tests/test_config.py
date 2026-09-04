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
