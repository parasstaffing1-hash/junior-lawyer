"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  ensureDefaultBackupPolicy,
  getSystemHealthDashboard,
  queueBackupRun,
  queueRestoreVerification,
  reviewRestoreDrill,
  runSystemHealthCheck,
  updateRecoveryObjectives,
  updateSystemIncident,
  type BackupRunRecord,
  type SystemHealthDashboardRecord,
  type SystemHealthStatus,
} from "@/lib/api";
import { PulseIcon, ShieldIcon } from "@/components/icons";

type Tab = "health" | "backups" | "recovery";
const nice=(v:string)=>v.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());
const dateText=(v:string|null|undefined)=>v?new Intl.DateTimeFormat("en-IN",{dateStyle:"medium",timeStyle:"short"}).format(new Date(v)):"—";
const bytes=(value:number|null|undefined)=>{if(!value)return "0 B";const units=["B","KB","MB","GB","TB"];let n=value,i=0;while(n>=1024&&i<units.length-1){n/=1024;i++}return `${n.toFixed(i?1:0)} ${units[i]}`};
const healthLabel=(s:SystemHealthStatus)=>s==="healthy"?"Healthy":s==="degraded"?"Needs attention":s==="down"?"Unavailable":"Unknown";
const runTone=(run:BackupRunRecord)=>run.status==="failed"?"down":run.status==="verified"?"healthy":run.status==="succeeded"?"healthy":"unknown";

export function SystemHealthWorkspace(){
  const [tab,setTab]=useState<Tab>("health");
  const [data,setData]=useState<SystemHealthDashboardRecord|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const [message,setMessage]=useState<string|null>(null);

  const refresh=useCallback(async()=>{try{setData(await getSystemHealthDashboard());setError(null)}catch(e){setError(e instanceof Error?e.message:"Unable to load system health")}},[]);
  useEffect(()=>{void refresh();const t=window.setInterval(()=>void refresh(),15000);return()=>window.clearInterval(t)},[refresh]);

  const status=data?.latest_run?.status??"unknown";
  const successfulBackup=useMemo(()=>data?.recent_backups.find(item=>["succeeded","verified"].includes(item.status))??null,[data]);
  const lastDrill=useMemo(()=>data?.recent_restore_drills.find(item=>["passed","reviewed"].includes(item.status))??null,[data]);

  async function runCheck(){setBusy(true);setMessage(null);try{await runSystemHealthCheck();setMessage("System checks completed.");await refresh()}catch(e){setError(e instanceof Error?e.message:"Health check failed")}finally{setBusy(false)}}
  async function createPolicy(){setBusy(true);try{await ensureDefaultBackupPolicy();setMessage("Default recovery policy created. Review it before production use.");await refresh()}catch(e){setError(e instanceof Error?e.message:"Unable to create backup policy")}finally{setBusy(false)}}
  async function queueBackup(policyId:string){setBusy(true);try{const job=await queueBackupRun(policyId);setMessage(`Backup queued as job ${job.id.slice(0,8)}. A maintenance worker must be online.`);await refresh()}catch(e){setError(e instanceof Error?e.message:"Unable to queue backup")}finally{setBusy(false)}}
  async function verifyBackup(runId:string){setBusy(true);try{const job=await queueRestoreVerification(runId);setMessage(`Restore verification queued as job ${job.id.slice(0,8)}.`);await refresh()}catch(e){setError(e instanceof Error?e.message:"Unable to queue verification")}finally{setBusy(false)}}
  async function incidentAction(id:string,action:"acknowledge"|"resolve"){setBusy(true);try{await updateSystemIncident(id,action);setMessage(action==="acknowledge"?"Incident acknowledged.":"Incident resolved by reviewer.");await refresh()}catch(e){setError(e instanceof Error?e.message:"Unable to update incident")}finally{setBusy(false)}}
  async function reviewDrill(id:string){setBusy(true);try{await reviewRestoreDrill(id,"Reviewed from System Health workspace");setMessage("Restore verification marked reviewed.");await refresh()}catch(e){setError(e instanceof Error?e.message:"Unable to review restore drill")}finally{setBusy(false)}}
  async function saveObjectives(event:FormEvent<HTMLFormElement>){event.preventDefault();const f=new FormData(event.currentTarget);setBusy(true);try{await updateRecoveryObjectives({target_rpo_minutes:Number(f.get("rpo")),target_rto_minutes:Number(f.get("rto")),restore_verification_days:Number(f.get("verify_days")),max_queue_lag_seconds:Number(f.get("queue_lag")),worker_stale_seconds:Number(f.get("worker_stale")),slow_job_seconds:Number(f.get("slow_job")),min_storage_free_percent:Number(f.get("storage_free")),max_database_latency_ms:Number(f.get("db_latency"))});setMessage("Recovery objectives updated.");await refresh()}catch(e){setError(e instanceof Error?e.message:"Unable to update objectives")}finally{setBusy(false)}}

  return <main className="page system-health-page">
    <header className="search-header"><div><div className="eyebrow">Reliability & recovery</div><h1>System health</h1><p>Observe the API, database, storage, workers, search, OCR and recovery posture. Backups are verified without restoring into the live database.</p></div><div className="health-header-actions"><button className="secondary-button" onClick={()=>void refresh()} disabled={busy}>Refresh</button><button className="primary-button" onClick={()=>void runCheck()} disabled={busy}><PulseIcon/> Run checks</button></div></header>
    {error?<div className="alert error">{error}</div>:null}{message?<div className="jobs-message">{message}</div>:null}
    <section className="metrics">
      <div className="metric"><div className="metric-label">Overall</div><div className={`metric-value health-word ${status}`}>{healthLabel(status)}</div><div className="metric-note">last check {dateText(data?.latest_run?.finished_at)}</div></div>
      <div className="metric"><div className="metric-label">Open incidents</div><div className="metric-value">{data?.open_incidents.length??0}</div><div className="metric-note">component-level review items</div></div>
      <div className="metric"><div className="metric-label">Last backup</div><div className="metric-value small-metric">{successfulBackup?dateText(successfulBackup.finished_at):"None"}</div><div className="metric-note">RPO target {data?.recovery_objectives.target_rpo_minutes??"—"} min</div></div>
      <div className="metric"><div className="metric-label">Restore proof</div><div className="metric-value small-metric">{lastDrill?nice(lastDrill.status):"None"}</div><div className="metric-note">RTO target {data?.recovery_objectives.target_rto_minutes??"—"} min</div></div>
    </section>
    <div className="workspace-tabs"><button className={tab==="health"?"active":""} onClick={()=>setTab("health")}>Health</button><button className={tab==="backups"?"active":""} onClick={()=>setTab("backups")}>Backups</button><button className={tab==="recovery"?"active":""} onClick={()=>setTab("recovery")}>Recovery</button></div>

    {tab==="health"?<div className="health-layout">
      <section className="premium-panel health-components"><div className="panel-title-row"><h2>Components</h2><span>{data?.components.length??0} checks</span></div>{data?.components.length?data.components.map(c=><div className="health-component-row" key={c.id}><span className={`health-dot ${c.status}`}></span><div><strong>{nice(c.component_key)}</strong><small>{c.message_en}</small></div><div className="health-component-meta"><strong>{healthLabel(c.status)}</strong><small>{c.latency_ms!==null?`${c.latency_ms} ms`:nice(c.category)}</small></div></div>):<div className="empty-state compact"><div className="empty-state-title">No health run yet</div><div className="empty-state-copy">Run checks to establish a baseline.</div></div>}</section>
      <section className="premium-panel health-incidents"><div className="panel-title-row"><h2>Incidents</h2><span>{data?.open_incidents.length??0} open</span></div>{data?.open_incidents.length?data.open_incidents.map(i=><div className="incident-card" key={i.id}><div className="incident-card-head"><span className={`health-dot ${i.severity==="critical"||i.severity==="high"?"down":"degraded"}`}></span><div><strong>{i.title}</strong><small>{nice(i.severity)} · {nice(i.status)}</small></div></div><p>{i.description}</p><div className="incident-actions">{i.status==="open"?<button className="secondary-button" disabled={busy} onClick={()=>void incidentAction(i.id,"acknowledge")}>Acknowledge</button>:null}<button className="ghost-button" disabled={busy} onClick={()=>void incidentAction(i.id,"resolve")}>Resolve</button></div></div>):<div className="empty-state compact"><ShieldIcon/><div className="empty-state-title">No open incidents</div><div className="empty-state-copy">Degraded or unavailable components will appear here after a health run.</div></div>}</section>
    </div>:null}

    {tab==="backups"?<div className="health-layout">
      <section className="premium-panel backup-policy-panel"><div className="panel-title-row"><h2>Backup policies</h2>{!data?.backup_policies.length?<button className="secondary-button" onClick={()=>void createPolicy()} disabled={busy}>Create safe default</button>:null}</div>{data?.backup_policies.length?data.backup_policies.map(p=><div className="backup-policy-card" key={p.id}><div><strong>{p.name}</strong><small>{p.include_database?"Database":""}{p.include_database&&p.include_documents?" + ":""}{p.include_documents?"Files":""} · {p.schedule_rrule||"Manual"}</small></div><div className="backup-policy-badges"><span>{p.retention_days}d retention</span><span>RPO {p.rpo_minutes}m</span><span>{p.encryption_mode==="none"?"Local / not encrypted":"External encryption"}</span></div><button className="primary-button" disabled={busy||!p.enabled} onClick={()=>void queueBackup(p.id)}>Queue backup</button></div>):<div className="empty-state compact"><div className="empty-state-title">No backup policy</div><div className="empty-state-copy">Create a default local policy for development, then replace it with encrypted off-site storage for production.</div></div>}</section>
      <section className="premium-panel backup-run-panel"><div className="panel-title-row"><h2>Recent backup runs</h2><span>{data?.recent_backups.length??0}</span></div>{data?.recent_backups.length?data.recent_backups.map(r=><div className="backup-run-row" key={r.id}><span className={`health-dot ${runTone(r)}`}></span><div><strong>{nice(r.status)}</strong><small>{dateText(r.finished_at||r.started_at||r.created_at)} · {bytes(r.total_bytes)}</small>{r.error?<small className="danger-copy">{r.error}</small>:null}</div><div className="backup-run-actions"><small>{r.manifest_sha256?`${r.manifest_sha256.slice(0,10)}…`:"No manifest"}</small>{["succeeded","verified"].includes(r.status)?<button className="ghost-button" disabled={busy} onClick={()=>void verifyBackup(r.id)}>Verify restore</button>:null}</div></div>):<div className="empty-state compact"><div className="empty-state-title">No backups recorded</div><div className="empty-state-copy">Queue a policy run; a maintenance worker will create the backup.</div></div>}</section>
    </div>:null}

    {tab==="recovery"&&data?<div className="health-layout">
      <form className="premium-panel recovery-objectives" onSubmit={e=>void saveObjectives(e)}><div className="panel-title-row"><h2>Recovery objectives</h2><span>Firm policy</span></div><div className="recovery-form-grid"><label>Target RPO · minutes<input name="rpo" type="number" min="1" defaultValue={data.recovery_objectives.target_rpo_minutes}/></label><label>Target RTO · minutes<input name="rto" type="number" min="1" defaultValue={data.recovery_objectives.target_rto_minutes}/></label><label>Restore verification · days<input name="verify_days" type="number" min="1" defaultValue={data.recovery_objectives.restore_verification_days}/></label><label>Max queue lag · seconds<input name="queue_lag" type="number" min="30" defaultValue={data.recovery_objectives.max_queue_lag_seconds}/></label><label>Worker stale · seconds<input name="worker_stale" type="number" min="30" defaultValue={data.recovery_objectives.worker_stale_seconds}/></label><label>Slow job · seconds<input name="slow_job" type="number" min="60" defaultValue={data.recovery_objectives.slow_job_seconds}/></label><label>Minimum storage free · %<input name="storage_free" type="number" min="1" max="90" defaultValue={data.recovery_objectives.min_storage_free_percent}/></label><label>Max DB latency · ms<input name="db_latency" type="number" min="10" defaultValue={data.recovery_objectives.max_database_latency_ms}/></label></div><div className="recovery-note">RPO/RTO are operational targets. A passing verification checks backup integrity in isolation; it does not restore into the live system or claim regulatory certification.</div><button className="primary-button" disabled={busy}>Save objectives</button></form>
      <section className="premium-panel restore-drills"><div className="panel-title-row"><h2>Restore verification</h2><span>{data.recent_restore_drills.length} drills</span></div>{data.recent_restore_drills.length?data.recent_restore_drills.map(d=><div className="restore-row" key={d.id}><span className={`health-dot ${d.status==="passed"||d.status==="reviewed"?"healthy":"down"}`}></span><div><strong>{nice(d.status)}</strong><small>{dateText(d.finished_at||d.started_at)} · DB {d.database_verified?"✓":"—"} · Files {d.documents_verified?"✓":"—"} · Hashes {d.artifact_hashes_verified?"✓":"—"}</small></div><div className="backup-run-actions"><small>{d.result_hash?`${d.result_hash.slice(0,10)}…`:"No result hash"}</small>{d.status==="passed"?<button className="ghost-button" disabled={busy} onClick={()=>void reviewDrill(d.id)}>Mark reviewed</button>:null}</div></div>):<div className="empty-state compact"><div className="empty-state-title">No restore proof yet</div><div className="empty-state-copy">Verify a successful backup from the Backups tab. Verification never writes to the live database.</div></div>}</section>
    </div>:null}
  </main>;
}
