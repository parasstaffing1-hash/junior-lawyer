"use client";

import { TextAnalyzerTool } from "@/components/tools/text-analyzer-tool";
import { compareContracts } from "@/lib/tools";

export function ContractCompareTool() {
  return (
    <TextAnalyzerTool
      toolKey="contract-compare"
      title="Contract compare"
      intro="Clause-level comparison between two versions of an agreement, showing what was added, removed or reworded."
      caveat="A textual diff aligned at clause level. It reports what changed, not whether a change is material or acceptable."
      inputs={[
        { key: "original_text", label: "Original version", placeholder: "Paste the earlier version…", rows: 12 },
        { key: "revised_text", label: "Revised version", placeholder: "Paste the later version…", rows: 12 },
      ]}
      run={(values) => compareContracts({ original_text: values.original_text, revised_text: values.revised_text })}
      emptyHint="Paste both versions, then compare."
      submitLabel="Compare versions"
    />
  );
}
