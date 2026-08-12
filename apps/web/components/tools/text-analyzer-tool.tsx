"use client";

import { FormEvent, useState, type ReactNode } from "react";
import { DataView, ResultPanel, ToolFrame, splitDisclaimer } from "@/components/tools/tool-frame";

/**
 * Shared shape for the tools that take prose in and return structured findings:
 * citation extraction, key dates, clause extraction, contract comparison.
 */
export function TextAnalyzerTool({
  toolKey,
  title,
  intro,
  caveat,
  inputs,
  run,
  emptyHint,
  submitLabel = "Analyse",
}: {
  toolKey: string;
  title: string;
  intro: string;
  caveat?: ReactNode;
  inputs: { key: string; label: string; placeholder: string; rows?: number }[];
  run: (values: Record<string, string>) => Promise<Record<string, unknown>>;
  emptyHint: string;
  submitLabel?: string;
}) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(inputs.map((input) => [input.key, ""])),
  );
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(await run(values));
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Request failed");
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
            <div className="card-title">Input</div>
          </div>
          {inputs.map((input) => (
            <label className="tool-field" key={input.key}>
              <span>{input.label}</span>
              <textarea
                rows={input.rows ?? 10}
                placeholder={input.placeholder}
                value={values[input.key] ?? ""}
                onChange={(e) => setValues((current) => ({ ...current, [input.key]: e.target.value }))}
              />
            </label>
          ))}
          <button className="button primary" disabled={busy}>
            {busy ? "Working…" : submitLabel}
          </button>
        </form>

        <ResultPanel error={error} hasResult={Boolean(result)} emptyHint={emptyHint}>
          <DataView value={body} />
          {disclaimer ? <p className="tool-disclaimer">{disclaimer}</p> : null}
        </ResultPanel>
      </div>
    </ToolFrame>
  );
}
