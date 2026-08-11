import { DraftingWorkspace } from "@/components/drafting-workspace";
import { getDraftCatalog, getDrafts, getMatters } from "@/lib/server-api";

export default async function DraftingPage({ searchParams }: { searchParams: Promise<{ draft?: string }> }) {
  const query = await searchParams;
  let matters = [] as Awaited<ReturnType<typeof getMatters>>;
  let catalog = [] as Awaited<ReturnType<typeof getDraftCatalog>>;
  let drafts = [] as Awaited<ReturnType<typeof getDrafts>>;
  let error = "";
  try {
    [matters, catalog, drafts] = await Promise.all([getMatters(), getDraftCatalog(), getDrafts()]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Unable to load Drafting Studio";
  }

  return (
    <main className="page">
      <div className="hero-row drafting-hero">
        <div>
          <div className="eyebrow">Legal work product</div>
          <h1 className="page-title">Drafting Studio</h1>
          <p className="page-subtitle">Matter-backed drafting with English, हिन्दी and bilingual output. Deterministic where possible; lawyer-controlled where judgment is required.</p>
        </div>
        <div className="drafting-hero-note"><strong>Source-first</strong><span>No invented facts or citations</span></div>
      </div>
      {error ? <div className="notice-panel"><span>{error}</span></div> : null}
      {!error && matters.length ? <DraftingWorkspace matters={matters} catalog={catalog} initialDrafts={drafts} initialDraftId={query.draft} /> : null}
      {!error && !matters.length ? <section className="card"><div className="empty-state"><div className="empty-state-title">Create a matter first</div><div className="empty-state-copy">Drafting Studio uses matter facts, documents, chronology and evidence as its source record.</div></div></section> : null}
    </main>
  );
}
