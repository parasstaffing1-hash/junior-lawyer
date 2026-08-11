"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  deleteSavedSearch,
  detectSearchDuplicates,
  getSearchDuplicates,
  getSearchIndexHealth,
  rebuildSearchIndex,
  getSavedSearches,
  markSavedSearchRun,
  recordRecentSearchItem,
  saveSearch,
  universalSearch,
  type SavedSearch,
  type SearchEntityType,
  type UniversalSearchResponse,
  type UniversalSearchResult,
  type SearchIndexHealth,
  type SearchDuplicateRecord,
} from "@/lib/api";
import { SearchIcon } from "@/components/icons";

const SCOPES: Array<{ value: SearchEntityType; label: string }> = [
  { value: "matter", label: "Matters" }, { value: "client", label: "Clients" },
  { value: "document", label: "Documents" }, { value: "fact", label: "Facts" },
  { value: "evidence", label: "Evidence" }, { value: "witness", label: "Witnesses" },
  { value: "contract", label: "Contracts" }, { value: "draft", label: "Drafts" },
  { value: "deadline", label: "Deadlines" }, { value: "hearing", label: "Hearings" },
  { value: "task", label: "Tasks" }, { value: "invoice", label: "Invoices" },
  { value: "statute", label: "Statutes" }, { value: "judgment", label: "Judgments" },
  { value: "precedent", label: "Precedents" }, { value: "communication", label: "Communications" },
];

const ENTITY_LABEL = Object.fromEntries(SCOPES.map((x) => [x.value, x.label.replace(/s$/, "")])) as Record<SearchEntityType, string>;

export function SearchWorkspace() {
  const router = useRouter();
  const params = useSearchParams();
  const initial = params?.get("q") ?? "";
  const [query, setQuery] = useState(initial);
  const [scopes, setScopes] = useState<SearchEntityType[]>([]);
  const [data, setData] = useState<UniversalSearchResponse | null>(null);
  const [saved, setSaved] = useState<SavedSearch[]>([]);
  const [loading, setLoading] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [error, setError] = useState("");
  const [indexHealth, setIndexHealth] = useState<SearchIndexHealth | null>(null);
  const [duplicates, setDuplicates] = useState<SearchDuplicateRecord[]>([]);
  const [indexBusy, setIndexBusy] = useState(false);

  async function refreshIndexHealth() {
    const health = await getSearchIndexHealth(); setIndexHealth(health);
    if (health.exact_duplicate_pairs + health.near_duplicate_pairs > 0) {
      setDuplicates(await getSearchDuplicates(8));
    }
  }

  useEffect(() => {
    void getSavedSearches().then(setSaved).catch(() => undefined);
    void refreshIndexHealth().catch(() => undefined);
  }, []);
  useEffect(() => { if (initial.trim()) void runSearch(initial); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  async function runSearch(value = query, selected = scopes) {
    const clean = value.trim(); if (!clean) { setData(null); return; }
    setLoading(true); setError("");
    try {
      const response = await universalSearch(clean, { scopes: selected, limit: 60 });
      setData(response);
      router.replace(`/search?q=${encodeURIComponent(clean)}`, { scroll: false });
    } catch (e) { setError(e instanceof Error ? e.message : "Search failed"); }
    finally { setLoading(false); }
  }

  async function openResult(result: UniversalSearchResult) {
    void recordRecentSearchItem(result).catch(() => undefined);
    router.push(result.href);
  }

  function toggleScope(scope: SearchEntityType) {
    setScopes((current) => current.includes(scope) ? current.filter((x) => x !== scope) : [...current, scope]);
  }

  async function createSaved() {
    if (!query.trim() || !saveName.trim()) return;
    const created = await saveSearch({ name: saveName.trim(), query: query.trim(), scopes, pinned: false });
    setSaved((rows) => [created, ...rows]); setSaveName("");
  }

  async function runSaved(item: SavedSearch) {
    setQuery(item.query); setScopes(item.scopes_json ?? []); await markSavedSearchRun(item.id); await runSearch(item.query, item.scopes_json ?? []);
  }

  async function removeSaved(id: string) {
    await deleteSavedSearch(id); setSaved((rows) => rows.filter((x) => x.id !== id));
  }

  const grouped = useMemo(() => data?.groups ?? [], [data]);

  async function rebuildIndex() {
    setIndexBusy(true); setError("");
    try { await rebuildSearchIndex(true); await refreshIndexHealth(); }
    catch (e) { setError(e instanceof Error ? e.message : "Index rebuild failed"); }
    finally { setIndexBusy(false); }
  }

  async function scanDuplicates() {
    setIndexBusy(true); setError("");
    try { await detectSearchDuplicates(); await refreshIndexHealth(); }
    catch (e) { setError(e instanceof Error ? e.message : "Duplicate scan failed"); }
    finally { setIndexBusy(false); }
  }

  return (
    <main className="page search-page">
      <div className="page-header search-header">
        <div><div className="eyebrow">Universal command center</div><h1>Search everything you are allowed to see.</h1>
          <p>English, हिन्दी and Hinglish across matters, documents, evidence, legal sources and firm knowledge.</p></div>
        <button className="secondary-button" onClick={() => window.dispatchEvent(new Event("jl:open-search"))}>Open ⌘K</button>
      </div>

      <section className="search-hero premium-panel">
        <form onSubmit={(e) => { e.preventDefault(); void runSearch(); }} className="universal-search-form">
          <SearchIcon /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. dhara 138 cheque notice, ABC v XYZ, payment evidence…" />
          <button className="primary-button" type="submit" disabled={loading}>{loading ? "Searching…" : "Search"}</button>
        </form>
        <div className="scope-row"><button type="button" className={`scope-chip${scopes.length === 0 ? " active" : ""}`} onClick={() => setScopes([])}>All</button>
          {SCOPES.map((scope) => <button type="button" key={scope.value} className={`scope-chip${scopes.includes(scope.value) ? " active" : ""}`} onClick={() => toggleScope(scope.value)}>{scope.label}</button>)}</div>
        {data && <div className="search-query-meta"><span>{data.result_count} permitted results</span><span>Normalized: {data.normalized_query}</span>
          {data.expanded_terms.length > 0 && <span>Expanded: {data.expanded_terms.slice(0, 8).join(" · ")}</span>}</div>}
      </section>

      {error && <div className="alert error">{error}</div>}

      <div className="search-layout">
        <aside className="search-side premium-panel">
          <div className="panel-title-row"><h2>Saved searches</h2><span>{saved.length}</span></div>
          {saved.length === 0 && <p className="muted">Save recurring research or matter lookups here.</p>}
          {saved.map((item) => <div className="saved-search" key={item.id}>
            <button onClick={() => void runSaved(item)}><strong>{item.name}</strong><small>{item.query}</small></button>
            <button className="text-danger" aria-label="Delete saved search" onClick={() => void removeSaved(item.id)}>×</button>
          </div>)}
          <div className="save-search-box"><input value={saveName} onChange={(e) => setSaveName(e.target.value)} placeholder="Name this search" />
            <button className="secondary-button" disabled={!query.trim() || !saveName.trim()} onClick={() => void createSaved()}>Save current</button></div>
          <div className="privacy-note"><strong>Permission-first search</strong><p>Restricted matters and clients are removed before ranking, snippets, counts and recent-item storage.</p></div>
          <div className="index-health-card">
            <div className="panel-title-row"><h2>Search index</h2><span>{indexHealth ? indexHealth.entry_count.toLocaleString() : "—"}</span></div>
            <p className="muted">Materialized chunks · local ranking · PostgreSQL FTS/trigram ready.</p>
            {indexHealth && <div className="index-metrics"><span><strong>{indexHealth.chunk_count.toLocaleString()}</strong> chunks</span><span><strong>{indexHealth.exact_duplicate_pairs + indexHealth.near_duplicate_pairs}</strong> duplicate pairs</span></div>}
            <div className="index-actions"><button className="secondary-button" disabled={indexBusy} onClick={() => void rebuildIndex()}>{indexBusy ? "Working…" : "Rebuild index"}</button><button className="secondary-button" disabled={indexBusy || !indexHealth?.entry_count} onClick={() => void scanDuplicates()}>Scan duplicates</button></div>
            {duplicates.length > 0 && <div className="duplicate-mini-list">{duplicates.slice(0, 3).map((row) => <div key={row.id}><strong>{row.kind === "exact" ? "Exact" : "Near"} duplicate</strong><small>{row.left.title} ↔ {row.right.title} · {Math.round(row.similarity * 100)}%</small></div>)}</div>}
          </div>
        </aside>

        <section className="search-results-column">
          {!data && <div className="search-empty-state premium-panel"><SearchIcon /><h2>One index for the whole firm workspace.</h2><p>Search by party, CNR, case number, section, document text, witness, invoice, deadline, precedent, judgment or ordinary language.</p></div>}
          {data && data.result_count === 0 && <div className="search-empty-state premium-panel"><h2>No permitted results</h2><p>Try a broader phrase, another language, or remove scope filters.</p></div>}
          {grouped.map((group) => <section className="result-group premium-panel" key={group.entity_type}>
            <div className="panel-title-row"><h2>{SCOPES.find((x) => x.value === group.entity_type)?.label ?? group.entity_type}</h2><span>{group.count}</span></div>
            <div className="result-list">{group.results.map((result) => <button key={`${result.entity_type}-${result.entity_id}`} className="search-result-card" onClick={() => void openResult(result)}>
              <div className="search-result-top"><span className="result-type">{ENTITY_LABEL[result.entity_type]}</span><span className="result-score">{Math.round(result.score * 100)}</span></div>
              <strong>{result.title}</strong>{result.subtitle && <span className="result-subtitle">{result.subtitle}</span>}
              {result.snippet && <p>{result.snippet}</p>}
              <div className="result-badges">{result.badges.slice(0, 4).map((badge) => <span key={badge}>{badge}</span>)}</div>
            </button>)}</div>
          </section>)}
        </section>
      </div>
    </main>
  );
}
