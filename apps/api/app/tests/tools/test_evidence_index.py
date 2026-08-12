from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tools.evidence_index.models import EvidenceIndexRequest, IndexDocument
from app.tools.evidence_index.service import EvidenceIndexError, generate_evidence_index

client = TestClient(app)


def test_auto_pagination_and_default_evidence_labels() -> None:
    result = generate_evidence_index(
        EvidenceIndexRequest(
            documents=[
                IndexDocument(title="Agreement", page_count=3),
                IndexDocument(title="Invoice", page_count=2),
            ]
        )
    )
    assert [doc.label for doc in result.documents] == ["E-1", "E-2"]
    assert [doc.page_range for doc in result.documents] == ["1-3", "4-5"]
    assert result.summary.total_pages == 5
    assert result.summary.first_page == 1
    assert result.summary.last_page == 5


def test_custom_prefix_numeric_padding_and_first_page() -> None:
    result = generate_evidence_index(
        EvidenceIndexRequest(
            index_type="exhibit",
            label_prefix="PX",
            numbering_start=7,
            zero_pad=3,
            first_page=10,
            documents=[IndexDocument(title="Photo", page_count=1)],
        )
    )
    assert result.documents[0].label == "PX-007"
    assert result.documents[0].page_range == "10"


def test_alphabetic_numbering_crosses_z() -> None:
    documents = [IndexDocument(title=f"Document {i}", page_count=1) for i in range(27)]
    result = generate_evidence_index(
        EvidenceIndexRequest(
            index_type="annexure",
            numbering_style="alphabetic",
            documents=documents,
        )
    )
    assert result.documents[0].label == "ANN-A"
    assert result.documents[25].label == "ANN-Z"
    assert result.documents[26].label == "ANN-AA"


def test_existing_labels_are_preserved_and_duplicates_rejected() -> None:
    with pytest.raises(EvidenceIndexError, match="duplicate label"):
        generate_evidence_index(
            EvidenceIndexRequest(
                documents=[
                    IndexDocument(title="A", label="EX-A", page_count=1),
                    IndexDocument(title="B", label="ex-a", page_count=1),
                ]
            )
        )


def test_provided_pages_detect_gaps_and_calculate_counts() -> None:
    result = generate_evidence_index(
        EvidenceIndexRequest(
            pagination_mode="provided",
            documents=[
                IndexDocument(title="A", start_page=1, end_page=2),
                IndexDocument(title="B", start_page=5, end_page=7),
            ],
        )
    )
    assert result.summary.page_gaps == ["3-4"]
    assert result.documents[1].page_count == 3
    assert result.summary.total_pages == 5
    assert any("page gaps" in warning for warning in result.warnings)


def test_provided_page_overlap_is_rejected() -> None:
    with pytest.raises(EvidenceIndexError, match="overlap"):
        generate_evidence_index(
            EvidenceIndexRequest(
                pagination_mode="provided",
                documents=[
                    IndexDocument(title="A", start_page=1, end_page=4),
                    IndexDocument(title="B", start_page=4, end_page=6),
                ],
            )
        )


def test_possible_duplicates_missing_metadata_and_categories_are_summarized() -> None:
    result = generate_evidence_index(
        EvidenceIndexRequest(
            pagination_mode="none",
            documents=[
                IndexDocument(title="Invoice", document_date=date(2026, 7, 1), category="Financial"),
                IndexDocument(title="invoice", document_date=date(2026, 7, 1), category="Financial", confidential=True),
                IndexDocument(title="Email", category="Correspondence", source_file="email.eml"),
            ],
        )
    )
    assert result.summary.category_counts == {"Correspondence": 1, "Financial": 2}
    assert result.summary.confidential_count == 1
    assert result.summary.total_pages is None
    assert any("Possible duplicate" in warning for warning in result.warnings)
    assert any("no document date" in warning for warning in result.warnings)
    assert any("no source file" in warning for warning in result.warnings)


def test_markdown_and_csv_are_export_ready() -> None:
    result = generate_evidence_index(
        EvidenceIndexRequest(
            case_reference="CASE-9",
            title="Exhibit Index",
            index_type="exhibit",
            documents=[
                IndexDocument(
                    title="Agreement, signed",
                    document_date=date(2026, 7, 1),
                    category="Contract",
                    source_file="agreement.pdf",
                    page_count=2,
                )
            ],
        )
    )
    assert "# Exhibit Index" in result.markdown
    assert "EX-1" in result.markdown
    assert result.csv.startswith("sequence,case_reference,label")
    assert '"Agreement, signed"' in result.csv
    assert "CASE-9" in result.csv


def test_api_validation_requires_page_count_in_auto_mode() -> None:
    response = client.post(
        "/api/v1/tools/evidence-indexes/generate",
        json={"documents": [{"title": "Missing pages"}]},
    )
    assert response.status_code == 422


def test_api_generates_annexure_index() -> None:
    response = client.post(
        "/api/v1/tools/evidence-indexes/generate",
        json={
            "case_reference": "ABC/2026",
            "index_type": "annexure",
            "numbering_style": "alphabetic",
            "documents": [
                {
                    "title": "Services Agreement",
                    "document_date": "2026-07-01",
                    "source_file": "agreement.pdf",
                    "page_count": 4,
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["documents"][0]["label"] == "ANN-A"
    assert payload["documents"][0]["page_range"] == "1-4"
    assert payload["summary"]["document_count"] == 1
