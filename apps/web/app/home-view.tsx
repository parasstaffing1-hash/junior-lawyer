"use client";

import Link from "next/link";
import { PlusIcon, ScaleIcon, SparklesIcon } from "@/components/icons";
import { useExperience } from "@/components/experience-provider";

type UILanguage = "en" | "hi" | "bilingual";
type Copy = { en: string; hi: string };

function t(copy: Copy, language: UILanguage) {
  if (language === "hi") return copy.hi;
  if (language === "bilingual") return `${copy.en} / ${copy.hi}`;
  return copy.en;
}

/** One dashboard tile. `note` is already localized by the server component. */
export type Metric = {
  label: Copy;
  value: number;
  note: Copy;
};

export type RecentMatter = {
  id: string;
  title: string;
  caseNumber: string | null;
  court: string;
  status: string;
  updatedAt: string;
};

export type AttentionItem = {
  id: string;
  title: string;
  matterTitle: string;
  when: string;
  kind: string;
};

export type HomeViewProps = {
  /** Rendered on the server so client and server agree on the date. */
  today: Copy;
  greeting: Copy;
  metrics: Metric[];
  recentMatters: RecentMatter[];
  attention: AttentionItem[];
  apiReachable: boolean;
};

/**
 * The API serves naive UTC timestamps ("2026-08-14T11:23:18"), which `Date`
 * would otherwise read as local time — an IST reader would see a fresh record
 * as 5h30m old.
 */
function parseApiDate(iso: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso);
  return new Date(hasZone ? iso : `${iso}Z`);
}

/** "18 min ago" / "yesterday" — the same shape the static mock used. */
function relativeTime(iso: string, language: UILanguage): string {
  const then = parseApiDate(iso).getTime();
  if (Number.isNaN(then)) return "";
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (minutes < 1) return t({ en: "just now", hi: "अभी" }, language);
  if (minutes < 60) return t({ en: `${minutes} min ago`, hi: `${minutes} मिनट पहले` }, language);
  const hours = Math.round(minutes / 60);
  if (hours < 24) return t({ en: `${hours}h ago`, hi: `${hours} घंटे पहले` }, language);
  const days = Math.round(hours / 24);
  if (days === 1) return t({ en: "yesterday", hi: "कल" }, language);
  return t({ en: `${days} days ago`, hi: `${days} दिन पहले` }, language);
}

function formatWhen(iso: string, language: UILanguage): string {
  const date = parseApiDate(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const locale = language === "hi" ? "hi-IN" : "en-IN";
  return date.toLocaleDateString(locale, { day: "numeric", month: "short" });
}

export default function HomeView({
  today,
  greeting,
  metrics,
  recentMatters,
  attention,
  apiReachable,
}: HomeViewProps) {
  const { preferences } = useExperience();
  const language = preferences.ui_language;

  return (
    <main className="page">
      <div className="hero-row">
        <div>
          <div className="page-icon" aria-hidden="true"><ScaleIcon /></div>
          <div className="eyebrow">{t(today, language)}</div>
          <h1 className="page-title">{t(greeting, language)}</h1>
          <p className="page-subtitle">
            {t({ en: "Your matters, deadlines and legal work in one calm workspace. Hindi, English and mixed-language documents share one legal record.", hi: "आपके मामले, समय-सीमाएँ और कानूनी काम एक शांत कार्यक्षेत्र में। हिन्दी, अंग्रेज़ी और मिश्रित भाषा के दस्तावेज़ एक ही कानूनी रिकॉर्ड में जुड़े रहते हैं।" }, language)}
          </p>
        </div>
        <button className="primary-button" type="button" aria-label={t({ en: "Create a new matter", hi: "नया मामला बनाएँ" }, language)}>
          <PlusIcon /> {t({ en: "New matter", hi: "नया मामला" }, language)}
        </button>
      </div>

      {!apiReachable ? (
        <div className="notice-panel">
          <strong>{t({ en: "API is not connected.", hi: "API जुड़ा नहीं है।" }, language)}</strong>
          <span>
            {t({ en: "Start the FastAPI server to load live matters, hearings and deadlines.", hi: "लाइव मामले, सुनवाई और समय-सीमाएँ देखने के लिए FastAPI सर्वर चालू करें।" }, language)}
          </span>
        </div>
      ) : null}

      <section className="metrics">
        {metrics.map((metric) => (
          <div className="metric" key={metric.label.en}>
            <div className="metric-label">{t(metric.label, language)}</div>
            <div className="metric-value">{metric.value}</div>
            <div className="metric-note">{t(metric.note, language)}</div>
          </div>
        ))}
      </section>

      <section className="grid-2">
        <div className="card">
          <div className="card-header">
            <div className="card-title">{t({ en: "Recent matters", hi: "हाल के मामले" }, language)}</div>
            <Link className="card-action" href="/matters">{t({ en: "View all", hi: "सभी देखें" }, language)}</Link>
          </div>
          {recentMatters.length ? recentMatters.map((matter) => (
            <Link className="matter-row matter-link" href={`/matters/${matter.id}`} key={matter.id}>
              <div>
                <div className="matter-title">{matter.title}</div>
                <div className="matter-meta">
                  {matter.caseNumber ?? t({ en: "No case number", hi: "कोई केस नंबर नहीं" }, language)} · {relativeTime(matter.updatedAt, language)}
                </div>
              </div>
              <div className="matter-court">{matter.court}</div>
              <div className="status">{matter.status.replace("_", " ")}</div>
            </Link>
          )) : (
            <div className="empty-state">
              <div className="empty-state-title">{t({ en: "No matters yet", hi: "अभी कोई मामला नहीं" }, language)}</div>
              <div className="empty-state-copy">
                {t({ en: "Create a matter, then upload pleadings, orders, contracts and evidence into its workspace.", hi: "एक मामला बनाएँ, फिर उसमें वाद-पत्र, आदेश, अनुबंध और साक्ष्य अपलोड करें।" }, language)}
              </div>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">{t({ en: "Needs attention", hi: "ध्यान आवश्यक" }, language)}</div>
            <Link className="card-action" href="/calendar">{t({ en: "This week", hi: "इस सप्ताह" }, language)}</Link>
          </div>
          {attention.length ? attention.map((item) => (
            <div className="task-row" key={item.id}>
              <div className="task-dot" />
              <div>
                <div className="task-title">{item.title}</div>
                <div className="task-meta">{item.matterTitle} · {formatWhen(item.when, language)}</div>
              </div>
            </div>
          )) : (
            <div className="empty-state">
              <div className="empty-state-title">{t({ en: "Nothing due this week", hi: "इस सप्ताह कुछ भी देय नहीं" }, language)}</div>
              <div className="empty-state-copy">
                {t({ en: "Hearings and deadlines appear here once a matter has a procedure pack.", hi: "किसी मामले में प्रक्रिया पैक जुड़ते ही सुनवाई और समय-सीमाएँ यहाँ दिखेंगी।" }, language)}
              </div>
            </div>
          )}
        </div>
      </section>

      <div className="soft-panel">
        <div className="ai-command">
          <SparklesIcon />
          <span>{t({ en: "Ask Junior Lawyer — summarize a document, find contradictions, research an issue, or prepare a draft…", hi: "जूनियर लॉयर से पूछें — दस्तावेज़ का सार बनाएँ, विरोधाभास खोजें, कानूनी शोध करें या मसौदा तैयार करें…" }, language)}</span>
        </div>
      </div>
    </main>
  );
}
