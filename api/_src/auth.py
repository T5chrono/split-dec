import logging
import uuid

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import (
    ALLOW_LEGACY_HS256,
    DATABASE_URL,
    SUPABASE_JWT_SECRET,
    SUPABASE_URL,
    supabase_url_problem,
)

_bearer = HTTPBearer(auto_error=False)

logger = logging.getLogger("splitdec.auth")

# What an unauthenticated caller is told when the *deployment* is broken rather
# than the token. Nothing that names a variable, a project or a file: an
# unauthenticated 500 that reads "SUPABASE_JWT_SECRET is not configured" hands
# a stranger a piece of the deployment's shape for free, and there is nothing
# they could do with the accurate version anyway. The precise cause goes to the
# server log, which is the one reader who can act on it.
_UNAVAILABLE = "Authentication is unavailable"

# The algorithms this deployment accepts, and the key each is verified with.
# The `alg` header travels inside the token being checked, so it is attacker
# controlled: it may *select* from this set and nothing else. Feeding it
# straight to `algorithms=[alg]` made the token nominate its own verification —
# harmless today only because every branch already picked its own key, but one
# key-handling change away from being the classic algorithm-confusion bug, and
# it left "none" resting on PyJWT's internal guard rather than on ours.
#
# HS256 is **off unless ALLOW_LEGACY_HS256 says otherwise**. It exists for
# Supabase projects still on the shared JWT secret; this one is not — its JWKS
# serves a single ES256 key and has done since before the secret was last
# touched, so leaving the symmetric path open kept a second, weaker way to mint
# a valid token alive for no working flow. A shared secret is a symmetric
# credential: anything that can read it can *issue* tokens, where the JWKS key
# can only verify them. Turning it back on takes two deliberate acts — the flag
# and the secret — rather than one forgotten environment variable.
SYMMETRIC_ALGORITHMS = frozenset({"HS256"}) if ALLOW_LEGACY_HS256 else frozenset()
ASYMMETRIC_ALGORITHMS = frozenset({"ES256", "RS256"})  # Supabase signing keys, via JWKS

# Cached at module scope so a warm invocation reuses the client, and through
# it the JWKS response PyJWT holds for five minutes.
_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        # Checked here rather than at import: the module has to be importable
        # in CI and under pytest, where neither variable is set and no token is
        # ever verified. The first real verification is the first moment the
        # answer matters, and it fails closed.
        problem = supabase_url_problem(SUPABASE_URL, DATABASE_URL)
        if problem:
            logger.error("Refusing to verify tokens: %s", problem)
            raise HTTPException(status_code=500, detail=_UNAVAILABLE)
        # `cache_keys=True` is deliberately *not* passed. PyJWT keeps two
        # caches: the JWKS response, on by default and good for five minutes,
        # and behind that flag an LRU of individual signing keys with no
        # expiry at all. With the flag on, a `kid` it has already resolved
        # never consults the key set again, so a key Supabase revokes goes on
        # verifying tokens for as long as this instance stays warm. The
        # response cache is what spares us a fetch per request; the flag
        # bought nothing on top of it and bounded nothing.
        _jwks_client = jwt.PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def _expected_issuer() -> str | None:
    """Who the token has to say minted it, or `None` if we cannot say.

    Supabase publishes this at the project's own
    `/auth/v1/.well-known/openid-configuration`, and for a hosted project it is
    the project URL with `/auth/v1` on the end — checked against this project's
    discovery document rather than assumed, because a wrong value here is a 401
    for every user at once.

    `None` on the symmetric path in a deployment that never set SUPABASE_URL:
    that is the legacy shared-secret configuration, which is off here, and
    inventing an issuer for it would refuse tokens that are otherwise fine. The
    asymmetric path cannot reach `None` — `_get_jwks_client` has already
    refused if SUPABASE_URL is unset or does not match the database's project.
    """
    return f"{SUPABASE_URL.rstrip('/')}/auth/v1" if SUPABASE_URL else None


def _require_issuer() -> tuple[str, ...]:
    """`("iss",)` when there is an issuer to compare against, else nothing.

    Separate from the pin itself because PyJWT treats the two independently:
    `issuer=` checks the claim only *if the token carries one*, and `require`
    is the only thing that makes its absence fatal. Neither alone is a check.
    """
    return ("iss",) if _expected_issuer() else ()


def verify_jwt(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> uuid.UUID:
    """Validate the Supabase access token and return the caller's user id.

    Tokens are verified against the project's JWKS (asymmetric signing keys).
    The legacy HS256 path is gated behind `ALLOW_LEGACY_HS256` and refused like
    any other unsupported algorithm while that flag is off.

    `exp`, `aud` and `sub` are *required*, not merely checked. PyJWT verifies a
    claim it finds and shrugs at one it does not, so before this a correctly
    signed token that simply left `exp` out was accepted, and accepted for
    ever — the one token shape that never becomes invalid. Whoever can sign
    such a token can already sign anything, so this is a second lock on a door
    that only opens after the first one is gone; it costs a line, and the
    difference between a breach that ends with the key rotation and one that
    does not is worth a line.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = credentials.credentials
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg in SYMMETRIC_ALGORITHMS:
            if not SUPABASE_JWT_SECRET:
                logger.error(
                    "Legacy HS256 is enabled but no shared secret is configured"
                )
                raise HTTPException(status_code=500, detail=_UNAVAILABLE)
            key = SUPABASE_JWT_SECRET
        elif alg in ASYMMETRIC_ALGORITHMS:
            key = _get_jwks_client().get_signing_key_from_jwt(token).key
        else:
            # Unsupported, absent, "none", or HS256 while the legacy flag is
            # off — refused before any key is fetched, so an unknown `alg` can
            # never reach a decode call.
            raise HTTPException(status_code=401, detail="Unsupported token algorithm")
        payload = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience="authenticated",
            issuer=_expected_issuer(),
            options={"require": ["exp", "aud", "sub", *_require_issuer()]},
        )
    except HTTPException:
        raise
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    # An anonymous sign-in produces a token with the same `aud` and `role` as a
    # real one — "authenticated" in both — so nothing above this line separates
    # the two. Three things currently stop such a token existing: the provider
    # is switched off in the dashboard, every route needs a `public.users` row,
    # and an anonymous account cannot get one because it has no email address
    # and that column is NOT NULL, so the mirroring trigger rolls the sign-up
    # back. All three are somewhere else, and the last is an accident of the
    # schema rather than a decision — make `email` nullable one day and the
    # door opens with nothing here to notice. `is_anonymous` travels in the
    # token, which is the one thing this function is actually looking at.
    #
    # Absent or false both pass: only the literal claim is refused, so ordinary
    # tokens — including any minted before Supabase added the claim — are
    # unaffected.
    if payload.get("is_anonymous"):
        raise HTTPException(status_code=401, detail="Anonymous tokens are not accepted")
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Token has no valid subject")
