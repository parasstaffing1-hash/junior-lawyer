"use client";

import { useEffect, useMemo, useState } from "react";
import {
  adoptLegacyMatter,
  getLegacyMatters,
  getMatterSecurityAccess,
  getMatterSecurityGrants,
  getMatterSecurityProfile,
  getMatters,
  updateMatterSecurityProfile,
  upsertMatterSecurityGrant,
  type LegacyMatter,
  type Matter,
  type MatterAccessDecision,
  type MatterAccessLevel,
  type MatterSecurityGrant,
  type MatterSecurityProfile,
  type SecurityMember,
} from "@/lib/api";

export function MatterSecurityPanel({ members, canManage }: { members: SecurityMember[]; canManage: boolean }) {
  const [matters, setMatters] = useState<Matter[]>([]);
  const [legacy, setLegacy] = useState<LegacyMatter[]>([]);
  const [matterId, setMatterId] = useState("");
  const [profile, setProfile] = useState<MatterSecurityProfile | null>(null);
  const [access, setAccess] = useState<MatterAccessDecision | null>(null);
  const [grants, setGrants] = useState<MatterSecurityGrant[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [grant, setGrant] = useState({ membership_id: "", effect: "allow" as "allow" | "deny", access_level: "work" as MatterAccessLevel, allow_remote_ai: "inherit", allow_export: "inherit" });

  const memberById = useMemo(() => new Map(members.map((item) => [item.id, item])), [members]);

  async function loadMatter(target: string) {
    if (!target) { setProfile(null); setAccess(null); setGrants([]); return; }
    setError("");
    try {
      const [profileData, accessData] = await Promise.all([getMatterSecurityProfile(target), getMatterSecurityAccess(target)]);
      setProfile(profileData); setAccess(accessData);
      if (canManage) setGrants(await getMatterSecurityGrants(target));
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to load matter security"); }
  }

  useEffect(() => {
    void (async () => {
      try {
        const matterData = await getMatters();
        setMatters(matterData);
        if (matterData[0]) { setMatterId(matterData[0].id); await loadMatter(matterData[0].id); }
        if (canManage) {
          try { setLegacy(await getLegacyMatters()); } catch { setLegacy([]); }
        }
      } catch (err) { setError(err instanceof Error ? err.message : "Unable to load matters"); }
    })();
    // Initial load only; member/role changes do not alter the current selection.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canManage]);

  async function patchProfile(payload: Partial<Pick<MatterSecurityProfile, "classification" | "access_mode" | "remote_ai_policy" | "export_policy">>) {
    if (!matterId || !profile) return;
    setBusy(true); setError("");
    try {
      const updated = await updateMatterSecurityProfile(matterId, payload);
      setProfile(updated); setAccess(await getMatterSecurityAccess(matterId));
      if (canManage) setGrants(await getMatterSecurityGrants(matterId));
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to update matter security"); }
    finally { setBusy(false); }
  }

  async function saveGrant() {
    if (!matterId || !grant.membership_id) return;
    setBusy(true); setError("");
    try {
      await upsertMatterSecurityGrant(matterId, {
        membership_id: grant.membership_id,
        effect: grant.effect,
        access_level: grant.access_level,
        allow_remote_ai: grant.allow_remote_ai === "inherit" ? null : grant.allow_remote_ai === "allow",
        allow_export: grant.allow_export === "inherit" ? null : grant.allow_export === "allow",
        reason: "Managed from Security & access workspace",
      });
      setGrants(await getMatterSecurityGrants(matterId));
      setGrant({ membership_id: "", effect: "allow", access_level: "work", allow_remote_ai: "inherit", allow_export: "inherit" });
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save access grant"); }
    finally { setBusy(false); }
  }

  async function adopt(item: LegacyMatter) {
    setBusy(true); setError("");
    try {
      await adoptLegacyMatter(item.id);
      const next = await getMatters(); setMatters(next); setLegacy((rows) => rows.filter((row) => row.id !== item.id));
      setMatterId(item.id); await loadMatter(item.id);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to adopt legacy matter"); }
    finally { setBusy(false); }
  }

  return (
    <section className="card matter-security-card">
      <div className="card-header">
        <div><div className="card-title">Matter confidentiality</div><div className="security-card-copy">Ethical walls and explicit-access matters ignore ordinary role visibility until a named grant exists.</div></div>
        <select className="security-matter-select" value={matterId} onChange={(e) => { setMatterId(e.target.value); void loadMatter(e.target.value); }}>
          {!matters.length ? <option value="">No secured matters</option> : null}
          {matters.map((matter) => <option key={matter.id} value={matter.id}>{matter.title}</option>)}
        </select>
      </div>
      {error ? <div className="inline-error matter-security-error">{error}</div> : null}
      {profile ? (
        <>
          <div className="matter-security-controls">
            <SecuritySelect label="Classification" value={profile.classification} disabled={!canManage || busy} onChange={(value) => void patchProfile({ classification: value as MatterSecurityProfile["classification"] })} options={[["internal","Internal"],["confidential","Confidential"],["highly_confidential","Highly confidential"],["ethical_wall","Ethical wall"]]} />
            <SecuritySelect label="Access mode" value={profile.access_mode} disabled={!canManage || busy} onChange={(value) => void patchProfile({ access_mode: value as MatterSecurityProfile["access_mode"] })} options={[["organization","Organization roles"],["explicit","Explicit grants only"]]} />
            <SecuritySelect label="Remote AI" value={profile.remote_ai_policy} disabled={!canManage || busy} onChange={(value) => void patchProfile({ remote_ai_policy: value as MatterSecurityProfile["remote_ai_policy"] })} options={[["inherit","Inherit firm"],["allow","Allow"],["deny","Deny"]]} />
            <SecuritySelect label="Export" value={profile.export_policy} disabled={!canManage || busy} onChange={(value) => void patchProfile({ export_policy: value as MatterSecurityProfile["export_policy"] })} options={[["inherit","Inherit firm"],["allow","Allow"],["deny","Deny"]]} />
          </div>
          <div className="matter-access-strip">
            <span>Current access <strong>{access?.matter_access_level ?? "none"}</strong></span>
            <span>Remote AI <strong>{access?.remote_ai_allowed ? "allowed" : "blocked"}</strong></span>
            <span>Export <strong>{access?.export_allowed ? "allowed" : "blocked"}</strong></span>
            <span>Boundary <strong>{profile.classification === "ethical_wall" || profile.access_mode === "explicit" ? "explicit" : "role based"}</strong></span>
          </div>
          {profile.classification === "ethical_wall" ? <div className="ethical-wall-note"><strong>Ethical wall active.</strong><span>Owners and admins do not receive content access automatically; access is through explicit grants. Security administrators can manage the wall itself.</span></div> : null}
          {canManage ? (
            <div className="grant-workspace">
              <div className="grant-form">
                <select value={grant.membership_id} onChange={(e) => setGrant({ ...grant, membership_id: e.target.value })}><option value="">Select member…</option>{members.filter((m) => m.status === "active").map((m) => <option value={m.id} key={m.id}>{m.user?.display_name ?? m.user_id} · {m.role}</option>)}</select>
                <select value={grant.effect} onChange={(e) => setGrant({ ...grant, effect: e.target.value as "allow" | "deny" })}><option value="allow">Allow</option><option value="deny">Deny</option></select>
                <select value={grant.access_level} onChange={(e) => setGrant({ ...grant, access_level: e.target.value as MatterAccessLevel })}><option value="view">View</option><option value="work">Work</option><option value="manage">Manage</option></select>
                <select value={grant.allow_remote_ai} onChange={(e) => setGrant({ ...grant, allow_remote_ai: e.target.value })}><option value="inherit">AI: inherit</option><option value="allow">AI: allow</option><option value="deny">AI: deny</option></select>
                <select value={grant.allow_export} onChange={(e) => setGrant({ ...grant, allow_export: e.target.value })}><option value="inherit">Export: inherit</option><option value="allow">Export: allow</option><option value="deny">Export: deny</option></select>
                <button className="secondary-button" disabled={busy || !grant.membership_id} type="button" onClick={() => void saveGrant()}>Save grant</button>
              </div>
              <div className="grant-list">
                {grants.map((item) => { const member = memberById.get(item.membership_id); return <div className="grant-row" key={item.id}><div><strong>{member?.user?.display_name ?? item.membership_id.slice(0,8)}</strong><span>{member?.user?.email ?? "Explicit matter grant"}</span></div><span className={`grant-effect ${item.effect}`}>{item.effect}</span><span>{item.access_level}</span><span>AI {item.allow_remote_ai == null ? "inherit" : item.allow_remote_ai ? "allow" : "deny"}</span><span>Export {item.allow_export == null ? "inherit" : item.allow_export ? "allow" : "deny"}</span></div>; })}
                {!grants.length ? <div className="empty-state compact"><div className="empty-state-copy">No explicit grants. Organization-role access applies unless the matter is behind a wall.</div></div> : null}
              </div>
            </div>
          ) : null}
        </>
      ) : null}
      {canManage && legacy.length ? <div className="legacy-matters"><div><strong>Legacy matters</strong><span>Assign pre-Batch-10 matters to this organization before access controls apply.</span></div>{legacy.slice(0,5).map((item) => <button disabled={busy} type="button" key={item.id} onClick={() => void adopt(item)}><span>{item.title}</span><b>Adopt</b></button>)}</div> : null}
    </section>
  );
}

function SecuritySelect({ label, value, disabled, onChange, options }: { label: string; value: string; disabled: boolean; onChange: (value: string) => void; options: [string,string][] }) {
  return <label><span>{label}</span><select disabled={disabled} value={value} onChange={(e) => onChange(e.target.value)}>{options.map(([key,text]) => <option key={key} value={key}>{text}</option>)}</select></label>;
}
