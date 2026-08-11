"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  AgendaItem,
  attachProcedure,
  ComplianceStatus,
  createHearing,
  createManualDeadline,
  getAgenda,
  getDeadlines,
  getHearings,
  getMatterProcedures,
  getProcedurePacks,
  getProcedureStats,
  Hearing,
  Matter,
  MatterDeadline,
  MatterProcedure,
  patchCompliance,
  patchDeadline,
  ProcedurePack,
  ProcedureStats,
  seedProcedurePacks,
} from "@/lib/api";

function formatDay(value: string) {
  const date = new Date(value.includes("T") ? value : `${value}T00:00:00`);
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(date);
}
function formatWhen(value: string) {
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
function human(value: string) { return value.replaceAll("_", " "); }

function StatStrip({ stats }: { stats: ProcedureStats }) {
  return (
    <section className="procedure-metrics">
      <div><span>Hearings</span><strong>{stats.upcoming_hearings}</strong><small>upcoming</small></div>
      <div><span>Deadlines</span><strong>{stats.upcoming_deadlines}</strong><small>{stats.overdue_deadlines} overdue</small></div>
      <div className={stats.unreviewed_deadlines ? "attention" : ""}><span>Review dates</span><strong>{stats.unreviewed_deadlines}</strong><small>lawyer confirmation</small></div>
      <div><span>Compliance</span><strong>{stats.pending_compliances}</strong><small>open items</small></div>
    </section>
  );
}

export function ProcedureWorkspace({
  matters,
  initialPacks,
  initialAgenda,
  initialStats,
}: {
  matters: Matter[];
  initialPacks: ProcedurePack[];
  initialAgenda: AgendaItem[];
  initialStats: ProcedureStats;
}) {
  const [matterId, setMatterId] = useState(matters[0]?.id ?? "");
  const [packs, setPacks] = useState(initialPacks);
  const [packId, setPackId] = useState(initialPacks[0]?.id ?? "");
  const [procedures, setProcedures] = useState<MatterProcedure[]>([]);
  const [deadlines, setDeadlines] = useState<MatterDeadline[]>([]);
  const [hearings, setHearings] = useState<Hearing[]>([]);
  const [agenda, setAgenda] = useState(initialAgenda);
  const [stats, setStats] = useState(initialStats);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [deadlineTitle, setDeadlineTitle] = useState("Internal filing/review date");
  const [triggerDate, setTriggerDate] = useState(new Date().toISOString().slice(0, 10));
  const [offsetDays, setOffsetDays] = useState(7);
  const [dayBasis, setDayBasis] = useState<"calendar" | "business">("calendar");
  const [hearingWhen, setHearingWhen] = useState("");
  const [hearingPurpose, setHearingPurpose] = useState("Hearing");

  const selectedMatter = useMemo(() => matters.find((matter) => matter.id === matterId), [matters, matterId]);

  async function refreshMatter(target = matterId) {
    if (!target) return;
    const [nextProcedures, nextDeadlines, nextHearings, nextAgenda, nextStats] = await Promise.all([
      getMatterProcedures(target), getDeadlines(target), getHearings(target), getAgenda(target), getProcedureStats(),
    ]);
    setProcedures(nextProcedures); setDeadlines(nextDeadlines); setHearings(nextHearings); setAgenda(nextAgenda); setStats(nextStats);
  }

  useEffect(() => {
    refreshMatter().catch((err) => setError(err instanceof Error ? err.message : "Unable to load matter schedule"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matterId]);

  async function seedPacks() {
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await seedProcedurePacks();
      const next = await getProcedurePacks();
      setPacks(next); setPackId(next[0]?.id ?? "");
      setMessage(result.created ? "Workflow pack added." : "Workflow pack already available.");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to seed workflow pack"); }
    finally { setBusy(false); }
  }

  async function attach() {
    if (!matterId || !packId) return;
    setBusy(true); setError(""); setMessage("");
    try { await attachProcedure(matterId, packId); await refreshMatter(); setMessage("Procedure workflow attached to matter."); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to attach workflow"); }
    finally { setBusy(false); }
  }

  async function toggleCompliance(procedure: MatterProcedure, complianceId: string, current: ComplianceStatus) {
    setBusy(true); setError("");
    try {
      await patchCompliance(complianceId, { status: current === "completed" ? "pending" : "completed" });
      await refreshMatter(procedure.matter_id);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to update compliance"); }
    finally { setBusy(false); }
  }

  async function submitDeadline(event: FormEvent) {
    event.preventDefault(); if (!matterId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await createManualDeadline(matterId, {
        title: deadlineTitle, trigger_date: triggerDate, offset_days: offsetDays,
        day_basis: dayBasis, count_from_next_day: true, adjustment: "none",
        source_name: "Manual / internal workflow", source_citation: "Not verified as a legal limitation rule",
      });
      await refreshMatter(); setMessage("Date calculated and placed in lawyer review.");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to calculate deadline"); }
    finally { setBusy(false); }
  }

  async function reviewDeadline(deadline: MatterDeadline, complete = false) {
    setBusy(true); setError("");
    try {
      await patchDeadline(deadline.id, complete ? { completed: true } : { reviewed_by_lawyer: true });
      await refreshMatter();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to update deadline"); }
    finally { setBusy(false); }
  }

  async function submitHearing(event: FormEvent) {
    event.preventDefault(); if (!matterId || !hearingWhen) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await createHearing({
        matter_id: matterId, scheduled_for: new Date(hearingWhen).toISOString(),
        court_name: selectedMatter?.court_name, purpose: hearingPurpose,
      });
      setHearingWhen(""); await refreshMatter(); setMessage("Hearing added to the matter calendar.");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to add hearing"); }
    finally { setBusy(false); }
  }

  return (
    <>
      <StatStrip stats={stats} />
      {message ? <div className="success-panel procedure-message">{message}</div> : null}
      {error ? <div className="notice-panel">{error}</div> : null}

      <section className="card procedure-control-card">
        <div className="procedure-control-row">
          <label>Matter
            <select value={matterId} onChange={(event) => setMatterId(event.target.value)}>
              {matters.map((matter) => <option key={matter.id} value={matter.id}>{matter.title}</option>)}
            </select>
          </label>
          <label>Procedure pack
            <select value={packId} onChange={(event) => setPackId(event.target.value)} disabled={!packs.length}>
              {packs.map((pack) => <option key={pack.id} value={pack.id}>{pack.name_en} · v{pack.version}</option>)}
              {!packs.length ? <option>No packs loaded</option> : null}
            </select>
          </label>
          <div className="procedure-control-actions">
            {!packs.length ? <button className="button secondary" type="button" onClick={seedPacks} disabled={busy}>Add workflow pack</button> : null}
            <button className="button primary" type="button" onClick={attach} disabled={busy || !packId}>Attach workflow</button>
          </div>
        </div>
        <div className="procedure-source-warning">Built-in workflow packs are operational templates. Statutory limitation rules must be imported with source/version metadata and independently verified.</div>
      </section>

      <div className="procedure-grid">
        <section className="card">
          <div className="card-header"><div><div className="card-title">Upcoming agenda</div><div className="quiet-text">Selected matter · next 30 days</div></div></div>
          {agenda.length ? <div className="agenda-list">{agenda.map((item) => (
            <div className="agenda-row" key={`${item.kind}-${item.id}`}>
              <div className={`agenda-date ${item.kind}`}><strong>{new Date(item.when).getDate()}</strong><span>{new Intl.DateTimeFormat("en-IN", { month: "short" }).format(new Date(item.when))}</span></div>
              <div><span className="agenda-kind">{item.kind}</span><strong>{item.title}</strong><small>{formatWhen(item.when)} · {human(item.status)}</small></div>
              {item.requires_review ? <span className="procedure-review-badge">Review</span> : <span className="verified-badge">Confirmed</span>}
            </div>
          ))}</div> : <div className="empty-state compact"><div className="empty-state-title">No upcoming items</div><div className="empty-state-copy">Add a hearing or create a reviewed deadline for this matter.</div></div>}
        </section>

        <aside className="procedure-side-stack">
          <form className="card procedure-form" onSubmit={submitHearing}>
            <div className="card-header"><div className="card-title">Add hearing</div></div>
            <div className="procedure-form-body">
              <label>Date & time<input type="datetime-local" value={hearingWhen} onChange={(event) => setHearingWhen(event.target.value)} required /></label>
              <label>Purpose<input value={hearingPurpose} onChange={(event) => setHearingPurpose(event.target.value)} /></label>
              <button className="button primary" disabled={busy || !hearingWhen}>Add to calendar</button>
            </div>
          </form>
          <form className="card procedure-form" onSubmit={submitDeadline}>
            <div className="card-header"><div className="card-title">Calculate date</div><div className="card-action">Review-gated</div></div>
            <div className="procedure-form-body">
              <label>Label<input value={deadlineTitle} onChange={(event) => setDeadlineTitle(event.target.value)} /></label>
              <div className="procedure-form-split"><label>Trigger<input type="date" value={triggerDate} onChange={(event) => setTriggerDate(event.target.value)} /></label><label>Days<input type="number" min="0" max="3650" value={offsetDays} onChange={(event) => setOffsetDays(Number(event.target.value))} /></label></div>
              <label>Basis<select value={dayBasis} onChange={(event) => setDayBasis(event.target.value as "calendar" | "business")}><option value="calendar">Calendar days</option><option value="business">Business days</option></select></label>
              <button className="button secondary" disabled={busy}>Calculate & review</button>
            </div>
          </form>
        </aside>
      </div>

      <div className="procedure-grid procedure-lower-grid">
        <section className="card">
          <div className="card-header"><div><div className="card-title">Procedure checklist</div><div className="quiet-text">Operational workflow · lawyer controlled</div></div></div>
          {procedures.length ? procedures.map((procedure) => (
            <div className="procedure-workflow" key={procedure.id}>
              <div className="procedure-workflow-head"><strong>{procedure.pack_name}</strong><span>v{procedure.pack_version} · {procedure.status}</span></div>
              {procedure.compliances.map((item, index) => (
                <button className={`compliance-row ${item.status}`} key={item.id} type="button" onClick={() => toggleCompliance(procedure, item.id, item.status)} disabled={busy}>
                  <span className="compliance-index">{String(index + 1).padStart(2, "0")}</span>
                  <span><strong>{item.title}</strong><small>{Array.isArray(item.metadata_json.checklist) ? (item.metadata_json.checklist as string[]).slice(0, 2).join(" · ") : "Workflow step"}</small></span>
                  <span className="compliance-state">{item.status === "completed" ? "✓ Complete" : human(item.status)}</span>
                </button>
              ))}
            </div>
          )) : <div className="empty-state compact"><div className="empty-state-title">No workflow attached</div><div className="empty-state-copy">Attach the general litigation workflow to create an operational checklist.</div></div>}
        </section>

        <section className="card">
          <div className="card-header"><div><div className="card-title">Deadline review</div><div className="quiet-text">Calculated dates do not become confirmed until counsel reviews them</div></div></div>
          {deadlines.length ? <div className="deadline-list">{deadlines.map((deadline) => (
            <article className={`deadline-row ${deadline.status}`} key={deadline.id}>
              <div><span className={`deadline-status ${deadline.status}`}>{human(deadline.status)}</span><strong>{deadline.title}</strong><small>Trigger {formatDay(deadline.trigger_date)} · due {formatDay(deadline.due_date)}</small></div>
              <div className="deadline-actions">
                {!deadline.reviewed_by_lawyer ? <button type="button" onClick={() => reviewDeadline(deadline)} disabled={busy}>Confirm date</button> : null}
                {!deadline.completed_at ? <button type="button" onClick={() => reviewDeadline(deadline, true)} disabled={busy}>Complete</button> : null}
              </div>
            </article>
          ))}</div> : <div className="empty-state compact"><div className="empty-state-title">No calculated dates</div><div className="empty-state-copy">Use the calculator to create a transparent date record.</div></div>}
        </section>
      </div>

      <section className="card hearing-register">
        <div className="card-header"><div><div className="card-title">Hearing register</div><div className="quiet-text">Court dates and directions stay attached to the matter</div></div></div>
        {hearings.length ? <div className="hearing-list">{hearings.map((hearing) => (
          <article className="hearing-row" key={hearing.id}>
            <div className="hearing-date"><strong>{formatDay(hearing.scheduled_for)}</strong><span>{new Intl.DateTimeFormat("en-IN", { hour: "2-digit", minute: "2-digit" }).format(new Date(hearing.scheduled_for))}</span></div>
            <div className="hearing-main"><span>{hearing.court_name ?? selectedMatter?.court_name ?? "Court"}</span><strong>{hearing.purpose ?? "Hearing"}</strong><small>{hearing.judge_or_bench ?? "Bench not recorded"}</small></div>
            <div className="hearing-direction-count"><strong>{hearing.directions.filter((item) => item.status === "open").length}</strong><span>open directions</span></div>
            <span className={`hearing-status ${hearing.status}`}>{human(hearing.status)}</span>
          </article>
        ))}</div> : <div className="empty-state compact"><div className="empty-state-title">No hearings recorded</div><div className="empty-state-copy">Add the next court date above. Orders can later be processed for reviewable directions.</div></div>}
      </section>
    </>
  );
}
