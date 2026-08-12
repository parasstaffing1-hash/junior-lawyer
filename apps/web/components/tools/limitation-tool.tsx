"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import {
  calculateLimitationPeriod,
  type ExpiryAdjustment,
  type LimitationPeriodResponse,
  type PeriodUnit,
} from "@/lib/tools";

function today() {
  return new Date().toISOString().slice(0, 10);
}

export function LimitationTool() {
  const [triggerDate, setTriggerDate] = useState(today());
  const [periodValue, setPeriodValue] = useState("3");
  const [periodUnit, setPeriodUnit] = useState<PeriodUnit>("years");
  const [extensionDays, setExtensionDays] = useState("");
  const [extensionReason, setExtensionReason] = useState("");
  const [adjustment, setAdjustment] = useState<ExpiryAdjustment>("next_business_day");
  const [excluded, setExcluded] = useState("");
  const [result, setResult] = useState<LimitationPeriodResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const days = Number(extensionDays);
      setResult(
        await calculateLimitationPeriod({
          trigger_date: triggerDate,
          period_value: Number(periodValue),
          period_unit: periodUnit,
          extension_periods: days > 0 ? [{ days, reason: extensionReason || null }] : [],
          expiry_adjustment: adjustment,
          excluded_dates: excluded.split(/[\s,]+/).map((v) => v.trim()).filter(Boolean),
        }),
      );
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Calculation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <div className="eyebrow">
        <Link href="/tools">Tools</Link> · Dates &amp; limitation
      </div>
      <h1 className="page-title">Limitation period</h1>
      <p className="page-subtitle">
        Computes an expiry date from the trigger, applies any extension you record, and optionally
        moves an expiry that falls on a non-working day to the next business day.
      </p>

      <div className="notice-panel" style={{ marginBottom: 14 }}>
        <span>
          This is date arithmetic on the values you enter. It does not decide which limitation
          article applies, and it does not account for condonation, exclusions under the Limitation
          Act, or local court practice. Those remain lawyer-review items.
        </span>
      </div>

      <div className="tool-layout">
        <form className="card tool-form" onSubmit={submit}>
          <div className="card-header">
            <div className="card-title">Inputs</div>
          </div>

          <label className="tool-field">
            <span>Trigger date</span>
            <input type="date" value={triggerDate} onChange={(e) => setTriggerDate(e.target.value)} required />
          </label>

          <div className="tool-field-row">
            <label className="tool-field">
              <span>Period</span>
              <input
                type="number"
                min={1}
                value={periodValue}
                onChange={(e) => setPeriodValue(e.target.value)}
                required
              />
            </label>
            <label className="tool-field">
              <span>Unit</span>
              <select value={periodUnit} onChange={(e) => setPeriodUnit(e.target.value as PeriodUnit)}>
                <option value="days">Days</option>
                <option value="weeks">Weeks</option>
                <option value="months">Months</option>
                <option value="years">Years</option>
              </select>
            </label>
          </div>

          <div className="tool-field-row">
            <label className="tool-field">
              <span>Extension (days)</span>
              <input
                type="number"
                min={0}
                placeholder="0"
                value={extensionDays}
                onChange={(e) => setExtensionDays(e.target.value)}
              />
            </label>
            <label className="tool-field">
              <span>Extension reason</span>
              <input
                type="text"
                placeholder="e.g. certified copy time"
                value={extensionReason}
                onChange={(e) => setExtensionReason(e.target.value)}
              />
            </label>
          </div>

          <label className="tool-field">
            <span>Expiry adjustment</span>
            <select value={adjustment} onChange={(e) => setAdjustment(e.target.value as ExpiryAdjustment)}>
              <option value="none">Report the exact date</option>
              <option value="next_business_day">Move to next business day</option>
            </select>
          </label>

          <label className="tool-field">
            <span>Excluded dates</span>
            <textarea
              rows={2}
              placeholder="2026-08-15, 2026-10-02"
              value={excluded}
              onChange={(e) => setExcluded(e.target.value)}
            />
          </label>

          <button className="button primary" disabled={busy}>
            {busy ? "Calculating…" : "Calculate"}
          </button>
        </form>

        <section className="card tool-result" aria-live="polite">
          <div className="card-header">
            <div className="card-title">Result</div>
          </div>
          {error ? <div className="notice-panel"><span>{error}</span></div> : null}
          {!result && !error ? (
            <div className="empty-state compact">
              <div className="empty-state-title">No calculation yet</div>
              <div className="empty-state-copy">Enter a trigger date and period, then calculate.</div>
            </div>
          ) : null}
          {result ? (
            <>
              <div className="tool-headline">{result.final_expiry_date}</div>
              <dl className="tool-readout">
                <div><dt>Trigger</dt><dd>{result.trigger_date}</dd></div>
                <div><dt>Period</dt><dd>{result.period_value} {result.period_unit}</dd></div>
                <div><dt>Base expiry</dt><dd>{result.base_expiry_date}</dd></div>
                <div><dt>Extension applied</dt><dd>{result.total_extension_days} days</dd></div>
                <div><dt>Before adjustment</dt><dd>{result.expiry_before_business_day_adjustment}</dd></div>
              </dl>
              {result.expiry_adjustment ? (
                <div className="notice-panel">
                  <span>
                    Moved from {result.expiry_adjustment.original_date} to {result.expiry_adjustment.adjusted_date} — {result.expiry_adjustment.reason}
                  </span>
                </div>
              ) : null}
              {result.calculation_notes.length ? (
                <ul className="tool-notes">
                  {result.calculation_notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              ) : null}
              <p className="tool-disclaimer">{result.disclaimer}</p>
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}
