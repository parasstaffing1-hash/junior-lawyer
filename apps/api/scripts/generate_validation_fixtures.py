#!/usr/bin/env python3
"""Generate deterministic synthetic/de-identified validation fixtures.

No client data, network access or AI is used. The corpus is suitable for search/worker/load
validation; the optional PDF is useful for large-document reader/OCR pipeline checks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

EN = [
    "The petitioner states that payment was made under the services agreement.",
    "The respondent denies receipt of the statutory notice and disputes the invoice.",
    "The court directed the parties to file affidavits and preserve electronic records.",
    "The agreement contains confidentiality, termination, liability and arbitration clauses.",
    "The bank statement records a transaction connected with the disputed consideration.",
]
HI = [
    "याचिकाकर्ता का कहना है कि सेवा समझौते के अनुसार भुगतान किया गया था।",
    "प्रतिवादी वैधानिक नोटिस की प्राप्ति से इनकार करता है और चालान पर विवाद करता है।",
    "न्यायालय ने पक्षकारों को शपथपत्र दाखिल करने और इलेक्ट्रॉनिक रिकॉर्ड सुरक्षित रखने का निर्देश दिया।",
    "समझौते में गोपनीयता, समाप्ति, दायित्व और मध्यस्थता संबंधी धाराएँ हैं।",
    "बैंक विवरण में विवादित प्रतिफल से संबंधित लेनदेन दर्ज है।",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_jsonl(path: Path, *, documents: int, pages_per_document: int, seed: int) -> dict:
    rng = random.Random(seed)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for doc in range(1, documents + 1):
            lang = "hi" if doc % 3 == 0 else "en" if doc % 3 == 1 else "mixed"
            for page in range(1, pages_per_document + 1):
                en = EN[rng.randrange(len(EN))]
                hi = HI[rng.randrange(len(HI))]
                text = hi if lang == "hi" else en if lang == "en" else f"{en} {hi}"
                row = {
                    "document_key": f"SYN-{doc:07d}",
                    "page": page,
                    "language": lang,
                    "matter_key": f"MAT-{((doc - 1) % 5000) + 1:05d}",
                    "text": text,
                    "synthetic": True,
                }
                stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return {"path": str(path), "sha256": sha256(path), "documents": documents, "pages": documents * pages_per_document, "size_bytes": path.stat().st_size, "seed": seed}


def write_large_pdf(path: Path, *, pages: int, seed: int) -> dict:
    try:
        import fitz
    except Exception as exc:
        raise SystemExit(f"PyMuPDF is required for --pdf-pages: {exc}")
    rng = random.Random(seed)
    pdf = fitz.open()
    for number in range(1, pages + 1):
        page = pdf.new_page(width=595, height=842)
        en = EN[rng.randrange(len(EN))]
        hi = HI[rng.randrange(len(HI))]
        # Built-in PDF fonts may not shape all Devanagari glyphs consistently. The canonical Hindi
        # text is included in metadata/fixture JSON; the PDF remains a large-page navigation fixture.
        page.insert_text((48, 60), f"Synthetic legal validation page {number} / {pages}", fontsize=12)
        page.insert_textbox((48, 90, 545, 760), f"{en}\n\nHindi fixture reference: HI-{number:04d}\n\nSection 138 / dhara 138 / citation 2026 INSC {number}", fontsize=10)
    pdf.set_metadata({"title": "Synthetic Junior Lawyer large-document validation fixture", "subject": "No client data"})
    pdf.save(path, garbage=4, deflate=True)
    pdf.close()
    return {"path": str(path), "sha256": sha256(path), "pages": pages, "size_bytes": path.stat().st_size, "seed": seed, "synthetic": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(ROOT / "validation-output"))
    parser.add_argument("--documents", type=int, default=10000)
    parser.add_argument("--pages-per-document", type=int, default=1)
    parser.add_argument("--pdf-pages", type=int, default=0)
    parser.add_argument("--seed", type=int, default=28)
    args = parser.parse_args()
    if not 1 <= args.documents <= 1_000_000:
        parser.error("--documents must be between 1 and 1,000,000")
    if not 1 <= args.pages_per_document <= 20:
        parser.error("--pages-per-document must be between 1 and 20")
    if not 0 <= args.pdf_pages <= 5000:
        parser.error("--pdf-pages must be between 0 and 5000")
    output = Path(args.output_dir).resolve(); output.mkdir(parents=True, exist_ok=True)
    records = [write_jsonl(output / "synthetic-legal-corpus.jsonl", documents=args.documents, pages_per_document=args.pages_per_document, seed=args.seed)]
    if args.pdf_pages:
        records.append(write_large_pdf(output / f"synthetic-large-{args.pdf_pages}-pages.pdf", pages=args.pdf_pages, seed=args.seed))
    manifest = {"synthetic": True, "contains_client_data": False, "seed": args.seed, "artifacts": records}
    raw = json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    manifest["snapshot_hash"] = hashlib.sha256(raw).hexdigest()
    path = output / "validation-fixture-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
