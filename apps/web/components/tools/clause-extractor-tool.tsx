"use client";

import { TextAnalyzerTool } from "@/components/tools/text-analyzer-tool";
import { extractContractClauses } from "@/lib/tools";

export function ClauseExtractorTool() {
  return (
    <TextAnalyzerTool
      toolKey="contract-clauses"
      title="Clause extractor"
      intro="Splits a contract into clauses and classifies each one by type."
      caveat="Classification is rule-based on clause wording. Treat the labels as a starting index for review, not as a legal characterisation."
      inputs={[{ key: "text", label: "Contract text", placeholder: "Paste the full contract text…", rows: 14 }]}
      run={(values) => extractContractClauses({ text: values.text })}
      emptyHint="Paste a contract, then extract."
      submitLabel="Extract clauses"
    />
  );
}
