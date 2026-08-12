"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import {
  calculateDeadline,
  type CountMode,
  type LegalDeadlineResponse,
} from "@/lib/tools";

const WEEKDAYS = [
  { value: 0, label: "Mon" },
  { value: 1, label: "Tue" },
  { value: 2, label: "Wed" },
  { value: 3, label: "Thu" },
  { value: 4, label: "Fri" },
  { value: 5, label: "Sat" },
  { value: 6, label: "Sun" },
];

function today() {
  return new Date().toISOString().slice(0, 10);
}

export function DeadlineTool() {
  const [startDate, setStartDate] = useState(today());
  const [days, setDays] = useState("30");
  const [countMode, setCountMode] = useState<CountMode>("calendar_days");
  const [includeStart, setIncludeStart] = useState(false);
  const [rollForward, setRollForward] = useState(true);
  const [weekend, setWeekend] = useState<number[]>([5, 6]);
  const [excluded, setExcluded] = useState("");
  const [result, setResult] = useState<LegalDeadlineResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function toggleWeekend(day: number) {
    setWeekend((current) =>
      current.includes(day) ? current.filter((value) => value !== day) : [...current, day].sort(),
    );
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const excludedDates = excluded
        .split(/[\s,]+/)
        .map((value) => value.trim())
        .filter(Boolean);
      setResult(
        await calculateDeadline({
          start_date: startDate,
          days: Number(days),
          count_mode: countMode,
          include_start_date: includeStart,
          roll_if_non_business: rollForward,
          excluded_dates: excludedDates,
          weekend_weekdays: weekend,
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
      <h1 className="page-title">Deadline calculator</h1>
      <p className="page-subtitle">
        Counts forward from a trigger date in calendar or business days, skipping the weekend
        pattern and any court holidays you supply.
      </p>

      <div className="tool-layout">
        <form className="card tool-form" onSubmit={submit}>
          <div className="card-header">
            <div className="card-title">Inputs</div>
          </div>

          <label className="tool-field">
            <span>Start date</span>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
          </label>

          <label className="tool-field">
            <span>Days</span>
            <input
              type="number"
              min={0}
              max={3650}
              value={days}
              onChange={(e) => setDays(e.target.value)}
              required
            />
          </label>

          <label className="tool-field">
            <span>Count mode</span>
            <select value={countMode} onChange={(e) => setCountMode(e.target.value as CountMode)}>
              <option value="calendar_days">Calendar days</option>
              <option value="business_days">Business days</option>
            </select>
          </label>

          <fieldset className="tool-field">
            <legend>Non-working days</legend>
            <div className="tool-chip-row">
              {WEEKDAYS.map((day) => (
                <button
                  type="button"
                  key={day.value}
                  aria-pressed={weekend.includes(day.value)}
                  className={`tool-chip${weekend.includes(day.value) ? " active" : ""}`}
                  onClick={() => toggleWeekend(day.value)}
                >
                  {day.label}
                </button>
              ))}
            </div>
          </fieldset>

          <label className="tool-field">
            <span>Excluded dates</span>
            <textarea
              rows={2}
              placeholder="2026-08-15, 2026-10-02"
              value={excluded}
              onChange={(e) => setExcluded(e.target.value)}
            />
          </label>

          <label className="tool-check">
            <input type="checkbox" checked={includeStart} onChange={(e) => setIncludeStart(e.target.checked)} />
            <span>Count the start date itself</span>
          </label>

          <label className="tool-check">
            <input type="checkbox" checked={rollForward} onChange={(e) => setRollForward(e.target.checked)} />
            <span>Roll forward if the due date is a non-working day</span>
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
              <div className="tool-headline">{result.due_date}</div>
              <dl className="tool-readout">
                <div><dt>Start</dt><dd>{result.start_date}</dd></div>
                <div><dt>Period</dt><dd>{result.days} {result.count_mode === "business_days" ? "business days" : "calendar days"}</dd></div>
                <div><dt>Start counted</dt><dd>{result.include_start_date ? "Yes" : "No"}</dd></div>
                <div><dt>Excluded dates applied</dt><dd>{result.excluded_dates_used.length || "None"}</dd></div>
              </dl>
              {result.adjustment ? (
                <div className="notice-panel">
                  <span>
                    Rolled from {result.adjustment.original_date} to {result.adjustment.adjusted_date} — {result.adjustment.reason}
                  </span>
                </div>
              ) : null}
              <p className="tool-disclaimer">{result.disclaimer}</p>
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}
