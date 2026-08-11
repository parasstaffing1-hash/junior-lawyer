import { AssistantWorkspace } from "@/components/assistant-workspace";
import { getAIProviderStatus, getAIRuns, getMatters } from "@/lib/server-api";

export default async function AssistantPage() {
  let matters = [] as Awaited<ReturnType<typeof getMatters>>;
  let runs = [] as Awaited<ReturnType<typeof getAIRuns>>;
  let providers = null as Awaited<ReturnType<typeof getAIProviderStatus>> | null;
  let error = "";
  try {
    [matters, runs, providers] = await Promise.all([getMatters(), getAIRuns(), getAIProviderStatus()]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Unable to load verified reasoning workspace";
  }
  return (
    <main className="page">
      <div className="hero-row ai-hero">
        <div>
          <div className="eyebrow">Verified reasoning layer</div>
          <h1 className="page-title">Junior Lawyer Assistant</h1>
          <p className="page-subtitle">Model calls sit behind deterministic routing, evidence packets, explicit budgets and citation verification. Remote AI is opt-in per request.</p>
        </div>
        <div className="ai-hero-note"><strong>Evidence bounded</strong><span>Sources first · model second · lawyer last</span></div>
      </div>
      {error ? <div className="notice-panel">{error}</div> : null}
      {!error && providers ? <AssistantWorkspace matters={matters} initialRuns={runs} providers={providers} /> : null}
    </main>
  );
}
