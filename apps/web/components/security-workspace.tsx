"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { LockIcon, ShieldIcon, UsersIcon } from "@/components/icons";
import { MatterSecurityPanel } from "@/components/matter-security-panel";
import { MFAPanel } from "@/components/mfa-panel";
import {
  createSecurityMember,
  getSecurityAudit,
  getSecurityMembers,
  getSecurityOverview,
  securityLogout,
  updateSecurityPolicy,
  verifySecurityAudit,
  type OrganizationRole,
  type SecurityAuditEntry,
  type SecurityAuditVerification,
  type SecurityMember,
  type SecurityOverview,
} from "@/lib/api";

const roleLabel: Record<OrganizationRole, string> = {
  owner: "Owner", admin: "Admin", partner: "Partner", lawyer: "Lawyer", junior: "Junior",
  paralegal: "Paralegal", billing: "Billing", read_only: "Read only",
};

export function SecurityWorkspace() {
  const [overview, setOverview] = useState<SecurityOverview | null>(null);
  const [members, setMembers] = useState<SecurityMember[]>([]);
  const [audit, setAudit] = useState<SecurityAuditEntry[]>([]);
  const [verification, setVerification] = useState<SecurityAuditVerification | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [newMember, setNewMember] = useState({ email: "", display_name: "", password: "", role: "lawyer" as OrganizationRole, locale: "en" });

  const load = useCallback(async () => {
    setError("");
    try {
      const [overviewData, memberData, auditData] = await Promise.all([
        getSecurityOverview(), getSecurityMembers(), getSecurityAudit(60),
      ]);
      setOverview(overviewData); setMembers(memberData); setAudit(auditData);
      try { setVerification(await verifySecurityAudit()); } catch { setVerification(null); }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load security workspace");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function togglePolicy(field: "allow_remote_ai_default" | "allow_exports_default" | "require_mfa_for_remote_ai" | "require_mfa_for_highly_confidential", value: boolean) {
    if (!overview) return;
    setBusy(true); setError("");
    try {
      const policy = await updateSecurityPolicy({ [field]: value });
      setOverview({ ...overview, policy });
    } catch (err) { setError(err instanceof Error ? err.message : "Policy update failed"); }
    finally { setBusy(false); }
  }

  async function addMember(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await createSecurityMember(newMember);
      setNewMember({ email: "", display_name: "", password: "", role: "lawyer", locale: "en" });
      setInviteOpen(false); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to add member"); }
    finally { setBusy(false); }
  }

  async function logout() {
    try { await securityLogout(); } finally { window.location.href = "/login"; }
  }

  if (error && !overview) {
    return (
      <section className="security-signin-card card">
        <ShieldIcon />
        <h2>Security workspace requires a firm session.</h2>
        <p>{error}</p>
        <Link href="/login" className="primary-button">Sign in</Link>
      </section>
    );
  }
  if (!overview) return <section className="card security-loading">Loading firm security…</section>;

  const canManage = ["owner", "admin"].includes(overview.actor.role);
  return (
    <div className="security-stack">
      {error ? <div className="notice-panel">{error}</div> : null}
      <MFAPanel />
      <section className="security-summary card">
        <div>
          <div className="eyebrow">{overview.organization.slug}</div>
          <h2>{overview.organization.name}</h2>
          <p>Signed in as {overview.actor.display_name} · {roleLabel[overview.actor.role]}</p>
        </div>
        <div className="security-session"><LockIcon /><div><strong>Session active</strong><span>{overview.actor.mfa_enrolled ? "MFA enrolled" : "MFA not enrolled"}</span></div></div>
        <button className="secondary-button" type="button" onClick={logout}>Sign out</button>
      </section>

      <section className="metrics security-metrics">
        <div className="metric"><div className="metric-label">Firm members</div><div className="metric-value">{overview.members}</div><div className="metric-note">{overview.active_sessions} active sessions</div></div>
        <div className="metric"><div className="metric-label">Restricted matters</div><div className="metric-value">{overview.restricted_matters}</div><div className="metric-note">{overview.ethical_wall_matters} ethical walls</div></div>
        <div className="metric"><div className="metric-label">Legal holds</div><div className="metric-value">{overview.active_legal_holds}</div><div className="metric-note">Deletion blocked while active</div></div>
        <div className="metric"><div className="metric-label">Audit events</div><div className="metric-value">{overview.audit_entries}</div><div className="metric-note">{verification?.valid ? "Chain verified" : "Verification requires admin"}</div></div>
      </section>

      <MatterSecurityPanel members={members} canManage={canManage} />

      <section className="security-grid">
        <div className="card security-policy-card">
          <div className="card-header"><div><div className="card-title">Firm policy</div><div className="security-card-copy">Organization defaults; matter-level policy can be stricter.</div></div><ShieldIcon /></div>
          <PolicyToggle label="Remote AI by default" note="Keep off unless the firm has approved a remote provider." checked={overview.policy.allow_remote_ai_default} disabled={!canManage || busy} onChange={(v) => togglePolicy("allow_remote_ai_default", v)} />
          <PolicyToggle label="Exports by default" note="Matter and user grants can still deny export." checked={overview.policy.allow_exports_default} disabled={!canManage || busy} onChange={(v) => togglePolicy("allow_exports_default", v)} />
          <PolicyToggle label="Require MFA for remote AI" note="Remote model calls are blocked for users without MFA." checked={overview.policy.require_mfa_for_remote_ai} disabled={!canManage || busy} onChange={(v) => togglePolicy("require_mfa_for_remote_ai", v)} />
          <PolicyToggle label="Require MFA for highly confidential matters" note="Blocks export and remote AI until MFA is present." checked={overview.policy.require_mfa_for_highly_confidential} disabled={!canManage || busy} onChange={(v) => togglePolicy("require_mfa_for_highly_confidential", v)} />
          <div className="security-policy-facts"><span>Idle session <strong>{overview.policy.session_idle_timeout_minutes} min</strong></span><span>Absolute lifetime <strong>{overview.policy.session_absolute_lifetime_hours} h</strong></span><span>Concurrent sessions <strong>{overview.policy.max_concurrent_sessions}</strong></span></div>
        </div>

        <div className="card security-members-card">
          <div className="card-header"><div><div className="card-title">People & roles</div><div className="security-card-copy">Role access is the baseline; ethical walls require explicit grants.</div></div>{canManage ? <button className="secondary-button" onClick={() => setInviteOpen((v) => !v)} type="button"><UsersIcon /> Add member</button> : null}</div>
          {inviteOpen ? <form className="member-form" onSubmit={addMember}><input required placeholder="Name" value={newMember.display_name} onChange={(e) => setNewMember({ ...newMember, display_name: e.target.value })}/><input required type="email" placeholder="Email" value={newMember.email} onChange={(e) => setNewMember({ ...newMember, email: e.target.value })}/><input required minLength={12} type="password" placeholder="Temporary password (12+ chars)" value={newMember.password} onChange={(e) => setNewMember({ ...newMember, password: e.target.value })}/><select value={newMember.role} onChange={(e) => setNewMember({ ...newMember, role: e.target.value as OrganizationRole })}>{Object.entries(roleLabel).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select><button className="primary-button" disabled={busy} type="submit">Create account</button></form> : null}
          <div className="member-list">{members.map((member) => <div className="member-row" key={member.id}><div className="member-avatar">{(member.user?.display_name ?? "U").slice(0,1).toUpperCase()}</div><div><strong>{member.user?.display_name ?? "Member"}</strong><span>{member.user?.email ?? member.user_id}</span></div><span className="quiet-badge">{roleLabel[member.role]}</span><span className={`security-state ${member.status}`}>{member.status}</span></div>)}</div>
        </div>
      </section>

      <section className="card audit-card">
        <div className="card-header"><div><div className="card-title">Security audit trail</div><div className="security-card-copy">Append-only hash chain for security-sensitive events; no document or prompt bodies are stored here.</div></div><div className={`audit-verification ${verification?.valid ? "valid" : "unknown"}`}><ShieldIcon /><span>{verification?.valid ? `${verification.checked_entries} entries verified` : "Admin verification"}</span></div></div>
        <div className="audit-list">{audit.length ? audit.map((entry) => <div className="audit-row" key={entry.id}><span className={`audit-outcome ${entry.outcome}`}>{entry.outcome}</span><div><strong>{entry.action}</strong><span>{entry.resource_type}{entry.resource_id ? ` · ${entry.resource_id.slice(0,8)}…` : ""}</span></div><time>{new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(entry.occurred_at))}</time><code>#{entry.sequence}</code></div>) : <div className="empty-state compact"><div className="empty-state-title">No audit events yet</div></div>}</div>
      </section>
    </div>
  );
}

function PolicyToggle({ label, note, checked, disabled, onChange }: { label: string; note: string; checked: boolean; disabled: boolean; onChange: (value: boolean) => void }) {
  return <label className="policy-toggle"><div><strong>{label}</strong><span>{note}</span></div><input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} /><i aria-hidden="true" /></label>;
}
