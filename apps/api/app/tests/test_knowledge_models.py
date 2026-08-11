from app import models  # noqa: F401
from app.db.base import Base
from app.models.knowledge import (
    KnowledgeAssetKind, KnowledgeAssetStatus, KnowledgeLanguage, KnowledgeSourceType,
    MatterPlaybookStatus, ResearchCollectionStatus, SanitizationStatus,
)


def test_batch16_schema_tables_present():
    expected = {
        "knowledge_collections", "knowledge_assets", "knowledge_asset_sources", "knowledge_asset_versions",
        "knowledge_tags", "knowledge_asset_tags", "knowledge_annotations", "matter_playbooks",
        "matter_playbook_items", "research_collections", "research_collection_items",
    }
    assert expected <= set(Base.metadata.tables)


def test_batch16_enum_values_are_stable():
    assert KnowledgeAssetKind.CONTRACT_CLAUSE.value == "contract_clause"
    assert KnowledgeAssetStatus.APPROVED.value == "approved"
    assert KnowledgeLanguage.BILINGUAL.value == "bilingual"
    assert SanitizationStatus.REVIEWED.value == "reviewed"
    assert KnowledgeSourceType.DRAFT_SECTION.value == "draft_section"
    assert MatterPlaybookStatus.APPROVED.value == "approved"
    assert ResearchCollectionStatus.APPROVED.value == "approved"
