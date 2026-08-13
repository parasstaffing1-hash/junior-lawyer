"use client";

import { FormEvent, useMemo, useState } from "react";
import { DocumentIcon, PlusIcon } from "@/components/icons";
import {
  approveContract,
  ContractCatalogItem,
  ContractDetail,
  ContractLanguage,
  ContractListItem,
  ContractQuestion,
  ContractQuestionnaire,
  ContractRiskProfile,
  ContractRiskStatus,
  ContractType,
  contractDownloadUrl,
  createContract,
  draftContract,
  getContract,
  getContractQuestionnaire,
  reviewContract,
  updateContractRisk,
} from "@/lib/api";

function typeLabel(value: ContractType) {
  return value.split("_").map((part) => part[0]?.toUpperCase() + part.slice(1)).join(" ");
}

function detailToList(contract: ContractDetail): ContractListItem {
  return {
    id: contract.id,
    title: contract.title,
    contract_type: contract.contract_type,
    language: contract.language,
    status: contract.status,
    risk_profile: contract.risk_profile,
    party_a_name: contract.party_a_name,
    party_b_name: contract.party_b_name,
    health_score: contract.health_score,
    clause_count: (contract.clauses ?? []).length,
    open_high_risks: (contract.risks ?? []).filter((risk) => risk.level === "high" && risk.status === "open").length,
    updated_at: contract.updated_at,
  };
}

function languageLabel(value: ContractLanguage) {
  if (value === "hi") return "हिन्दी";
  if (value === "bilingual") return "EN + हिन्दी";
  return "English";
}

function AnswerField({
  question,
  value,
  onChange,
}: {
  question: ContractQuestion;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const id = `contract-${question.key}`;
  if (question.kind === "boolean") {
    return (
      <label className="contract-toggle-field" htmlFor={id}>
        <span><strong>{question.label_en}</strong><small>{question.label_hi}</small></span>
        <input id={id} type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} />
      </label>
    );
  }
  if (question.kind === "select") {
    return (
      <label className="contract-field" htmlFor={id}>
        <span>{question.label_en}<small>{question.label_hi}</small></span>
        <select id={id} value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} required={question.required}>
          <option value="">Select</option>
          {(question.options ?? []).map((option) => <option key={option.value} value={option.value}>{option.label_en} · {option.label_hi}</option>)}
        </select>
      </label>
    );
  }
  if (question.kind === "textarea") {
    return (
      <label className="contract-field contract-field-wide" htmlFor={id}>
        <span>{question.label_en}<small>{question.label_hi}</small></span>
        <textarea id={id} rows={4} value={String(value ?? "")} placeholder={question.placeholder ?? ""} onChange={(event) => onChange(event.target.value)} required={question.required} />
      </label>
    );
  }
  return (
    <label className="contract-field" htmlFor={id}>
      <span>{question.label_en}<small>{question.label_hi}</small></span>
      <input
        id={id}
        type={question.kind === "number" ? "number" : question.kind === "date" ? "date" : "text"}
        value={String(value ?? "")}
        placeholder={question.placeholder ?? ""}
        onChange={(event) => onChange(question.kind === "number" ? (event.target.value === "" ? "" : Number(event.target.value)) : event.target.value)}
        required={question.required}
      />
    </label>
  );
}

export function ContractWorkspace({
  initialCatalog,
  initialContracts,
}: {
  initialCatalog: ContractCatalogItem[];
  initialContracts: ContractListItem[];
}) {
  const [catalog] = useState(initialCatalog);
  const [contracts, setContracts] = useState(initialContracts);
  const [selected, setSelected] = useState<ContractDetail | null>(null);
  const [builderOpen, setBuilderOpen] = useState(false);
  const [questionnaire, setQuestionnaire] = useState<ContractQuestionnaire | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [title, setTitle] = useState("");
  const [partyA, setPartyA] = useState("");
  const [partyB, setPartyB] = useState("");
  const [language, setLanguage] = useState<ContractLanguage>("en");
  const [riskProfile, setRiskProfile] = useState<ContractRiskProfile>("balanced");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const metrics = useMemo(() => ({
    total: contracts.length,
    review: contracts.filter((item) => item.status === "in_review").length,
    high: contracts.reduce((sum, item) => sum + item.open_high_risks, 0),
    approved: contracts.filter((item) => item.status === "approved").length,
  }), [contracts]);

  async function chooseType(type: ContractType) {
    setLoading(true);
    setMessage(null);
    try {
      const form = await getContractQuestionnaire(type);
      const initial: Record<string, unknown> = {};
      for (const question of form.questions) {
        if (question.default !== null && question.default !== undefined) initial[question.key] = question.default;
      }
      setQuestionnaire(form);
      setAnswers(initial);
      setTitle(form.name_en);
      setBuilderOpen(true);
      setSelected(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load contract playbook");
    } finally {
      setLoading(false);
    }
  }

  async function openContract(contractId: string) {
    setLoading(true);
    setMessage(null);
    try {
      setSelected(await getContract(contractId));
      setBuilderOpen(false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load contract");
    } finally {
      setLoading(false);
    }
  }

  function syncList(contract: ContractDetail) {
    setContracts((current) => {
      const next = [detailToList(contract), ...current.filter((item) => item.id !== contract.id)];
      return next;
    });
  }

  async function createDraft(event: FormEvent) {
    event.preventDefault();
    if (!questionnaire) return;
    setLoading(true);
    setMessage(null);
    try {
      const effectiveDate = typeof answers.effective_date === "string" && answers.effective_date ? answers.effective_date : null;
      const governingState = typeof answers.governing_state === "string" && answers.governing_state ? answers.governing_state : null;
      const created = await createContract({
        title,
        contract_type: questionnaire.contract_type,
        language,
        risk_profile: riskProfile,
        jurisdiction: "India",
        governing_state: governingState,
        party_a_name: partyA,
        party_b_name: partyB,
        effective_date: effectiveDate,
        questionnaire_json: answers,
      });
      const result = await draftContract(created.id);
      setSelected(result.contract);
      syncList(result.contract);
      setBuilderOpen(false);
      setMessage(`Draft v${result.version.version_number} generated locally as DOCX.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to create contract draft");
    } finally {
      setLoading(false);
    }
  }

  async function runReview() {
    if (!selected) return;
    setLoading(true);
    setMessage(null);
    try {
      const updated = await reviewContract(selected.id);
      setSelected(updated);
      syncList(updated);
      setMessage("Deterministic playbook review refreshed.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Review failed");
    } finally {
      setLoading(false);
    }
  }

  async function setRiskStatus(riskId: string, status: ContractRiskStatus) {
    if (!selected) return;
    setLoading(true);
    setMessage(null);
    try {
      const updated = await updateContractRisk(selected.id, riskId, status);
      setSelected(updated);
      syncList(updated);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Risk update failed");
    } finally {
      setLoading(false);
    }
  }

  async function approve() {
    if (!selected) return;
    setLoading(true);
    setMessage(null);
    try {
      const result = await approveContract(selected.id);
      setSelected(result.contract);
      syncList(result.contract);
      setMessage(`Lawyer-approved version v${result.version.version_number} generated.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Approval failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <section className="contract-metrics">
        <div><span>Contracts</span><strong>{metrics.total}</strong></div>
        <div><span>In review</span><strong>{metrics.review}</strong></div>
        <div><span>Open high risks</span><strong>{metrics.high}</strong></div>
        <div><span>Approved</span><strong>{metrics.approved}</strong></div>
      </section>

      {message && <div className="contract-message">{message}</div>}

      {builderOpen && questionnaire ? (
        <section className="contract-builder card">
          <div className="contract-builder-head">
            <div>
              <div className="eyebrow">New deterministic draft</div>
              <h2>{questionnaire.name_en}</h2>
              <p>{questionnaire.name_hi} · {questionnaire.description}</p>
            </div>
            <button className="text-button" type="button" onClick={() => setBuilderOpen(false)}>Close</button>
          </div>
          <form onSubmit={createDraft}>
            <div className="contract-form-section">
              <div className="contract-form-section-title"><span>01</span><div><strong>Draft setup</strong><small>Document identity and drafting posture</small></div></div>
              <div className="contract-form-grid">
                <label className="contract-field contract-field-wide"><span>Contract title<small>अनुबंध शीर्षक</small></span><input value={title} onChange={(event) => setTitle(event.target.value)} required /></label>
                <label className="contract-field"><span>Party A<small>पक्ष A</small></span><input value={partyA} onChange={(event) => setPartyA(event.target.value)} required /></label>
                <label className="contract-field"><span>Party B<small>पक्ष B</small></span><input value={partyB} onChange={(event) => setPartyB(event.target.value)} required /></label>
                <label className="contract-field"><span>Output language<small>आउटपुट भाषा</small></span><select value={language} onChange={(event) => setLanguage(event.target.value as ContractLanguage)}><option value="en">English</option><option value="hi">हिन्दी</option><option value="bilingual">English + हिन्दी</option></select></label>
                <label className="contract-field"><span>Drafting posture<small>ड्राफ्टिंग स्थिति</small></span><select value={riskProfile} onChange={(event) => setRiskProfile(event.target.value as ContractRiskProfile)}><option value="balanced">Balanced</option><option value="pro_party_a">Protect Party A</option><option value="pro_party_b">Protect Party B</option></select></label>
              </div>
            </div>
            <div className="contract-form-section">
              <div className="contract-form-section-title"><span>02</span><div><strong>Commercial terms</strong><small>These answers drive clause selection and risk checks</small></div></div>
              <div className="contract-form-grid">
                {questionnaire.questions.map((question) => (
                  <AnswerField key={question.key} question={question} value={answers[question.key]} onChange={(value) => setAnswers((current) => ({ ...current, [question.key]: value }))} />
                ))}
              </div>
            </div>
            <div className="contract-builder-footer">
              <div><strong>{questionnaire.default_clauses.length}</strong><span>clauses selected by playbook</span></div>
              <button className="primary-button" disabled={loading}>{loading ? "Generating…" : "Generate contract"}</button>
            </div>
          </form>
        </section>
      ) : (
        <section className="contract-type-strip">
          <div className="contract-type-strip-head"><div><div className="eyebrow">Start a draft</div><h2>Choose a playbook</h2></div><span>English · हिन्दी · Bilingual</span></div>
          <div className="contract-type-grid">
            {catalog.map((item) => (
              <button key={item.contract_type} type="button" className="contract-type-card" onClick={() => chooseType(item.contract_type)} disabled={loading}>
                <span className="contract-type-icon"><DocumentIcon /></span>
                <strong>{item.name_en}</strong>
                <small>{item.name_hi}</small>
                <p>{item.description}</p>
                <span className="contract-type-action"><PlusIcon /> Draft</span>
              </button>
            ))}
            {catalog.length === 0 && <div className="contract-api-empty">Start the API to load the contract playbooks.</div>}
          </div>
        </section>
      )}

      {!builderOpen && (
        <section className="contract-workspace-grid">
          <div className="card contract-list-card">
            <div className="card-header"><div><div className="card-title">Contract workspace</div><div className="card-subtitle">Drafts and approved versions</div></div></div>
            <div className="contract-list">
              {contracts.map((contract) => (
                <button key={contract.id} className={`contract-list-row${selected?.id === contract.id ? " active" : ""}`} type="button" onClick={() => openContract(contract.id)}>
                  <div className="contract-list-icon"><DocumentIcon /></div>
                  <div className="contract-list-main"><strong>{contract.title}</strong><span>{contract.party_a_name} ↔ {contract.party_b_name}</span><small>{typeLabel(contract.contract_type)} · {languageLabel(contract.language)}</small></div>
                  <div className="contract-list-score"><strong>{contract.health_score}</strong><span>health</span>{contract.open_high_risks > 0 && <em>{contract.open_high_risks} high</em>}</div>
                </button>
              ))}
              {contracts.length === 0 && <div className="empty-mini padded">No contracts yet. Choose a playbook above to create the first deterministic draft.</div>}
            </div>
          </div>

          <div className="contract-detail-column">
            {selected ? (
              <>
                <section className="card contract-detail-card">
                  <div className="contract-detail-head">
                    <div><div className="eyebrow">{typeLabel(selected.contract_type)}</div><h2>{selected.title}</h2><p>{selected.party_a_name} ↔ {selected.party_b_name}</p></div>
                    <div className={`contract-health ${selected.health_score < 70 ? "warning" : ""}`}><strong>{selected.health_score}</strong><span>Contract health</span></div>
                  </div>
                  <div className="contract-detail-meta">
                    <span className={`contract-status ${selected.status}`}>{selected.status.replace("_", " ")}</span>
                    <span>{languageLabel(selected.language)}</span>
                    <span>{selected.risk_profile.replaceAll("_", " ")}</span>
                    <span>{selected.governing_state || "State not set"}</span>
                  </div>
                  <div className="contract-actions">
                    <a className="secondary-button" href={contractDownloadUrl(selected.id)}>Download DOCX</a>
                    <button className="secondary-button" type="button" onClick={runReview} disabled={loading}>Run review</button>
                    <button className="primary-button" type="button" onClick={approve} disabled={loading || selected.status === "approved"}>{selected.status === "approved" ? "Approved" : "Approve"}</button>
                  </div>
                </section>

                <section className="card contract-risk-card">
                  <div className="card-header"><div><div className="card-title">Playbook review</div><div className="card-subtitle">Deterministic checks · no LLM call</div></div><div className="card-action">{(selected.risks ?? []).filter((risk) => risk.status === "open").length} open</div></div>
                  <div className="contract-risk-list">
                    {(selected.risks ?? []).map((risk) => (
                      <div className="contract-risk-row" key={risk.id}>
                        <span className={`risk-indicator ${risk.level}`} />
                        <div><div className="contract-risk-title"><strong>{risk.title}</strong><span className={`risk-level ${risk.level}`}>{risk.level}</span></div><p>{risk.explanation}</p><small>{risk.rule_code}</small></div>
                        <div className="contract-risk-actions">
                          {risk.status === "open" ? <><button type="button" onClick={() => setRiskStatus(risk.id, "resolved")}>Resolve</button><button type="button" onClick={() => setRiskStatus(risk.id, "ignored")}>Ignore</button></> : <span className={`risk-status ${risk.status}`}>{risk.status}</span>}
                        </div>
                      </div>
                    ))}
                    {(selected.risks ?? []).length === 0 && <div className="empty-mini padded">No playbook risks detected.</div>}
                  </div>
                </section>

                <section className="card contract-clauses-card">
                  <div className="card-header"><div><div className="card-title">Selected clauses</div><div className="card-subtitle">Canonical library IDs stay separate from language rendering</div></div><div className="card-action">{(selected.clauses ?? []).length} clauses</div></div>
                  <div className="contract-clause-list">
                    {(selected.clauses ?? []).map((clause, index) => (
                      <details key={clause.id} className="contract-clause-row">
                        <summary><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{clause.title_en}</strong><small>{clause.title_hi}</small></div><em>{clause.variant_key.replaceAll("_", " ")}</em></summary>
                        <div className="contract-clause-copy"><p>{clause.body_en}</p>{selected.language !== "en" && clause.body_hi && <p className="hindi-copy">{clause.body_hi}</p>}<code>{clause.clause_code}</code></div>
                      </details>
                    ))}
                  </div>
                </section>
              </>
            ) : (
              <div className="card contract-empty-detail"><div className="contract-empty-mark"><DocumentIcon /></div><h2>Select a contract</h2><p>Review its health score, clause variants, deterministic risks and generated DOCX here.</p></div>
            )}
          </div>
        </section>
      )}
    </>
  );
}
