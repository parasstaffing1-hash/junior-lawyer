"use client";

import { FormEvent, useMemo, useState } from "react";
import {
  AIProviderStatus, AIPrepareResponse, AIReasoningPayload, AIRun, AITaskType, Matter,
  prepareAIReasoning, reviewAIRun, runAIReasoning,
} from "@/lib/api";

const TASKS: Array<{ value: AITaskType | string; label: string; tier: "₹0" | "local" | "strong" }> = [
  { value: "matter_summary", label: "Matter summary", tier: "local" },
  { value: "document_summary", label: "Document summary", tier: "local" },
  { value: "kanoongpt_bare_act", label: "KanoonGPT: Chat with Bare Acts", tier: "strong" },
  { value: "kanoongpt_case_law", label: "KanoonGPT: Search Case Law (Roadmap)", tier: "strong" },
  { value: "client_update", label: "Client update", tier: "local" },
  { value: "research_synthesis", label: "Research synthesis", tier: "strong" },
  { value: "issue_spotting", label: "Issue spotting", tier: "strong" },
  { value: "argument_analysis", label: "Argument analysis", tier: "strong" },
  { value: "counterargument", label: "Counterarguments", tier: "strong" },
  { value: "custom_drafting", label: "Bespoke legal drafting", tier: "strong" },
  { value: "custom_clause", label: "Custom contract clause", tier: "strong" },
  { value: "hearing_questions", label: "Hearing questions", tier: "strong" },
  { value: "search_cases", label: "Search cases", tier: "₹0" },
  { value: "verify_citation", label: "Verify citation", tier: "₹0" },
  { value: "build_chronology", label: "Build chronology", tier: "₹0" },
];

function human(value: string) { return value.replaceAll("_", " "); }
function when(value: string) { return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value)); }
function count(summary: Record<string, unknown>, key: string) { const value = summary[key]; return typeof value === "number" ? value : 0; }

function renderTextWithCitations(text: string, sources: any[]) {
  if (!text) return null;
  return text.split('\n').map((line, lineIdx) => {
    const parts = line.split(/(\[S\d+\])/g);
    return (
      <p key={lineIdx} style={{ minHeight: "1rem", margin: "0.5rem 0" }}>
        {parts.map((part, i) => {
          const match = part.match(/^\[(S\d+)\]$/);
          if (match) {
            const key = match[1];
            const source = sources.find((s: any) => s.source_key === key);
            return (
              <span 
                key={i} 
                className="ai-tier local" 
                style={{ cursor: "pointer", display: "inline-block", margin: "0 2px", padding: "1px 4px", fontSize: "0.75rem", verticalAlign: "super" }} 
                title={source ? `${source.title}\n${source.locator || ""}` : "Source"}
              >
                {key}
              </span>
            );
          }
          // Process basic markdown bold
          const boldParts = part.split(/(\*\*.*?\*\*)/g);
          return (
            <span key={i}>
              {boldParts.map((bp, j) => {
                if (bp.startsWith('**') && bp.endsWith('**')) {
                  return <strong key={j}>{bp.slice(2, -2)}</strong>;
                }
                return bp;
              })}
            </span>
          );
        })}
      </p>
    );
  });
}

export function AssistantWorkspace({ matters, initialRuns, providers }: { matters: Matter[]; initialRuns: AIRun[]; providers: AIProviderStatus }) {
  const [matterId, setMatterId] = useState(matters[0]?.id ?? "");
  const [task, setTask] = useState<AITaskType>("matter_summary");
  const [query, setQuery] = useState("Prepare a supervising-lawyer summary of this matter, highlighting disputed facts and the next points requiring attention.");
  const [language, setLanguage] = useState<"en" | "hi" | "bilingual">("en");
  const [includeCorpus, setIncludeCorpus] = useState(true);
  const [allowRemote, setAllowRemote] = useState(false);
  const [allowLocalHigh, setAllowLocalHigh] = useState(false);
  const [maxSources, setMaxSources] = useState(12);
  const [prepared, setPrepared] = useState<AIPrepareResponse | null>(null);
  const [runs, setRuns] = useState(initialRuns);
  const [selectedRun, setSelectedRun] = useState<AIRun | null>(initialRuns[0] ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [reviewer, setReviewer] = useState("Counsel");

  const selectedTask = useMemo(() => TASKS.find((item) => item.value === task), [task]);
  const payload = (): AIReasoningPayload => ({
    matter_id: matterId || null, task_type: task, query, output_language: language,
    prefer_local: true, allow_remote: allowRemote, allow_local_for_high_complexity: allowLocalHigh,
    include_corpus: includeCorpus, max_sources: maxSources, max_input_tokens: 6000, max_output_tokens: 1200,
  });

  async function preview(event?: FormEvent) {
    event?.preventDefault(); setBusy(true); setError(""); setMessage("");
    try { const result = await prepareAIReasoning(payload()); setPrepared(result); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to prepare reasoning request"); }
    finally { setBusy(false); }
  }
  async function run() {
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await runAIReasoning(payload());
      setSelectedRun(result); setRuns((current) => [result, ...current.filter((row) => row.id !== result.id)]);
      setMessage(result.status === "blocked" ? "Request was recorded but blocked by the routing policy." : "Reasoning run completed and verification results are available.");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to run verified reasoning"); }
    finally { setBusy(false); }
  }
  async function review(status: "reviewed" | "rejected") {
    if (!selectedRun) return; setBusy(true); setError("");
    try {
      const updated = await reviewAIRun(selectedRun.id, { status, reviewed_by: reviewer });
      setSelectedRun(updated); setRuns((current) => current.map((row) => row.id === updated.id ? updated : row));
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to record lawyer review"); }
    finally { setBusy(false); }
  }

  const verification = selectedRun?.verification_summary_json ?? {};
  const claimCounts = (verification.claim_counts ?? {}) as Record<string, unknown>;

  return (
    <div className="ai-workspace">
      <section className="ai-provider-strip">
        <div><span>Deterministic core</span><strong>Always first</strong><small>No model call</small></div>
        <div className={providers.local_enabled ? "ready" : ""}><span>Local model</span><strong>{providers.local_enabled ? "Ready" : "Off"}</strong><small>{providers.local_model ?? "configure in .env"}</small></div>
        <div className={providers.remote_enabled ? "ready" : ""}><span>Remote model</span><strong>{providers.remote_enabled ? "Available" : "Off"}</strong><small>explicit opt-in required</small></div>
        <div><span>Secrets persisted</span><strong>{providers.secrets_persisted ? "Yes" : "No"}</strong><small>environment only</small></div>
      </section>

      {message ? <div className="success-panel">{message}</div> : null}
      {error ? <div className="notice-panel">{error}</div> : null}

      <section className="card ai-composer">
        <form onSubmit={preview}>
          <div className="ai-composer-top">
            <label>Matter<select value={matterId} onChange={(e) => { setMatterId(e.target.value); setPrepared(null); }}><option value="">No matter / corpus only</option>{matters.map((matter) => <option key={matter.id} value={matter.id}>{matter.title}</option>)}</select></label>
            <label>Task<select value={task} onChange={(e) => { setTask(e.target.value as AITaskType); setPrepared(null); }}>{TASKS.map((item) => <option value={item.value} key={item.value}>{item.label} · {item.tier}</option>)}</select></label>
            <label>Output<select value={language} onChange={(e) => setLanguage(e.target.value as typeof language)}><option value="en">English</option><option value="hi">हिन्दी</option><option value="bilingual">Bilingual</option></select></label>
          </div>
          <label className="ai-query-label">Request<textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={4} /></label>
          <div className="ai-policy-row">
            <label><input type="checkbox" checked={includeCorpus} onChange={(e) => setIncludeCorpus(e.target.checked)} /> Search legal corpus</label>
            <label><input type="checkbox" checked={allowRemote} onChange={(e) => setAllowRemote(e.target.checked)} /> Allow remote model for this request</label>
            <label><input type="checkbox" checked={allowLocalHigh} onChange={(e) => setAllowLocalHigh(e.target.checked)} /> Allow local fallback for complex work</label>
            <label className="ai-source-limit">Sources <input type="number" min={2} max={24} value={maxSources} onChange={(e) => setMaxSources(Number(e.target.value))} /></label>
          </div>
          {allowRemote ? <div className="ai-remote-warning"><strong>Remote confidentiality check</strong><span>This request may send the selected evidence packet to the configured remote provider. Confirm that your firm/client policy permits that disclosure.</span></div> : null}
          <div className="ai-composer-foot">
            <div><strong>{selectedTask?.label}</strong><span>Preview shows the route and exact evidence packet before any model call.</span></div>
            <div className="ai-actions"><button type="submit" className="button secondary" disabled={busy || query.trim().length < 2}>Preview route</button><button type="button" className="button primary" onClick={run} disabled={busy || query.trim().length < 2}>Run verified reasoning</button></div>
          </div>
        </form>
      </section>

      {prepared ? <section className="card ai-route-card">
        <div className="card-header"><div><div className="card-title">Routing decision</div><div className="quiet-text">No model call is made by preview</div></div><span className={`ai-tier ${prepared.routing.tier}`}>{prepared.routing.tier}</span></div>
        <div className="ai-route-body"><div><span>Reason</span><p>{prepared.routing.reason}</p>{prepared.routing.quality_warning ? <p className="ai-warning">{prepared.routing.quality_warning}</p> : null}</div><div className="ai-budget"><div><span>Sources</span><strong>{prepared.routing.source_count}</strong></div><div><span>Input estimate</span><strong>{prepared.routing.estimated_input_tokens.toLocaleString()}</strong></div><div><span>Budget</span><strong>{prepared.budget.max_input_tokens.toLocaleString()}</strong></div></div></div>
        {prepared.sources.length ? <div className="ai-source-grid">{prepared.sources.map((source) => <article key={source.source_key} className="ai-source-card"><div><strong>{source.source_key}</strong><span>{human(source.source_type)}</span>{source.official ? <b>Official</b> : source.verified ? <b>Verified</b> : <b className="muted">Review</b>}</div><h3>{source.title}</h3><small>{source.locator ?? "Structured source"} · {Math.round(source.relevance_score * 100)}% relevance</small><p>{source.text}</p></article>)}</div> : <div className="empty-state compact"><div className="empty-state-title">No sources selected</div><div className="empty-state-copy">This may be a deterministic route or the matter/corpus may not yet contain relevant evidence.</div></div>}
      </section> : null}

      <div className="ai-main-grid">
        <aside className="card ai-run-list"><div className="card-header"><div><div className="card-title">Reasoning history</div><div className="quiet-text">Immutable run snapshots</div></div></div>{runs.length ? runs.map((run) => <button key={run.id} className={`ai-run-item${selectedRun?.id === run.id ? " active" : ""}`} onClick={() => setSelectedRun(run)}><div><span>{human(run.task_type)}</span><i className={`ai-verify-dot ${run.verification_status}`} /></div><strong>{run.query}</strong><small>{when(run.created_at)} · {run.route_tier} · {run.status}</small></button>) : <div className="empty-state compact"><div className="empty-state-title">No runs yet</div></div>}</aside>

        <section className="ai-result-stack">
          {!selectedRun ? <div className="card drafting-empty"><div className="drafting-empty-mark">AI</div><h2>No reasoning run selected</h2><p>Preview a request first, then execute it only when the routing and source packet look right.</p></div> : <>
            <article className="card ai-result-card">
              <div className="ai-result-head"><div><span className={`ai-tier ${selectedRun.route_tier}`}>{selectedRun.route_tier}</span><h2>{human(selectedRun.task_type)}</h2><p>{selectedRun.query}</p></div><div className={`ai-verification ${selectedRun.verification_status}`}><span>Verification</span><strong>{human(selectedRun.verification_status)}</strong></div></div>
              {selectedRun.error_message ? <div className="notice-panel">{selectedRun.error_message}</div> : null}
              {selectedRun.response_text ? <div className="ai-response-text">{renderTextWithCitations(selectedRun.response_text, selectedRun.sources)}</div> : null}
              <div className="ai-result-meta"><span>{selectedRun.model_name ?? "No model"}</span><span>{selectedRun.actual_input_tokens ?? selectedRun.estimated_input_tokens} input tokens</span><span>{selectedRun.actual_output_tokens ?? 0} output tokens</span><span>{selectedRun.sources.length} sources</span></div>
            </article>

            <section className="ai-verification-grid">
              <div className="card"><div className="card-header"><div><div className="card-title">Claim audit</div><div className="quiet-text">Source-marker and lexical support checks</div></div></div><div className="ai-audit-metrics"><div><strong>{count(claimCounts,"supported")}</strong><span>supported</span></div><div><strong>{count(claimCounts,"weak_support")}</strong><span>weak</span></div><div><strong>{count(claimCounts,"uncited")}</strong><span>uncited</span></div><div><strong>{count(claimCounts,"invalid_source")}</strong><span>invalid source</span></div></div>{selectedRun.claims.filter((claim) => claim.substantive).slice(0,8).map((claim) => <div className="ai-claim-row" key={claim.id}><span className={`claim-status ${claim.status}`}>{human(claim.status)}</span><p>{claim.claim_text}</p><small>{claim.cited_source_keys_json.join(", ") || "No source marker"}{claim.explanation ? ` · ${claim.explanation}` : ""}</small></div>)}</div>
              <div className="card"><div className="card-header"><div><div className="card-title">Citation audit</div><div className="quiet-text">Reported citations re-resolved against corpus</div></div></div>{selectedRun.citations.length ? selectedRun.citations.map((citation) => <div className="ai-citation-row" key={citation.id}><span className={`claim-status ${citation.status}`}>{citation.status}</span><strong>{citation.raw_citation}</strong><small>{citation.normalized_citation ?? "Unparsed"}</small></div>) : <div className="empty-state compact"><div className="empty-state-title">No reported citations in output</div><div className="empty-state-copy">Inline S# source markers are audited separately.</div></div>}</div>
            </section>

            <section className="card ai-review-card"><div><span>Lawyer review</span><strong>{human(selectedRun.review_status)}</strong><p>Verification checks source mechanics; it does not replace professional review of legal reasoning.</p></div><label>Reviewer<input value={reviewer} onChange={(e) => setReviewer(e.target.value)} /></label><div><button className="button secondary" disabled={busy || !reviewer.trim()} onClick={() => review("rejected")}>Reject output</button><button className="button primary" disabled={busy || !reviewer.trim()} onClick={() => review("reviewed")}>Mark reviewed</button></div></section>
          </>}
        </section>
      </div>
    </div>
  );
}
