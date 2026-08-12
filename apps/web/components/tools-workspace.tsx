"use client";

import Link from "next/link";
import { TOOL_CATALOG, type ToolDescriptor } from "@/lib/tools";
import { useExperience } from "@/components/experience-provider";

function label(tool: ToolDescriptor, language: string) {
  if (language === "hi") return tool.nameHi;
  if (language === "bilingual") return `${tool.name} · ${tool.nameHi}`;
  return tool.name;
}

function ToolCard({ tool, language }: { tool: ToolDescriptor; language: string }) {
  const name = label(tool, language);
  if (!tool.interactive) {
    return (
      <div className="tool-card tool-card-pending" aria-disabled="true">
        <div className="tool-card-head">
          <div className="tool-card-title">{name}</div>
          <span className="quiet-badge">API only</span>
        </div>
        <p className="tool-card-copy">{tool.summary}</p>
        <div className="tool-card-foot">No workspace yet · available at /api/v1/tools/{tool.key}</div>
      </div>
    );
  }
  return (
    <Link className="tool-card" href={tool.href}>
      <div className="tool-card-head">
        <div className="tool-card-title">{name}</div>
        <span className="verified-badge">deterministic</span>
      </div>
      <p className="tool-card-copy">{tool.summary}</p>
      <div className="tool-card-foot">Open tool →</div>
    </Link>
  );
}

export function ToolsWorkspace() {
  const { preferences } = useExperience();
  const language = preferences.ui_language;
  const groups = Array.from(new Set(TOOL_CATALOG.map((tool) => tool.group)));
  const ready = TOOL_CATALOG.filter((tool) => tool.interactive).length;

  return (
    <main className="page">
      <div className="eyebrow">Legal tools</div>
      <h1 className="page-title">{language === "hi" ? "कानूनी उपकरण" : "Tools"}</h1>
      <p className="page-subtitle">
        Deterministic calculators and document utilities. Same input, same output — no model call,
        nothing sent to a provider.{" "}
        {ready === TOOL_CATALOG.length
          ? `All ${TOOL_CATALOG.length} tools run here and on the API.`
          : `${ready} of ${TOOL_CATALOG.length} have a workspace; the rest are callable on the API while their screens are built.`}
      </p>

      {groups.map((group) => (
        <section className="card" key={group} style={{ marginTop: 18 }}>
          <div className="card-header">
            <div className="card-title">{group}</div>
          </div>
          <div className="tool-grid">
            {TOOL_CATALOG.filter((tool) => tool.group === group).map((tool) => (
              <ToolCard tool={tool} language={language} key={tool.key} />
            ))}
          </div>
        </section>
      ))}

      <div className="notice-panel" style={{ marginTop: 18 }}>
        <span>
          Fee and stamp-duty results depend on the rule pack selected. A pack that has not been
          lawyer-verified is refused by the engine rather than used silently.
        </span>
      </div>
    </main>
  );
}
