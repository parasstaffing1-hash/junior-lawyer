from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.portal import ClientPortalSession, ClientPortalUser
from app.services.portal.service import csrf_valid
from app.services.security.crypto import new_csrf_token, token_hash


def test_portal_csrf_uses_separate_token_hash():
    raw = new_csrf_token()
    session = ClientPortalSession(
        portal_user_id=uuid4(), token_hash="a" * 64, csrf_hash=token_hash(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1), last_seen_at=datetime.now(timezone.utc),
    )
    assert csrf_valid(session, raw)
    assert not csrf_valid(session, raw + "x")


def test_portal_user_has_separate_org_email_uniqueness_constraint():
    names = {c.name for c in ClientPortalUser.__table__.constraints if c.name}
    assert "uq_portal_user_access" in names
    assert "uq_portal_user_org_email" in names


def test_portal_session_token_column_is_unique():
    assert ClientPortalSession.__table__.c.token_hash.unique is True
