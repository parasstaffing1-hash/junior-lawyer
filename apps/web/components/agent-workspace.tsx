"use client";

import { useState } from "react";

import { CheckIcon, LockIcon, SparklesIcon } from "@/components/icons";
import { apiFetch } from "@/lib/client";
import { formatEnum } from "@/lib/format";
import type { AgentRunWithSteps, AgentRun, Matter } from "@/lib/server-api";

type StepOutput = Record<string, unknown>;

function statusTone(status: string) {
  if (status === "completed" || status === "approved") return "ok";
  if (status === "skipped" || status === "awaiting_approval") return "warn";
  if (status === "failed" || status === "rejected") return "bad";
  return "";
}

/** Each step shapes its own output, so each gets its own reading. */
function StepBody({ stepKey, output }: { stepKey: string; output: StepOutput }) {
  if (stepKey === "matter_brief") {
    return (
      <dl className="tool-subreadout">
        <div><dt>Court</dt><dd>{String(output.court ?? "—")}</dd></div>
        <div><dt>Client</dt><dd>{String(output.client ?? "—")}</dd></div>
        <div><dt>Case number</dt><dd>{String(output.case_number ?? "Not allotted")}</dd></div>
        <div><dt>Documents</dt><dd>{String(output.documents_ready ?? 0)} of {String(output.document_count ?? 0)} processed</dd></div>
      </dl>
    );
  }

  if (stepKey === "limitation") {
    const deadlines = (output.deadlines as Array<Record<string, unknown>>) ?? [];
    if (!deadlines.length) {
      return <p className="agent-step-note">{String(output.note ?? "Nothing recorded.")}</p>;
    }
    return (
      <ul className="agent-list">
        {deadlines.map((d, i) => (
          <li key={i}>
            <strong>{String(d.label || "Deadline")}</strong>
            <span>
              {String(d.due_on ?? "no date")}
              {typeof d.days_remaining === "number"
                ? ` · ${d.days_remaining < 0 ? `${Math.abs(d.days_remaining)} days past` : `${d.days_remaining} days left`}`
                : ""}
            </span>
          </li>
        ))}
      </ul>
    );
  }

  if (stepKey === "upcoming") {
    const items = (output.items as Array<Record<string, unknown>>) ?? [];
    if (!items.length) return <p className="agent-step-note">Nothing due in the next {String(output.window_days ?? 14)} days.</p>;
    return (
      <ul className="agent-list">
        {items.map((item, i) => (
          <li key={i}>
            <strong>{String(item.title ?? "")}</strong>
            <span>{formatEnum(String(item.kind ?? ""))} · {String(item.when ?? "")}</span>
          </li>
        ))}
      </ul>
    );
  }

  if (stepKey === "procedural_history") {
    const events = (output.events as Array<Record<string, unknown>>) ?? [];
    if (!events.length) return <p className="agent-step-note">No timeline events on this matter yet.</p>;
    return (
      <ul className="agent-list">
        {events.map((e, i) => (
          <li key={i}><strong>{String(e.label ?? "")}</strong><span>{String(e.on ?? "")}</span></li>
        ))}
      </ul>
    );
  }

  if (stepKey === "gaps") {
    const contradictions = (output.contradictions as Array<Record<string, unknown>>) ?? [];
    const reviewItems = (output.review_items as Array<Record<string, unknown>>) ?? [];
    if (!contradictions.length && !reviewItems.length) {
      return <p className="agent-step-note">Nothing unresolved on the file.</p>;
    }
    return (
      <ul className="agent-list">
        {contradictions.map((c, i) => (
          <li key={`c${i}`}><strong>{String(c.label ?? "")}</strong><span>Contradiction · {formatEnum(String(c.severity ?? ""))}</span></li>
        ))}
        {reviewItems.map((r, i) => (
          <li key={`r${i}`}><strong>{String(r.label ?? "")}</strong><span>Needs review</span></li>
        ))}
      </ul>
    );
  }

  // AI steps
  if (typeof output.response_text === "string" && output.response_text) {
    return <p className="agent-step-prose">{output.response_text}</p>;
  }
  return null;
}

export function AgentWorkspace({
  matters,
  initialRuns,
  apiReachable,
}: {
  matters: Matter[];
  initialRuns: AgentRun[];
  apiReachable: boolean;
}) {
  const [matterId, setMatterId] = useState(matters[0]?.id ?? "");
  const [run, setRun] = useState<AgentRunWithSteps | null>(null);
  const [runs, setRuns] = useState<AgentRun[]>(initialRuns);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function start() {
    if (!matterId) return;
    setBusy(true);
    setError("");
    try {
      const created = await apiFetch<AgentRunWithSteps>("/agent/runs", {
        method: "POST",
        body: JSON.stringify({ matter_id: matterId, recipe: "hearing_prep" }),
      });
      setRun(created);
      setRuns((previous) => [created, ...previous]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the run");
    } finally {
      setBusy(false);
    }
  }

  async function review(approved: boolean) {
    if (!run) return;
    setBusy(true);
    try {
      const updated = await apiFetch<AgentRunWithSteps>(`/agent/runs/${run.id}/review`, {
        method: "PATCH",
        body: JSON.stringify({ approved, notes: null }),
      });
      setRun(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not record the decision");
    } finally {
      setBusy(false);
    }
  }

  const summary = (run?.summary_json ?? {}) as Record<string, number>;

  return (
    <main className="page">
      <div className="hero-row">
        <div>
          <div className="page-icon" aria-hidden="true"><SparklesIcon /></div>
          <div className="eyebrow">Junior Lawyer Agent</div>
          <h1 className="page-title">Prepare for hearing</h1>
          <p className="page-subtitle">
            One instruction, several steps. The agent reads the matter, its history, the
            limitation position, what is due and what is missing — then stops for you. It
            does not file, send or change anything.
          </p>
        </div>
      </div>

      {!apiReachable ? (
        <div className="notice-panel">
          <strong>API is not connected.</strong>
          <span>Start the FastAPI server to run the agent.</span>
        </div>
      ) : null}

      <section className="card agent-launch">
        <div className="card-header">
          <div className="card-title">Run</div>
          <div className="card-action">{runs.length} previous</div>
        </div>
        <div className="agent-launch-body">
          <label className="tool-field">
            <span>Matter</span>
            <select value={matterId} onChange={(e) => setMatterId(e.target.value)}>
              {matters.length ? (
                matters.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)
              ) : (
                <option value="">No matters yet</option>
              )}
            </select>
          </label>
          <button className="primary-button" type="button" onClick={start} disabled={busy || !matterId}>
            {busy ? "Running…" : "Prepare for hearing"}
          </button>
        </div>
        {error ? <p className="agent-error" role="alert">{error}</p> : null}
      </section>

      {run ? (
        <>
          <section className="metrics agent-summary">
            <div className="metric">
              <div className="metric-label">Steps completed</div>
              <div className="metric-value">{summary.steps_completed ?? 0}</div>
              <div className="metric-note">of {summary.steps_total ?? 0}</div>
            </div>
            <div className="metric">
              <div className="metric-label">Due in 14 days</div>
              <div className="metric-value">{summary.due_in_14_days ?? 0}</div>
              <div className="metric-note">hearings and deadlines</div>
            </div>
            <div className="metric">
              <div className="metric-label">Expired deadlines</div>
              <div className="metric-value">{summary.expired_deadlines ?? 0}</div>
              <div className="metric-note">past their date</div>
            </div>
            <div className="metric">
              <div className="metric-label">Unresolved</div>
              <div className="metric-value">{summary.unresolved_contradictions ?? 0}</div>
              <div className="metric-note">contradictions</div>
            </div>
          </section>

          {!run.ai_available ? (
            <div className="notice-panel">
              <strong>{summary.steps_skipped ?? 0} steps did not run.</strong>
              <span>
                No AI provider is configured, so the reasoning steps were skipped. Everything
                above comes from the rule engines and is unaffected.
              </span>
            </div>
          ) : null}

          <ol className="agent-steps">
            {(run.steps ?? []).map((step) => (
              <li className={`card agent-step ${statusTone(String(step.status))}`} key={step.id}>
                <div className="agent-step-head">
                  <span className="agent-step-mark" aria-hidden="true">
                    {step.status === "completed" ? <CheckIcon /> : step.status === "skipped" ? <LockIcon /> : step.ordinal + 1}
                  </span>
                  <div className="agent-step-heading">
                    <strong>{step.label}</strong>
                    <span>{formatEnum(String(step.kind))}</span>
                  </div>
                  <span className="agent-step-state">{formatEnum(String(step.status))}</span>
                </div>
                <div className="agent-step-body">
                  {step.status === "skipped" ? (
                    <p className="agent-step-note">{step.note}</p>
                  ) : step.status === "failed" ? (
                    <p className="agent-step-note bad">{step.error_message}</p>
                  ) : (
                    <StepBody stepKey={step.step_key} output={(step.output_json ?? {}) as StepOutput} />
                  )}
                </div>
              </li>
            ))}
          </ol>

          <section className="card agent-approval">
            <div className="card-header">
              <div className="card-title">Your decision</div>
              <div className="card-action">{formatEnum(String(run.status))}</div>
            </div>
            <div className="agent-approval-body">
              <p>
                Nothing here has been filed, sent or written back to the matter. Approving
                records that you have read it.
              </p>
              <div className="agent-approval-actions">
                <button className="primary-button" type="button" onClick={() => review(true)} disabled={busy || run.status !== "awaiting_approval"}>
                  Approve
                </button>
                <button className="secondary-button" type="button" onClick={() => review(false)} disabled={busy || run.status !== "awaiting_approval"}>
                  Reject
                </button>
              </div>
            </div>
          </section>
        </>
      ) : null}
    </main>
  );
}
