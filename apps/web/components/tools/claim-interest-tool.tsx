"use client";

import { FormEvent, useState } from "react";
import { DataView, ResultPanel, ToolFrame, splitDisclaimer } from "@/components/tools/tool-frame";
import { calculateClaimInterest } from "@/lib/tools";

const DAY_COUNTS = [
  { value: "actual_365", label: "Actual / 365" },
  { value: "actual_366", label: "Actual / 366" },
  { value: "actual_360", label: "Actual / 360" },
  { value: "actual_actual", label: "Actual / actual" },
  { value: "30_360", label: "30 / 360" },
];

const FREQUENCIES = [
  { value: "annual", label: "Annually" },
  { value: "semiannual", label: "Half-yearly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "monthly", label: "Monthly" },
  { value: "daily", label: "Daily" },
];

export function ClaimInterestTool() {
  const [principal, setPrincipal] = useState("100000");
  const [rate, setRate] = useState("9");
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState(new Date().toISOString().slice(0, 10));
  const [method, setMethod] = useState("simple");
  const [dayCount, setDayCount] = useState("actual_365");
  const [frequency, setFrequency] = useState("annual");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(
        await calculateClaimInterest({
          principal,
          annual_rate_percent: rate,
          start_date: startDate,
          end_date: endDate,
          method,
          day_count_convention: dayCount,
          ...(method === "compound" ? { compounding_frequency: frequency } : {}),
        }),
      );
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Calculation failed");
    } finally {
      setBusy(false);
    }
  }

  const { body, disclaimer } = splitDisclaimer(result);
  const total = result?.total_amount;

  return (
    <ToolFrame
      toolKey="claim-interest"
      title="Claim interest"
      intro="Simple or compound interest on a claim between two dates, using the day-count convention the contract or decree specifies."
      caveat="Arithmetic on the figures you supply. It does not decide the rate, the period, or whether interest is payable at all — those come from the contract, statute or decree."
    >
      <div className="tool-layout">
        <form className="card tool-form" onSubmit={submit}>
          <div className="card-header">
            <div className="card-title">Inputs</div>
          </div>

          <div className="tool-field-row">
            <label className="tool-field">
              <span>Principal (₹)</span>
              <input type="number" min={0} step="0.01" value={principal} onChange={(e) => setPrincipal(e.target.value)} required />
            </label>
            <label className="tool-field">
              <span>Annual rate (%)</span>
              <input type="number" min={0} step="0.01" value={rate} onChange={(e) => setRate(e.target.value)} required />
            </label>
          </div>

          <div className="tool-field-row">
            <label className="tool-field">
              <span>From</span>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
            </label>
            <label className="tool-field">
              <span>To</span>
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} required />
            </label>
          </div>

          <label className="tool-field">
            <span>Method</span>
            <select value={method} onChange={(e) => setMethod(e.target.value)}>
              <option value="simple">Simple</option>
              <option value="compound">Compound</option>
            </select>
          </label>

          {method === "compound" ? (
            <label className="tool-field">
              <span>Compounding</span>
              <select value={frequency} onChange={(e) => setFrequency(e.target.value)}>
                {FREQUENCIES.map((option) => (
                  <option value={option.value} key={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
          ) : null}

          <label className="tool-field">
            <span>Day count</span>
            <select value={dayCount} onChange={(e) => setDayCount(e.target.value)}>
              {DAY_COUNTS.map((option) => (
                <option value={option.value} key={option.value}>{option.label}</option>
              ))}
            </select>
          </label>

          <button className="button primary" disabled={busy}>{busy ? "Calculating…" : "Calculate"}</button>
        </form>

        <ResultPanel error={error} hasResult={Boolean(result)} emptyHint="Enter a principal, rate and period.">
          {typeof total === "string" || typeof total === "number" ? (
            <div className="tool-headline">₹{String(total)}</div>
          ) : null}
          <DataView value={body} />
          {disclaimer ? <p className="tool-disclaimer">{disclaimer}</p> : null}
        </ResultPanel>
      </div>
    </ToolFrame>
  );
}
