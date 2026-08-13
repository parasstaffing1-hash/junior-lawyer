import { CaseTimelineTool } from "@/components/tools/case-timeline-tool";

export const metadata = {
  title: "Case timeline — free legal tool",
  description: "Build an ordered chronology from dated events.",
  alternates: { canonical: "/tools/case-timelines" },
};

export default function Page(){return <CaseTimelineTool/>;}
