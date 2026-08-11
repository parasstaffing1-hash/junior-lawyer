"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getQADashboard, getQARun, getQASuite, runQASuite, seedQASuite, type QADashboardRecord, type QARunDetail, type QASuiteDetail } from "@/lib/api";
import { ShieldIcon, PulseIcon, BookIcon } from "@/components/icons";

type Tab="release"|"cases"|"history";
const nice=(value:string)=>value.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());
const pct=(value:number|null|undefined)=>value===null||value===undefined?"—":`${Math.round(value*100)}%`;
const dateText=(v:string|null|undefined)=>v?new Intl.DateTimeFormat("en-IN",{dateStyle:"medium",timeStyle:"short"}).format(new Date(v)):"—";

export function QAWorkspace(){
  const [tab,setTab]=useState<Tab>("release");
  const [data,setData]=useState<QADashboardRecord|null>(null);
  const [suite,setSuite]=useState<QASuiteDetail|null>(null);
  const [runDetail,setRunDetail]=useState<QARunDetail|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const [message,setMessage]=useState<string|null>(null);

  const refresh=useCallback(async()=>{try{const next=await getQADashboard();setData(next);setError(null);const selected=next.suites.find(s=>s.default_gate)||next.suites[0];if(selected)setSuite(await getQASuite(selected.id));if(next.latest_runs[0])setRunDetail(await getQARun(next.latest_runs[0].id));}catch(e){setError(e instanceof Error?e.message:"Unable to load QA workspace")}},[]);
  useEffect(()=>{void refresh()},[refresh]);
  const latest=data?.latest_runs[0]??null;
  const categories=useMemo(()=>data?.latest_gate_result?.category_scores??{},[data]);
  const gatePass=data?.latest_gate_result?.passed??false;

  async function seed(){setBusy(true);setMessage(null);try{await seedQASuite();setMessage("Core bilingual legal release suite created.");await refresh()}catch(e){setError(e instanceof Error?e.message:"Unable to seed QA suite")}finally{setBusy(false)}}
  async function run(){const selected=data?.suites.find(s=>s.default_gate)||data?.suites[0];if(!selected)return;setBusy(true);setMessage(null);try{const result=await runQASuite(selected.id,"manual-ui");setMessage(result.status==="passed"?"Release gate passed.":"Release gate failed. Review failing golden cases before release.");await refresh()}catch(e){setError(e instanceof Error?e.message:"Evaluation run failed")}finally{setBusy(false)}}
  async function openRun(id:string){try{setRunDetail(await getQARun(id));setTab("release")}catch(e){setError(e instanceof Error?e.message:"Unable to load evaluation run")}}

  return <main className="page qa-page">
    <header className="search-header"><div><div className="eyebrow">Release quality & legal accuracy</div><h1>Quality assurance</h1><p>Golden legal cases, bilingual accuracy checks, citation/security gates and reproducible release evidence. These tests measure software behaviour—not legal outcomes.</p></div><div className="health-header-actions">{!data?.suites.length?<button className="secondary-button" onClick={()=>void seed()} disabled={busy}>Create core suite</button>:null}<button className="primary-button" onClick={()=>void run()} disabled={busy||!data?.suites.length}><PulseIcon/> Run release gate</button></div></header>
    {error?<div className="alert error">{error}</div>:null}{message?<div className="jobs-message">{message}</div>:null}
    <section className="metrics">
      <div className="metric"><div className="metric-label">Release gate</div><div className={`metric-value health-word ${gatePass?"healthy":"degraded"}`}>{latest?gatePass?"PASS":"HOLD":"Not run"}</div><div className="metric-note">critical gates cannot be averaged away</div></div>
      <div className="metric"><div className="metric-label">Overall score</div><div className="metric-value">{pct(latest?.overall_score)}</div><div className="metric-note">minimum {pct(data?.default_gate?.min_overall_score)}</div></div>
      <div className="metric"><div className="metric-label">Golden cases</div><div className="metric-value">{latest?.total_cases??suite?.cases.length??0}</div><div className="metric-note">{latest?`${latest.passed_cases} passed · ${latest.failed_cases} failed`:"ready for first run"}</div></div>
      <div className="metric"><div className="metric-label">Critical failures</div><div className="metric-value">{latest?.critical_failures??0}</div><div className="metric-note">allowed {data?.default_gate?.max_critical_failures??0}</div></div>
    </section>
    <div className="workspace-tabs"><button className={tab==="release"?"active":""} onClick={()=>setTab("release")}>Release</button><button className={tab==="cases"?"active":""} onClick={()=>setTab("cases")}>Golden cases</button><button className={tab==="history"?"active":""} onClick={()=>setTab("history")}>History</button></div>

    {tab==="release"?<div className="health-layout">
      <section className="premium-panel"><div className="panel-title-row"><h2>Category gates</h2><span>{Object.keys(categories).length} measured</span></div>{Object.keys(categories).length?Object.entries(categories).sort().map(([category,score])=><div className="health-component-row" key={category}><span className={`health-dot ${score>=0.95?"healthy":"degraded"}`}></span><div><strong>{nice(category)}</strong><small>Deterministic golden benchmark</small></div><div className="health-component-meta"><strong>{pct(score)}</strong><small>{["security","citation"].includes(category)?"zero-failure gate":"weighted score"}</small></div></div>):<div className="empty-state compact"><ShieldIcon/><div className="empty-state-title">No release evidence yet</div><div className="empty-state-copy">Run the core suite to establish a reproducible baseline.</div></div>}</section>
      <section className="premium-panel"><div className="panel-title-row"><h2>Latest findings</h2><span>{runDetail?.findings.length??0}</span></div>{runDetail?.findings.length?runDetail.findings.map(f=><div className="incident-card" key={f.id}><div className="incident-card-head"><span className={`health-dot ${f.severity==="critical"?"down":"degraded"}`}></span><div><strong>{f.message}</strong><small>{nice(f.category)} · {nice(f.severity)} · {f.code}</small></div></div></div>):<div className="empty-state compact"><ShieldIcon/><div className="empty-state-title">No QA findings</div><div className="empty-state-copy">Passing golden cases produce no release finding.</div></div>}</section>
    </div>:null}

    {tab==="cases"?<section className="premium-panel"><div className="panel-title-row"><h2>{suite?.suite.name||"Golden cases"}</h2><span>{suite?.cases.length??0} cases</span></div>{suite?.cases.map(c=><div className="health-component-row" key={c.id}><span className={`health-dot ${c.critical?"degraded":"healthy"}`}></span><div><strong>{c.title}</strong><small>{c.case_key} · {nice(c.evaluator)}{c.source_note?` · ${c.source_note}`:""}</small></div><div className="health-component-meta"><strong>{nice(c.category)}</strong><small>{c.critical?"Critical gate":`Weight ${c.weight}`}</small></div></div>)}</section>:null}

    {tab==="history"?<section className="premium-panel"><div className="panel-title-row"><h2>Release history</h2><span>{data?.latest_runs.length??0}</span></div>{data?.latest_runs.length?data.latest_runs.map(r=><button className="health-component-row qa-history-button" key={r.id} onClick={()=>void openRun(r.id)}><span className={`health-dot ${r.status==="passed"?"healthy":"down"}`}></span><div><strong>{r.status==="passed"?"Release gate passed":"Release gate held"}</strong><small>{dateText(r.finished_at||r.created_at)} · v{r.app_version||"—"} · {r.build_ref||"manual"}</small></div><div className="health-component-meta"><strong>{pct(r.overall_score)}</strong><small>{r.snapshot_hash?`${r.snapshot_hash.slice(0,10)}…`:"No hash"}</small></div></button>):<div className="empty-state compact"><BookIcon/><div className="empty-state-title">No historical runs</div><div className="empty-state-copy">Each evaluation run will be stored with a reproducible snapshot hash.</div></div>}</section>:null}
  </main>;
}
