import uuid

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import SUPABASE_JWT_SECRET, SUPABASE_URL

_bearer = HTTPBearer(auto_error=False)

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
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
        if alg == "HS256":
            if not SUPABASE_JWT_SECRET:
                raise HTTPException(
                    status_code=500, detail="SUPABASE_JWT_SECRET is not configured"
                )
            payload = jwt.decode(
                token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated"
            )
        else:
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token, signing_key.key, algorithms=[alg], audience="authenticated"
            )
    except HTTPException:
        raise
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Token has no valid subject")
