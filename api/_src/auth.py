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

# Cached at module scope so warm invocations reuse fetched keys.
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
        _jwks_client = jwt.PyJWKClient(
            f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json", cache_keys=True
        )
    return _jwks_client


def verify_jwt(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> uuid.UUID:
    """Validate the Supabase access token and return the caller's user id.

    Tokens are verified against the project's JWKS (asymmetric signing keys).
    The legacy HS256 path is gated behind `ALLOW_LEGACY_HS256` and refused like
    any other unsupported algorithm while that flag is off.
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
        payload = jwt.decode(token, key, algorithms=[alg], audience="authenticated")
    except HTTPException:
        raise
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Token has no valid subject")
