"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import {
  getRecentSearchItems,
  getSearchCommands,
  recordRecentSearchItem,
  universalSearch,
  type RecentSearchItem,
  type SearchCommand,
  type UniversalSearchResult,
} from "@/lib/api";
import { SearchIcon } from "@/components/icons";
import { useExperience } from "@/components/experience-provider";

const TYPE_LABEL: Record<string, string> = {
  matter: "Matter", client: "Client", document: "Document", fact: "Fact", evidence: "Evidence",
  witness: "Witness", contract: "Contract", draft: "Draft", deadline: "Deadline", hearing: "Hearing",
  task: "Task", invoice: "Invoice", statute: "Statute", judgment: "Judgment", precedent: "Precedent",
  communication: "Communication",
};

export function UniversalCommandPalette() {
  const router = useRouter();
  const { preferences } = useExperience();
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<UniversalSearchResult[]>([]);
  const [commands, setCommands] = useState<SearchCommand[]>([]);
  const [recent, setRecent] = useState<RecentSearchItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);

  const close = useCallback(() => { setOpen(false); setQuery(""); setResults([]); setActive(0); }, []);
  const openPalette = useCallback(() => setOpen(true), []);

  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); setOpen((value) => !value);
      }
      if (event.key === "Escape") close();
      if (event.key === "Tab" && open && dialogRef.current) {
        const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'));
        if (focusable.length) {
          const first = focusable[0], last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
      }
    };
    const custom = () => openPalette();
    window.addEventListener("keydown", key);
    window.addEventListener("jl:open-search", custom);
    return () => { window.removeEventListener("keydown", key); window.removeEventListener("jl:open-search", custom); };
  }, [close, openPalette, open]);

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(() => inputRef.current?.focus(), 10);
    void Promise.all([getSearchCommands(), getRecentSearchItems(8)]).then(([cmds, items]) => {
      setCommands(cmds); setRecent(items);
    }).catch(() => undefined);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (!query.trim()) { setResults([]); setActive(0); return; }
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const [search, cmds] = await Promise.all([universalSearch(query, { limit: 18 }), getSearchCommands(query)]);
        setResults(search.results); setCommands(cmds.slice(0, 5)); setActive(0);
      } finally { setLoading(false); }
    }, 180);
    return () => window.clearTimeout(timer);
  }, [open, query]);

  const entries = useMemo(() => [
    ...commands.map((item) => ({ kind: "command" as const, item })),
    ...results.map((item) => ({ kind: "result" as const, item })),
  ], [commands, results]);

  const navigateCommand = (command: SearchCommand) => { close(); router.push(command.href); };
  const navigateResult = async (result: UniversalSearchResult) => {
    void recordRecentSearchItem(result).catch(() => undefined);
    close(); router.push(result.href);
  };

  const onKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (!entries.length) return;
    if (event.key === "ArrowDown") { event.preventDefault(); setActive((v) => (v + 1) % entries.length); }
    if (event.key === "ArrowUp") { event.preventDefault(); setActive((v) => (v - 1 + entries.length) % entries.length); }
    if (event.key === "Enter") {
      event.preventDefault(); const entry = entries[active]; if (!entry) return;
      if (entry.kind === "command") navigateCommand(entry.item); else void navigateResult(entry.item);
    }
  };

  if (!open) return null;
  return (
    <div className="command-overlay" role="presentation" onMouseDown={(e) => { if (e.currentTarget === e.target) close(); }}>
      <div ref={dialogRef} className="command-palette" role="dialog" aria-modal="true" aria-label={preferences.ui_language === "hi" ? "यूनिवर्सल खोज" : "Universal search"}>
        <div className="command-input-row">
          <SearchIcon />
          <input ref={inputRef} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={onKeyDown}
            placeholder={preferences.ui_language === "hi" ? "मामले, मुवक्किल, दस्तावेज़, कानून खोजें…" : preferences.ui_language === "bilingual" ? "Search / खोजें…" : "Search matters, clients, documents, law…"} aria-label={preferences.ui_language === "hi" ? "खोज" : "Search"} />
          <kbd>Esc</kbd>
        </div>
        <div className="command-body">
          {!query.trim() && recent.length > 0 && (
            <section className="command-section">
              <div className="command-section-title">Recent</div>
              {recent.map((item) => <button key={item.id} className="command-row" onClick={() => { close(); router.push(item.href); }}>
                <span className="command-type">{TYPE_LABEL[item.entity_type] ?? item.entity_type}</span>
                <span className="command-copy"><strong>{item.title_snapshot}</strong><small>{item.subtitle_snapshot}</small></span>
              </button>)}
            </section>
          )}
          {commands.length > 0 && (
            <section className="command-section">
              <div className="command-section-title">Commands</div>
              {commands.map((item, idx) => <button key={item.id} className={`command-row${idx === active ? " selected" : ""}`} onClick={() => navigateCommand(item)}>
                <span className="command-type">{item.write_action ? "Create" : "Go"}</span>
                <span className="command-copy"><strong>{item.title}</strong><small>{item.description}</small></span>
                {item.shortcut && <kbd>{item.shortcut}</kbd>}
              </button>)}
            </section>
          )}
          {query.trim() && (
            <section className="command-section">
              <div className="command-section-title">Results {loading ? "· searching…" : `· ${results.length}`}</div>
              {!loading && results.length === 0 && <div className="command-empty">No permitted results found.</div>}
              {results.map((item, idx) => {
                const selected = commands.length + idx === active;
                return <button key={`${item.entity_type}-${item.entity_id}`} className={`command-row${selected ? " selected" : ""}`} onClick={() => void navigateResult(item)}>
                  <span className="command-type">{TYPE_LABEL[item.entity_type] ?? item.entity_type}</span>
                  <span className="command-copy"><strong>{item.title}</strong><small>{item.subtitle || item.snippet}</small></span>
                  <span className="command-score">{Math.round(item.score * 100)}</span>
                </button>;
              })}
            </section>
          )}
        </div>
        <div className="command-footer"><span>↑↓ Navigate</span><span>↵ Open</span>{preferences.show_keyboard_hints ? <span>⌘K Toggle</span> : null}<button onClick={() => { close(); router.push(`/search?q=${encodeURIComponent(query)}`); }}>Full search</button></div>
      </div>
    </div>
  );
}
