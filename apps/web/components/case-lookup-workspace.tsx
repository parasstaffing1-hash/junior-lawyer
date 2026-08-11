"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { getSavedCases, saveCaseCandidate, searchCases, type CaseCandidate, type SavedCaseSummary } from "@/lib/api";

function CaseCard({ candidate, onSave }: { candidate: CaseCandidate; onSave:(id:string)=>void }) {
  const record=candidate.case_record;
  return <article className="case-result-card"><div className="case-result-main"><div className="case-result-title">{record.case_title || `${record.case_type || "Case"} ${record.case_number}/${record.year || ""}`}</div><div className="case-result-ref">{[record.case_type, record.case_number+(record.year?`/${record.year}`:""), record.cnr].filter(Boolean).join(" · ")}</div><p>{[record.court_name, record.district, record.state].filter(Boolean).join(", ")}</p></div><div className="case-result-side"><span className={candidate.exact_match?"verified-badge":"quiet-badge"}>{candidate.exact_match?"exact match":`${candidate.rank_score}% match`}</span>{candidate.saved_case_id ? <Link className="button secondary small" href={`/cases/${candidate.saved_case_id}`}>Open case</Link> : <button className="button secondary small" type="button" onClick={()=>onSave(candidate.id)}>Save case</button>}</div></article>;
}

export function CaseLookupWorkspace() {
  const [query,setQuery]=useState(""); const [saved,setSaved]=useState<SavedCaseSummary[]>([]); const [candidates,setCandidates]=useState<CaseCandidate[]>([]); const [message,setMessage]=useState(""); const [busy,setBusy]=useState(false);
  useEffect(()=>{getSavedCases().then(setSaved).catch(()=>{});},[]);
  async function submit(e:FormEvent){e.preventDefault(); if(!query.trim())return; setBusy(true); try{const result=await searchCases(query);setCandidates(result.candidates);setMessage(result.message||"");}catch(err){setMessage(err instanceof Error?err.message:"Search failed");}finally{setBusy(false);}}
  async function save(id:string){const row=await saveCaseCandidate(id); setSaved((rows)=>[row,...rows.filter(r=>r.id!==row.id)]);}
  return <main className="page"><div className="eyebrow">Court records</div><h1 className="page-title">Search Case</h1><p className="page-subtitle">Enter an exact CNR or a case type/number/year. Saved court/location preferences rank ambiguous results without hiding other matches.</p>
    <form className="case-search-box" onSubmit={submit}><input aria-label="Case number or CNR" placeholder="CS 234/2025 or UPLU010012342024" value={query} onChange={(e)=>setQuery(e.target.value)}/><button className="button primary" disabled={busy}>{busy?"Searching…":"Search"}</button></form>
    {message?<div className="notice-panel"><span>{message}</span></div>:null}
    {candidates.length?<section className="card"><div className="card-header"><div className="card-title">{candidates.length} matching case{candidates.length===1?"":"s"}</div></div><div className="case-result-list">{candidates.map(c=><CaseCard candidate={c} onSave={save} key={c.id}/>)}</div></section>:null}
    <section className="card" style={{marginTop:18}}><div className="card-header"><div className="card-title">My Cases</div><div className="card-action">Cache-first · refresh from official source when required</div></div>{saved.length?<div className="case-saved-grid">{saved.map(row=><Link className="saved-case-card" href={`/cases/${row.id}`} key={row.id}><div><strong>{row.case_title||`${row.case_type||"Case"} ${row.case_number}`}</strong><span>{row.cnr||`${row.case_type||""} ${row.case_number}/${row.year||""}`}</span></div><div><span className="quiet-badge">{row.case_status||"status unknown"}</span><span>{row.next_hearing_date?`Next ${row.next_hearing_date}`:"No next hearing"}</span></div></Link>)}</div>:<div className="empty-state compact"><div className="empty-state-title">No saved cases yet</div><div className="empty-state-copy">Search/import an official result and save it here for instant cached lookup plus deterministic change tracking.</div></div>}</section>
  </main>;
}
