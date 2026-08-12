"use client";

import { RulePackCalculator } from "@/components/tools/rule-pack-calculator";
import { calculateStampDuty, getStampDutyRulePacks } from "@/lib/tools";

export function StampDutyTool() {
  return (
    <RulePackCalculator
      toolKey="stamp-duty"
      title="Stamp duty"
      intro="Applies an installed stamp-duty rule pack to an instrument, using the higher of consideration and market value where the pack requires it."
      caveat="Stamp duty is state-specific and changes often. The packs shipped with this build are marked DEMO ONLY — install a verified state pack before relying on any figure."
      dateLabel="Instrument date"
      dateField="instrument_date"
      valueFields={[
        { key: "consideration_value", label: "Consideration value (₹)", hint: "2500000" },
        { key: "market_value", label: "Market value (₹)", hint: "optional" },
        { key: "assessable_value", label: "Assessable value (₹)", hint: "optional override" },
      ]}
      loadPacks={getStampDutyRulePacks}
      calculate={calculateStampDuty}
    />
  );
}
