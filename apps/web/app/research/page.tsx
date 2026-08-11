import { ResearchWorkspace } from "@/components/research-workspace";
import { getResearchStats, ResearchStats } from "@/lib/server-api";

export default async function ResearchPage() {
  let stats: ResearchStats | null = null;
  try {
    stats = await getResearchStats();
  } catch {
    // The API may not be running during a frontend-only preview.
  }

  return (
    <main className="page research-page">
      <div className="hero-row research-hero">
        <div>
          <div className="eyebrow">Legal research · India</div>
          <h1 className="page-title">Find authority, not generated answers.</h1>
          <p className="page-subtitle">
            Bilingual deterministic search across statutes and paragraph-level judgments, ranked by relevance and court authority with source provenance.
          </p>
        </div>
        <div className="research-stat-stack">
          <div><strong>{stats?.statute_sections.toLocaleString("en-IN") ?? "—"}</strong><span>statutory provisions</span></div>
          <div><strong>{stats?.judgment_paragraphs.toLocaleString("en-IN") ?? "—"}</strong><span>judgment paragraphs</span></div>
          <div><strong>{stats?.resolved_citations.toLocaleString("en-IN") ?? "—"}</strong><span>resolved citations</span></div>
        </div>
      </div>
      <ResearchWorkspace initialStats={stats} />
    </main>
  );
}
