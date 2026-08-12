"use client";

import { FormEvent, useState, type ReactNode } from "react";
import { DataView, ResultPanel, ToolFrame, splitDisclaimer } from "@/components/tools/tool-frame";

export interface RowField {
  key: string;
  label: string;
  type?: "text" | "date" | "number";
  options?: { value: string; label: string }[];
  wide?: boolean;
}

type Row = Record<string, string>;

/**
 * Case timelines and evidence indexes are both "build a list of records, then
 * render it" tools, so they share a repeatable-row editor.
 */
export function RowBuilderTool({
  toolKey,
  title,
  intro,
  caveat,
  rowLabel,
  rowFields,
  headerFields,
  build,
  emptyHint,
  submitLabel,
}: {
  toolKey: string;
  title: string;
  intro: string;
  caveat?: ReactNode;
  rowLabel: string;
  rowFields: RowField[];
  headerFields: RowField[];
  build: (header: Row, rows: Row[]) => Promise<Record<string, unknown>>;
  emptyHint: string;
  submitLabel: string;
}) {
  const blank = () => Object.fromEntries(rowFields.map((field) => [field.key, ""])) as Row;
  const [header, setHeader] = useState<Row>(() => Object.fromEntries(headerFields.map((f) => [f.key, ""])) as Row);
  const [rows, setRows] = useState<Row[]>([blank()]);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function updateRow(index: number, key: string, value: string) {
    setRows((current) => current.map((row, i) => (i === index ? { ...row, [key]: value } : row)));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const filled = rows.filter((row) => Object.values(row).some((value) => value.trim()));
      setResult(await build(header, filled));
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  function renderField(field: RowField, value: string, onChange: (v: string) => void) {
    if (field.options) {
      return (
        <select aria-label={field.label} value={value} onChange={(e) => onChange(e.target.value)}>
          {field.options.map((option) => (
            <option value={option.value} key={option.value}>{option.label}</option>
          ))}
        </select>
      );
    }
    return (
      <input
        aria-label={field.label}
        type={field.type ?? "text"}
        placeholder={field.label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }

  return (
    <ToolFrame toolKey={toolKey} title={title} intro={intro} caveat={caveat}>
      <div className="tool-layout tool-layout-wide">
        <form className="card tool-form" onSubmit={submit}>
          <div className="card-header"><div className="card-title">Entries</div></div>

          {headerFields.map((field) => (
            <label className="tool-field" key={field.key}>
              <span>{field.label}</span>
              {renderField(field, header[field.key] ?? "", (v) => setHeader((c) => ({ ...c, [field.key]: v })))}
            </label>
          ))}

          <fieldset className="tool-field">
            <legend>{rowLabel}</legend>
            {rows.map((row, index) => (
              <div className="tool-row-card" key={index}>
                <div className="tool-row-head">
                  <span>{rowLabel} {index + 1}</span>
                  {rows.length > 1 ? (
                    <button
                      type="button"
                      className="button secondary small"
                      onClick={() => setRows((current) => current.filter((_, i) => i !== index))}
                    >
                      Remove
                    </button>
                  ) : null}
                </div>
                <div className="tool-row-fields">
                  {rowFields.map((field) => (
                    <div className={field.wide ? "tool-row-field wide" : "tool-row-field"} key={field.key}>
                      {renderField(field, row[field.key] ?? "", (v) => updateRow(index, field.key, v))}
                    </div>
                  ))}
                </div>
              </div>
            ))}
            <button type="button" className="button secondary small" onClick={() => setRows((c) => [...c, blank()])}>
              Add {rowLabel.toLowerCase()}
            </button>
          </fieldset>

          <button className="button primary" disabled={busy}>{busy ? "Working…" : submitLabel}</button>
        </form>

        <ResultPanel error={error} hasResult={Boolean(result)} emptyHint={emptyHint}>
          <DataView value={splitDisclaimer(result).body} />
          {splitDisclaimer(result).disclaimer ? (
            <p className="tool-disclaimer">{splitDisclaimer(result).disclaimer}</p>
          ) : null}
        </ResultPanel>
      </div>
    </ToolFrame>
  );
}
