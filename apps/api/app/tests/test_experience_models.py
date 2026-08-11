from app.models.experience import UIContrast, UIDensity, UIFontScale, UILanguage, UserExperiencePreference, UserOnboardingProgress
from app.services.experience.service import ONBOARDING_STEPS, normalize_steps


def test_experience_preference_defaults_are_accessible_and_calm():
    row = UserExperiencePreference(organization_id=None, membership_id=None)  # construction-only unit test
    assert row.ui_language is None or row.ui_language == UILanguage.ENGLISH
    assert UIContrast.HIGH.value == "high"
    assert UIDensity.COMPACT.value == "compact"
    assert UIFontScale.EXTRA_LARGE.value == "extra_large"


def test_onboarding_steps_are_bounded_and_deduplicated():
    assert normalize_steps(["search", "SEARCH", "keyboard", "unknown"]) == ["search", "keyboard"]


def test_onboarding_step_catalog_is_stable():
    assert ONBOARDING_STEPS == {"profile", "first_matter", "first_document", "search", "keyboard"}


def test_onboarding_model_uses_list_payload():
    row = UserOnboardingProgress(organization_id=None, membership_id=None, completed_steps_json=["search"])
    assert row.completed_steps_json == ["search"]
