import os
import sys
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# The app module reads DATABASE_URL at import time; give it a harmless value.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://unused:unused@localhost:6543/unused"
)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from _src.auth import verify_jwt  # noqa: E402
from _src.db import get_db  # noqa: E402
from _src.main import app  # noqa: E402
from _src.models import Base, Group, GroupMember, User  # noqa: E402


class CurrentUser:
    """Mutable holder so tests can switch the authenticated caller."""

    def __init__(self) -> None:
        self.id: uuid.UUID | None = None


@pytest.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        # Stand-in for Supabase's auth schema (used by account deletion).
        await conn.execute(text("ATTACH ':memory:' AS auth"))
        await conn.execute(text("CREATE TABLE auth.users (id TEXT PRIMARY KEY)"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    yield async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
def current_user() -> CurrentUser:
    return CurrentUser()


@pytest.fixture
async def client(db_session, current_user):
    async def override_get_db():
        async with db_session() as session:
            yield session

    def override_verify_jwt() -> uuid.UUID:
        assert current_user.id is not None, "test forgot to set current_user.id"
        return current_user.id

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_jwt] = override_verify_jwt
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def make_user(db_session, email: str, name: str | None = None) -> User:
    user = User(id=uuid.uuid4(), email=email, full_name=name or email.split("@")[0])
    async with db_session() as s:
        s.add(user)
        # Mirror into the fake auth schema like the Supabase trigger would.
        await s.execute(
            text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": str(user.id)}
        )
        await s.commit()
    return user


async def make_group(db_session, creator: User, *members: User, name: str = "Trip") -> Group:
    async with db_session() as s:
        group = Group(name=name, created_by=creator.id)
        s.add(group)
        await s.flush()
        for u in (creator, *members):
            s.add(GroupMember(group_id=group.id, user_id=u.id))
        await s.commit()
        return group


@pytest.fixture
async def two_user_group(db_session, current_user):
    """Alice + Bob in one group; Alice is the authenticated caller."""
    alice = await make_user(db_session, "alice@test.dev", "Alice")
    bob = await make_user(db_session, "bob@test.dev", "Bob")
    group = await make_group(db_session, alice, bob)
    current_user.id = alice.id
    return {"alice": alice, "bob": bob, "group": group}


def expense_payload(payer: User, participants: list[User], **overrides) -> dict:
    body = {
        "description": "Dinner",
        "category": "Dining out",
        "split_type": "EQUAL",
        "total_amount": "30.00",
        "currency": "PLN",
        "paid_by_user_id": str(payer.id),
        "splits": [{"user_id": str(u.id)} for u in participants],
    }
    body.update(overrides)
    return body


def idem() -> dict:
    return {"Idempotency-Key": str(uuid.uuid4())}
