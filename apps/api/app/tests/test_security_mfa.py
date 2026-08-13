import time

import pytest

pytest.importorskip("aiosqlite")
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import *  # noqa: F401,F403 - register every ORM model for metadata
from app.models.security import (
    Organization,
    OrganizationMembership,
    OrganizationRole,
    SecurityUser,
    UserMFACredential,
    UserRecoveryCode,
)
from app.services.security import totp
from app.services.security.context import ActorContext
from app.services.security.crypto import hash_password
from app.services.security.service import (
    confirm_mfa_enrolment,
    disable_mfa,
    login,
    mfa_status,
    start_mfa_enrolment,
)

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def make_actor(db: AsyncSession) -> tuple[ActorContext, SecurityUser]:
    organization = Organization(name="Example Chambers", slug="example-chambers")
    db.add(organization)
    await db.flush()
    user = SecurityUser(
        email="lawyer@example.com",
        display_name="Example Lawyer",
        password_hash=hash_password(PASSWORD),
    )
    db.add(user)
    await db.flush()
    membership = OrganizationMembership(
        organization_id=organization.id,
        user_id=user.id,
        role=OrganizationRole.OWNER,
    )
    db.add(membership)
    await db.commit()
    actor = ActorContext(
        user_id=user.id,
        membership_id=membership.id,
        organization_id=organization.id,
        email=user.email,
        display_name=user.display_name,
        role=OrganizationRole.OWNER,
        mfa_enrolled=False,
    )
    return actor, user


# --- the algorithm itself ----------------------------------------------------


def test_totp_matches_rfc6238_reference_vector():
    # RFC 6238 Appendix B: the ASCII secret "12345678901234567890" at
    # T=59 produces 94287082 for SHA-1; we take the low 6 digits.
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert totp.code_for_counter(secret, 1) == "287082"


def test_code_is_accepted_within_drift_but_not_beyond_it():
    secret = totp.new_secret()
    now = time.time()
    previous = totp.code_for_counter(secret, totp.counter_at(now) - 1)
    stale = totp.code_for_counter(secret, totp.counter_at(now) - 5)
    assert totp.verify(secret, previous, at=now) is not None
    assert totp.verify(secret, stale, at=now) is None


def test_a_spent_counter_cannot_be_replayed():
    secret = totp.new_secret()
    now = time.time()
    counter = totp.counter_at(now)
    code = totp.code_for_counter(secret, counter)
    assert totp.verify(secret, code, at=now) == counter
    assert totp.verify(secret, code, at=now, last_used_counter=counter) is None


def test_malformed_codes_are_rejected_without_raising():
    secret = totp.new_secret()
    for candidate in ("", "abcdef", "12345", "1234567", "12 34 56"):
        assert totp.verify(secret, candidate) is None


# --- enrolment ---------------------------------------------------------------


async def test_enrolment_only_binds_once_confirmed(db):
    actor, user = await make_actor(db)
    credential, uri = await start_mfa_enrolment(db, actor)
    assert credential.confirmed_at is None
    assert credential.secret in uri
    assert "otpauth://totp/" in uri

    # An unconfirmed enrolment must not start demanding codes at login.
    state = await mfa_status(db, actor)
    assert state["enabled"] is False
    assert state["enrolment_started"] is True
    assert user.mfa_enrolled is False

    codes = await confirm_mfa_enrolment(
        db, actor, totp.code_for_counter(credential.secret, totp.counter_at())
    )
    assert len(codes) == 10
    state = await mfa_status(db, actor)
    assert state["enabled"] is True
    assert state["recovery_codes_remaining"] == 10


async def test_confirming_with_a_wrong_code_leaves_mfa_off(db):
    actor, user = await make_actor(db)
    await start_mfa_enrolment(db, actor)
    with pytest.raises(HTTPException) as exc:
        await confirm_mfa_enrolment(db, actor, "000000")
    assert exc.value.status_code == 400
    assert (await mfa_status(db, actor))["enabled"] is False


async def test_re_enrolling_while_enabled_is_refused(db):
    actor, _ = await make_actor(db)
    credential, _ = await start_mfa_enrolment(db, actor)
    await confirm_mfa_enrolment(
        db, actor, totp.code_for_counter(credential.secret, totp.counter_at())
    )
    with pytest.raises(HTTPException) as exc:
        await start_mfa_enrolment(db, actor)
    assert exc.value.status_code == 409


# --- login -------------------------------------------------------------------


async def enable_mfa(db: AsyncSession, actor: ActorContext) -> UserMFACredential:
    credential, _ = await start_mfa_enrolment(db, actor)
    await confirm_mfa_enrolment(
        db, actor, totp.code_for_counter(credential.secret, totp.counter_at())
    )
    return credential


async def test_login_without_a_code_is_refused_once_mfa_is_enabled(db):
    actor, _ = await make_actor(db)
    await enable_mfa(db, actor)
    with pytest.raises(HTTPException) as exc:
        await login(db, email="lawyer@example.com", password=PASSWORD)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Multi-factor code required"


async def test_login_succeeds_with_a_valid_code_and_records_the_method(db):
    actor, _ = await make_actor(db)
    credential = await enable_mfa(db, actor)
    # The code spent confirming enrolment is burned, so sign in with the next
    # window's code — which is exactly what a user does thirty seconds later.
    _, _, _, _, session = await login(
        db,
        email="lawyer@example.com",
        password=PASSWORD,
        mfa_code=totp.code_for_counter(credential.secret, totp.counter_at() + 1),
    )
    assert session.auth_method == "totp"


async def test_the_code_used_to_confirm_enrolment_cannot_also_log_in(db):
    actor, _ = await make_actor(db)
    credential = await enable_mfa(db, actor)
    with pytest.raises(HTTPException) as exc:
        await login(
            db,
            email="lawyer@example.com",
            password=PASSWORD,
            mfa_code=totp.code_for_counter(credential.secret, totp.counter_at()),
        )
    assert exc.value.detail == "Invalid multi-factor code"


async def test_a_wrong_password_still_fails_before_the_code_is_considered(db):
    actor, _ = await make_actor(db)
    credential = await enable_mfa(db, actor)
    with pytest.raises(HTTPException) as exc:
        await login(
            db,
            email="lawyer@example.com",
            password="not-the-password",
            mfa_code=totp.code_for_counter(credential.secret, totp.counter_at()),
        )
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid email, password, or organization"


async def test_a_recovery_code_works_once_and_then_is_spent(db):
    actor, _ = await make_actor(db)
    await start_mfa_enrolment(db, actor)
    credential = await db.scalar(
        select(UserMFACredential).where(UserMFACredential.user_id == actor.user_id)
    )
    codes = await confirm_mfa_enrolment(
        db, actor, totp.code_for_counter(credential.secret, totp.counter_at())
    )
    recovery = codes[0]

    _, _, _, _, session = await login(
        db, email="lawyer@example.com", password=PASSWORD, mfa_code=recovery
    )
    assert session.auth_method == "totp"
    assert (await mfa_status(db, actor))["recovery_codes_remaining"] == 9

    with pytest.raises(HTTPException) as exc:
        await login(db, email="lawyer@example.com", password=PASSWORD, mfa_code=recovery)
    assert exc.value.detail == "Invalid multi-factor code"


async def test_disable_requires_the_password_and_clears_every_credential(db):
    actor, user = await make_actor(db)
    await enable_mfa(db, actor)

    with pytest.raises(HTTPException) as exc:
        await disable_mfa(db, actor, password="wrong")
    assert exc.value.status_code == 403
    assert (await mfa_status(db, actor))["enabled"] is True

    await disable_mfa(db, actor, password=PASSWORD)
    assert (await mfa_status(db, actor))["enabled"] is False
    assert user.mfa_enrolled is False
    assert (await db.scalars(select(UserRecoveryCode))).all() == []
    # And login goes back to password-only.
    _, _, _, _, session = await login(db, email="lawyer@example.com", password=PASSWORD)
    assert session.auth_method == "password"
