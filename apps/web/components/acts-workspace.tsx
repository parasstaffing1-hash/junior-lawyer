"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { BookIcon, ScaleIcon } from "@/components/icons";
import {
  browseStatutes,
  getStatuteSections,
  getStatuteShelf,
  searchStatuteSections,
  type StatuteListItem,
  type StatuteSectionRecord,
  type StatuteShelf,
} from "@/lib/api";

const PAGE_SIZE = 25;

/**
 * The Acts shelf: browse and search bare acts, then read a provision.
 *
 * The corpus ships empty until acts are ingested, and this says so plainly
 * rather than showing an ambiguous blank list — an empty shelf is a missing
 * import, not a failed search, and the two need different responses.
 */
export function ActsWorkspace() {
  const [shelf, setShelf] = useState<StatuteShelf | null>(null);
  const [acts, setActs] = useState<StatuteListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [state, setState] = useState("");
  const [selected, setSelected] = useState<StatuteListItem | null>(null);
  const [sections, setSections] = useState<StatuteSectionRecord[]>([]);
  const [sectionQuery, setSectionQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(
    async (nextOffset = 0) => {
      setBusy(true);
      setError("");
      try {
        const result = await browseStatutes({
          search: search.trim() || undefined,
          state: state || undefined,
          limit: PAGE_SIZE,
          offset: nextOffset,
        });
        setActs(result.acts);
        setTotal(result.total);
        setOffset(nextOffset);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load acts");
      } finally {
        setBusy(false);
      }
    },
    [search, state],
  );

  useEffect(() => {
    void (async () => {
      try { setShelf(await getStatuteShelf()); } catch { setShelf(null); }
      await load(0);
    })();
    // Intentionally once on mount; filters submit explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function openAct(act: StatuteListItem) {
    setSelected(act);
    setSectionQuery("");
    setBusy(true);
    try { setSections(await getStatuteSections(act.id)); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to load sections"); }
    finally { setBusy(false); }
  }

  async function findSection(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    try {
      const term = sectionQuery.trim();
      setSections(term ? await searchStatuteSections(selected.id, term) : await getStatuteSections(selected.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Section search failed");
    } finally { setBusy(false); }
  }

  const empty = shelf !== null && shelf.total_acts === 0;

  return (
    <div className="acts-layout">
      <section className="acts-browse">
        <form
          className="acts-filters"
          onSubmit={(event) => { event.preventDefault(); void load(0); }}
        >
          <label>
            Search acts
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Title, short title or act number — e.g. 138, Negotiable, परक्राम्य"
            />
          </label>
          {shelf?.states.length ? (
            <label>
              State
              <select value={state} onChange={(event) => setState(event.target.value)}>
                <option value="">All jurisdictions</option>
                {shelf.states.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.name} ({item.count})
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <button className="primary-button" type="submit" disabled={busy}>
            {busy ? "Searching…" : "Search"}
          </button>
        </form>

        {error ? <div className="notice-panel">{error}</div> : null}

        {empty ? (
          <div className="acts-empty">
            <h3><BookIcon /> No acts loaded yet</h3>
            <p>
              The corpus is empty. Bare acts are imported from an approved source
              rather than typed in, so this shelf fills once an import has run.
            </p>
            <p className="muted">
              Until then, the assistant will answer that a point is “not established
              from the provided sources” rather than reciting law it cannot cite.
            </p>
          </div>
        ) : (
          <>
            <p className="muted acts-count">
              {total} act{total === 1 ? "" : "s"}
              {total > PAGE_SIZE ? ` · showing ${offset + 1}–${Math.min(offset + PAGE_SIZE, total)}` : ""}
            </p>
            <ul className="acts-list">
              {acts.map((act) => (
                <li key={act.id}>
                  <button type="button" onClick={() => void openAct(act)}>
                    <strong>{act.short_title || act.title_en}</strong>
                    {act.title_hi ? <span className="acts-hindi">{act.title_hi}</span> : null}
                    <small>
                      {[act.act_number ? `Act ${act.act_number}` : null, act.act_year, act.state || act.jurisdiction]
                        .filter(Boolean)
                        .join(" · ")}
                    </small>
                  </button>
                </li>
              ))}
            </ul>
            {total > PAGE_SIZE ? (
              <div className="button-row">
                <button
                  className="ghost-button"
                  type="button"
                  disabled={busy || offset === 0}
                  onClick={() => void load(Math.max(0, offset - PAGE_SIZE))}
                >
                  Previous
                </button>
                <button
                  className="ghost-button"
                  type="button"
                  disabled={busy || offset + PAGE_SIZE >= total}
                  onClick={() => void load(offset + PAGE_SIZE)}
                >
                  Next
                </button>
              </div>
            ) : null}
          </>
        )}
      </section>

      <section className="acts-reader">
        {selected ? (
          <>
            <div className="acts-reader-head">
              <h3><ScaleIcon /> {selected.short_title || selected.title_en}</h3>
              {selected.title_hi ? <p className="acts-hindi">{selected.title_hi}</p> : null}
              <p className="muted">
                {[selected.act_number ? `Act ${selected.act_number}` : null, selected.act_year, selected.state || selected.jurisdiction]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
            <form className="acts-section-search" onSubmit={findSection}>
              <input
                value={sectionQuery}
                onChange={(event) => setSectionQuery(event.target.value)}
                placeholder="Find a section by number or wording"
              />
              <button className="secondary-button" type="submit" disabled={busy}>Find</button>
            </form>
            {sections.length === 0 ? (
              <p className="muted">No provisions match.</p>
            ) : (
              <ol className="acts-sections">
                {sections.map((section) => (
                  <li key={section.id}>
                    <strong>
                      {section.section_number}
                      {section.heading_en ? ` — ${section.heading_en}` : ""}
                    </strong>
                    {section.heading_hi ? <span className="acts-hindi">{section.heading_hi}</span> : null}
                    {section.text_en ? <p>{section.text_en}</p> : null}
                    {section.text_hi ? <p className="acts-hindi">{section.text_hi}</p> : null}
                  </li>
                ))}
              </ol>
            )}
          </>
        ) : (
          <p className="muted">Choose an act to read its sections.</p>
        )}
      </section>
    </div>
  );
}
