import HomeView, { type AttentionItem, type Metric, type RecentMatter } from "./home-view";
import { getAgenda, getMattersOrThrow, type Matter } from "@/lib/server-api";
import type { ProcedureAgendaItem } from "@/lib/generated-types";

/**
 * The overview is server-rendered so its counts come from the same source as
 * every other page. Language switching stays in the client half (HomeView).
 */
export default async function HomePage() {
  let matters: Matter[] = [];
  let agenda: ProcedureAgendaItem[] = [];
  let apiReachable = true;

  try {
    matters = await getMattersOrThrow();
    agenda = await getAgenda(7);
  } catch {
    apiReachable = false;
  }

  const now = new Date();
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

  const active = matters.filter((matter) => matter.status === "active");
  const updatedThisWeek = matters.filter((matter) => new Date(matter.updated_at) >= weekAgo).length;
  const documentCount = matters.reduce((total, matter) => total + matter.document_count, 0);

  const hearings = agenda.filter((item) => item.kind === "hearing");
  const deadlines = agenda.filter((item) => item.kind === "deadline");
  const needsReview = agenda.filter((item) => item.requires_review).length;

  const nextHearing = [...hearings].sort((a, b) => a.when.localeCompare(b.when))[0];
  const nextHearingDate = nextHearing
    ? new Date(nextHearing.when).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
    : null;

  const metrics: Metric[] = [
    {
      label: { en: "Active matters", hi: "सक्रिय मामले" },
      value: active.length,
      note: {
        en: `${updatedThisWeek} updated this week`,
        hi: `इस सप्ताह ${updatedThisWeek} अपडेट`,
      },
    },
    {
      label: { en: "Upcoming hearings", hi: "आगामी सुनवाई" },
      value: hearings.length,
      note: nextHearingDate
        ? { en: `Next on ${nextHearingDate}`, hi: `अगली सुनवाई ${nextHearingDate}` }
        : { en: "None in the next 7 days", hi: "अगले 7 दिनों में कोई नहीं" },
    },
    {
      label: { en: "Pending tasks", hi: "लंबित कार्य" },
      value: deadlines.length,
      note: {
        en: `${needsReview} need attention`,
        hi: `${needsReview} पर ध्यान आवश्यक`,
      },
    },
    {
      label: { en: "Documents", hi: "दस्तावेज़" },
      value: documentCount,
      note: { en: "Across all matters", hi: "सभी मामलों में" },
    },
  ];

  const mattersByTitle = new Map(matters.map((matter) => [matter.id, matter.title]));

  const recentMatters: RecentMatter[] = [...matters]
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, 3)
    .map((matter) => ({
      id: matter.id,
      title: matter.title,
      caseNumber: matter.case_number ?? matter.reference_number ?? null,
      court: matter.court_name ?? matter.jurisdiction,
      status: matter.status,
      updatedAt: matter.updated_at,
    }));

  const attention: AttentionItem[] = [...agenda]
    .sort((a, b) => a.when.localeCompare(b.when))
    .slice(0, 3)
    .map((item) => ({
      id: item.id,
      title: item.title,
      matterTitle: mattersByTitle.get(item.matter_id) ?? item.kind,
      when: item.when,
      kind: item.kind,
    }));

  const hour = now.getHours();
  const greeting =
    hour < 12
      ? { en: "Good morning.", hi: "सुप्रभात।" }
      : hour < 17
        ? { en: "Good afternoon.", hi: "नमस्कार।" }
        : { en: "Good evening.", hi: "शुभ संध्या।" };

  const today = {
    en: now.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" }),
    hi: now.toLocaleDateString("hi-IN", { weekday: "long", day: "numeric", month: "long" }),
  };

  return (
    <HomeView
      today={today}
      greeting={greeting}
      metrics={metrics}
      recentMatters={recentMatters}
      attention={attention}
      apiReachable={apiReachable}
    />
  );
}
