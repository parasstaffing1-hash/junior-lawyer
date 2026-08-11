"use client";

import { FormEvent, useMemo, useRef, useState } from "react";
import {
  ContractCatalogItem,
  ContractReviewDetail,
  ContractReviewListItem,
  ContractType,
  ReviewFindingStatus,
  contractRedlineDownloadUrl,
  generateContractRedline,
  getContractReview,
  reanalyzeContractReview,
  updateContractReviewClauseDecision,
  updateContractReviewFinding,
  uploadContractReview,
} from "@/lib/api";
import { DocumentIcon, PlusIcon } from "@/components/icons";

function pretty(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function listFromDetail(detail: ContractReviewDetail): ContractReviewListItem {
  return {
    id: detail.id,
    title: detail.title,
    counterparty_name: detail.counterparty_name,
    contract_type: detail.contract_type,
    status: detail.status,
    language: detail.language,
    health_score: detail.health_score,
    clause_count: detail.clauses.length,
    open_high_risks: detail.findings.filter((item) => item.level === "high" && item.status === "open").length,
    source_filename: detail.source_filename,
    updated_at: detail.updated_at,
  };
}

export function ContractReviewWorkspace({
  catalog,
  initialReviews,
}: {
  catalog: ContractCatalogItem[];
  initialReviews: ContractReviewListItem[];
}) {
  const [reviews, setReviews] = useState(initialReviews);
  const [selected, setSelected] = useState<ContractReviewDetail | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [contractType, setContractType] = useState<ContractType>("services");
  const [title, setTitle] = useState("Counterparty agreement review");
  const [counterparty, setCounterparty] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const metrics = useMemo(() => ({
    total: reviews.length,
    high: reviews.reduce((sum, item) => sum + item.open_high_risks, 0),
    negotiation: reviews.filter((item) => item.status === "in_negotiation").length,
    healthy: reviews.filter((item) => item.health_score >= 80).length,
  }), [reviews]);

  function sync(detail: ContractReviewDetail) {
    setReviews((current) => [listFromDetail(detail), ...current.filter((item) => item.id !== detail.id)]);
  }

  async function openReview(id: string) {
    setLoading(true);
    setMessage(null);
    try {
      setSelected(await getContractReview(id));
      setUploadOpen(false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to open contract review");
    } finally {
      setLoading(false);
    }
  }

  async function submitUpload(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setMessage("Choose a DOCX, PDF or TXT contract first.");
      return;
    }
    setLoading(true);
    setMessage(null);
    try {
      const data = new FormData();
      data.set("file", file);
      data.set("contract_type", contractType);
      data.set("title", title);
      if (counterparty) data.set("counterparty_name", counterparty);
      const detail = await uploadContractReview(data);
      setSelected(detail);
      sync(detail);
      setUploadOpen(false);
      setMessage(`Reviewed ${detail.clauses.length} clauses locally with ${detail.findings.length} playbook findings.`);
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Contract review failed");
    } finally {
      setLoading(false);
    }
  }

  async function refreshAnalysis() {
    if (!selected) return;
    setLoading(true);
    setMessage(null);
    try {
      const detail = await reanalyzeContractReview(selected.id);
      setSelected(detail);
      sync(detail);
      setMessage("Deterministic playbook analysis rebuilt from the original file.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Reanalysis failed");
    } finally {
      setLoading(false);
    }
  }

  async function setFinding(findingId: string, status: ReviewFindingStatus) {
    if (!selected) return;
    setLoading(true);
    try {
      const detail = await updateContractReviewFinding(selected.id, findingId, status);
      setSelected(detail);
      sync(detail);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to update finding");
    } finally {
      setLoading(false);
    }
  }

  async function decide(clauseId: string, decision: "keep" | "replace" | "accept_risk" | "remove") {
    if (!selected) return;
    setLoading(true);
    try {
      const detail = await updateContractReviewClauseDecision(selected.id, clauseId, decision);
      setSelected(detail);
      sync(detail);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save negotiation decision");
    } finally {
      setLoading(false);
    }
  }

  async function makeRedline() {
    if (!selected) return;
    setLoading(true);
    setMessage(null);
    try {
      const version = await generateContractRedline(selected.id);
      const detail = await getContractReview(selected.id);
      setSelected(detail);
      sync(detail);
      setMessage(`Redline v${version.version_number} generated locally. Replacements use approved playbook clauses.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to generate redline");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="contract-review-module">
      <div className="contract-review-divider">
        <div>
          <div className="eyebrow">Counterparty review · deterministic</div>
          <h2>Review, negotiate and redline.</h2>
          <p>Upload a third-party agreement, compare it against the clause library and record lawyer-controlled negotiation decisions.</p>
        </div>
        <button className="primary-button" type="button" onClick={() => { setUploadOpen(true); setSelected(null); }}>
          <PlusIcon /> Review contract
        </button>
      </div>

      <div className="review-metrics">
        <div><span>Reviews</span><strong>{metrics.total}</strong></div>
        <div><span>Open high risks</span><strong>{metrics.high}</strong></div>
        <div><span>Negotiations</span><strong>{metrics.negotiation}</strong></div>
        <div><span>Health ≥ 80</span><strong>{metrics.healthy}</strong></div>
      </div>

      {message && <div className="contract-message">{message}</div>}

      {uploadOpen && (
        <form className="card review-upload" onSubmit={submitUpload}>
          <div className="review-upload-head"><div><div className="eyebrow">New review</div><h3>Counterparty agreement</h3></div><button type="button" className="text-button" onClick={() => setUploadOpen(false)}>Close</button></div>
          <div className="contract-form-grid">
            <label className="contract-field contract-field-wide"><span>Review title<small>समीक्षा शीर्षक</small></span><input value={title} onChange={(event) => setTitle(event.target.value)} required /></label>
            <label className="contract-field"><span>Contract type<small>अनुबंध प्रकार</small></span><select value={contractType} onChange={(event) => setContractType(event.target.value as ContractType)}>{catalog.map((item) => <option key={item.contract_type} value={item.contract_type}>{item.name_en}</option>)}</select></label>
            <label className="contract-field"><span>Counterparty<small>प्रतिपक्ष</small></span><input value={counterparty} onChange={(event) => setCounterparty(event.target.value)} placeholder="Optional" /></label>
            <label className="contract-field contract-field-wide"><span>Contract file<small>DOCX · PDF · TXT</small></span><input ref={fileRef} type="file" accept=".docx,.pdf,.txt" onChange={(event) => setFile(event.target.files?.[0] || null)} required /></label>
          </div>
          <div className="review-upload-foot"><span>Original file is preserved by SHA-256. No LLM call is needed for the baseline review.</span><button className="primary-button" disabled={loading}>{loading ? "Reviewing…" : "Run review"}</button></div>
        </form>
      )}

      {!uploadOpen && (
        <div className="review-grid">
          <div className="card review-list-card">
            <div className="card-header"><div><div className="card-title">Review queue</div><div className="card-subtitle">Counterparty files and negotiations</div></div></div>
            <div className="review-list">
              {reviews.map((item) => (
                <button key={item.id} type="button" className={`review-list-row${selected?.id === item.id ? " active" : ""}`} onClick={() => openReview(item.id)}>
                  <span className="contract-list-icon"><DocumentIcon /></span>
                  <span className="review-list-main"><strong>{item.title}</strong><small>{item.counterparty_name || item.source_filename}</small><em>{pretty(item.contract_type)} · {item.clause_count} clauses</em></span>
                  <span className="review-list-score"><strong>{item.health_score}</strong><small>health</small>{item.open_high_risks > 0 && <em>{item.open_high_risks} high</em>}</span>
                </button>
              ))}
              {reviews.length === 0 && <div className="empty-mini padded">No counterparty reviews yet.</div>}
            </div>
          </div>

          <div className="review-detail-column">
            {selected ? (
              <>
                <section className="card review-summary-card">
                  <div className="contract-detail-head">
                    <div><div className="eyebrow">{pretty(selected.contract_type)} · {selected.language}</div><h2>{selected.title}</h2><p>{selected.source_filename}{selected.counterparty_name ? ` · ${selected.counterparty_name}` : ""}</p></div>
                    <div className={`contract-health ${selected.health_score < 70 ? "warning" : ""}`}><strong>{selected.health_score}</strong><span>Review health</span></div>
                  </div>
                  <div className="contract-detail-meta"><span className={`contract-status ${selected.status}`}>{pretty(selected.status)}</span><span>{selected.clauses.length} clauses</span><span>{selected.findings.filter((item) => item.status === "open").length} open findings</span><span>SHA {selected.source_sha256.slice(0, 10)}…</span></div>
                  <div className="contract-actions"><button className="secondary-button" onClick={refreshAnalysis} disabled={loading}>Reanalyze</button><button className="primary-button" onClick={makeRedline} disabled={loading}>Generate redline</button></div>
                </section>

                <section className="card contract-risk-card">
                  <div className="card-header"><div><div className="card-title">Negotiation findings</div><div className="card-subtitle">Similarity is evidence for review—not an enforceability decision</div></div><div className="card-action">{selected.findings.length} findings</div></div>
                  <div className="contract-risk-list">
                    {selected.findings.map((finding) => (
                      <div className="contract-risk-row" key={finding.id}>
                        <span className={`risk-indicator ${finding.level}`} />
                        <div><div className="contract-risk-title"><strong>{finding.title}</strong><span className={`risk-level ${finding.level}`}>{finding.level}</span></div><p>{finding.explanation}</p><small>{finding.recommended_action}</small></div>
                        <div className="contract-risk-actions">{finding.status === "open" ? <><button onClick={() => setFinding(finding.id, "resolved")}>Resolve</button><button onClick={() => setFinding(finding.id, "accepted")}>Accept risk</button></> : <span className={`risk-status ${finding.status}`}>{finding.status}</span>}</div>
                      </div>
                    ))}
                    {selected.findings.length === 0 && <div className="empty-mini padded">No playbook deviations detected.</div>}
                  </div>
                </section>

                <section className="card review-clauses-card">
                  <div className="card-header"><div><div className="card-title">Clause-by-clause review</div><div className="card-subtitle">Counterparty text ↔ approved position</div></div><div className="card-action">{selected.clauses.length} sections</div></div>
                  <div className="review-clause-list">
                    {selected.clauses.map((clause) => (
                      <details className="review-clause" key={clause.id}>
                        <summary><span>{String(clause.position).padStart(2, "0")}</span><div><strong>{clause.heading || pretty(clause.clause_type)}</strong><small>{pretty(clause.clause_type)} · {Math.round(clause.similarity * 100)}% library similarity</small></div><em className={`deviation ${clause.deviation_status}`}>{clause.deviation_status}</em></summary>
                        <div className="review-clause-compare">
                          <div><span>Counterparty text</span><p>{clause.source_text}</p></div>
                          <div><span>Approved position</span><p>{clause.suggested_body_en || "No canonical clause matched. Lawyer classification required."}</p>{clause.suggested_body_hi && <p className="hindi-copy">{clause.suggested_body_hi}</p>}</div>
                        </div>
                        <div className="review-clause-actions">
                          <span>Decision: <strong>{clause.decision ? pretty(clause.decision) : "Not set"}</strong></span>
                          <div><button onClick={() => decide(clause.id, "keep")}>Keep</button>{clause.suggested_body_en && <button onClick={() => decide(clause.id, "replace")}>Replace</button>}<button onClick={() => decide(clause.id, "remove")}>Remove</button><button onClick={() => decide(clause.id, "accept_risk")}>Accept risk</button></div>
                        </div>
                      </details>
                    ))}
                  </div>
                </section>

                {selected.redlines.length > 0 && <section className="card redline-versions"><div className="card-header"><div><div className="card-title">Redline versions</div><div className="card-subtitle">Immutable negotiation packages</div></div></div>{[...selected.redlines].reverse().map((version) => <a key={version.id} href={contractRedlineDownloadUrl(selected.id, version.id)}><span>v{version.version_number}</span><div><strong>{version.generated_filename}</strong><small>{version.changes_json.length} clause decisions · SHA {version.sha256.slice(0, 10)}…</small></div><em>Download</em></a>)}</section>}
              </>
            ) : (
              <div className="card contract-empty-detail"><div className="contract-empty-mark"><DocumentIcon /></div><h2>Select a review</h2><p>Inspect deviations, compare approved wording, record negotiation decisions and generate a redline package.</p></div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
