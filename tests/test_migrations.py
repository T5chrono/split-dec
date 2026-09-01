"""Static checks over supabase/migrations/*.sql.

The migrations are applied to the live database by hand (Supabase MCP or the
dashboard), and nothing else in CI looks at them -- no test creates a function,
because the suite builds its schema from the SQLAlchemy models on SQLite. So
the one rule here that has already been broken once gets a guard.
"""

import re
from pathlib import Path

import pytest

MIGRATIONS = Path(__file__).resolve().parent.parent / "supabase" / "migrations"

# `--` to end of line. Crude, but these files contain no string literal with a
# double hyphen in it, and stripping comments is what keeps the prose in
# 20260901000000 (which discusses SECURITY DEFINER) out of the parse below.
_COMMENT = re.compile(r"--[^\n]*")
_FUNCTION = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+public\.(\w+)\s*\((.*?)\)(.*?)\$\$;",
    re.IGNORECASE | re.DOTALL,
)
_REVOKE = re.compile(
    r"REVOKE\s+EXECUTE\s+ON\s+FUNCTION\s+public\.(\w+)\s*\(", re.IGNORECASE
)


def _sql() -> str:
    files = sorted(MIGRATIONS.glob("*.sql"))
    assert files, f"no migrations found under {MIGRATIONS}"
    return "\n".join(_COMMENT.sub("", f.read_text(encoding="utf-8")) for f in files)


def test_security_definer_functions_are_not_executable_by_the_api_roles():
    """Every SECURITY DEFINER function in `public` must have its EXECUTE
    revoked from PUBLIC/anon/authenticated.

    `public` is exposed through Supabase's Data API, where a function is
    reachable at /rest/v1/rpc/<name>, and Postgres grants EXECUTE to PUBLIC by
    default -- so a SECURITY DEFINER function added without a REVOKE is
    callable by anyone holding the publishable key, which is in the frontend
    bundle. 20260702000001 established the rule for handle_new_user();
    20260827000100 added handle_user_updated() a year later without it, and
    production carried `anon=X/postgres` on that function until
    20260901000000. This test is why that cannot happen a third time.
    """
    sql = _sql()
    revoked = {name.lower() for name in _REVOKE.findall(sql)}
    definers = {
        name.lower()
        for name, _args, body in _FUNCTION.findall(sql)
        if "SECURITY DEFINER" in body.upper()
    }
    assert definers, "parser found no SECURITY DEFINER functions -- it has drifted"
    missing = sorted(definers - revoked)
    assert not missing, (
        "SECURITY DEFINER function(s) in schema public with no REVOKE EXECUTE: "
        + ", ".join(missing)
        + ". Add `REVOKE EXECUTE ON FUNCTION public.<name>() FROM PUBLIC, anon, "
        "authenticated;` to a migration and apply it."
    )


@pytest.mark.parametrize("name", ["handle_new_user", "handle_user_updated"])
def test_the_known_trigger_functions_are_covered(name):
    """Pins the two that exist today, so a regex that stops matching fails
    loudly here instead of quietly emptying the set above."""
    assert name in {n.lower() for n in _REVOKE.findall(_sql())}
