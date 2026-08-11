from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
WEB = ROOT / "apps" / "web"


def test_app_shell_has_skip_link_and_main_landmark():
    text = (WEB / "components/app-shell.tsx").read_text(encoding="utf-8")
    assert 'href="#main-content"' in text
    assert '<main id="main-content"' in text


def test_sidebar_exposes_current_page_semantics():
    text = (WEB / "components/sidebar.tsx").read_text(encoding="utf-8")
    assert "aria-current" in text
    assert 'aria-label="Primary navigation"' in text


def test_large_document_reader_uses_bounded_page_window():
    text = (WEB / "components/document-reader.tsx").read_text(encoding="utf-8")
    assert "getDocumentPageWindow" in text
    assert "findInDocument" in text
    assert "document_page_window" in text


def test_motion_and_focus_accessibility_css_present():
    text = (WEB / "app/globals.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in text
    assert ":focus-visible" in text
    assert ".skip-link" in text
