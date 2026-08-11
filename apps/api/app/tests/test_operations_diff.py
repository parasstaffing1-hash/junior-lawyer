from datetime import date

from app.models.operations import ChangeSeverity, CourtChangeType
from app.services.operations.diff import detect_snapshot_changes, stable_snapshot_hash
from app.services.operations.providers import source_capabilities


def test_snapshot_hash_is_stable_and_ignores_source_payload():
    a = {"case_status": "Pending", "stage": "Arguments", "order_count": 2, "source_payload_json": {"x": 1}}
    b = {"order_count": 2, "stage": "Arguments", "case_status": "Pending", "source_payload_json": {"x": 999}}
    assert stable_snapshot_hash(a) == stable_snapshot_hash(b)


def test_new_order_is_high_severity():
    changes = detect_snapshot_changes(
        {"order_count": 1, "latest_order_date": date(2026, 8, 1)},
        {"order_count": 2, "latest_order_date": date(2026, 8, 8)},
    )
    assert any(x.change_type == CourtChangeType.NEW_ORDER and x.severity == ChangeSeverity.HIGH for x in changes)


def test_hearing_date_change_detected():
    changes = detect_snapshot_changes(
        {"next_hearing_date": date(2026, 8, 10)},
        {"next_hearing_date": date(2026, 8, 17)},
    )
    item = next(x for x in changes if x.change_type == CourtChangeType.HEARING_DATE_CHANGED)
    assert item.old_value == "2026-08-10"
    assert item.new_value == "2026-08-17"


def test_status_stage_and_judge_changes_are_independent():
    changes = detect_snapshot_changes(
        {"case_status": "Pending", "stage": "Evidence", "judge_or_bench": "Bench A"},
        {"case_status": "Disposed", "stage": "Final", "judge_or_bench": "Bench B"},
    )
    kinds = {x.change_type for x in changes}
    assert CourtChangeType.CASE_STATUS_CHANGED in kinds
    assert CourtChangeType.STAGE_CHANGED in kinds
    assert CourtChangeType.JUDGE_CHANGED in kinds


def test_first_snapshot_does_not_create_fake_changes():
    assert detect_snapshot_changes(None, {"case_status": "Pending", "order_count": 1}) == []


def test_ecourts_source_does_not_claim_automatic_captcha_bypass():
    ecourts = next(item for item in source_capabilities() if item.source_kind.value == "ecourts_manual")
    assert ecourts.automatic_fetch is False
    assert ecourts.requires_user_or_approved_connector is True
