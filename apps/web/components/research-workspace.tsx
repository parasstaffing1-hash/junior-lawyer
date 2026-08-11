"use client";

import { FormEvent, useMemo, useState } from "react";
import { SearchIcon } from "@/components/icons";
import {
  CourtLevel,
  ResearchResult,
  ResearchScope,
  ResearchStats,
  searchResearch,
  seedResearchSources,
} from "@/lib/api";

const COURTS: Array<{ value: "" | CourtLevel; label: string }> = [
  { value: "", label: "All courts" },
  { value: "supreme_court", label: "Supreme Court" },
  { value: "high_court", label: "High Courts" },
  { value: "appellate_tribunal", label: "Appellate tribunals" },
  { value: "tribunal", label: "Tribunals" },
  { value: "district_court", label: "District courts" },
];

function formatCourt(value: CourtLevel | null) {
  if (!value) return null;
  return value.split("_").map((part) => part[0]?.toUpperCase() + part.slice(1)).join(" ");
}

function scorePercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function ResultCard({ result, rank }: { result: ResearchResult; rank: number }) {
  const isStatute = result.result_type === "statute_section";
  return (
    <article className="research-result">
      <div className="research-rank">{String(rank).padStart(2, "0")}</div>
      <div className="research-result-main">
        <div className="research-result-topline">
          <span className={`source-pill ${isStatute ? "statute" : "judgment"}`}>
            {isStatute ? "Statute" : formatCourt(result.court_level) ?? "Judgment"}
          </span>
          {Boolean(result.metadata.official) && <span className="official-pill">Official source</span>}
          {result.paragraph_number && <span className="quiet-meta">¶ {result.paragraph_number}</span>}
          {result.section_number && <span className="quiet-meta">Section {result.section_number}</span>}
        </div>
        <h3>{result.title}</h3>
        <div className="research-byline">
          {result.subtitle && <span>{result.subtitle}</span>}
          {result.court_name && <span>{result.court_name}</span>}
          {result.decision_date && <span>{new Date(result.decision_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</span>}
        </div>
        <p className="research-snippet">{result.snippet}</p>
        <div className="research-result-footer">
          <span>{result.source_name}</span>
          <span>Relevance {scorePercent(result.score)}</span>
          <span>Authority {scorePercent(result.authority_score)}</span>
          {result.source_url && (
            <a href={result.source_url} target="_blank" rel="noreferrer">Open source ↗</a>
          )}
        </div>
      </div>
    </article>
  );
}

export function ResearchWorkspace({ initialStats }: { initialStats: ResearchStats | null }) {
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState<ResearchScope>("all");
  const [courtLevel, setCourtLevel] = useState<"" | CourtLevel>("");
  const [act, setAct] = useState("");
  const [section, setSection] = useState("");
  const [results, setResults] = useState<ResearchResult[]>([]);
  const [expandedTerms, setExpandedTerms] = useState<string[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [stats, setStats] = useState(initialStats);

  const corpusEmpty = useMemo(
    () => !stats || stats.statute_sections + stats.judgment_paragraphs === 0,
    [stats],
  );

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (query.trim().length < 2) return;
    setLoading(true);
    setMessage(null);
    try {
      const response = await searchResearch({
        query: query.trim(),
        scope,
        court_level: courtLevel || null,
        act: act.trim() || null,
        section: section.trim() || null,
      });
      setResults(response.results);
      setExpandedTerms(response.expanded_terms);
      setTotal(response.total);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  async function seedSources() {
    setLoading(true);
    setMessage(null);
    try {
      await seedResearchSources();
      setStats((current) => current ? { ...current, sources: Math.max(current.sources, 3) } : current);
      setMessage("Official source registry added. Import statutes and judgments to begin searching.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to seed source registry");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <section className="research-search-card">
        <form onSubmit={submit}>
          <div className="research-search-input">
            <SearchIcon />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search English, हिन्दी or Hinglish — e.g. dhara 138 cheque notice"
              aria-label="Legal research query"
            />
            <button className="primary-button" disabled={loading || query.trim().length < 2}>
              {loading ? "Searching…" : "Research"}
            </button>
          </div>
          <div className="research-filters">
            <label>
              <span>Scope</span>
              <select value={scope} onChange={(event) => setScope(event.target.value as ResearchScope)}>
                <option value="all">Statutes + judgments</option>
                <option value="statutes">Statutes only</option>
                <option value="judgments">Judgments only</option>
              </select>
            </label>
            <label>
              <span>Court</span>
              <select value={courtLevel} onChange={(event) => setCourtLevel(event.target.value as "" | CourtLevel)}>
                {COURTS.map((court) => <option key={court.value || "all"} value={court.value}>{court.label}</option>)}
              </select>
            </label>
            <label>
              <span>Act</span>
              <input value={act} onChange={(event) => setAct(event.target.value)} placeholder="e.g. NI Act" />
            </label>
            <label>
              <span>Section</span>
              <input value={section} onChange={(event) => setSection(event.target.value)} placeholder="e.g. 138" />
            </label>
          </div>
        </form>
      </section>

      {message && <div className="research-message">{message}</div>}

      {corpusEmpty && total === null ? (
        <section className="corpus-empty">
          <div>
            <div className="eyebrow">Corpus not loaded</div>
            <h2>Start with authoritative material.</h2>
            <p>
              Register the official India Code, eCourts and Supreme Court sources, then import approved
              statute and judgment exports. Search runs locally after ingestion.
            </p>
          </div>
          <button className="secondary-button" type="button" onClick={seedSources} disabled={loading}>
            Register official sources
          </button>
        </section>
      ) : null}

      {total !== null && (
        <section className="research-results-section">
          <div className="research-results-heading">
            <div>
              <div className="eyebrow">Research results</div>
              <h2>{total.toLocaleString("en-IN")} passages found</h2>
            </div>
            {expandedTerms.length > 0 && (
              <div className="query-expansion" title="Deterministic bilingual query expansion">
                {expandedTerms.slice(0, 8).map((term) => <span key={term}>{term}</span>)}
              </div>
            )}
          </div>
          {results.length ? (
            <div className="research-results">
              {results.map((result, index) => <ResultCard key={`${result.result_type}-${result.id}`} result={result} rank={index + 1} />)}
            </div>
          ) : (
            <div className="soft-panel empty-state compact">
              <div className="empty-state-title">No matching authority found</div>
              <div className="empty-state-copy">Try removing a filter or searching a broader legal concept.</div>
            </div>
          )}
        </section>
      )}
    </>
  );
}
