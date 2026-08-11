import { ProcedureWorkspace } from "@/components/procedure-workspace";
import { getAgenda, getMatters, getProcedurePacks, getProcedureStats } from "@/lib/server-api";

export default async function CalendarPage() {
  let matters = [] as Awaited<ReturnType<typeof getMatters>>;
  let packs = [] as Awaited<ReturnType<typeof getProcedurePacks>>;
  let agenda = [] as Awaited<ReturnType<typeof getAgenda>>;
  let stats = null as Awaited<ReturnType<typeof getProcedureStats>> | null;
  let error = "";
  try {
    [matters, packs, agenda, stats] = await Promise.all([
      getMatters(), getProcedurePacks(), getAgenda(), getProcedureStats(),
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Unable to load procedure workspace";
  }
  return (
    <main className="page">
      <div className="hero-row procedure-hero">
        <div>
          <div className="eyebrow">Procedure & hearing operations</div>
          <h1 className="page-title">Calendar</h1>
          <p className="page-subtitle">Hearings, directions, compliance and transparent deadline calculations. Legal dates remain reviewable until counsel confirms the controlling rule.</p>
        </div>
        <div className="procedure-hero-note"><strong>Review-gated</strong><span>No silent limitation assumptions</span></div>
      </div>
      {error ? <div className="notice-panel">{error}</div> : null}
      {!error && stats ? <ProcedureWorkspace matters={matters} initialPacks={packs} initialAgenda={agenda} initialStats={stats} /> : null}
    </main>
  );
}
