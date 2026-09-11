"""Recipient-controlled opt-out from invitation email.

Covers the three halves that have to agree: the token (unforgeable, and tied to
one address), the endpoint (POST-only, idempotent, no oracle), and what
`invite_to_group` does with a suppressed address — which is to send no email
and change nothing else.
"""

import uuid

import pytest
from conftest import make_user
from sqlalchemy import select

from _src import emailer, unsubscribe
from _src.models import EmailSuppression, GroupInvitation, WriteEvent
from _src.ratelimit import recipient_key

SECRET = "test-unsubscribe-secret"
RECIPIENT = "victim@test.dev"


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setattr(unsubscribe, "UNSUBSCRIBE_SECRET", SECRET)
    # The router imported the name at module load, so patching only the source
    # module would leave the endpoint reading the old (empty) value.
    monkeypatch.setattr("_src.routers.unsubscribe.UNSUBSCRIBE_SECRET", SECRET)


@pytest.fixture(autouse=True)
def _full_bucket(monkeypatch):
    """The token bucket is module state that survives between tests, so a file
    with a dozen requests in it would otherwise start throttling itself."""
    monkeypatch.setattr("_src.routers.unsubscribe._tokens", 1000.0)


class TestTheToken:
    def test_round_trips_to_the_recipient_digest(self):
        token = unsubscribe.mint_token(RECIPIENT)
        assert unsubscribe.verify_token(token) == recipient_key(RECIPIENT)

    def test_is_case_insensitive_like_every_other_address_match(self):
        assert unsubscribe.mint_token("Victim@Test.dev") == unsubscribe.mint_token(RECIPIENT)

    def test_names_exactly_one_address(self):
        other = unsubscribe.mint_token("someone.else@test.dev")
        assert unsubscribe.verify_token(other) != recipient_key(RECIPIENT)

    def test_does_not_contain_the_address(self):
        """It travels in a URL, so it reaches the function's request logs. A
        digest there is what write_events already stores; an address is not."""
        token = unsubscribe.mint_token(RECIPIENT)
        assert "victim" not in token.lower()
        assert "test.dev" not in token.lower()

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "nonsense",
            "no-dot-separator",
            "a.b.c",
            "!!!.!!!",
            # A real digest with a signature that is not ours: the shape is
            # right and only the secret is missing, which is the forgery this
            # is actually defending against.
            f"{unsubscribe._b64(bytes.fromhex(recipient_key(RECIPIENT)))}."
            f"{unsubscribe._b64(b'x' * 32)}",
        ],
    )
    def test_refuses_anything_it_did_not_sign(self, bad):
        assert unsubscribe.verify_token(bad) is None

    def test_a_tampered_digest_does_not_verify(self):
        digest, signature = unsubscribe.mint_token(RECIPIENT).split(".")
        other = unsubscribe._b64(bytes.fromhex(recipient_key("someone.else@test.dev")))
        assert unsubscribe.verify_token(f"{other}.{signature}") is None
        assert digest != other  # the test would be vacuous otherwise

    def test_without_a_secret_there_is_no_token_and_nothing_verifies(self, monkeypatch):
        token = unsubscribe.mint_token(RECIPIENT)
        monkeypatch.setattr(unsubscribe, "UNSUBSCRIBE_SECRET", "")
        assert unsubscribe.mint_token(RECIPIENT) is None
        assert unsubscribe.verify_token(token) is None


class TestTheEndpoint:
    async def _post(self, client, token):
        return await client.post(f"/api/unsubscribe?token={token}")

    async def test_records_the_objection(self, client, db_session):
        assert (await self._post(client, unsubscribe.mint_token(RECIPIENT))).status_code == 204
        async with db_session() as s:
            rows = (await s.execute(select(EmailSuppression))).scalars().all()
        assert [r.recipient_hash for r in rows] == [recipient_key(RECIPIENT)]

    async def test_is_idempotent(self, client, db_session):
        """A provider retrying a one-click POST, and a reader pressing the
        button again next month, must both succeed."""
        token = unsubscribe.mint_token(RECIPIENT)
        for _ in range(3):
            assert (await self._post(client, token)).status_code == 204
        async with db_session() as s:
            rows = (await s.execute(select(EmailSuppression))).scalars().all()
        assert len(rows) == 1

    async def test_an_unsigned_token_is_refused_and_stores_nothing(self, client, db_session):
        assert (await self._post(client, "forged.token")).status_code == 400
        async with db_session() as s:
            assert (await s.execute(select(EmailSuppression))).scalars().all() == []

    async def test_a_missing_token_is_refused(self, client):
        assert (await client.post("/api/unsubscribe")).status_code == 400

    async def test_there_is_no_get(self, client):
        """`List-Unsubscribe-Post` means a provider POSTs this URL with no
        human involved, and scanners prefetch every GET in a message. A GET
        that unsubscribed would fire on delivery."""
        assert (await client.get(f"/api/unsubscribe?token={unsubscribe.mint_token(RECIPIENT)}")).status_code == 405

    async def test_answers_503_when_the_deployment_has_no_secret(
        self, client, db_session, monkeypatch
    ):
        token = unsubscribe.mint_token(RECIPIENT)
        monkeypatch.setattr("_src.routers.unsubscribe.UNSUBSCRIBE_SECRET", "")
        r = await self._post(client, token)
        assert r.status_code == 503
        # Generic to the caller: an anonymous error naming an environment
        # variable hands a stranger the deployment's shape.
        assert "UNSUBSCRIBE_SECRET" not in r.text

    async def test_the_bucket_eventually_refuses(self, client, monkeypatch):
        monkeypatch.setattr("_src.routers.unsubscribe._tokens", 1.0)
        token = unsubscribe.mint_token(RECIPIENT)
        assert (await self._post(client, token)).status_code == 204
        assert (await self._post(client, token)).status_code == 429

    async def test_requires_no_authentication(self, client, current_user):
        """The person this exists for has no account — that is the whole
        reason they want the mail stopped."""
        current_user.id = None  # any auth dependency would assert in conftest
        assert (
            await self._post(client, unsubscribe.mint_token(RECIPIENT))
        ).status_code == 204


class TestWhatSuppressionChangesAboutInviting:
    async def _invite(self, client, group_id, email):
        return await client.post(
            f"/api/groups/{group_id}/invitations", json={"email": email}
        )

    @pytest.fixture
    def _captured(self, monkeypatch):
        sent: list[dict] = []
        monkeypatch.setattr(emailer, "RESEND_API_KEY", "re_test_key")
        monkeypatch.setattr(emailer, "_post_resend", lambda payload: sent.append(payload))
        return sent

    async def test_a_suppressed_address_gets_no_email(
        self, client, db_session, two_user_group, _captured
    ):
        await client.post(f"/api/unsubscribe?token={unsubscribe.mint_token(RECIPIENT)}")
        assert (await self._invite(client, two_user_group["group"].id, RECIPIENT)).status_code == 201
        assert _captured == []

    async def test_the_invitation_itself_is_unaffected(
        self, client, db_session, two_user_group, current_user, _captured
    ):
        """Opting out of email is not opting out of SplitDec. The row stands,
        and the person still finds it waiting if they ever sign up."""
        g = two_user_group
        await client.post(f"/api/unsubscribe?token={unsubscribe.mint_token(RECIPIENT)}")
        inv = (await self._invite(client, g["group"].id, RECIPIENT)).json()
        assert (await client.get(f"/api/groups/{g['group'].id}/invitations")).json()[0]["id"] == inv["id"]

        newcomer = await make_user(db_session, RECIPIENT, "Victim")
        current_user.id = newcomer.id
        assert len((await client.get("/api/invitations/mine")).json()) == 1
        assert (await client.post(f"/api/invitations/{inv['id']}/accept")).status_code == 204

    async def test_the_sender_is_still_charged(
        self, client, db_session, two_user_group, _captured
    ):
        """Refunding the slot would let a caller read their own remaining
        allowance to discover whether an address has unsubscribed — the
        registration oracle this endpoint is built to deny, rebuilt out of a
        rate limit."""
        await client.post(f"/api/unsubscribe?token={unsubscribe.mint_token(RECIPIENT)}")
        await self._invite(client, two_user_group["group"].id, RECIPIENT)
        async with db_session() as s:
            events = (await s.execute(select(WriteEvent))).scalars().all()
        assert [e.recipient_hash for e in events] == [recipient_key(RECIPIENT)]

    async def test_an_unsuppressed_address_still_gets_mail(
        self, client, two_user_group, _captured
    ):
        assert (
            await self._invite(client, two_user_group["group"].id, "someone@test.dev")
        ).status_code == 201
        assert len(_captured) == 1
        assert _captured[0]["to"] == ["someone@test.dev"]

    async def test_suppression_does_not_leak_into_the_response(
        self, client, db_session, two_user_group, _captured
    ):
        """The caller must not be able to tell the two apart — same shape, same
        status, same stored row, exactly as for a registered vs unregistered
        address."""
        await client.post(f"/api/unsubscribe?token={unsubscribe.mint_token(RECIPIENT)}")
        muted = await self._invite(client, two_user_group["group"].id, RECIPIENT)
        heard = await self._invite(client, two_user_group["group"].id, "someone@test.dev")
        assert muted.status_code == heard.status_code == 201
        assert muted.json().keys() == heard.json().keys()
        varies = ("id", "email", "created_at")
        assert {k: v for k, v in muted.json().items() if k not in varies} == {
            k: v for k, v in heard.json().items() if k not in varies
        }


class TestDeletingAnAccountLeavesTheObjectionStanding:
    async def test_suppression_survives_account_deletion(
        self, client, db_session, two_user_group, current_user
    ):
        """Otherwise deleting and re-creating an account is how you resume mail
        to an address that refused it. Keeping the record of an objection is
        what honouring it requires — and the row names a digest, not an
        address, so nothing identifying is kept behind."""
        g = two_user_group
        await client.post(
            f"/api/unsubscribe?token={unsubscribe.mint_token(g['alice'].email)}"
        )
        assert (
            await client.delete(f"/api/groups/{g['group'].id}/members/{g['bob'].id}")
        ).status_code == 204
        assert (await client.delete("/api/users/me")).status_code == 204

        async with db_session() as s:
            rows = (await s.execute(select(EmailSuppression))).scalars().all()
        assert [r.recipient_hash for r in rows] == [recipient_key(g["alice"].email)]


class TestTheEmailCarriesTheWayOut:
    def test_body_and_headers_carry_the_signed_link(self):
        token = unsubscribe.mint_token(RECIPIENT)
        content = emailer.invitation_email_content("Alice", "Trip", token)
        headers = emailer.unsubscribe_headers(token)
        assert f"{emailer.APP_URL}/unsubscribe?token={token}" in content["html"]
        assert f"<{emailer.APP_URL}/api/unsubscribe?token={token}>" in headers["List-Unsubscribe"]
        # One-click (RFC 8058) is what makes the mail client's own button work.
        assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
        assert emailer.UNSUBSCRIBE_MAILTO in headers["List-Unsubscribe"]

    def test_without_a_token_it_degrades_to_the_contact_address(self):
        content = emailer.invitation_email_content("Alice", "Trip", None)
        headers = emailer.unsubscribe_headers(None)
        assert emailer.CONTACT_EMAIL in content["html"]
        assert headers["List-Unsubscribe"] == f"<{emailer.UNSUBSCRIBE_MAILTO}>"
        # No one-click without an https endpoint to honour it.
        assert "List-Unsubscribe-Post" not in headers

    async def test_a_real_send_carries_them(self, monkeypatch):
        sent: list[dict] = []
        monkeypatch.setattr(emailer, "RESEND_API_KEY", "re_test_key")
        monkeypatch.setattr(emailer, "_post_resend", lambda payload: sent.append(payload))
        token = unsubscribe.mint_token(RECIPIENT)
        assert await emailer.send_invitation_email(
            RECIPIENT, "Alice", "Trip", correlator=uuid.uuid4(), unsubscribe_token=token
        )
        assert sent[0]["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
