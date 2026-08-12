"use client";

import { TextAnalyzerTool } from "@/components/tools/text-analyzer-tool";
import { extractCitations } from "@/lib/tools";

export function CitationsTool() {
  return (
    <TextAnalyzerTool
      toolKey="legal-citations"
      title="Citation extractor"
      intro="Finds Indian and neutral citations in a judgment, pleading or note, and normalises each one into year, volume, page and court."
      caveat="Recognises SCC, AIR, SCC OnLine, Indian neutral and UK neutral formats. It reports what the text contains; it does not verify that a citation is real or still good law."
      inputs={[{ key: "text", label: "Text", placeholder: "Paste a judgment, pleading or research note…", rows: 14 }]}
      run={(values) => extractCitations({ text: values.text, deduplicate: true })}
      emptyHint="Paste text containing citations, then extract."
      submitLabel="Extract citations"
    />
  );
}
