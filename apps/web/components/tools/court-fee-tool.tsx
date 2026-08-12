"use client";

import { RulePackCalculator } from "@/components/tools/rule-pack-calculator";
import { calculateCourtFee, getCourtFeeRulePacks } from "@/lib/tools";

export function CourtFeeTool() {
  return (
    <RulePackCalculator
      toolKey="court-fees"
      title="Court fee"
      intro="Applies an installed court-fee rule pack to a claim value as at the filing date."
      caveat="The number is only as good as the rule pack. The packs shipped with this build are marked DEMO ONLY and are not official Indian fee schedules — install a lawyer-verified pack before relying on any figure."
      dateLabel="Filing date"
      dateField="filing_date"
      valueFields={[{ key: "claim_value", label: "Claim value (₹)", hint: "500000" }]}
      loadPacks={getCourtFeeRulePacks}
      calculate={calculateCourtFee}
    />
  );
}
