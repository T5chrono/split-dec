"""Direct tests for the JWT boundary.

Every other API test overrides `verify_jwt` — that is what makes them readable,
but it also means the suite exercises the authorization rules on the assumption
that authentication happened, and never the authentication itself. FastAPI is
the sole authorization boundary in this deployment (RLS is off) and this
function is its front door, so the front door gets its own tests: signature,
expiry, audience, subject, and which algorithms are allowed to assert any of
those.

The last class puts the real dependency back and drives the app through it, so
a wiring mistake — a router mounted without it, an override left behind —
cannot pass unnoticed either.
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport, AsyncClient

from _src import auth
from _src.db import get_db
from _src.main import app

# Snapshotted before any fixture patches it: the algorithm set the module was
# actually imported with, which is what `test_hs256_is_off_in_the_module_as_
# imported` needs and what a monkeypatched `auth.SYMMETRIC_ALGORITHMS` can no
# longer tell you.
SHIPPED_SYMMETRIC_ALGORITHMS = auth.SYMMETRIC_ALGORITHMS

# 64 bytes, so PyJWT does not warn about key length on any algorithm below.
SECRET = "test-jwt-secret-" * 4
WRONG_SECRET = "attacker-secret-" * 4
SUBJECT = uuid.uuid4()


def _claims(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(SUBJECT),
        "aud": "authenticated",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    claims.update(overrides)
    return claims


def _hs256(secret: str = SECRET, **overrides) -> str:
    return jwt.encode(_claims(**overrides), secret, algorithm="HS256")


def _hmac_token(alg: str, secret: bytes) -> str:
    """Hand-rolled, because PyJWT refuses to *sign* with a PEM key — which is
    the guard being tested here, and the one an attacker simply does not run."""
    claims = _claims()
    claims["iat"] = int(claims["iat"].timestamp())
    claims["exp"] = int(claims["exp"].timestamp())
    parts = [
        jwt.utils.base64url_encode(json.dumps({"alg": alg, "typ": "JWT"}).encode()),
        jwt.utils.base64url_encode(json.dumps(claims).encode()),
    ]
    signed = b".".join(parts)
    signature = hmac.new(secret, signed, hashlib.sha256).digest()
    return b".".join([signed, jwt.utils.base64url_encode(signature)]).decode()


def _call(token: str | None) -> uuid.UUID:
    credentials = (
        None
        if token is None
        else HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    )
    return auth.verify_jwt(credentials)


def _status(token: str | None) -> int:
    with pytest.raises(HTTPException) as excinfo:
        _call(token)
    return excinfo.value.status_code


@pytest.fixture(autouse=True)
def _shared_secret(monkeypatch):
    """Configure *and enable* the legacy symmetric path.

    HS256 is off unless `ALLOW_LEGACY_HS256` is set (auth.py), so without this
    every symmetric test below would pass for the wrong reason — a 401 that
    means "algorithm not enabled" rather than "signature rejected". The class
    at the bottom of this file is the one that tests the gate itself.
    """
    monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.setattr(auth, "SYMMETRIC_ALGORITHMS", frozenset({"HS256"}))


@pytest.fixture
def signing_key():
    """An EC key pair standing in for the project's Supabase signing key."""
    private = ec.generate_private_key(ec.SECP256R1())
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private, public_pem


@pytest.fixture
def jwks(monkeypatch, signing_key):
    """Point the JWKS lookup at that key pair's public half."""
    _, public_pem = signing_key

    class StubKey:
        key = serialization.load_pem_public_key(public_pem)

    class StubClient:
        calls = 0

        def get_signing_key_from_jwt(self, token):
            StubClient.calls += 1
            return StubKey()

    client = StubClient()
    monkeypatch.setattr(auth, "_get_jwks_client", lambda: client)
    return client


class TestSymmetricTokens:
    """The legacy HS256 path, verified against the shared Supabase secret.

    Enabled for this class by the autouse fixture above; `ALLOW_LEGACY_HS256`
    is what enables it in a real deployment, and it is unset in this one.
    """

    def test_valid_token_yields_the_subject(self):
        assert _call(_hs256()) == SUBJECT

    def test_missing_header_is_refused(self):
        assert _status(None) == 401

    def test_garbage_is_refused(self):
        assert _status("not-a-token") == 401

    def test_wrong_signature_is_refused(self):
        assert _status(_hs256(secret=WRONG_SECRET)) == 401

    def test_tampered_payload_is_refused(self):
        header, _, signature = _hs256().split(".")
        other = jwt.encode(_claims(sub=str(uuid.uuid4())), SECRET, algorithm="HS256")
        assert _status(f"{header}.{other.split('.')[1]}.{signature}") == 401

    def test_expired_token_is_refused(self):
        stale = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert _status(_hs256(exp=stale)) == 401

    def test_wrong_audience_is_refused(self):
        """Supabase issues tokens for more than one audience; only the
        authenticated one may reach this API."""
        assert _status(_hs256(aud="anon")) == 401

    def test_missing_audience_is_refused(self):
        claims = _claims()
        del claims["aud"]
        assert _status(jwt.encode(claims, SECRET, algorithm="HS256")) == 401

    def test_missing_subject_is_refused(self):
        claims = _claims()
        del claims["sub"]
        assert _status(jwt.encode(claims, SECRET, algorithm="HS256")) == 401

    def test_non_uuid_subject_is_refused(self):
        assert _status(_hs256(sub="not-a-uuid")) == 401

    def test_unconfigured_secret_is_a_server_error_not_a_pass(self, monkeypatch):
        """Refusing every caller is the right answer; treating an unset secret
        as a successful verification would not be."""
        monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", "")
        assert _status(_hs256()) == 500


class TestAsymmetricTokens:
    """The current path: a signing key fetched from the project's JWKS."""

    def test_valid_token_yields_the_subject(self, jwks, signing_key):
        private, _ = signing_key
        assert _call(jwt.encode(_claims(), private, algorithm="ES256")) == SUBJECT

    def test_another_key_is_refused(self, jwks):
        other = ec.generate_private_key(ec.SECP256R1())
        assert _status(jwt.encode(_claims(), other, algorithm="ES256")) == 401

    def test_expired_token_is_refused(self, jwks, signing_key):
        private, _ = signing_key
        stale = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert _status(jwt.encode(_claims(exp=stale), private, algorithm="ES256")) == 401

    def test_wrong_audience_is_refused(self, jwks, signing_key):
        private, _ = signing_key
        assert _status(jwt.encode(_claims(aud="anon"), private, algorithm="ES256")) == 401


class TestAlgorithmAllowList:
    """`alg` travels inside the token being checked, so it may select from the
    supported set and nothing more."""

    def test_none_is_refused(self):
        assert _status(jwt.encode(_claims(), key=None, algorithm="none")) == 401

    def test_unsupported_algorithm_is_refused(self):
        """Signed with the real secret and still refused: HS512 is not one of
        the algorithms this deployment issues."""
        assert _status(jwt.encode(_claims(), SECRET, algorithm="HS512")) == 401

    def test_no_key_is_fetched_for_an_unsupported_algorithm(self, jwks):
        """The refusal comes before the JWKS lookup, so an unknown `alg` never
        reaches a decode call or a network fetch."""
        before = jwks.calls
        assert _status(jwt.encode(_claims(), SECRET, algorithm="HS384")) == 401
        assert jwks.calls == before

    def test_the_public_key_is_not_a_shared_secret(self, jwks, signing_key):
        """Algorithm confusion. The JWKS key is public, so a token that HMACs
        itself with it must not verify — as HS256, which is checked against the
        private shared secret instead, nor relabelled ES256, where the HMAC is
        not a signature the public key accepts."""
        _, public_pem = signing_key
        assert _status(_hmac_token("HS256", public_pem)) == 401
        assert _status(_hmac_token("ES256", public_pem)) == 401


class TestLegacyHS256IsOffByDefault:
    """The gate in front of the symmetric path.

    This project's Supabase JWKS serves a single ES256 key, so HS256 verifies
    nothing the app actually issues. Leaving it on kept a second way to mint a
    valid token alive for no working flow — and a materially weaker one: the
    shared secret is symmetric, so anything that can read it can *issue*
    tokens, where the JWKS key can only check them.

    Off means refused like any other unsupported algorithm, before a key is
    touched — not "accepted but fails to verify".
    """

    @pytest.fixture(autouse=True)
    def _disabled(self, monkeypatch):
        monkeypatch.setattr(auth, "SYMMETRIC_ALGORITHMS", frozenset())

    def test_a_correctly_signed_hs256_token_is_refused(self):
        """Signed with the real secret, which is still configured. The flag is
        what refuses it, not the signature."""
        assert _status(_hs256()) == 401

    def test_the_refusal_does_not_depend_on_the_secret_being_unset(self, monkeypatch):
        monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", "")
        assert _status(_hs256()) == 401

    def test_asymmetric_tokens_are_unaffected(self, jwks, signing_key):
        private, _ = signing_key
        assert _call(jwt.encode(_claims(), private, algorithm="ES256")) == SUBJECT


def test_hs256_is_off_in_the_module_as_imported():
    """The class above simulates the flag being off; this asserts that off is
    what the module actually imported with.

    Read from a copy taken at import time, before any fixture patched it —
    asserting on `auth.SYMMETRIC_ALGORITHMS` here would only re-read whatever
    the last monkeypatch set, and pass for that reason.
    """
    from _src import config

    if config.ALLOW_LEGACY_HS256:
        pytest.skip("ALLOW_LEGACY_HS256 is set in this environment")
    assert SHIPPED_SYMMETRIC_ALGORITHMS == frozenset()


class TestTheAppActuallyUsesIt:
    """The rest of the suite overrides `verify_jwt`; here it is left in place,
    so the app is driven through the real front door."""

    @pytest.fixture
    async def unauthenticated_client(self, db_session):
        async def override_get_db():
            async with db_session() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
        app.dependency_overrides.clear()

    async def test_no_token_is_401(self, unauthenticated_client):
        assert (await unauthenticated_client.get("/api/groups")).status_code == 401

    async def test_forged_token_is_401(self, unauthenticated_client):
        forged = _hs256(secret=WRONG_SECRET)
        r = await unauthenticated_client.get(
            "/api/groups", headers={"Authorization": f"Bearer {forged}"}
        )
        assert r.status_code == 401

    async def test_valid_token_reaches_the_endpoint(self, unauthenticated_client):
        r = await unauthenticated_client.get(
            "/api/groups", headers={"Authorization": f"Bearer {_hs256()}"}
        )
        assert r.status_code == 200
        assert r.json() == []
