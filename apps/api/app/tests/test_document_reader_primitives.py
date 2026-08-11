from app.schemas.document import DocumentPageMatchRead


def test_document_match_schema_accepts_page_snippet():
    item = DocumentPageMatchRead(page_number=12, snippet="...धारा 138...", match_count=2)
    assert item.page_number == 12
    assert item.match_count == 2
