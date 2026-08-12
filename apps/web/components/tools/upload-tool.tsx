"use client";

import { FormEvent, useEffect, useState, type ReactNode } from "react";
import { DataView, ResultPanel, ToolFrame, splitDisclaimer } from "@/components/tools/tool-frame";
import { downloadBlob } from "@/lib/client";

export interface UploadAction {
  key: string;
  label: string;
  /** Returns JSON to display, or a blob to download. */
  run: (file: File, options: Record<string, unknown>) => Promise<
    Record<string, unknown> | { blob: Blob; filename: string | null }
  >;
  download?: boolean;
}

function isBlobResult(value: unknown): value is { blob: Blob; filename: string | null } {
  return typeof value === "object" && value !== null && "blob" in value;
}

export function UploadTool({
  toolKey,
  title,
  intro,
  caveat,
  accept,
  actions,
  capabilities,
  optionFields = [],
}: {
  toolKey: string;
  title: string;
  intro: string;
  caveat?: ReactNode;
  accept: string;
  actions: UploadAction[];
  capabilities?: () => Promise<Record<string, unknown>>;
  optionFields?: { key: string; label: string; type?: "text" | "number"; placeholder?: string }[];
}) {
  const [file, setFile] = useState<File | null>(null);
  const [options, setOptions] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [capability, setCapability] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (!capabilities) return;
    capabilities().then(setCapability).catch(() => undefined);
  }, [capabilities]);

  async function run(action: UploadAction, event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(action.key);
    setError("");
    setStatus("");
    try {
      const parsed: Record<string, unknown> = {};
      for (const field of optionFields) {
        const raw = options[field.key];
        if (raw) parsed[field.key] = field.type === "number" ? Number(raw) : raw;
      }
      const output = await action.run(file, parsed);
      if (isBlobResult(output)) {
        downloadBlob(output.blob, output.filename ?? `${toolKey}-output`);
        setResult(null);
        setStatus(`Downloaded ${output.filename ?? "file"}.`);
      } else {
        setResult(output);
      }
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy("");
    }
  }

  const unavailable =
    capability && capability.available === false
      ? `The ${String(capability.engine ?? "processing")} engine is not installed on the server, so this tool cannot run yet.`
      : "";

  const { body, disclaimer } = splitDisclaimer(result);

  return (
    <ToolFrame toolKey={toolKey} title={title} intro={intro} caveat={caveat}>
      {unavailable ? (
        <div className="notice-panel" style={{ marginBottom: 14 }}><span>{unavailable}</span></div>
      ) : null}
      <div className="tool-layout">
        <form className="card tool-form" onSubmit={(e) => run(actions[0], e)}>
          <div className="card-header"><div className="card-title">File</div></div>

          <label className="tool-field">
            <span>Document</span>
            <input
              type="file"
              accept={accept}
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setResult(null);
                setStatus("");
              }}
            />
          </label>
          {file ? (
            <p className="tool-provenance">
              {file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB
            </p>
          ) : null}

          {optionFields.map((field) => (
            <label className="tool-field" key={field.key}>
              <span>{field.label}</span>
              <input
                type={field.type ?? "text"}
                placeholder={field.placeholder}
                value={options[field.key] ?? ""}
                onChange={(e) => setOptions((c) => ({ ...c, [field.key]: e.target.value }))}
              />
            </label>
          ))}

          <div className="tool-action-row">
            {actions.map((action, index) => (
              <button
                key={action.key}
                type={index === 0 ? "submit" : "button"}
                className={index === 0 ? "button primary" : "button secondary"}
                disabled={!file || Boolean(busy)}
                onClick={index === 0 ? undefined : (e) => run(action, e)}
              >
                {busy === action.key ? "Working…" : action.label}
              </button>
            ))}
          </div>
        </form>

        <ResultPanel
          error={error}
          hasResult={Boolean(result) || Boolean(status)}
          emptyHint="Choose a file to begin."
        >
          {status ? <p className="tool-status">{status}</p> : null}
          {result ? <DataView value={body} /> : null}
          {disclaimer ? <p className="tool-disclaimer">{disclaimer}</p> : null}
        </ResultPanel>
      </div>
    </ToolFrame>
  );
}
