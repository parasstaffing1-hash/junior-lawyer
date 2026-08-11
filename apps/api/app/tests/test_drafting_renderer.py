from uuid import uuid4
from zipfile import ZipFile

from app.core.config import settings
from app.models.drafting import LegalDraft, LegalDraftLanguage, LegalDraftSection, LegalDraftStatus, LegalDraftType
from app.services.drafting.renderer import generate_docx, resolve_draft_storage_key


def test_bilingual_docx_contains_hindi_and_review_warning(tmp_path):
    original = settings.storage_root
    settings.storage_root = tmp_path / "documents"
    try:
        draft = LegalDraft(
            id=uuid4(),
            matter_id=uuid4(),
            title="Petition Test",
            draft_type=LegalDraftType.PETITION,
            language=LegalDraftLanguage.BILINGUAL,
            status=LegalDraftStatus.DRAFT,
            questionnaire_json={},
            health_score=80,
            metadata_json={},
        )
        section = LegalDraftSection(
            id=uuid4(),
            draft_id=draft.id,
            section_key="prayer",
            title_en="Prayer",
            title_hi="प्रार्थना",
            body_en="The petitioner seeks appropriate relief.",
            body_hi="याचिकाकर्ता उचित राहत की प्रार्थना करता है।",
            position=1,
            reviewed=False,
            locked=False,
            metadata_json={},
        )
        draft.sections = [section]
        filename, storage_key, digest = generate_docx(draft, version_number=1)
        path = resolve_draft_storage_key(storage_key)
        assert filename.endswith("-v1.docx")
        assert len(digest) == 64
        assert path.exists()
        with ZipFile(path) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")
        assert "DRAFT — LAWYER REVIEW REQUIRED" in xml
        assert "प्रार्थना" in xml
        assert "याचिकाकर्ता" in xml
    finally:
        settings.storage_root = original
