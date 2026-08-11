from app.services.crm.conflicts import onboarding_readiness


def test_onboarding_ready_only_when_all_gates_complete():
    status, missing = onboarding_readiness(
        conflict_cleared=True, identity_complete=True, address_complete=True, engagement_complete=True,
    )
    assert status == "ready"
    assert missing == []


def test_onboarding_lists_missing_gates():
    status, missing = onboarding_readiness(
        conflict_cleared=False, identity_complete=True, address_complete=False, engagement_complete=False,
    )
    assert status == "in_progress"
    assert missing == ["conflict check", "address", "engagement"]
