"use client";

import { FormEvent, useEffect, useState } from "react";
import { DataView, ResultPanel, ToolFrame, splitDisclaimer } from "@/components/tools/tool-frame";
import type { RulePackSummary } from "@/lib/tools";

/**
 * Court fee and stamp duty are the same shape: pick a rule pack, give a date
 * and a value, get a computed amount. The pack is the legal content, so its
 * provenance is shown prominently rather than hidden behind an id.
 */
export function RulePackCalculator({
  toolKey,
  title,
  intro,
  caveat,
  dateLabel,
  dateField,
  valueFields,
  loadPacks,
  calculate,
}: {
  toolKey: string;
  title: string;
  intro: string;
  caveat: string;
  dateLabel: string;
  dateField: string;
  valueFields: { key: string; label: string; hint?: string }[];
  loadPacks: () => Promise<RulePackSummary[]>;
  calculate: (payload: Record<string, unknown>) => Promise<Record<string, unknown>>;
}) {
  const [packs, setPacks] = useState<RulePackSummary[]>([]);
  const [packId, setPackId] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    loadPacks()
      .then((rows) => {
        setPacks(rows);
        if (rows.length) setPackId(String(rows[0].id ?? rows[0].pack_id ?? ""));
      })
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Could not load rule packs"));
  }, [loadPacks]);

  const selected = packs.find((pack) => String(pack.id ?? pack.pack_id) === packId);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload: Record<string, unknown> = { rule_pack_id: packId, [dateField]: date };
      for (const field of valueFields) {
        if (values[field.key]) payload[field.key] = values[field.key];
      }
      setResult(await calculate(payload));
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Calculation failed");
    } finally {
      setBusy(false);
    }
  }

  const { body, disclaimer } = splitDisclaimer(result);

  return (
    <ToolFrame toolKey={toolKey} title={title} intro={intro} caveat={caveat}>
      <div className="tool-layout">
        <form className="card tool-form" onSubmit={submit}>
          <div className="card-header">
            <div className="card-title">Inputs</div>
          </div>

          {loadError ? (
            <div className="notice-panel" style={{ marginBottom: 12 }}>
              <span>{loadError}</span>
            </div>
          ) : null}

          <label className="tool-field">
            <span>Rule pack</span>
            <select value={packId} onChange={(e) => setPackId(e.target.value)} required>
              {packs.length === 0 ? <option value="">No rule packs installed</option> : null}
              {packs.map((pack) => {
                const id = String(pack.id ?? pack.pack_id);
                return (
                  <option value={id} key={id}>
                    {String(pack.name ?? pack.title ?? id)}
                    {pack.jurisdiction ? ` — ${pack.jurisdiction}` : ""}
                  </option>
                );
              })}
            </select>
          </label>

          {selected?.source_note ? (
            <p className="tool-provenance">{String(selected.source_note)}</p>
          ) : null}

          <label className="tool-field">
            <span>{dateLabel}</span>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          </label>

          {valueFields.map((field) => (
            <label className="tool-field" key={field.key}>
              <span>{field.label}</span>
              <input
                type="number"
                min={0}
                step="0.01"
                placeholder={field.hint ?? ""}
                value={values[field.key] ?? ""}
                onChange={(e) => setValues((current) => ({ ...current, [field.key]: e.target.value }))}
              />
            </label>
          ))}

          <button className="button primary" disabled={busy || !packId}>
            {busy ? "Calculating…" : "Calculate"}
          </button>
        </form>

        <ResultPanel error={error} hasResult={Boolean(result)} emptyHint="Pick a rule pack and enter a value.">
          <DataView value={body} />
          {disclaimer ? <p className="tool-disclaimer">{disclaimer}</p> : null}
        </ResultPanel>
      </div>
    </ToolFrame>
  );
}
