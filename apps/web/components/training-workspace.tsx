"use client";

import Link from "next/link";
import { useMemo, useState, useSyncExternalStore } from "react";

import { CheckIcon, LockIcon, ScaleIcon } from "@/components/icons";
import { calculateLimitationPeriod } from "@/lib/tools";
import {
  BRIEF,
  STEPS,
  getProgress,
  getServerProgress,
  sameOrder,
  sameSet,
  setProgress,
  subscribeProgress,
  type Step,
} from "@/lib/training";

function formatDate(iso: string) {
  const date = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
}

export function TrainingWorkspace() {
  const progress = useSyncExternalStore(subscribeProgress, getProgress, getServerProgress);
  const completed = progress.completed;

  /**
   * `null` means "follow the stage the student is on"; `""` means they closed
   * everything. Deriving the open card this way keeps it in step with progress
   * without an effect to synchronise the two.
   */
  const [openOverride, setOpenOverride] = useState<string | null>(null);

  const currentIndex = useMemo(() => {
    const index = STEPS.findIndex((step) => !completed.includes(step.key));
    return index === -1 ? STEPS.length : index;
  }, [completed]);

  const openKey =
    openOverride === null ? STEPS[Math.min(currentIndex, STEPS.length - 1)].key : openOverride;

  function complete(key: string) {
    if (completed.includes(key)) return;
    setProgress({ completed: [...completed, key] });
    // Fall back to following the current stage, which is now the next one.
    setOpenOverride(null);
  }

  function reset() {
    setProgress({ completed: [] });
    setOpenOverride(null);
  }

  const done = completed.length;
  const total = STEPS.length;

  return (
    <main className="page">
      <div className="hero-row">
        <div>
          <div className="page-icon" aria-hidden="true"><ScaleIcon /></div>
          <div className="eyebrow">Training</div>
          <h1 className="page-title">Articled clerk walkthrough</h1>
          <p className="page-subtitle">
            One matter, taken in the order a district practice takes it. Each stage stays locked
            until the one before it is answered, because the sequence is the thing being taught.
          </p>
        </div>
        {done > 0 ? (
          <button className="secondary-button" type="button" onClick={reset}>
            Start again
          </button>
        ) : null}
      </div>

      <div className="notice-panel" style={{ marginBottom: 18 }}>
        <strong>Teaching material.</strong>
        <span>
          The matter below is fictional and the answers are general procedure, not advice on any
          real case. Provisions are cited so you can read them yourself in{" "}
          <Link href="/acts">Acts</Link> — check them there rather than trusting this page.
        </span>
      </div>

      <section className="card training-brief">
        <div className="card-header">
          <div className="card-title">The brief</div>
          <div className="card-action">{BRIEF.forum}</div>
        </div>
        <div className="training-brief-body">
          <p>{BRIEF.summary}</p>
          <dl className="tool-subreadout">
            <div>
              <dt>Client</dt>
              <dd>{BRIEF.client}</dd>
            </div>
            <div>
              <dt>Opposite party</dt>
              <dd>{BRIEF.opponent}</dd>
            </div>
            <div>
              <dt>Claim value</dt>
              <dd>₹{BRIEF.claimValue.toLocaleString("en-IN")}</dd>
            </div>
            <div>
              <dt>Breach</dt>
              <dd>{formatDate(BRIEF.breachDate)}</dd>
            </div>
          </dl>
        </div>
      </section>

      <div className="training-progress">
        <div className="training-progress-track" aria-hidden="true">
          <span style={{ width: `${(done / total) * 100}%` }} />
        </div>
        <span className="training-progress-count" role="status">
          {done} of {total} stages
        </span>
      </div>

      <ol className="training-steps">
        {STEPS.map((step, index) => {
          const isDone = completed.includes(step.key);
          const isLocked = index > currentIndex;
          const isOpen = openKey === step.key && !isLocked;
          return (
            <StepCard
              key={step.key}
              step={step}
              index={index}
              done={isDone}
              locked={isLocked}
              open={isOpen}
              onToggle={() => setOpenOverride(isOpen ? "" : step.key)}
              onPass={() => complete(step.key)}
            />
          );
        })}
      </ol>

      {done === total ? (
        <div className="card training-complete">
          <div className="empty-state">
            <div className="empty-state-title">All six stages answered.</div>
            <div className="empty-state-copy">
              You have taken one matter from intake to the first hearing in the order it happens.
              The same steps are live in this workspace — open{" "}
              <Link href="/matters">Matters</Link> to run one for real, or{" "}
              <Link href="/tools">Tools</Link> for the calculators used here.
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}

function StepCard({
  step,
  index,
  done,
  locked,
  open,
  onToggle,
  onPass,
}: {
  step: Step;
  index: number;
  done: boolean;
  locked: boolean;
  open: boolean;
  onToggle: () => void;
  onPass: () => void;
}) {
  const state = done ? "done" : locked ? "locked" : "current";
  return (
    <li className={`card training-step ${state}${open ? " open" : ""}`}>
      <button
        className="training-step-head"
        type="button"
        onClick={onToggle}
        disabled={locked}
        aria-expanded={open}
      >
        <span className="training-step-mark" aria-hidden="true">
          {done ? <CheckIcon /> : locked ? <LockIcon /> : index + 1}
        </span>
        <span className="training-step-heading">
          <span className="training-step-stage">{step.stage}</span>
          <strong>{step.title}</strong>
        </span>
        <span className="training-step-state">
          {done ? "Answered" : locked ? "Locked" : "Now"}
        </span>
      </button>

      {open ? (
        <div className="training-step-body">
          <p className="training-prompt">{step.prompt}</p>
          {done ? (
            <div className="training-why">
              <strong>Why it goes here</strong>
              <p>{step.why}</p>
              <p className="training-authority">{step.authority}</p>
            </div>
          ) : (
            <StepGate step={step} onPass={onPass} />
          )}
        </div>
      ) : null}
    </li>
  );
}

function StepGate({ step, onPass }: { step: Step; onPass: () => void }) {
  const [hint, setHint] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [dateAnswer, setDateAnswer] = useState("");
  const [busy, setBusy] = useState(false);

  const gate = step.gate;

  async function check() {
    if (gate.kind === "single") {
      if (picked[0] === gate.correct) onPass();
      else setHint(step.hint);
      return;
    }
    if (gate.kind === "multi") {
      if (sameSet(picked, gate.correct)) onPass();
      else setHint(step.hint);
      return;
    }
    if (gate.kind === "order") {
      if (picked.length !== gate.options.length) {
        setHint(`Put all ${gate.options.length} in order before checking.`);
        return;
      }
      if (sameOrder(picked, gate.correct)) onPass();
      else setHint(step.hint);
      return;
    }

    // computed-date: the app works the answer out with the same engine the
    // limitation tool uses, so the gate can never drift from the calculator.
    if (!dateAnswer) {
      setHint("Enter a date first.");
      return;
    }
    setBusy(true);
    try {
      const result = await calculateLimitationPeriod({
        trigger_date: gate.triggerDate,
        period_value: gate.periodValue,
        period_unit: gate.periodUnit,
        extension_periods: [],
        expiry_adjustment: "next_business_day",
        excluded_dates: [],
      });
      const expected = String(result.final_expiry_date ?? "").slice(0, 10);
      if (!expected) {
        setHint("The limitation engine did not return a date. Is the API running?");
        return;
      }
      if (dateAnswer === expected) onPass();
      else setHint(step.hint);
    } catch {
      setHint("Could not reach the limitation engine. Start the API and try again.");
    } finally {
      setBusy(false);
    }
  }

  function toggle(id: string) {
    setHint("");
    if (gate.kind === "single") {
      setPicked([id]);
      return;
    }
    setPicked((previous) =>
      previous.includes(id) ? previous.filter((value) => value !== id) : [...previous, id],
    );
  }

  return (
    <div className="training-gate">
      {gate.kind === "computed-date" ? (
        <label className="tool-field training-date">
          <span>Last date for filing</span>
          <input
            type="date"
            value={dateAnswer}
            onChange={(event) => {
              setDateAnswer(event.target.value);
              setHint("");
            }}
          />
        </label>
      ) : (
        <ul className="training-options">
          {gate.options.map((option) => {
            const position = picked.indexOf(option.id);
            const chosen = position !== -1;
            return (
              <li key={option.id}>
                <button
                  type="button"
                  className={`training-option${chosen ? " chosen" : ""}`}
                  onClick={() => toggle(option.id)}
                  aria-pressed={chosen}
                >
                  <span className="training-option-mark" aria-hidden="true">
                    {gate.kind === "order"
                      ? chosen
                        ? position + 1
                        : ""
                      : chosen
                        ? <CheckIcon />
                        : ""}
                  </span>
                  <span>{option.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <div className="training-actions">
        <button className="primary-button" type="button" onClick={check} disabled={busy}>
          {busy ? "Checking…" : "Check answer"}
        </button>
        {gate.kind === "order" && picked.length ? (
          <button className="secondary-button" type="button" onClick={() => setPicked([])}>
            Clear order
          </button>
        ) : null}
        {gate.kind === "multi" ? (
          <span className="training-note">Select every answer that holds.</span>
        ) : null}
      </div>

      {hint ? (
        <p className="training-verdict wrong" role="alert">
          Not yet. {hint}
        </p>
      ) : null}
    </div>
  );
}
