from app.services.security.audit import ZERO_HASH, compute_audit_hash


def test_audit_hash_is_deterministic_and_tamper_sensitive():
    payload = {"sequence": 1, "action": "matter.access.upsert", "metadata_json": {"role": "lawyer"}}
    digest, mode = compute_audit_hash(ZERO_HASH, payload)
    again, _ = compute_audit_hash(ZERO_HASH, payload)
    changed, _ = compute_audit_hash(ZERO_HASH, {**payload, "action": "matter.delete"})
    assert mode == "sha256-chain-v1"
    assert digest == again
    assert digest != changed


def test_audit_hash_supports_hmac_mode():
    payload = {"sequence": 7, "action": "security.policy.update"}
    digest, mode = compute_audit_hash(ZERO_HASH, payload, key="test-only-secret")
    other, _ = compute_audit_hash(ZERO_HASH, payload, key="different-secret")
    assert mode == "hmac-sha256-v1"
    assert digest != other
