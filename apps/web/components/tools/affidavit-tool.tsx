"use client";

import { TemplateGeneratorTool } from "@/components/tools/template-generator-tool";
import { generateAffidavit, getAffidavitTemplates } from "@/lib/tools";

export function AffidavitTool() {
  return (
    <TemplateGeneratorTool
      toolKey="affidavits"
      title="Affidavit"
      intro="Builds an affidavit from a reviewed template, numbering the sworn paragraphs in order."
      caveat="Templates here are demonstration drafts. Attestation, verification wording and court-specific formatting must follow the rules of the court where the affidavit is filed."
      dateField="generation_date"
      dateLabel="Affidavit date"
      valuesKey="fields"
      withStatements
      loadTemplates={getAffidavitTemplates}
      generate={generateAffidavit}
    />
  );
}
