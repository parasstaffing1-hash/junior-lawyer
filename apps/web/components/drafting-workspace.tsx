"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  approveLegalDraft,
  beginDraftReview,
  createLegalDraft,
  DraftCatalogItem,
  DraftContextPreview,
  DraftFindingStatus,
  DraftSection,
  getDraft,
  getDraftContext,
  legalDraftDownloadUrl,
  LegalDraft,
  LegalDraftLanguage,
  LegalDraftListItem,
  Matter,
  patchDraftFinding,
  patchDraftSection,
  regenerateLegalDraft,
  renderLegalDraft,
} from "@/lib/api";

function languageLabel(language: LegalDraftLanguage) {
  if (language === "hi") return "हिन्दी";
  if (language === "bilingual") return "English + हिन्दी";
  return "English";
}

function statusLabel(status: string) {
  return status.replaceAll("_", " ");
}

function typeLabel(type: string) {
  return type.replaceAll("_", " ");
}

function HealthRing({ score }: { score: number }) {
  return (
    <div className={`draft-health ${score >= 85 ? "good" : score >= 65 ? "warn" : "risk"}`}>
      <strong>{score}</strong><span>/100</span>
    </div>
  );
}

function ContextStrip({ context }: { context: DraftContextPreview | null }) {
  if (!context) return null;
  return (
    <div className="draft-context-strip">
      <div><span>Safe facts</span><strong>{context.safe_facts}</strong></div>
      <div><span>Timeline</span><strong>{context.timeline_events}</strong></div>
      <div><span>Documents</span><strong>{context.documents}</strong></div>
      <div className={context.excluded_conflicting_facts ? "attention" : ""}>
        <span>Excluded conflicts</span><strong>{context.excluded_conflicting_facts}</strong>
      </div>
    </div>
  );
}

function DraftSectionEditor({
  draft,
  section,
  onChange,
}: {
  draft: LegalDraft;
  section: DraftSection;
  onChange: (draft: LegalDraft) => void;
}) {
  const [english, setEnglish] = useState(section.body_en);
  const [hindi, setHindi] = useState(section.body_hi ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setEnglish(section.body_en);
    setHindi(section.body_hi ?? "");
  }, [section.id, section.body_en, section.body_hi]);

  async function saveText() {
    setSaving(true); setError("");
    try {
      onChange(await patchDraftSection(draft.id, section.id, {
        body_en: english,
        body_hi: hindi || null,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save section");
    } finally { setSaving(false); }
  }

  async function toggleReviewed() {
    setSaving(true); setError("");
    try {
      onChange(await patchDraftSection(draft.id, section.id, { reviewed: !section.reviewed }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update review status");
    } finally { setSaving(false); }
  }

  return (
    <article className={`draft-section-card${section.reviewed ? " reviewed" : ""}`}>
      <div className="draft-section-head">
        <div>
          <div className="draft-section-number">{String(section.position).padStart(2, "0")}</div>
          <h3>{section.title_en}</h3>
          {section.title_hi ? <div className="draft-hindi-title">{section.title_hi}</div> : null}
        </div>
        <div className="draft-section-actions">
          <span className={`draft-source-pill ${section.source}`}>{section.source}</span>
          <button className={`review-check${section.reviewed ? " checked" : ""}`} onClick={toggleReviewed} disabled={saving} type="button">
            {section.reviewed ? "Reviewed ✓" : "Mark reviewed"}
          </button>
        </div>
      </div>

      {draft.language !== "hi" ? (
        <label className="draft-editor-label">English
          <textarea className="draft-editor" value={english} onChange={(event) => setEnglish(event.target.value)} rows={Math.max(5, Math.min(15, english.split("\n").length + 3))} />
        </label>
      ) : null}
      {draft.language !== "en" ? (
        <label className="draft-editor-label">हिन्दी
          <textarea className="draft-editor hindi" value={hindi} onChange={(event) => setHindi(event.target.value)} rows={Math.max(5, Math.min(15, hindi.split("\n").length + 3))} />
        </label>
      ) : null}

      <div className="draft-section-footer">
        <div className="source-stack">
          {(section.sources ?? []).length ? (section.sources ?? []).slice(0, 4).map((source) => (
            <div className="source-chip" key={source.id} title={source.excerpt ?? undefined}>
              <span>{source.verified ? "✓" : "!"}</span>{source.label}{source.locator ? ` · ${source.locator}` : ""}
            </div>
          )) : <span className="quiet-text">No automatic source attached to this section.</span>}
        </div>
        <button className="button secondary small" onClick={saveText} disabled={saving} type="button">{saving ? "Saving…" : "Save section"}</button>
      </div>
      {error ? <div className="inline-error">{error}</div> : null}
    </article>
  );
}

export function DraftingWorkspace({
  matters,
  catalog,
  initialDrafts,
  initialDraftId,
}: {
  matters: Matter[];
  catalog: DraftCatalogItem[];
  initialDrafts: LegalDraftListItem[];
  initialDraftId?: string;
}) {
  const [drafts, setDrafts] = useState(initialDrafts);
  const [current, setCurrent] = useState<LegalDraft | null>(null);
  const [matterId, setMatterId] = useState(matters[0]?.id ?? "");
  const [draftType, setDraftType] = useState(catalog[0]?.draft_type ?? "legal_notice");
  const [language, setLanguage] = useState<LegalDraftLanguage>("bilingual");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [context, setContext] = useState<DraftContextPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const definition = useMemo(() => catalog.find((item) => item.draft_type === draftType) ?? catalog[0], [catalog, draftType]);

  useEffect(() => {
    if (!matterId) return;
    getDraftContext(matterId).then(setContext).catch(() => setContext(null));
  }, [matterId]);

  useEffect(() => {
    if (!initialDraftId) return;
    getDraft(initialDraftId).then(setCurrent).catch(() => undefined);
  }, [initialDraftId]);

  function syncDraft(updated: LegalDraft) {
    setCurrent(updated);
    setDrafts((items) => items.map((item) => item.id === updated.id ? {
      ...item,
      title: updated.title,
      status: updated.status,
      health_score: updated.health_score,
      open_high_findings: (updated.findings ?? []).filter((finding) => finding.level === "high" && finding.status === "open").length,
      reviewed_sections: (updated.sections ?? []).filter((section) => section.reviewed).length,
      section_count: (updated.sections ?? []).length,
      updated_at: updated.updated_at,
    } : item));
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    if (!matterId || !definition) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const draft = await createLegalDraft({
        matter_id: matterId,
        draft_type: draftType,
        language,
        questionnaire_json: answers,
      });
      setCurrent(draft);
      const matter = matters.find((item) => item.id === matterId);
      setDrafts((items) => [{
        id: draft.id,
        matter_id: draft.matter_id,
        matter_title: matter?.title ?? "Matter",
        title: draft.title,
        draft_type: draft.draft_type,
        language: draft.language,
        status: draft.status,
        health_score: draft.health_score,
        open_high_findings: (draft.findings ?? []).filter((finding) => finding.level === "high" && finding.status === "open").length,
        reviewed_sections: 0,
        section_count: (draft.sections ?? []).length,
        updated_at: draft.updated_at,
      }, ...items]);
      setMessage("Source-backed draft created. Review every section before approval.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create draft");
    } finally { setBusy(false); }
  }

  async function openDraft(id: string) {
    setBusy(true); setError("");
    try { setCurrent(await getDraft(id)); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to load draft"); }
    finally { setBusy(false); }
  }

  async function updateFinding(findingId: string, status: DraftFindingStatus) {
    if (!current) return;
    setBusy(true); setError("");
    try { syncDraft(await patchDraftFinding(current.id, findingId, status)); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to update finding"); }
    finally { setBusy(false); }
  }

  async function regenerate() {
    if (!current) return;
    setBusy(true); setError(""); setMessage("");
    try {
      syncDraft(await regenerateLegalDraft(current.id));
      setMessage("Unlocked deterministic sections rebuilt from the latest matter record.");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to regenerate draft"); }
    finally { setBusy(false); }
  }

  async function render() {
    if (!current) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await renderLegalDraft(current.id);
      syncDraft(result.draft);
      setMessage(`Review DOCX v${result.version.version_number} generated.`);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to render DOCX"); }
    finally { setBusy(false); }
  }

  async function review() {
    if (!current) return;
    setBusy(true); setError("");
    try { syncDraft(await beginDraftReview(current.id)); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to start review"); }
    finally { setBusy(false); }
  }

  async function approve() {
    if (!current) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await approveLegalDraft(current.id);
      syncDraft(result.draft);
      setMessage(`Approved DOCX v${result.version.version_number} generated.`);
    } catch (err) { setError(err instanceof Error ? err.message : "Approval blocked"); }
    finally { setBusy(false); }
  }

  return (
    <div className="drafting-workspace">
      <section className="draft-builder card">
        <div className="card-header">
          <div><div className="card-title">New source-backed draft</div><p className="draft-builder-copy">Structure, facts, chronology and annexures are deterministic. Counsel controls legal positions and final approval.</p></div>
          <span className="zero-ai-pill">Default AI cost · ₹0</span>
        </div>
        <form onSubmit={create}>
          <div className="draft-builder-grid">
            <label>Matter
              <select value={matterId} onChange={(event) => setMatterId(event.target.value)} required>
                {matters.map((matter) => <option value={matter.id} key={matter.id}>{matter.title}</option>)}
              </select>
            </label>
            <label>Work product
              <select value={draftType} onChange={(event) => { setDraftType(event.target.value as typeof draftType); setAnswers({}); }}>
                {catalog.map((item) => <option value={item.draft_type} key={item.draft_type}>{item.name_en} · {item.name_hi}</option>)}
              </select>
            </label>
            <label>Output language
              <select value={language} onChange={(event) => setLanguage(event.target.value as LegalDraftLanguage)}>
                <option value="en">English</option><option value="hi">हिन्दी</option><option value="bilingual">English + हिन्दी</option>
              </select>
            </label>
          </div>
          <ContextStrip context={context} />
          {definition ? <div className="draft-question-grid">
            {definition.questions.map((question) => (
              <label className={question.kind === "textarea" ? "wide" : ""} key={question.key}>
                {language === "hi" ? question.label_hi : `${question.label_en}${language === "bilingual" ? ` · ${question.label_hi}` : ""}`}
                {question.kind === "textarea" ? (
                  <textarea rows={3} required={question.required} value={answers[question.key] ?? ""} onChange={(event) => setAnswers((old) => ({ ...old, [question.key]: event.target.value }))} />
                ) : (
                  <input type={question.kind === "number" ? "number" : question.kind === "date" ? "date" : "text"} required={question.required} value={answers[question.key] ?? ""} onChange={(event) => setAnswers((old) => ({ ...old, [question.key]: event.target.value }))} />
                )}
              </label>
            ))}
          </div> : null}
          <div className="draft-builder-footer">
            <div><strong>{definition?.name_en}</strong><span>{definition?.section_count ?? 0} structured sections</span></div>
            <button className="button primary" disabled={busy || !matterId} type="submit">{busy ? "Building…" : "Create draft"}</button>
          </div>
        </form>
      </section>

      {message ? <div className="success-panel">{message}</div> : null}
      {error ? <div className="notice-panel"><span>{error}</span></div> : null}

      <div className="drafting-main-grid">
        <aside className="draft-list-panel card">
          <div className="card-header"><div className="card-title">Drafts</div><div className="card-action">{drafts.length}</div></div>
          <div className="draft-list">
            {drafts.map((draft) => (
              <button className={`draft-list-item${current?.id === draft.id ? " active" : ""}`} onClick={() => openDraft(draft.id)} key={draft.id} type="button">
                <div className="draft-list-top"><span>{typeLabel(draft.draft_type)}</span><span className={`status-dot ${draft.status}`} /></div>
                <strong>{draft.title}</strong>
                <small>{draft.matter_title}</small>
                <div className="draft-list-meta"><span>{draft.health_score}/100</span><span>{draft.reviewed_sections}/{draft.section_count} reviewed</span></div>
              </button>
            ))}
            {!drafts.length ? <div className="empty-mini padded">No drafts yet.</div> : null}
          </div>
        </aside>

        <section className="draft-desk">
          {current ? (
            <>
              <div className="draft-desk-header card">
                <div>
                  <div className="eyebrow">{typeLabel(current.draft_type)} · {languageLabel(current.language)}</div>
                  <h2>{current.title}</h2>
                  <p>{[current.court_name, current.case_number].filter(Boolean).join(" · ") || "Matter-backed work product"}</p>
                </div>
                <div className="draft-desk-score"><HealthRing score={current.health_score} /><span className={`draft-status ${current.status}`}>{statusLabel(current.status)}</span></div>
              </div>

              <div className="draft-toolbar card">
                <button className="button secondary small" onClick={regenerate} disabled={busy} type="button">Rebuild from matter</button>
                <button className="button secondary small" onClick={review} disabled={busy || current.status === "approved"} type="button">Start review</button>
                <button className="button secondary small" onClick={render} disabled={busy} type="button">Generate DOCX</button>
                {current.generated_filename ? <a className="button secondary small" href={legalDraftDownloadUrl(current.id)}>Download DOCX</a> : null}
                <button className="button primary small" onClick={approve} disabled={busy || current.status === "approved"} type="button">Approve</button>
              </div>

              {(current.findings ?? []).length ? <section className="draft-findings card">
                <div className="card-header"><div className="card-title">Draft checks</div><div className="card-action">{(current.findings ?? []).filter((item) => item.status === "open").length} open</div></div>
                <div className="draft-finding-grid">
                  {(current.findings ?? []).map((finding) => (
                    <article className={`draft-finding ${finding.level} ${finding.status}`} key={finding.id}>
                      <div><span className={`severity-badge ${finding.level}`}>{finding.level}</span><span className="finding-status">{finding.status}</span></div>
                      <strong>{finding.title}</strong><p>{finding.explanation}</p>
                      {finding.status === "open" ? <div className="finding-actions">
                        <button onClick={() => updateFinding(finding.id, "resolved")} type="button">Resolve</button>
                        <button onClick={() => updateFinding(finding.id, "accepted")} type="button">Accept for review</button>
                      </div> : null}
                    </article>
                  ))}
                </div>
              </section> : null}

              <div className="draft-section-stack">
                {(current.sections ?? []).map((section) => <DraftSectionEditor draft={current} section={section} onChange={syncDraft} key={section.id} />)}
              </div>
            </>
          ) : (
            <div className="card drafting-empty">
              <div className="drafting-empty-mark">JL</div><h2>Drafting desk</h2>
              <p>Create a draft above or open an existing work product. The desk keeps source evidence beside every deterministic section.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
