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

const matters = [
  { title: "ABC Pvt Ltd v. XYZ Ltd", meta: "COMS 284/2026 · Updated 18 min ago", court: "Delhi High Court" },
  { title: "Mehra Family Property Matter", meta: "CS 112/2026 · Updated yesterday", court: "District Court" },
  { title: "Northstar Services Agreement", meta: "Contract review · Updated 2 days ago", court: "Commercial" },
];

export default function HomePage() {
  const { preferences } = useExperience();
  const language = preferences.ui_language;
  return (
    <main className="page">
      <div className="hero-row">
        <div>
          <div className="page-icon" aria-hidden="true"><ScaleIcon /></div>
          <div className="eyebrow">{t({ en: "Saturday, 8 August", hi: "शनिवार, 8 अगस्त" }, language)}</div>
          <h1 className="page-title">{t({ en: "Good morning.", hi: "सुप्रभात।" }, language)}</h1>
          <p className="page-subtitle">
            {t({ en: "Your matters, deadlines and legal work in one calm workspace. Hindi, English and mixed-language documents share one legal record.", hi: "आपके मामले, समय-सीमाएँ और कानूनी काम एक शांत कार्यक्षेत्र में। हिन्दी, अंग्रेज़ी और मिश्रित भाषा के दस्तावेज़ एक ही कानूनी रिकॉर्ड में जुड़े रहते हैं।" }, language)}
          </p>
        </div>
        <button className="primary-button" type="button" aria-label={t({ en: "Create a new matter", hi: "नया मामला बनाएँ" }, language)}>
          <PlusIcon /> {t({ en: "New matter", hi: "नया मामला" }, language)}
        </button>
      </div>

      <section className="metrics">
        <div className="metric"><div className="metric-label">{t({ en: "Active matters", hi: "सक्रिय मामले" }, language)}</div><div className="metric-value">12</div><div className="metric-note">{t({ en: "3 updated this week", hi: "इस सप्ताह 3 अपडेट" }, language)}</div></div>
        <div className="metric"><div className="metric-label">{t({ en: "Upcoming hearings", hi: "आगामी सुनवाई" }, language)}</div><div className="metric-value">4</div><div className="metric-note">{t({ en: "Next on 11 Aug", hi: "अगली सुनवाई 11 अगस्त" }, language)}</div></div>
        <div className="metric"><div className="metric-label">{t({ en: "Pending tasks", hi: "लंबित कार्य" }, language)}</div><div className="metric-value">7</div><div className="metric-note">{t({ en: "2 need attention", hi: "2 पर ध्यान आवश्यक" }, language)}</div></div>
        <div className="metric"><div className="metric-label">{t({ en: "Documents", hi: "दस्तावेज़" }, language)}</div><div className="metric-value">186</div><div className="metric-note">{t({ en: "Across all matters", hi: "सभी मामलों में" }, language)}</div></div>
      </section>

      <section className="grid-2">
        <div className="card">
          <div className="card-header"><div className="card-title">{t({ en: "Recent matters", hi: "हाल के मामले" }, language)}</div><Link className="card-action" href="/matters">{t({ en: "View all", hi: "सभी देखें" }, language)}</Link></div>
          {matters.map((matter) => (
            <div className="matter-row" key={matter.title}>
              <div><div className="matter-title">{matter.title}</div><div className="matter-meta">{matter.meta}</div></div>
              <div className="matter-court">{matter.court}</div>
              <div className="status">{t({ en: "Active", hi: "सक्रिय" }, language)}</div>
            </div>
          ))}
        </div>

        <div className="card">
          <div className="card-header"><div className="card-title">{t({ en: "Needs attention", hi: "ध्यान आवश्यक" }, language)}</div><div className="card-action">{t({ en: "Today", hi: "आज" }, language)}</div></div>
          <div className="task-row"><div className="task-dot"/><div><div className="task-title">{t({ en: "Review affidavit draft", hi: "शपथपत्र का मसौदा देखें" }, language)}</div><div className="task-meta">ABC Pvt Ltd · {t({ en: "due today", hi: "आज की समय-सीमा" }, language)}</div></div></div>
          <div className="task-row"><div className="task-dot"/><div><div className="task-title">{t({ en: "Prepare hearing brief", hi: "सुनवाई का संक्षिप्त विवरण तैयार करें" }, language)}</div><div className="task-meta">Mehra Property · 11 Aug</div></div></div>
          <div className="task-row"><div className="task-dot"/><div><div className="task-title">{t({ en: "Check contract redlines", hi: "अनुबंध के संशोधन देखें" }, language)}</div><div className="task-meta">Northstar · {t({ en: "client version received", hi: "क्लाइंट का संस्करण प्राप्त" }, language)}</div></div></div>
        </div>
      </section>

      <div className="soft-panel">
        <div className="ai-command"><SparklesIcon /><span>{t({ en: "Ask Junior Lawyer — summarize a document, find contradictions, research an issue, or prepare a draft…", hi: "जूनियर लॉयर से पूछें — दस्तावेज़ का सार बनाएँ, विरोधाभास खोजें, कानूनी शोध करें या मसौदा तैयार करें…" }, language)}</span></div>
      </div>
    </main>
  );
}
