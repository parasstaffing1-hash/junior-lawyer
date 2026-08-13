"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { LockIcon, ShieldIcon } from "@/components/icons";
import {
  confirmMFAEnrolment,
  disableMFA,
  getMFAStatus,
  startMFAEnrolment,
  type MFAEnrolmentStart,
  type MFAStatus,
} from "@/lib/api";

/**
 * Two-factor enrolment for the signed-in user.
 *
 * Recovery codes are shown exactly once, when enrolment is confirmed — the
 * server only keeps their hashes, so there is no second chance to read them.
 */
export function MFAPanel() {
  const [status, setStatus] = useState<MFAStatus | null>(null);
  const [enrolment, setEnrolment] = useState<MFAEnrolmentStart | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [disarming, setDisarming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setStatus(await getMFAStatus()); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to read MFA status"); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function begin() {
    setBusy(true); setError(""); setRecoveryCodes([]);
    try { setEnrolment(await startMFAEnrolment()); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to start enrolment"); }
    finally { setBusy(false); }
  }

  async function confirm(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const result = await confirmMFAEnrolment(code.trim());
      setRecoveryCodes(result.recovery_codes);
      setEnrolment(null); setCode("");
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "That code was not accepted"); }
    finally { setBusy(false); }
  }

  async function turnOff(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      await disableMFA(password);
      setPassword(""); setDisarming(false); setRecoveryCodes([]);
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to disable MFA"); }
    finally { setBusy(false); }
  }

  return (
    <section className="panel-card">
      <div className="panel-card-head">
        <h3><ShieldIcon /> Two-factor authentication</h3>
        {status?.enabled ? <span className="quiet-badge">Enabled</span> : <span className="quiet-badge">Off</span>}
      </div>

      {status?.enabled ? (
        <div className="panel-card-body">
          <p className="muted">
            Sign-in requires a code from your authenticator app.
            {" "}{status.recovery_codes_remaining} recovery code{status.recovery_codes_remaining === 1 ? "" : "s"} remaining.
          </p>
          {disarming ? (
            <form className="stacked-form" onSubmit={turnOff}>
              <label>Confirm your password
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
              </label>
              <div className="button-row">
                <button className="danger-button" type="submit" disabled={busy}>Turn off two-factor</button>
                <button className="ghost-button" type="button" onClick={() => { setDisarming(false); setPassword(""); }}>Cancel</button>
              </div>
            </form>
          ) : (
            <button className="ghost-button" type="button" onClick={() => setDisarming(true)}>Turn off…</button>
          )}
        </div>
      ) : enrolment ? (
        <div className="panel-card-body">
          <p className="muted">Add this secret to your authenticator app, then enter the code it shows.</p>
          <code className="mfa-secret">{enrolment.secret}</code>
          <p className="muted mfa-uri">{enrolment.provisioning_uri}</p>
          <form className="stacked-form" onSubmit={confirm}>
            <label>Code from your app
              <input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" placeholder="123456" required />
            </label>
            <div className="button-row">
              <button className="primary-button" type="submit" disabled={busy}>Confirm and enable</button>
              <button className="ghost-button" type="button" onClick={() => { setEnrolment(null); setCode(""); }}>Cancel</button>
            </div>
          </form>
        </div>
      ) : (
        <div className="panel-card-body">
          <p className="muted"><LockIcon /> Protects the account even if the password is stolen. Recommended for every account holding client matters.</p>
          <button className="primary-button" type="button" onClick={begin} disabled={busy}>Set up two-factor</button>
        </div>
      )}

      {recoveryCodes.length ? (
        <div className="success-panel">
          <strong>Save these recovery codes now — they are shown only once.</strong>
          <ul className="recovery-code-list">
            {recoveryCodes.map((value) => <li key={value}><code>{value}</code></li>)}
          </ul>
        </div>
      ) : null}

      {error ? <div className="auth-error">{error}</div> : null}
    </section>
  );
}
