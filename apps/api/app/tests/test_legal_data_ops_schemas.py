from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.integrations import OfficialLegalImportRequest
from app.schemas.legal_data import LegalDataManifest, LegalDataManifestItem
from app.schemas.research import CorpusSearchRequest


def test_manifest_limits_kind_and_hash_shape():
    item = LegalDataManifestItem(kind="statute", source_url="https://indiacode.nic.in/x", payload={"external_id": "x"})
    manifest = LegalDataManifest(items=[item])
    assert manifest.items[0].kind == "statute"
    with pytest.raises(ValidationError):
        LegalDataManifestItem(kind="scrape", source_url="https://example.com", payload={})


def test_official_integration_can_target_feed():
    feed_id = uuid4()
    row = OfficialLegalImportRequest(kind="judgment", source_url="https://judgments.ecourts.gov.in/x", payload={"external_id": "j1"}, feed_id=feed_id)
    assert row.feed_id == feed_id


def test_research_supports_as_of_date():
    request = CorpusSearchRequest(query="धारा 138", as_of_date="2025-01-01")
    assert request.as_of_date.isoformat() == "2025-01-01"
