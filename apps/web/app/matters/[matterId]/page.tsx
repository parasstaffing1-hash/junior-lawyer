import Link from "next/link";

import { DocumentUploadPanel } from "@/components/document-upload-panel";
import { RebuildIntelligenceButton } from "@/components/rebuild-intelligence-button";
import { ReviewActions } from "@/components/review-actions";
import { RemedyWorkspace } from "@/components/remedy-workspace";
import {
  getContradictions,
  getDocuments,
  getEvidence,
  getDrafts,
  getFacts,
  getIntelligenceSummary,
  getMatter,
  getReviewItems,
  getStatements,
  getTimeline,
  type EvidenceMatrix,
  type IntelligenceSummary,
  type LegalDocument,
  type LegalDraftListItem,
  type Matter,
  type MatterContradiction,
  type MatterFact,
  type MatterStatement,
  type ReviewItem,
  type TimelineEvent,
} from "@/lib/server-api";

const views = ["overview", "documents", "facts", "timeline", "evidence", "review", "drafts", "remedies"] as const;
type WorkspaceView = (typeof views)[number];

const tabLabels: Record<WorkspaceView, string> = {
  overview: "Overview",
  documents: "Documents",
  facts: "Facts",
  timeline: "Timeline",
  evidence: "Evidence",
  review: "Review",
  drafts: "Drafts",
  remedies: "Remedies",
};

function languageLabel(language: LegalDocument["detected_language"]) {
  return {
    en: "English",
    hi: "हिन्दी",
    mixed: "EN + हिन्दी",
    hinglish: "Hinglish",
    unknown: "Unknown",
  }[language];
}

function methodLabel(method: LegalDocument["extraction_method"]) {
  return {
    native_pdf: "Native PDF",
    ocr: "OCR",
    mixed_pdf: "PDF + OCR",
    docx: "DOCX",
    text: "Text",
    image_ocr: "Image OCR",
    unknown: "Pending",
  }[method];
}

function formatBytes(bytes: number | null) {
  if (!bytes) return "—";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string) {
  const date = new Date(`${value}T00:00:00`);
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function confidence(value: number) {
  return `${Math.round(value * 100)}%`;
}

function SourceLine({ filename, page }: { filename: string | null; page: number | null }) {
  return (
    <span className="source-ref">
      {filename ?? "Source document"}{page ? ` · p.${page}` : ""}
    </span>
  );
}

function DocumentsView({ matterId, documents }: { matterId: string; documents: LegalDocument[] }) {
  return (
    <>
      <DocumentUploadPanel matterId={matterId} />
      <section className="card" style={{ marginTop: 18 }}>
        <div className="card-header">
          <div className="card-title">Document index</div>
          <div className="card-action">SHA-256 duplicate protection enabled</div>
        </div>
        {documents.length ? (
          <div className="document-table">
            <div className="document-table-head">
              <span>Document</span><span>Extraction</span><span>Language</span><span>Sources</span><span>Status</span>
            </div>
            {documents.map((document) => (
              <div className="document-row" key={document.id}>
                <div className="document-main">
                  <Link className="document-name document-name-link" href={`/documents/${document.id}`}>{document.filename}</Link>
                  <div className="document-meta">{formatBytes(document.size_bytes)} · {document.page_count ?? 0} pages</div>
                  {document.processing_error ? <div className="document-error">{document.processing_error}</div> : null}
                </div>
                <div><span className="quiet-badge">{methodLabel(document.extraction_method)}</span></div>
                <div><span className="quiet-badge">{languageLabel(document.detected_language)}</span></div>
                <div className="source-count">{Object.values(document.entity_counts).reduce((sum, count) => sum + count, 0)} entities</div>
                <div><span className={`processing-badge ${document.processing_status}`}>{document.processing_status}</span></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state compact">
            <div className="empty-state-title">No documents in this matter</div>
            <div className="empty-state-copy">Upload a PDF, DOCX, TXT, PNG, JPG or TIFF. Scans are OCR’d locally; searchable PDFs use native text.</div>
          </div>
        )}
      </section>
    </>
  );
}

function FactsView({ facts }: { facts: MatterFact[] }) {
  if (!facts.length) {
    return <EmptyIntelligence title="No structured facts yet" copy="Upload and process documents, then rebuild matter intelligence." />;
  }
  return (
    <section className="card intelligence-card">
      <div className="card-header">
        <div className="card-title">Structured facts</div>
        <div className="card-action">Every fact retains page-level provenance</div>
      </div>
      <div className="fact-list">
        {facts.map((fact) => (
          <article className="fact-row" key={fact.id}>
            <div>
              <div className="fact-label">{fact.label}</div>
              <div className="fact-value">{fact.value_text}</div>
              <div className="fact-meta">{fact.category.replaceAll("_", " ")} · confidence {confidence(fact.confidence)}</div>
            </div>
            <div className="fact-sources">
              {fact.sources.slice(0, 3).map((source) => (
                <div className="source-snippet" key={source.id}>
                  <SourceLine filename={source.filename} page={source.page_number} />
                  <p>{source.quote}</p>
                </div>
              ))}
              {fact.sources.length > 3 ? <div className="more-sources">+{fact.sources.length - 3} more sources</div> : null}
            </div>
            <div><span className={`fact-status ${fact.status}`}>{fact.status}</span></div>
          </article>
        ))}
      </div>
    </section>
  );
}

function TimelineView({ timeline }: { timeline: TimelineEvent[] }) {
  if (!timeline.length) {
    return <EmptyIntelligence title="No chronology yet" copy="Dates only become timeline events when deterministic legal/action cues support them." />;
  }
  return (
    <section className="card intelligence-card">
      <div className="card-header">
        <div className="card-title">Matter chronology</div>
        <div className="card-action">Repeatable events are preserved instead of treated as conflicts</div>
      </div>
      <div className="timeline-list">
        {timeline.map((event) => (
          <article className="timeline-row" key={event.id}>
            <div className="timeline-date">{formatDate(event.event_date)}</div>
            <div className="timeline-marker"><span /></div>
            <div className="timeline-content">
              <div className="timeline-title">{event.title}</div>
              <p>{event.description}</p>
              <div className="timeline-sources">
                {event.sources.slice(0, 2).map((source) => (
                  <SourceLine key={source.id} filename={source.filename} page={source.page_number} />
                ))}
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ContradictionCard({ contradiction }: { contradiction: MatterContradiction }) {
  return (
    <article className={`contradiction-card ${contradiction.severity}`}>
      <div className="contradiction-topline">
        <span className={`severity-badge ${contradiction.severity}`}>{contradiction.severity} conflict</span>
        <span className="quiet-text">{contradiction.status}</span>
      </div>
      <h3>{contradiction.label}</h3>
      <p>{contradiction.explanation}</p>
      <div className="conflict-values">
        {contradiction.values_json.map((value) => (
          <div className="conflict-value" key={value.fact_id}>
            <strong>{value.display}</strong>
            <span>{confidence(value.confidence)} confidence</span>
          </div>
        ))}
      </div>
    </article>
  );
}

function EvidenceView({ evidence, contradictions }: { evidence: EvidenceMatrix | null; contradictions: MatterContradiction[] }) {
  if (!evidence || !evidence.facts.length) {
    return <EmptyIntelligence title="No evidence matrix yet" copy="The matrix is generated from structured facts and their exact source pages." />;
  }
  const contradictionById = new Map(contradictions.map((item) => [item.id, item]));
  return (
    <div className="evidence-layout">
      <section className="card intelligence-card">
        <div className="card-header">
          <div className="card-title">Evidence matrix</div>
          <div className="card-action">Source-backed facts only</div>
        </div>
        <div className="evidence-table">
          <div className="evidence-head"><span>Fact</span><span>Evidence</span><span>Review</span></div>
          {evidence.facts.map(({ fact, contradiction_id, contradiction_severity }) => (
            <div className="evidence-row" key={fact.id}>
              <div>
                <div className="fact-label">{fact.label}</div>
                <div className="fact-value small">{fact.value_text}</div>
              </div>
              <div>
                <div className="evidence-source-count">{fact.sources.length} source{fact.sources.length === 1 ? "" : "s"}</div>
                {fact.sources.slice(0, 2).map((source) => (
                  <SourceLine key={source.id} filename={source.filename} page={source.page_number} />
                ))}
              </div>
              <div>
                {contradiction_id ? (
                  <span className={`severity-badge ${contradiction_severity ?? "medium"}`}>conflict</span>
                ) : (
                  <span className="verified-badge">consistent</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>
      <aside className="evidence-side">
        <div className="card contradiction-summary">
          <div className="card-header"><div className="card-title">Conflicts</div></div>
          {contradictions.length ? contradictions.slice(0, 4).map((item) => (
            <div className="mini-conflict" key={item.id}>
              <span className={`severity-dot ${item.severity}`} />
              <div><strong>{item.label}</strong><p>{item.values_json.length} competing values</p></div>
            </div>
          )) : <div className="empty-mini">No deterministic conflicts detected.</div>}
        </div>
        <div className="card statement-count-card">
          <div className="card-header"><div className="card-title">Statements</div></div>
          {Object.entries(evidence.statement_counts).map(([kind, count]) => (
            <div className="count-row" key={kind}><span>{kind}</span><strong>{count}</strong></div>
          ))}
          {!Object.keys(evidence.statement_counts).length ? <div className="empty-mini">No claims, admissions or denials detected yet.</div> : null}
        </div>
      </aside>
    </div>
  );
}

function ReviewView({ review, contradictions, statements }: { review: ReviewItem[]; contradictions: MatterContradiction[]; statements: MatterStatement[] }) {
  return (
    <div className="review-layout">
      <section className="card intelligence-card">
        <div className="card-header">
          <div className="card-title">Human review queue</div>
          <div className="card-action">The engine never silently chooses between conflicting sources</div>
        </div>
        {review.length ? (
          <div className="review-list">
            {review.map((item) => (
              <article className="review-row" key={item.id}>
                <span className={`priority-mark ${item.priority}`} />
                <div>
                  <div className="review-title">{item.title}</div>
                  <p>{item.reason}</p>
                </div>
                <div className="review-decision">
                  <span className={`review-status ${item.status}`}>{item.status}</span>
                  <ReviewActions item={item} />
                </div>
              </article>
            ))}
          </div>
        ) : <div className="empty-state compact"><div className="empty-state-title">Review queue is clear</div><div className="empty-state-copy">No open contradictions or low-confidence facts currently require attention.</div></div>}
      </section>

      {contradictions.length ? (
        <section className="contradictions-grid">
          {contradictions.map((item) => <ContradictionCard contradiction={item} key={item.id} />)}
        </section>
      ) : null}

      <section className="card intelligence-card">
        <div className="card-header">
          <div className="card-title">Claims, admissions & denials</div>
          <div className="card-action">Rule-based statement classification</div>
        </div>
        {statements.length ? (
          <div className="statement-list">
            {statements.map((statement) => (
              <article className="statement-row" key={statement.id}>
                <span className={`statement-kind ${statement.kind}`}>{statement.kind}</span>
                <div>
                  <p>{statement.raw_text}</p>
                  <div className="statement-meta">
                    {statement.speaker_role ?? "speaker not resolved"} · <SourceLine filename={statement.filename} page={statement.page_number} /> · {confidence(statement.confidence)}
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : <div className="empty-state compact"><div className="empty-state-title">No classified statements yet</div><div className="empty-state-copy">The detector supports English, Hindi, and common Hinglish pleading cues.</div></div>}
      </section>
    </div>
  );
}


function DraftsView({ drafts, matterId }: { drafts: LegalDraftListItem[]; matterId: string }) {
  return (
    <section className="card intelligence-card">
      <div className="card-header">
        <div><div className="card-title">Legal work product</div><div className="quiet-text">Source-backed drafts linked to this matter</div></div>
        <Link className="button primary small" href={`/drafting`}>New draft</Link>
      </div>
      {drafts.length ? <div className="matter-draft-list">
        {drafts.map((draft) => (
          <Link className="matter-draft-row" href={`/drafting?draft=${draft.id}`} key={draft.id}>
            <div>
              <span className="draft-type-kicker">{draft.draft_type.replaceAll("_", " ")}</span>
              <strong>{draft.title}</strong>
              <small>{draft.language === "bilingual" ? "English + हिन्दी" : draft.language === "hi" ? "हिन्दी" : "English"}</small>
            </div>
            <div className="matter-draft-status">
              <span className={`draft-status ${draft.status}`}>{draft.status.replaceAll("_", " ")}</span>
              <strong>{draft.health_score}/100</strong>
              <small>{draft.reviewed_sections}/{draft.section_count} reviewed</small>
            </div>
          </Link>
        ))}
      </div> : <div className="empty-state compact"><div className="empty-state-title">No drafts for this matter</div><div className="empty-state-copy">Create notices, pleadings, chronologies, annexure indexes or hearing notes from the verified matter record.</div></div>}
    </section>
  );
}

function EmptyIntelligence({ title, copy }: { title: string; copy: string }) {
  return (
    <section className="card">
      <div className="empty-state">
        <div className="empty-state-title">{title}</div>
        <div className="empty-state-copy">{copy}</div>
      </div>
    </section>
  );
}

function OverviewView({ summary, contradictions, timeline }: { summary: IntelligenceSummary | null; contradictions: MatterContradiction[]; timeline: TimelineEvent[] }) {
  if (!summary) return <EmptyIntelligence title="Matter intelligence unavailable" copy="Process at least one document and rebuild intelligence." />;
  return (
    <div className="overview-intelligence">
      <section className="intelligence-strip">
        <div><span>Facts</span><strong>{summary.facts}</strong></div>
        <div><span>Timeline</span><strong>{summary.timeline_events}</strong></div>
        <div><span>Contradictions</span><strong>{summary.contradictions}</strong></div>
        <div><span>Needs review</span><strong>{summary.open_review_items}</strong></div>
        <div><span>Admissions</span><strong>{summary.admissions}</strong></div>
      </section>
      <div className="grid-2 intelligence-overview-grid">
        <section className="card">
          <div className="card-header"><div className="card-title">Recent chronology</div><Link className="card-action" href="?view=timeline">View timeline</Link></div>
          {timeline.length ? timeline.slice(-5).reverse().map((event) => (
            <div className="overview-event" key={event.id}>
              <div className="overview-event-date">{formatDate(event.event_date)}</div>
              <div><strong>{event.title}</strong><p>{event.description}</p></div>
            </div>
          )) : <div className="empty-mini padded">No timeline events yet.</div>}
        </section>
        <section className="card">
          <div className="card-header"><div className="card-title">Attention</div><Link className="card-action" href="?view=review">Open review</Link></div>
          {contradictions.length ? contradictions.slice(0, 4).map((item) => (
            <div className="overview-alert" key={item.id}>
              <span className={`severity-dot ${item.severity}`} />
              <div><strong>{item.label}</strong><p>{item.values_json.map((value) => value.display).join(" vs ")}</p></div>
            </div>
          )) : <div className="empty-mini padded">No deterministic contradictions detected.</div>}
        </section>
      </div>
    </div>
  );
}

export default async function MatterWorkspace({
  params,
  searchParams,
}: {
  params: Promise<{ matterId: string }>;
  searchParams: Promise<{ view?: string }>;
}) {
  const { matterId } = await params;
  const requestedView = (await searchParams).view;
  const view: WorkspaceView = views.includes(requestedView as WorkspaceView)
    ? (requestedView as WorkspaceView)
    : "overview";

  let matter: Matter | undefined;
  let documents: LegalDocument[] = [];
  let summary: IntelligenceSummary | null = null;
  let facts: MatterFact[] = [];
  let timeline: TimelineEvent[] = [];
  let evidence: EvidenceMatrix | null = null;
  let contradictions: MatterContradiction[] = [];
  let review: ReviewItem[] = [];
  let statements: MatterStatement[] = [];
  let drafts: LegalDraftListItem[] = [];
  let apiError = "";

  try {
    [matter, documents] = await Promise.all([getMatter(matterId), getDocuments(matterId)]);
    try {
      summary = await getIntelligenceSummary(matterId);
      if (view === "overview") {
        [timeline, contradictions] = await Promise.all([getTimeline(matterId), getContradictions(matterId)]);
      } else if (view === "facts") {
        facts = await getFacts(matterId);
      } else if (view === "timeline") {
        timeline = await getTimeline(matterId);
      } else if (view === "evidence") {
        [evidence, contradictions] = await Promise.all([getEvidence(matterId), getContradictions(matterId)]);
      } else if (view === "review") {
        [review, contradictions, statements] = await Promise.all([
          getReviewItems(matterId),
          getContradictions(matterId),
          getStatements(matterId),
        ]);
      } else if (view === "drafts") {
        drafts = await getDrafts(matterId);
      }
    } catch (error) {
      apiError = error instanceof Error ? error.message : "Matter intelligence unavailable";
    }
  } catch (error) {
    apiError = error instanceof Error ? error.message : "Unable to load matter";
  }

  if (!matter) {
    return (
      <main className="page">
        <div className="eyebrow">Matter workspace</div>
        <h1 className="page-title">Matter unavailable</h1>
        <div className="notice-panel" style={{ marginTop: 24 }}><span>{apiError}</span></div>
      </main>
    );
  }

  const ready = documents.filter((document) => document.processing_status === "ready").length;
  const totalPages = documents.reduce((sum, document) => sum + (document.page_count ?? 0), 0);

  return (
    <main className="page">
      <div className="hero-row matter-hero">
        <div>
          <div className="eyebrow">Matter workspace</div>
          <h1 className="page-title">{matter.title}</h1>
          <p className="page-subtitle">
            {[matter.court_name, matter.case_number, matter.primary_language === "bilingual" ? "English + हिन्दी" : matter.primary_language]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <div className="hero-actions"><Link className="button secondary" href={`/matters/${matterId}?view=remedies`}>Find Legal Remedies</Link><RebuildIntelligenceButton matterId={matterId} /></div>
      </div>

      <nav className="workspace-tabs" aria-label="Matter workspace">
        {views.map((tab) => (
          <Link
            className={`workspace-tab${tab === view ? " active" : ""}`}
            href={tab === "overview" ? `/matters/${matterId}` : `/matters/${matterId}?view=${tab}`}
            key={tab}
          >
            {tabLabels[tab]}
            {tab === "review" && summary?.open_review_items ? <span className="tab-count">{summary.open_review_items}</span> : null}
          </Link>
        ))}
        <span className="workspace-tab future-tab">Research</span>
        <span className="workspace-tab future-tab">Hearings</span>
      </nav>

      <section className="metrics" style={{ marginTop: 22 }}>
        <div className="metric"><div className="metric-label">Documents</div><div className="metric-value">{documents.length}</div><div className="metric-note">{ready} processed</div></div>
        <div className="metric"><div className="metric-label">Source pages</div><div className="metric-value">{totalPages}</div><div className="metric-note">page-level provenance</div></div>
        <div className="metric"><div className="metric-label">Structured facts</div><div className="metric-value">{summary?.facts ?? 0}</div><div className="metric-note">deterministic extraction</div></div>
        <div className="metric"><div className="metric-label">Open conflicts</div><div className="metric-value">{summary?.contradictions ?? 0}</div><div className="metric-note">lawyer review required</div></div>
      </section>

      {apiError && documents.length ? <div className="notice-panel"><span>{apiError}</span></div> : null}

      {view === "overview" ? <OverviewView summary={summary} contradictions={contradictions} timeline={timeline} /> : null}
      {view === "documents" ? <DocumentsView matterId={matterId} documents={documents} /> : null}
      {view === "facts" ? <FactsView facts={facts} /> : null}
      {view === "timeline" ? <TimelineView timeline={timeline} /> : null}
      {view === "evidence" ? <EvidenceView evidence={evidence} contradictions={contradictions} /> : null}
      {view === "review" ? <ReviewView review={review} contradictions={contradictions} statements={statements} /> : null}
      {view === "drafts" ? <DraftsView drafts={drafts} matterId={matterId} /> : null}
      {view === "remedies" ? <RemedyWorkspace matterId={matterId} /> : null}
    </main>
  );
}
