"use client";

import { TemplateGeneratorTool } from "@/components/tools/template-generator-tool";
import { generateIntake, getIntakeTemplates } from "@/lib/tools";

export function IntakeTool() {
  return (
    <TemplateGeneratorTool
      toolKey="client-intakes"
      title="Client intake"
      intro="Turns a completed intake questionnaire into a structured matter record, including the conflict-check terms drawn from the party fields."
      caveat="Producing an intake record is not a conflict check. The conflict terms it surfaces still have to be run against the firm's own client and matter history."
      dateField="intake_date"
      dateLabel="Intake date"
      valuesKey="values"
      loadTemplates={getIntakeTemplates}
      generate={generateIntake}
    />
  );
}
