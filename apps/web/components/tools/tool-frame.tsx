"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { TOOL_CATALOG } from "@/lib/tools";

export function ToolFrame({
  toolKey,
  title,
  intro,
  caveat,
  children,
}: {
  toolKey: string;
  title: string;
  intro: string;
  caveat?: ReactNode;
  children: ReactNode;
}) {
  const group = TOOL_CATALOG.find((tool) => tool.key === toolKey)?.group ?? "Tools";
  return (
    <main className="page">
      <div className="eyebrow">
        <Link href="/tools">Tools</Link> · {group}
      </div>
      <h1 className="page-title">{title}</h1>
      <p className="page-subtitle">{intro}</p>
      {caveat ? (
        <div className="notice-panel" style={{ marginBottom: 14 }}>
          <span>{caveat}</span>
        </div>
      ) : null}
      {children}
    </main>
  );
}

export function ResultPanel({
  error,
  hasResult,
  emptyHint,
  children,
}: {
  error: string;
  hasResult: boolean;
  emptyHint: string;
  children?: ReactNode;
}) {
  return (
    <section className="card tool-result" aria-live="polite">
      <div className="card-header">
        <div className="card-title">Result</div>
      </div>
      {error ? (
        <div className="notice-panel">
          <span>{error}</span>
        </div>
      ) : null}
      {!hasResult && !error ? (
        <div className="empty-state compact">
          <div className="empty-state-title">Nothing to show yet</div>
          <div className="empty-state-copy">{emptyHint}</div>
        </div>
      ) : null}
      {hasResult ? children : null}
    </section>
  );
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function humanise(key: string) {
  return key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

/**
 * Renders an engine response without hand-writing a view per tool. The tools
 * return deeply-shaped but regular data, so a recursive renderer stays honest:
 * every field the engine returned is shown rather than a curated subset.
 */
export function DataView({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value === null || value === undefined || value === "") return <span className="tool-nil">—</span>;
  if (typeof value === "boolean") return <span>{value ? "Yes" : "No"}</span>;
  if (typeof value === "number" || typeof value === "string") return <span>{String(value)}</span>;

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="tool-nil">None</span>;
    return (
      <ol className="tool-list">
        {value.map((entry, index) => (
          <li key={index}>
            <DataView value={entry} depth={depth + 1} />
          </li>
        ))}
      </ol>
    );
  }

  if (isPlainObject(value)) {
    const entries = Object.entries(value).filter(([, v]) => v !== null && v !== undefined && v !== "");
    if (entries.length === 0) return <span className="tool-nil">—</span>;
    return (
      <dl className={depth === 0 ? "tool-readout" : "tool-subreadout"}>
        {entries.map(([key, entry]) => (
          <div key={key}>
            <dt>{humanise(key)}</dt>
            <dd>
              <DataView value={entry} depth={depth + 1} />
            </dd>
          </div>
        ))}
      </dl>
    );
  }

  return <span>{String(value)}</span>;
}

/** Pulls the disclaimer out so it renders as fine print rather than a data row. */
export function splitDisclaimer(result: Record<string, unknown> | null) {
  if (!result) return { body: null, disclaimer: "" };
  const { disclaimer, ...body } = result;
  return { body, disclaimer: typeof disclaimer === "string" ? disclaimer : "" };
}
