"use client";

import { UploadTool } from "@/components/tools/upload-tool";
import { analyzeOcr, getOcrCapabilities, processOcr } from "@/lib/tools";

export function OcrTool() {
  return (
    <UploadTool
      toolKey="legal-ocr"
      title="OCR"
      intro="Adds a searchable text layer to a scanned PDF. Runs locally through Tesseract — the file is not sent to any external service."
      caveat="Character recognition is probabilistic. Quality depends on the scan, and handwriting is not reliably supported. Always keep the original alongside the OCR'd copy."
      accept="application/pdf"
      capabilities={getOcrCapabilities}
      actions={[
        { key: "analyze", label: "Analyse pages", run: (file, options) => analyzeOcr(file, options) },
        { key: "process", label: "Make searchable", run: (file, options) => processOcr(file, options), download: true },
      ]}
    />
  );
}
