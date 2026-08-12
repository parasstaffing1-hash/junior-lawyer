"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { DataView, ResultPanel, ToolFrame, splitDisclaimer } from "@/components/tools/tool-frame";
import type { TemplateField, ToolTemplate } from "@/lib/tools";

function fieldLabel(field: TemplateField) {
  return field.label ?? field.title ?? field.key;
}

function fieldKind(field: TemplateField) {
  return String(field.field_type ?? field.kind ?? "text");
}

/**
 * Notice, affidavit and intake all work the same way: the server owns the
 * template, including its field definitions, so the form is rendered from
 * whatever the template declares rather than hard-coded per document type.
 */
export function TemplateGeneratorTool({
  toolKey,
  title,
  intro,
  caveat,
  dateField,
  dateLabel,
  valuesKey,
  withStatements = false,
  loadTemplates,
  generate,
}: {
  toolKey: string;
  title: string;
  intro: string;
  caveat: string;
  dateField: string;
  dateLabel: string;
  valuesKey: string;
  withStatements?: boolean;
  loadTemplates: () => Promise<ToolTemplate[]>;
  generate: (payload: Record<string, unknown>) => Promise<Record<string, unknown>>;
}) {
  const [templates, setTemplates] = useState<ToolTemplate[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [values, setValues] = useState<Record<string, string>>({});
  const [statements, setStatements] = useState<string[]>([""]);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    loadTemplates()
      .then((rows) => {
        setTemplates(rows);
        if (rows.length) setTemplateId(rows[0].id);
      })
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Could not load templates"));
  }, [loadTemplates]);

  const template = templates.find((row) => row.id === templateId);
  const fields = useMemo(() => template?.fields ?? [], [template]);

  // Switching template invalidates values keyed to the previous one.
  useEffect(() => setValues({}), [templateId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload: Record<string, unknown> = {
        template_id: templateId,
        [dateField]: date,
        [valuesKey]: values,
      };
      if (withStatements) {
        payload.statements = statements
          .map((text) => text.trim())
          .filter(Boolean)
          .map((text) => ({ text }));
      }
      setResult(await generate(payload));
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  }

  const { body, disclaimer } = splitDisclaimer(result);

  return (
    <ToolFrame toolKey={toolKey} title={title} intro={intro} caveat={caveat}>
      <div className="tool-layout tool-layout-wide">
        <form className="card tool-form" onSubmit={submit}>
          <div className="card-header">
            <div className="card-title">Details</div>
          </div>

          {loadError ? (
            <div className="notice-panel" style={{ marginBottom: 12 }}><span>{loadError}</span></div>
          ) : null}

          <label className="tool-field">
            <span>Template</span>
            <select value={templateId} onChange={(e) => setTemplateId(e.target.value)} required>
              {templates.length === 0 ? <option value="">No templates installed</option> : null}
              {templates.map((row) => (
                <option value={row.id} key={row.id}>
                  {row.title}{row.jurisdiction ? ` — ${row.jurisdiction}` : ""}
                </option>
              ))}
            </select>
          </label>

          {template?.source_note ? <p className="tool-provenance">{String(template.source_note)}</p> : null}

          <label className="tool-field">
            <span>{dateLabel}</span>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          </label>

          {fields.map((field) => {
            const kind = fieldKind(field);
            const key = field.key;
            const common = {
              value: values[key] ?? "",
              onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
                setValues((current) => ({ ...current, [key]: e.target.value })),
              required: Boolean(field.required),
              maxLength: typeof field.max_length === "number" ? field.max_length : undefined,
            };
            return (
              <label className="tool-field" key={key}>
                <span>
                  {fieldLabel(field)}
                  {field.required ? "" : " (optional)"}
                </span>
                {kind === "multiline" || kind === "textarea" ? (
                  <textarea rows={3} {...common} />
                ) : kind === "date" ? (
                  <input type="date" {...common} />
                ) : kind === "number" || kind === "amount" ? (
                  <input type="number" step="0.01" {...common} />
                ) : (
                  <input type="text" {...common} />
                )}
              </label>
            );
          })}

          {withStatements ? (
            <fieldset className="tool-field">
              <legend>Sworn statements</legend>
              {statements.map((text, index) => (
                <div className="tool-row-item" key={index}>
                  <textarea
                    rows={2}
                    placeholder={`Paragraph ${index + 1}`}
                    value={text}
                    onChange={(e) =>
                      setStatements((current) => current.map((row, i) => (i === index ? e.target.value : row)))
                    }
                  />
                  {statements.length > 1 ? (
                    <button
                      type="button"
                      className="button secondary small"
                      onClick={() => setStatements((current) => current.filter((_, i) => i !== index))}
                    >
                      Remove
                    </button>
                  ) : null}
                </div>
              ))}
              <button type="button" className="button secondary small" onClick={() => setStatements((c) => [...c, ""])}>
                Add paragraph
              </button>
            </fieldset>
          ) : null}

          <button className="button primary" disabled={busy || !templateId}>
            {busy ? "Generating…" : "Generate"}
          </button>
        </form>

        <ResultPanel error={error} hasResult={Boolean(result)} emptyHint="Pick a template and fill in the details.">
          <DataView value={body} />
          {disclaimer ? <p className="tool-disclaimer">{disclaimer}</p> : null}
        </ResultPanel>
      </div>
    </ToolFrame>
  );
}
