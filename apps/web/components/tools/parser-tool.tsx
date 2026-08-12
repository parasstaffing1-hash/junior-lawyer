"use client";

import { UploadTool } from "@/components/tools/upload-tool";
import { parseLegalDocument } from "@/lib/tools";

export function ParserTool() {
  return (
    <UploadTool
      toolKey="legal-documents"
      title="Document parser"
      intro="Extracts text and structure from a PDF or DOCX — headings, paragraphs and numbering — without sending the file anywhere."
      caveat="Extraction reflects how the document was produced. A scanned PDF has no text layer to extract; run it through OCR first."
      accept="application/pdf,.docx"
      actions={[{ key: "parse", label: "Parse document", run: (file, options) => parseLegalDocument(file, options) }]}
    />
  );
}
