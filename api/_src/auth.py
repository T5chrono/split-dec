import uuid

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import SUPABASE_JWT_SECRET, SUPABASE_URL

_bearer = HTTPBearer(auto_error=False)

# The algorithms this deployment accepts, and the key each is verified with.
# The `alg` header travels inside the token being checked, so it is attacker
# controlled: it may *select* from this set and nothing else. Feeding it
# straight to `algorithms=[alg]` made the token nominate its own verification —
# harmless today only because every branch already picked its own key, but one
# key-handling change away from being the classic algorithm-confusion bug, and
# it left "none" resting on PyJWT's internal guard rather than on ours.
SYMMETRIC_ALGORITHMS = frozenset({"HS256"})  # legacy shared Supabase JWT secret
ASYMMETRIC_ALGORITHMS = frozenset({"ES256", "RS256"})  # Supabase signing keys, via JWKS

# Cached at module scope so warm invocations reuse fetched keys.
_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(
            f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json", cache_keys=True
        )
    return _jwks_client


def verify_jwt(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> uuid.UUID:
    """Validate the Supabase access token and return the caller's user id.

    Supports both legacy HS256 (shared JWT secret) and the newer asymmetric
    signing keys (verified against the project's JWKS endpoint).
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = credentials.credentials
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg in SYMMETRIC_ALGORITHMS:
            if not SUPABASE_JWT_SECRET:
                raise HTTPException(
                    status_code=500, detail="SUPABASE_JWT_SECRET is not configured"
                )
            key = SUPABASE_JWT_SECRET
        elif alg in ASYMMETRIC_ALGORITHMS:
            key = _get_jwks_client().get_signing_key_from_jwt(token).key
        else:
            # Unsupported, absent, or "none" — refused before any key is
            # fetched, so an unknown `alg` can never reach a decode call.
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
