from app.db.base import Base
from app import models  # noqa: F401
from app.models.security import MatterAccessLevel, OrganizationRole
from app.services.security.permissions import ROLE_BASE_LEVEL


def test_security_schema_tables_are_registered():
    expected = {
        "organizations", "security_users", "organization_memberships",
        "organization_security_policies", "user_sessions", "matter_security_profiles",
        "matter_access_grants", "document_access_grants", "audit_chain_heads",
        "security_audit_entries", "retention_policies", "legal_holds", "deletion_requests",
    }
    assert expected.issubset(set(Base.metadata.tables))
    assert len(Base.metadata.tables) == 250


def test_role_baseline_is_least_privilege_for_non_legal_roles():
    assert ROLE_BASE_LEVEL[OrganizationRole.OWNER] == MatterAccessLevel.MANAGE
    assert ROLE_BASE_LEVEL[OrganizationRole.LAWYER] == MatterAccessLevel.WORK
    assert ROLE_BASE_LEVEL[OrganizationRole.JUNIOR] == MatterAccessLevel.WORK
    assert ROLE_BASE_LEVEL[OrganizationRole.READ_ONLY] == MatterAccessLevel.VIEW
    assert ROLE_BASE_LEVEL[OrganizationRole.BILLING] is None
