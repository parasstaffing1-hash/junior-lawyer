"use client";

import { TextAnalyzerTool } from "@/components/tools/text-analyzer-tool";
import { extractKeyDates } from "@/lib/tools";

export function KeyDatesTool() {
  return (
    <TextAnalyzerTool
      toolKey="key-dates-obligations"
      title="Key dates & obligations"
      intro="Pulls dated commitments out of contract or notice text — absolute dates, relative periods, and who owes what to whom."
      caveat="Pattern matching over the words supplied. It will miss obligations expressed unusually, and it does not decide whether a clause is enforceable."
      inputs={[{ key: "text", label: "Contract or notice text", placeholder: "The Seller shall deliver within 30 days of the Effective Date. Payment is due on 15 March 2026…", rows: 14 }]}
      run={(values) => extractKeyDates({ text: values.text })}
      emptyHint="Paste contract text, then extract."
      submitLabel="Extract dates & obligations"
    />
  );
}
