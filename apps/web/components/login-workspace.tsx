"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { LockIcon, ShieldIcon } from "@/components/icons";
import { securityBootstrap, securityLogin } from "@/lib/api";

export function LoginWorkspace() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationSlug, setOrganizationSlug] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [setupOpen, setSetupOpen] = useState(false);
  const [setupMessage, setSetupMessage] = useState("");
  const [setup, setSetup] = useState({
    organization_name: "", organization_slug: "", admin_email: "", admin_name: "", password: "", bootstrap_secret: "",
  });

  async function submitLogin(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      await securityLogin({ email, password, organization_slug: organizationSlug || undefined });
      router.push("/matters");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in");
    } finally { setBusy(false); }
  }

  async function submitSetup(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setSetupMessage("");
    try {
      const result = await securityBootstrap({ ...setup, bootstrap_secret: setup.bootstrap_secret || undefined });
      setSetupMessage(result.message);
      setEmail(setup.admin_email); setOrganizationSlug(setup.organization_slug); setSetupOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to initialize security");
    } finally { setBusy(false); }
  }

  return (
    <main className="auth-page">
      <section className="auth-brand-panel">
        <div className="auth-mark"><ShieldIcon /></div>
        <div>
          <div className="eyebrow">Junior Lawyer · secure workspace</div>
          <h1>Client work stays inside the firm boundary.</h1>
          <p>Organization sessions, ethical walls, matter permissions, remote-AI controls and tamper-evident audit records sit underneath the legal workspace.</p>
        </div>
        <div className="auth-trust-list">
          <span><LockIcon /> Server-side session state</span>
          <span><ShieldIcon /> Matter-level confidentiality</span>
          <span><ShieldIcon /> Remote AI blocked by default</span>
        </div>
      </section>

      <section className="auth-form-panel">
        <form className="auth-card" onSubmit={submitLogin}>
          <div className="auth-card-head">
            <div className="auth-mini-mark">JL</div>
            <div><h2>Sign in</h2><p>Use your law-firm workspace account.</p></div>
          </div>
          <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required /></label>
          <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required /></label>
          <label>Organization slug <span>optional</span><input value={organizationSlug} onChange={(e) => setOrganizationSlug(e.target.value)} placeholder="firm-name" /></label>
          {error ? <div className="auth-error">{error}</div> : null}
          {setupMessage ? <div className="success-panel">{setupMessage}</div> : null}
          <button className="primary-button auth-submit" disabled={busy} type="submit">{busy ? "Signing in…" : "Sign in securely"}</button>
          <button className="auth-setup-link" type="button" onClick={() => setSetupOpen((value) => !value)}>{setupOpen ? "Close first-time setup" : "First-time firm setup"}</button>
        </form>

        {setupOpen ? (
          <form className="auth-card setup-card" onSubmit={submitSetup}>
            <div className="auth-card-head"><div><h2>Initialize firm</h2><p>Available only before the first organization exists.</p></div></div>
            <div className="auth-grid">
              <label>Firm name<input required value={setup.organization_name} onChange={(e) => setSetup({ ...setup, organization_name: e.target.value })} /></label>
              <label>Firm slug<input required pattern="[a-z0-9][a-z0-9-]*" value={setup.organization_slug} onChange={(e) => setSetup({ ...setup, organization_slug: e.target.value.toLowerCase() })} /></label>
              <label>Owner name<input required value={setup.admin_name} onChange={(e) => setSetup({ ...setup, admin_name: e.target.value })} /></label>
              <label>Owner email<input required type="email" value={setup.admin_email} onChange={(e) => setSetup({ ...setup, admin_email: e.target.value })} /></label>
              <label className="wide">Owner password<input required minLength={12} type="password" value={setup.password} onChange={(e) => setSetup({ ...setup, password: e.target.value })} /></label>
              <label className="wide">Bootstrap secret <span>required in production</span><input type="password" value={setup.bootstrap_secret} onChange={(e) => setSetup({ ...setup, bootstrap_secret: e.target.value })} /></label>
            </div>
            <button className="secondary-button" disabled={busy} type="submit">Initialize security</button>
          </form>
        ) : null}
      </section>
    </main>
  );
}
