"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  createConflictCheck, createCRMClient, createCRMLead, convertCRMLead, getCRMClientDetail,
  getCRMClients, getCRMConflicts, getCRMLeads, getCRMOverview, getCRMTasks, reviewCRMConflict,
  type CRMClient, type CRMClientDetail, type CRMConflictCheck, type CRMLead, type CRMOverview, type CRMTask,
} from "@/lib/api";
import { PlusIcon, SearchIcon, ShieldIcon, UsersIcon } from "@/components/icons";

type Tab = "pipeline" | "clients" | "conflicts" | "tasks";
type Composer = "lead" | "client" | "conflict" | null;

const emptyOverview: CRMOverview = { leads_open: 0, clients_active: 0, conflict_reviews: 0, onboarding_open: 0, tasks_due: 0, unbilled_minutes: 0 };

function dateLabel(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short" }).format(new Date(value));
}

export function CRMWorkspace() {
  const [tab, setTab] = useState<Tab>("pipeline");
  const [composer, setComposer] = useState<Composer>(null);
  const [overview, setOverview] = useState(emptyOverview);
  const [leads, setLeads] = useState<CRMLead[]>([]);
  const [clients, setClients] = useState<CRMClient[]>([]);
  const [conflicts, setConflicts] = useState<CRMConflictCheck[]>([]);
  const [tasks, setTasks] = useState<CRMTask[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedClient, setSelectedClient] = useState<CRMClientDetail | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [o, l, c, f, t] = await Promise.all([getCRMOverview(), getCRMLeads(), getCRMClients(), getCRMConflicts(), getCRMTasks()]);
      setOverview(o); setLeads(l); setClients(c); setConflicts(f); setTasks(t);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to load client workspace"); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const filteredLeads = useMemo(() => leads.filter(x => `${x.name} ${x.company_name ?? ""} ${x.practice_area ?? ""}`.toLowerCase().includes(query.toLowerCase())), [leads, query]);
  const filteredClients = useMemo(() => clients.filter(x => `${x.display_name} ${x.client_number} ${x.email ?? ""}`.toLowerCase().includes(query.toLowerCase())), [clients, query]);

  async function submitLead(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);
    const data = new FormData(event.currentTarget);
    try {
      await createCRMLead({ name: String(data.get("name") || ""), company_name: String(data.get("company") || "") || undefined, email: String(data.get("email") || "") || undefined, phone: String(data.get("phone") || "") || undefined, source: String(data.get("source") || "") || undefined, practice_area: String(data.get("practice_area") || "") || undefined, language: String(data.get("language") || "bilingual") });
      setComposer(null); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to create lead"); } finally { setBusy(false); }
  }

  async function submitClient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);
    const data = new FormData(event.currentTarget);
    try {
      await createCRMClient({ display_name: String(data.get("display_name") || ""), legal_name: String(data.get("legal_name") || "") || undefined, client_type: String(data.get("client_type") || "individual") as "individual" | "organization", email: String(data.get("email") || "") || undefined, phone: String(data.get("phone") || "") || undefined, preferred_language: String(data.get("language") || "bilingual") });
      setComposer(null); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to create client"); } finally { setBusy(false); }
  }

  async function submitConflict(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);
    const data = new FormData(event.currentTarget);
    try {
      const related = String(data.get("related") || "").split(",").map(x => x.trim()).filter(Boolean);
      await createConflictCheck({ subject_name: String(data.get("subject_name") || ""), related_parties: related });
      setComposer(null); setTab("conflicts"); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to run conflict check"); } finally { setBusy(false); }
  }

  async function openClient(clientId: string) {
    setBusy(true); setError(null);
    try { setSelectedClient(await getCRMClientDetail(clientId)); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to open client"); }
    finally { setBusy(false); }
  }

  async function convertLead(lead: CRMLead) {
    setBusy(true); setError(null);
    try {
      await convertCRMLead(lead.id, { client_type: lead.company_name ? "organization" : "individual", legal_name: lead.company_name || lead.name });
      setTab("clients"); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to convert lead"); }
    finally { setBusy(false); }
  }

  async function decideConflict(check: CRMConflictCheck, decision: "cleared" | "conflict_found") {
    const note = window.prompt(decision === "cleared" ? "Enter the lawyer's clearance note" : "Enter the lawyer's conflict note");
    if (!note || note.trim().length < 3) return;
    setBusy(true); setError(null);
    try { await reviewCRMConflict(check.id, decision, note.trim()); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to record conflict decision"); }
    finally { setBusy(false); }
  }


  return (
    <main className="page crm-page">
      <div className="hero-row">
        <div>
          <div className="eyebrow">Firm relationships</div>
          <h1 className="page-title">Clients & intake</h1>
          <p className="page-subtitle">Move a potential client from first contact through conflict review, onboarding and matter opening without turning the legal workspace into a noisy sales CRM.</p>
        </div>
        <button className="primary-button" onClick={() => setComposer("lead")}><PlusIcon /> New intake</button>
      </div>

      {error ? <div className="notice-panel"><strong>Workspace notice</strong><span>{error}</span></div> : null}

      <section className="metrics crm-metrics">
        <div className="metric"><div className="metric-label">Open leads</div><div className="metric-value">{overview.leads_open}</div><div className="metric-note">Awaiting qualification</div></div>
        <div className="metric"><div className="metric-label">Active clients</div><div className="metric-value">{overview.clients_active}</div><div className="metric-note">Firm relationships</div></div>
        <div className="metric"><div className="metric-label">Conflict review</div><div className="metric-value">{overview.conflict_reviews}</div><div className="metric-note">Requires lawyer decision</div></div>
        <div className="metric"><div className="metric-label">Onboarding</div><div className="metric-value">{overview.onboarding_open}</div><div className="metric-note">Open compliance gates</div></div>
      </section>

      <div className="crm-toolbar">
        <div className="workspace-tabs crm-tabs">
          {(["pipeline", "clients", "conflicts", "tasks"] as Tab[]).map(item => <button key={item} className={`workspace-tab${tab === item ? " active" : ""}`} onClick={() => setTab(item)}>{item === "pipeline" ? "Pipeline" : item[0].toUpperCase() + item.slice(1)}</button>)}
        </div>
        <label className="crm-search"><SearchIcon /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search people, clients or matters" /></label>
      </div>

      {tab === "pipeline" ? <div className="grid-2 crm-grid">
        <section className="card"><div className="card-header"><div><div className="card-title">Intake pipeline</div><div className="crm-card-copy">Qualification before matter opening</div></div><button className="secondary-button" onClick={() => setComposer("lead")}>Add lead</button></div>
          {filteredLeads.length ? filteredLeads.map(lead => <div className="crm-row crm-lead-row" key={lead.id}><div className="crm-avatar">{lead.name.slice(0,2).toUpperCase()}</div><div><div className="matter-title">{lead.name}</div><div className="matter-meta">{lead.company_name || lead.practice_area || "New legal enquiry"}</div></div><div className={`crm-pill ${lead.status}`}>{lead.status.replaceAll("_", " ")}</div><div className="crm-row-actions"><span className="matter-meta">{lead.next_action || "No next action"}</span>{lead.status !== "converted" && lead.status !== "lost" ? <button className="text-button" disabled={busy} onClick={() => void convertLead(lead)}>Convert</button> : null}</div></div>) : <div className="empty-state compact"><div className="empty-state-title">No open intake yet</div><div className="empty-state-copy">Create the first enquiry and move it through a lawyer-reviewed conflict check before opening a matter.</div></div>}
        </section>
        <section className="card"><div className="card-header"><div className="card-title">Control gates</div></div><div className="crm-gates"><div><ShieldIcon /><span><strong>Conflict first</strong><small>No matter opening until cleared or expressly overridden.</small></span></div><div><UsersIcon /><span><strong>Human onboarding</strong><small>KYC, address and engagement gates remain reviewable.</small></span></div><div><span className="crm-zero">₹0</span><span><strong>No AI required</strong><small>Matching and workflow logic are deterministic.</small></span></div></div></section>
      </div> : null}

      {tab === "clients" ? <section className="card"><div className="card-header"><div><div className="card-title">Client register</div><div className="crm-card-copy">Organization-scoped client records</div></div><button className="secondary-button" onClick={() => setComposer("client")}>New client</button></div>{filteredClients.length ? filteredClients.map(client => <button type="button" className="crm-client-row crm-client-button" key={client.id} onClick={() => void openClient(client.id)}><div><div className="matter-title">{client.display_name}</div><div className="matter-meta">{client.client_number} · {client.legal_name || client.client_type}</div></div><div className="matter-court">{client.email || client.phone || "No contact recorded"}</div><span className="status">{client.status}</span></button>) : <div className="empty-state compact"><div className="empty-state-title">No clients registered</div></div>}</section> : null}

      {tab === "conflicts" ? <section className="card"><div className="card-header"><div><div className="card-title">Conflict review queue</div><div className="crm-card-copy">Similarity is a review signal, never an automatic clearance.</div></div><button className="secondary-button" onClick={() => setComposer("conflict")}>Run check</button></div>{conflicts.length ? conflicts.map(check => <div className="conflict-row" key={check.id}><div className="conflict-head"><div><div className="matter-title">{check.subject_name}</div><div className="matter-meta">{check.related_parties_json.length ? `Related: ${check.related_parties_json.join(", ")}` : "No related parties supplied"}</div></div><span className={`crm-pill ${check.status}`}>{check.status.replaceAll("_", " ")}</span></div>{(check.candidates ?? []).length ? <div className="candidate-list">{(check.candidates ?? []).slice(0,4).map(candidate => <div key={candidate.id}><span>{candidate.candidate_name}</span><small>{Math.round(candidate.match_score * 100)}% · {candidate.reason}</small></div>)}</div> : <div className="matter-meta conflict-empty">No deterministic candidates found. Lawyer clearance is still required.</div>}{check.status === "pending" || check.status === "review_required" ? <div className="conflict-actions"><button className="secondary-button" disabled={busy} onClick={() => void decideConflict(check, "conflict_found")}>Mark conflict</button><button className="primary-button" disabled={busy} onClick={() => void decideConflict(check, "cleared")}>Clear after review</button></div> : null}</div>) : <div className="empty-state compact"><div className="empty-state-title">No conflict checks yet</div></div>}</section> : null}

      {tab === "tasks" ? <section className="card"><div className="card-header"><div><div className="card-title">Intake & client tasks</div><div className="crm-card-copy">Visible matters only; restricted matter tasks stay hidden.</div></div></div>{tasks.length ? tasks.map(task => <div className="task-row" key={task.id}><div className="task-dot"/><div><div className="task-title">{task.title}</div><div className="task-meta">{task.priority} · {task.due_at ? `due ${dateLabel(task.due_at)}` : "no due date"} · {task.status.replaceAll("_", " ")}</div></div></div>) : <div className="empty-state compact"><div className="empty-state-title">No CRM tasks</div></div>}</section> : null}

      {selectedClient ? <div className="modal-backdrop" onMouseDown={() => setSelectedClient(null)}><aside className="client-detail" onMouseDown={e => e.stopPropagation()}><div className="client-detail-head"><div><div className="eyebrow">{selectedClient.client.client_number}</div><h2>{selectedClient.client.display_name}</h2><p>{selectedClient.client.legal_name || selectedClient.client.client_type}</p></div><button className="icon-button" onClick={() => setSelectedClient(null)}>×</button></div><div className="client-detail-body"><section><div className="section-kicker">Onboarding</div><div className="onboarding-score"><strong>{selectedClient.onboarding.status.replaceAll("_", " ")}</strong><span>{[selectedClient.onboarding.conflict_cleared, selectedClient.onboarding.identity_complete, selectedClient.onboarding.address_complete, selectedClient.onboarding.engagement_complete].filter(Boolean).length}/4 gates</span></div><div className="gate-grid"><span className={selectedClient.onboarding.conflict_cleared ? "done" : ""}>Conflict</span><span className={selectedClient.onboarding.identity_complete ? "done" : ""}>Identity</span><span className={selectedClient.onboarding.address_complete ? "done" : ""}>Address</span><span className={selectedClient.onboarding.engagement_complete ? "done" : ""}>Engagement</span></div></section><section><div className="section-kicker">Matters</div>{selectedClient.matters.length ? selectedClient.matters.map(m => <div className="detail-line" key={m.id}><span>{m.title}</span><small>{m.status}</small></div>) : <div className="detail-muted">No visible matters yet.</div>}</section><section><div className="section-kicker">KYC records</div>{selectedClient.kyc.length ? selectedClient.kyc.map(k => <div className="detail-line" key={k.id}><span>{k.document_type}{k.identifier_last4 ? ` · ••••${k.identifier_last4}` : ""}</span><small>{k.status}</small></div>) : <div className="detail-muted">No KYC verification recorded.</div>}</section><section><div className="section-kicker">Engagements</div>{selectedClient.engagements.length ? selectedClient.engagements.map(e => <div className="detail-line" key={e.id}><span>{e.title}</span><small>{e.status}</small></div>) : <div className="detail-muted">No engagement recorded.</div>}</section><section><div className="section-kicker">Client portal</div>{selectedClient.portal_access.length ? selectedClient.portal_access.map(p => <div className="detail-line" key={p.id}><span>{p.email}</span><small>{p.status}</small></div>) : <div className="detail-muted">No portal access issued.</div>}</section></div></aside></div> : null}

      {composer ? <div className="modal-backdrop" onMouseDown={() => setComposer(null)}><div className="crm-modal" onMouseDown={e => e.stopPropagation()}><div className="card-header"><div><div className="card-title">{composer === "lead" ? "New legal enquiry" : composer === "client" ? "New client" : "Run conflict check"}</div><div className="crm-card-copy">{composer === "conflict" ? "Search current client, contact and matter names. Restricted matches remain masked." : "Keep intake data minimal; enrich only when necessary."}</div></div><button className="icon-button" onClick={() => setComposer(null)}>×</button></div>
        {composer === "lead" ? <form className="crm-form" onSubmit={submitLead}><label>Name<input name="name" required /></label><label>Company<input name="company" /></label><div className="form-two"><label>Email<input name="email" type="email" /></label><label>Phone<input name="phone" /></label></div><div className="form-two"><label>Practice area<input name="practice_area" /></label><label>Source<input name="source" placeholder="Referral, website..." /></label></div><label>Language<select name="language" defaultValue="bilingual"><option value="bilingual">English + हिन्दी</option><option value="en">English</option><option value="hi">हिन्दी</option></select></label><button className="primary-button" disabled={busy}>{busy ? "Saving…" : "Create intake"}</button></form> : null}
        {composer === "client" ? <form className="crm-form" onSubmit={submitClient}><label>Display name<input name="display_name" required /></label><label>Legal name<input name="legal_name" /></label><div className="form-two"><label>Type<select name="client_type"><option value="individual">Individual</option><option value="organization">Organization</option></select></label><label>Language<select name="language" defaultValue="bilingual"><option value="bilingual">English + हिन्दी</option><option value="en">English</option><option value="hi">हिन्दी</option></select></label></div><div className="form-two"><label>Email<input name="email" type="email" /></label><label>Phone<input name="phone" /></label></div><button className="primary-button" disabled={busy}>{busy ? "Saving…" : "Create client"}</button></form> : null}
        {composer === "conflict" ? <form className="crm-form" onSubmit={submitConflict}><label>Prospective client / subject<input name="subject_name" required /></label><label>Related parties<textarea name="related" rows={4} placeholder="Separate names with commas" /></label><div className="notice-panel"><strong>Review rule</strong><span>A zero-candidate result is not automatic legal clearance.</span></div><button className="primary-button" disabled={busy}>{busy ? "Checking…" : "Run deterministic check"}</button></form> : null}
      </div></div> : null}
    </main>
  );
}
