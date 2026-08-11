"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { analyzeRemedies, createRemedyDraft, createRemedyMemo, getMatterRemedies, type RemedyAnalysis, type RemedyCandidate } from "@/lib/api";

function remedyLabels(language: string) {
  if (language === "hi") return { why:"यह क्यों लागू हो सकता है", forum:"उचित न्यायालय / मंच", deadline:"सीमा अवधि / समय-सीमा", maintainability:"पोषणीयता", documents:"आवश्यक दस्तावेज / साक्ष्य", risks:"जोखिम / शर्तें", steps:"अगले प्रक्रियात्मक कदम", authorities:"सत्यापित कानूनी प्राधिकार", memo:"विस्तृत उपचार ज्ञापन बनाएं", draft:"मसौदा बनाएं", matched:"मेल", noDeadline:"समय-सीमा का निर्धारण सत्यापित नियम/ट्रिगर से नहीं हो सका।", noChecks:"कोई मशीन-जांच योग्य शर्त कॉन्फ़िगर नहीं है।", noAuthority:"इस उम्मीदवार में सत्यापित प्राधिकार नहीं है; सत्यापन के बिना इस उपचार पर भरोसा न करें।" };
  if (language === "bilingual") return { why:"Why it may apply · क्यों लागू हो सकता है", forum:"Correct forum · उचित मंच", deadline:"Limitation / deadline · सीमा अवधि", maintainability:"Maintainability · पोषणीयता", documents:"Required documents / evidence · आवश्यक दस्तावेज", risks:"Risks / conditions · जोखिम", steps:"Procedural next steps · अगले कदम", authorities:"Verified authorities · सत्यापित प्राधिकार", memo:"Generate bilingual remedy memo", draft:"Create bilingual draft", matched:"match · मेल", noDeadline:"Not deterministically calculated · सत्यापित समय-सीमा की समीक्षा आवश्यक।", noChecks:"No machine-checkable prerequisites configured · समीक्षा आवश्यक।", noAuthority:"No verified authority copied into this candidate · सत्यापन के बिना भरोसा न करें।" };
  return { why:"Why it may apply", forum:"Correct forum", deadline:"Limitation / deadline", maintainability:"Maintainability", documents:"Required documents / evidence", risks:"Risks / conditions", steps:"Procedural next steps", authorities:"Verified legal authorities", memo:"Generate remedy memo", draft:"Create draft", matched:"match", noDeadline:"{t.noDeadline}", noChecks:"No machine-checkable prerequisites configured.", noAuthority:"No verified authority copied into this candidate. Do not rely on this remedy until the rule pack is completed." };
}

function pretty(value: unknown) {
  if (value == null) return "—";
  if (typeof value === "string" || typeof value === "number") return String(value);
  return JSON.stringify(value, null, 2);
}

function docKind(candidate: RemedyCandidate) {
  const value = `${candidate.remedy_code} ${candidate.remedy_name_en}`.toLowerCase();
  for (const key of ["appeal","revision","review","writ","quashing","bail","stay","injunction","execution","restoration","recall"]) if (value.includes(key)) return key;
  return "application";
}

function CandidateCard({ candidate, language }: { candidate: RemedyCandidate; language: string }) {
  const [memo, setMemo] = useState("");
  const [draftId, setDraftId] = useState<string | null>(null);
  const [busy, setBusy] = useState("");
  const maintainability = (candidate.maintainability_json.checks ?? []) as Array<Record<string, unknown>>;
  const deadline = candidate.deadline_json;
  const t = remedyLabels(language);
  async function memoAction() {
    setBusy("memo");
    try { const result = await createRemedyMemo(candidate.id, language === "hi" ? "hi" : language === "bilingual" ? "bilingual" : "en"); setMemo(result.content); } finally { setBusy(""); }
  }
  async function draftAction() {
    setBusy("draft");
    try { const result = await createRemedyDraft(candidate.id, docKind(candidate), language === "hi" ? "hi" : language === "bilingual" ? "bilingual" : "en"); setDraftId(result.legal_draft_id); } finally { setBusy(""); }
  }
  return <article className="remedy-card">
    <div className="remedy-head">
      <div><span className={`remedy-status ${candidate.status}`}>{candidate.status.replaceAll("_", " ")}</span><h3>{language === "hi" && candidate.remedy_name_hi ? candidate.remedy_name_hi : candidate.remedy_name_en}</h3></div>
      <div className="remedy-score"><strong>{candidate.applicability_score}</strong><span>{t.matched}</span></div>
    </div>
    <div className="remedy-grid">
      <section><h4>{t.why}</h4><ul>{candidate.why_applicable_json.map((item, i) => <li key={i}>{String(item)}</li>)}</ul></section>
      <section><h4>{t.forum}</h4><p className="pre-wrap">{pretty(candidate.forum_json)}</p></section>
      <section><h4>{t.deadline}</h4>{deadline.calculated ? <><strong>{String(deadline.due_date)}</strong><p>Trigger: {String(deadline.trigger_date ?? "—")} · {String(deadline.days ?? "—")} days</p></> : <p>{t.noDeadline}</p>}</section>
      <section><h4>{t.maintainability}</h4>{maintainability.length ? <ul>{maintainability.map((check, i) => <li key={i}><strong>{String(check.label ?? check.field)}</strong>: {check.passed === true ? "met" : check.passed === false ? "not met" : "needs review"}</li>)}</ul> : <p>{t.noChecks}</p>}</section>
      <section><h4>{t.documents}</h4><ul>{candidate.required_documents_json.map((item, i) => <li key={i}>{String(item.name ?? "Required document")} · {item.available ? "available" : "verify / obtain"}</li>)}</ul></section>
      <section><h4>{t.risks}</h4><ul>{candidate.risks_json.map((item, i) => <li key={i}>{String(item)}</li>)}</ul></section>
    </div>
    <section className="remedy-steps"><h4>{t.steps}</h4><ol>{candidate.procedural_steps_json.map((item, i) => <li key={i}>{String(item)}</li>)}</ol></section>
    <section className="remedy-authorities"><h4>{t.authorities}</h4>{candidate.authorities.length ? candidate.authorities.map((authority) => <div className="authority-row" key={authority.id}><div><strong>{authority.citation ?? authority.authority_type}</strong><p>{authority.proposition}</p></div>{authority.source_url ? <a href={authority.source_url} target="_blank" rel="noreferrer">Source ↗</a> : null}</div>) : <p className="quiet-text">{t.noAuthority}</p>}</section>
    <div className="remedy-actions">
      <button className="button secondary small" type="button" onClick={memoAction} disabled={!!busy}>{busy === "memo" ? "Generating…" : t.memo}</button>
      <button className="button primary small" type="button" onClick={draftAction} disabled={!!busy}>{busy === "draft" ? "Creating…" : `${t.draft} · ${docKind(candidate)}`}</button>
      {draftId ? <Link className="button secondary small" href={`/drafting?draft=${draftId}`}>Open draft</Link> : null}
    </div>
    {memo ? <div className="remedy-memo"><div className="card-header"><div className="card-title">Remedy memo</div><button className="text-button" onClick={()=>setMemo("")} type="button">Close</button></div><pre>{memo}</pre></div> : null}
  </article>;
}

export function RemedyWorkspace({ matterId, savedCaseId }: { matterId?: string; savedCaseId?: string }) {
  const [analyses, setAnalyses] = useState<RemedyAnalysis[]>([]);
  const [active, setActive] = useState<RemedyAnalysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [language, setLanguage] = useState("en");

  useEffect(() => { if (matterId) getMatterRemedies(matterId).then((rows)=>{setAnalyses(rows); setActive(rows[0] ?? null);}).catch(()=>{}); }, [matterId]);

  async function run() {
    setBusy(true); setError("");
    try { const result = await analyzeRemedies({matter_id:matterId, saved_case_id:savedCaseId, language}); setActive(result); setAnalyses((rows)=>[result, ...rows.filter((row)=>row.id!==result.id)]); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to analyze remedies"); }
    finally { setBusy(false); }
  }

  return <div className="remedy-workspace">
    <section className="card remedy-launch">
      <div><div className="eyebrow">Legal strategy</div><h2>Legal Remedy Analysis</h2><p>Deterministic rules, verified statutes/procedure and case posture first. AI is optional for complex comparison or wording after the source-backed analysis.</p></div>
      <div className="remedy-launch-actions"><select aria-label="Remedy analysis language" value={language} onChange={(e)=>setLanguage(e.target.value)}><option value="en">English</option><option value="hi">हिन्दी</option><option value="bilingual">English + हिन्दी</option><option value="hinglish">Hinglish input / English output</option></select><button className="button primary" type="button" disabled={busy} onClick={run}>{busy ? "Analyzing…" : "Find Legal Remedies"}</button></div>
    </section>
    {error ? <div className="notice-panel danger"><span>{error}</span></div> : null}
    {active ? <>
      {active.coverage_warnings.map((warning, i)=><div className="notice-panel warning" key={i}><span>{warning}</span></div>)}
      <section className="remedy-summary"><div><span>Remedies found</span><strong>{active.candidates.length}</strong></div><div><span>Analyzed</span><strong>{new Date(active.analyzed_at).toLocaleDateString("en-IN")}</strong></div><div><span>Sources</span><strong>{active.candidates.reduce((sum,c)=>sum+c.authorities.filter(a=>a.verified).length,0)}</strong></div></section>
      {active.candidates.length ? <div className="remedy-list">{active.candidates.map((candidate)=><CandidateCard candidate={candidate} language={language} key={candidate.id}/>)}</div> : <section className="card"><div className="empty-state"><div className="empty-state-title">No supported remedy asserted</div><div className="empty-state-copy">The current verified rule packs do not establish a remedy for this posture. Junior Lawyer is intentionally not inventing one. Review the research prompts/coverage and add a verified jurisdiction rule pack.</div>{Array.isArray(active.context_json.research_hints) ? <ul className="research-hints">{(active.context_json.research_hints as Array<Record<string,string>>).map((item)=><li key={item.code}><strong>{item.name_en}</strong><span>{item.reason}</span></li>)}</ul> : null}</div></section>}
      <p className="remedy-disclaimer">{active.disclaimer}</p>
    </> : analyses.length ? <button className="text-button" onClick={()=>setActive(analyses[0])}>Open latest analysis</button> : null}
  </div>;
}
