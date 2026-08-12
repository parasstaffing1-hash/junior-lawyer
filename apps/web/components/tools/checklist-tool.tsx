"use client";

import { FormEvent, useEffect, useState } from "react";
import { DataView, ResultPanel, ToolFrame, splitDisclaimer } from "@/components/tools/tool-frame";
import { evaluateChecklist, getChecklistTemplates, type ToolTemplate } from "@/lib/tools";

const STATUSES = [
  { value: "pending", label: "Pending" },
  { value: "present", label: "Present" },
  { value: "completed", label: "Completed" },
  { value: "missing", label: "Missing" },
  { value: "not_applicable", label: "Not applicable" },
];

interface EvaluatedItem {
  key: string;
  title: string;
  category?: string;
  requirement?: string;
  status?: string;
  applicable?: boolean;
  satisfied?: boolean;
}

/**
 * The templates endpoint returns context fields and an item count, but not the
 * items: which items apply depends on the context answers, so the server
 * decides. The flow is therefore evaluate-first — answer the context, get the
 * applicable items back, then set each status and re-evaluate.
 */
export function ChecklistTool() {
  const [templates, setTemplates] = useState<ToolTemplate[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [context, setContext] = useState<Record<string, string>>({});
  const [statuses, setStatuses] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getChecklistTemplates()
      .then((rows) => {
        setTemplates(rows);
        if (rows.length) setTemplateId(rows[0].id);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load templates"));
  }, []);

  const template = templates.find((row) => row.id === templateId);
  const contextFields = template?.context_fields ?? [];

  // Defaulting to the first allowed value keeps the required-context call valid
  // without making the lawyer guess which answers the template expects.
  useEffect(() => {
    if (!template) return;
    const defaults: Record<string, string> = {};
    for (const field of template.context_fields ?? []) {
      const allowed = field.allowed_values as string[] | undefined;
      if (allowed?.length) defaults[field.key] = allowed[0];
    }
    setContext(defaults);
    setStatuses({});
    setResult(null);
  }, [template]);

  const items = (result?.items as EvaluatedItem[] | undefined) ?? [];

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(
        await evaluateChecklist({
          template_id: templateId,
          assessment_date: date,
          context,
          items: items
            .filter((item) => statuses[item.key])
            .map((item) => ({ key: item.key, status: statuses[item.key] })),
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Evaluation failed");
    } finally {
      setBusy(false);
    }
  }

  const { body, disclaimer } = splitDisclaimer(result);
  const summary = result?.summary as Record<string, unknown> | undefined;

  return (
    <ToolFrame
      toolKey="legal-checklists"
      title="Legal checklist"
      intro="Answer the matter context, then mark off each item the template requires. The server decides which items apply from your answers."
      caveat="The checklist reflects the template installed, not the requirements of any particular court. The template in this build is a demonstration draft."
    >
      <div className="tool-layout tool-layout-wide">
        <form className="card tool-form" onSubmit={submit}>
          <div className="card-header"><div className="card-title">Assessment</div></div>

          <label className="tool-field">
            <span>Template</span>
            <select value={templateId} onChange={(e) => setTemplateId(e.target.value)} required>
              {templates.length === 0 ? <option value="">No templates installed</option> : null}
              {templates.map((row) => (
                <option value={row.id} key={row.id}>{row.title}</option>
              ))}
            </select>
          </label>

          {template?.source_note ? <p className="tool-provenance">{String(template.source_note)}</p> : null}

          <label className="tool-field">
            <span>Assessment date</span>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          </label>

          {contextFields.map((field) => {
            const allowed = field.allowed_values as string[] | undefined;
            return (
              <label className="tool-field" key={field.key}>
                <span>{field.label ?? field.key}</span>
                {allowed?.length ? (
                  <select
                    value={context[field.key] ?? allowed[0]}
                    onChange={(e) => setContext((c) => ({ ...c, [field.key]: e.target.value }))}
                  >
                    {allowed.map((value) => (
                      <option value={value} key={value}>{value}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    required={Boolean(field.required)}
                    value={context[field.key] ?? ""}
                    onChange={(e) => setContext((c) => ({ ...c, [field.key]: e.target.value }))}
                  />
                )}
              </label>
            );
          })}

          {items.length ? (
            <fieldset className="tool-field">
              <legend>Items ({items.length})</legend>
              {items.map((item) => (
                <div className="tool-check-row" key={item.key}>
                  <div className="tool-check-label">
                    <strong>{item.title}</strong>
                    <span>
                      {[item.category, item.requirement, item.applicable === false ? "not applicable" : null]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </div>
                  <select
                    aria-label={item.title}
                    value={statuses[item.key] ?? item.status ?? "pending"}
                    onChange={(e) => setStatuses((c) => ({ ...c, [item.key]: e.target.value }))}
                  >
                    {STATUSES.map((status) => (
                      <option value={status.value} key={status.value}>{status.label}</option>
                    ))}
                  </select>
                </div>
              ))}
            </fieldset>
          ) : null}

          <button className="button primary" disabled={busy || !templateId}>
            {busy ? "Evaluating…" : items.length ? "Re-evaluate" : "Evaluate"}
          </button>
        </form>

        <ResultPanel
          error={error}
          hasResult={Boolean(result)}
          emptyHint="Answer the matter context, then evaluate to see which items apply."
        >
          {summary ? (
            <>
              <div className="tool-headline">
                {String(summary.required_satisfied ?? 0)}/{String(summary.required_items ?? 0)}
              </div>
              <p className="tool-status">required items satisfied</p>
            </>
          ) : null}
          <DataView value={body} />
          {disclaimer ? <p className="tool-disclaimer">{disclaimer}</p> : null}
        </ResultPanel>
      </div>
    </ToolFrame>
  );
}
