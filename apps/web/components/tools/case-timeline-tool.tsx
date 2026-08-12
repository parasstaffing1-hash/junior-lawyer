"use client";

import { RowBuilderTool } from "@/components/tools/row-builder-tool";
import { generateCaseTimeline } from "@/lib/tools";

const EVENT_TYPES = ["fact", "communication", "filing", "hearing", "order", "payment", "contract", "notice", "evidence", "other"]
  .map((value) => ({ value, label: value.replace(/^./, (c) => c.toUpperCase()) }));

export function CaseTimelineTool() {
  return (
    <RowBuilderTool
      toolKey="case-timelines"
      title="Case timeline"
      intro="Orders dated events into a chronology, showing the gap between each step."
      caveat="A chronology of what you enter. It does not verify that an event happened or that a date is correct."
      rowLabel="Event"
      headerFields={[
        { key: "title", label: "Timeline title" },
        { key: "case_reference", label: "Case reference" },
      ]}
      rowFields={[
        { key: "event_date", label: "Date", type: "date" },
        { key: "event_type", label: "Type", options: EVENT_TYPES },
        { key: "title", label: "What happened", wide: true },
      ]}
      build={(header, rows) =>
        generateCaseTimeline({
          title: header.title || "Case timeline",
          case_reference: header.case_reference || null,
          include_day_gaps: true,
          events: rows.map((row) => ({
            event_date: row.event_date || null,
            event_type: row.event_type || "fact",
            title: row.title || "Untitled event",
          })),
        })
      }
      emptyHint="Add a few dated events, then build the chronology."
      submitLabel="Build timeline"
    />
  );
}
