"use client";

import { TemplateGeneratorTool } from "@/components/tools/template-generator-tool";
import { generateLegalNotice, getLegalNoticeTemplates } from "@/lib/tools";

export function LegalNoticeTool() {
  return (
    <TemplateGeneratorTool
      toolKey="legal-notices"
      title="Legal notice"
      intro="Fills a reviewed notice template with the party, claim and demand details you supply."
      caveat="The templates shipped with this build are demonstration drafts and jurisdiction-neutral. Replace them with firm-approved templates before sending anything to a recipient."
      dateField="generation_date"
      dateLabel="Notice date"
      valuesKey="fields"
      loadTemplates={getLegalNoticeTemplates}
      generate={generateLegalNotice}
    />
  );
}
