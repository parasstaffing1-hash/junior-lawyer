"use client";

import { RowBuilderTool } from "@/components/tools/row-builder-tool";
import { generateEvidenceIndex } from "@/lib/tools";

const INDEX_TYPES = [
  { value: "evidence", label: "Evidence" },
  { value: "exhibit", label: "Exhibit" },
  { value: "annexure", label: "Annexure" },
  { value: "bundle", label: "Bundle" },
];

export function EvidenceIndexTool() {
  return (
    <RowBuilderTool
      toolKey="evidence-indexes"
      title="Evidence index"
      intro="Numbers and paginates a set of documents into a filing index."
      caveat="Labels and page ranges follow the numbering scheme you choose. Check them against the court's filing rules before the bundle goes in."
      rowLabel="Document"
      headerFields={[
        { key: "title", label: "Index title" },
        { key: "case_reference", label: "Case reference" },
        { key: "index_type", label: "Index type", options: INDEX_TYPES },
      ]}
      rowFields={[
        { key: "title", label: "Document title", wide: true },
        { key: "document_date", label: "Date", type: "date" },
        { key: "page_count", label: "Pages", type: "number" },
      ]}
      build={(header, rows) =>
        generateEvidenceIndex({
          title: header.title || "Evidence index",
          case_reference: header.case_reference || null,
          index_type: header.index_type || "evidence",
          pagination_mode: "auto",
          first_page: 1,
          documents: rows.map((row) => ({
            title: row.title || "Untitled document",
            document_date: row.document_date || null,
            page_count: row.page_count ? Number(row.page_count) : null,
          })),
        })
      }
      emptyHint="List the documents going into the bundle, then build the index."
      submitLabel="Build index"
    />
  );
}
