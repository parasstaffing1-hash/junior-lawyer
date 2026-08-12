"use client";

import { FormEvent, useState } from "react";
import { DataView, ResultPanel, ToolFrame } from "@/components/tools/tool-frame";
import { downloadBlob } from "@/lib/client";
import { generateExport, previewExport } from "@/lib/tools";

const SOURCE_TYPES = [
  { value: "legal_notice", label: "Legal notice" },
  { value: "affidavit", label: "Affidavit" },
  { value: "case_timeline", label: "Case timeline" },
  { value: "evidence_index", label: "Evidence index" },
  { value: "legal_checklist", label: "Legal checklist" },
  { value: "client_intake", label: "Client intake" },
  { value: "generic", label: "Generic document" },
];

export function DocumentExportTool() {
  const [sourceType, setSourceType] = useState("legal_notice");
  const [format, setFormat] = useState("pdf");
  const [source, setSource] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  function payload() {
    // The source is another tool's output, so it is passed through unchanged
    // rather than re-modelled here.
    return {
      source_type: sourceType,
      output_format: format,
      source: JSON.parse(source),
    };
  }

  async function act(kind: "preview" | "generate", event: FormEvent) {
    event.preventDefault();
    setBusy(kind);
    setError("");
    setStatus("");
    try {
      const body = payload();
      if (kind === "preview") {
        setResult(await previewExport(body));
      } else {
        const output = await generateExport(body);
        downloadBlob(output.blob, output.filename ?? `document.${format}`);
        setResult(null);
        setStatus(`Downloaded ${output.filename ?? `document.${format}`}.`);
      }
    } catch (err) {
      setResult(null);
      setError(
        err instanceof SyntaxError
          ? "The source must be valid JSON — paste the result from another tool."
          : err instanceof Error
            ? err.message
            : "Export failed",
      );
    } finally {
      setBusy("");
    }
  }

  return (
    <ToolFrame
      toolKey="document-exports"
      title="Document export"
      intro="Renders the output of another tool — a notice, affidavit, timeline, index, checklist or intake — as a PDF or DOCX."
      caveat="Takes the JSON produced by the other tools. Generate the document there first, then paste its result here to export it."
    >
      <div className="tool-layout tool-layout-wide">
        <form className="card tool-form" onSubmit={(e) => act("preview", e)}>
          <div className="card-header"><div className="card-title">Source</div></div>

          <div className="tool-field-row">
            <label className="tool-field">
              <span>Source type</span>
              <select value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
                {SOURCE_TYPES.map((option) => (
                  <option value={option.value} key={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            <label className="tool-field">
              <span>Format</span>
              <select value={format} onChange={(e) => setFormat(e.target.value)}>
                <option value="pdf">PDF</option>
                <option value="docx">DOCX</option>
              </select>
            </label>
          </div>

          <label className="tool-field">
            <span>Source JSON</span>
            <textarea
              rows={14}
              placeholder='{"template_id": "...", "sections": [...]}'
              value={source}
              onChange={(e) => setSource(e.target.value)}
              required
            />
          </label>

          <div className="tool-action-row">
            <button className="button primary" disabled={!source || Boolean(busy)}>
              {busy === "preview" ? "Working…" : "Preview"}
            </button>
            <button
              type="button"
              className="button secondary"
              disabled={!source || Boolean(busy)}
              onClick={(e) => act("generate", e)}
            >
              {busy === "generate" ? "Working…" : `Download ${format.toUpperCase()}`}
            </button>
          </div>
        </form>

        <ResultPanel
          error={error}
          hasResult={Boolean(result) || Boolean(status)}
          emptyHint="Paste the JSON output of another tool."
        >
          {status ? <p className="tool-status">{status}</p> : null}
          {result ? <DataView value={result} /> : null}
        </ResultPanel>
      </div>
    </ToolFrame>
  );
}
