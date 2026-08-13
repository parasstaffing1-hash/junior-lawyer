"""The boot-time AI configuration line.

Misconfigured AI settings otherwise fail silently — the router blocks every run,
which is indistinguishable from a deliberate product decision.
"""

import logging

from app.core.config import Settings
from app.main import _log_ai_configuration


def configure(monkeypatch, **overrides):
    replacement = Settings(_env_file=None, **overrides)
    monkeypatch.setattr("app.main.settings", replacement)
    monkeypatch.setattr("app.services.ai.providers.Settings", Settings, raising=False)
    return replacement


def test_disabled_ai_says_so_without_warning(monkeypatch, caplog):
    configure(monkeypatch, ai_enabled=False)
    with caplog.at_level(logging.INFO, logger="junior_lawyer.ai"):
        _log_ai_configuration()
    record = caplog.records[-1]
    assert record.message == "ai_disabled"
    assert record.levelno == logging.INFO


def test_enabled_but_unconfigured_warns_and_names_the_missing_settings(monkeypatch, caplog):
    configure(
        monkeypatch,
        ai_enabled=True,
        ai_remote_enabled=True,
        ai_remote_base_url=None,
        ai_remote_model=None,
        ai_remote_api_key=None,
    )
    with caplog.at_level(logging.INFO, logger="junior_lawyer.ai"):
        _log_ai_configuration()
    record = caplog.records[-1]
    assert record.message == "ai_enabled_but_no_provider"
    assert record.levelno == logging.WARNING
    assert set(record.missing_settings) == {
        "AI_REMOTE_BASE_URL",
        "AI_REMOTE_MODEL",
        "AI_REMOTE_API_KEY",
    }


def test_a_working_configuration_reports_the_model_and_spare_count(monkeypatch, caplog):
    configure(
        monkeypatch,
        ai_enabled=True,
        ai_remote_enabled=True,
        ai_remote_base_url="https://example.test/v1",
        ai_remote_model="test-model",
        ai_remote_api_key="primary",
        ai_remote_api_key_fallbacks="spare-a,spare-b",
    )
    with caplog.at_level(logging.INFO, logger="junior_lawyer.ai"):
        _log_ai_configuration()
    record = caplog.records[-1]
    assert record.message == "ai_ready"
    assert record.providers == ["remote"]
    assert record.remote_model == "test-model"
    assert record.spare_credentials == 2


def test_the_log_line_never_carries_key_material(monkeypatch, caplog):
    secret = "super-secret-key-value"
    configure(
        monkeypatch,
        ai_enabled=True,
        ai_remote_enabled=True,
        ai_remote_base_url="https://example.test/v1",
        ai_remote_model="test-model",
        ai_remote_api_key=secret,
        ai_remote_api_key_fallbacks=f"{secret}-2",
    )
    with caplog.at_level(logging.INFO, logger="junior_lawyer.ai"):
        _log_ai_configuration()
    assert secret not in str(caplog.records[-1].__dict__)
