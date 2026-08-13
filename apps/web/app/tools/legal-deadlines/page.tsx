import { DeadlineTool } from "@/components/tools/deadline-tool";

export const metadata = {
  title: "Deadline calculator — free legal tool",
  description: "Count calendar or business days from a trigger date, skipping weekends, court holidays and excluded dates.",
  alternates: { canonical: "/tools/legal-deadlines" },
};

export default function LegalDeadlinesPage(){return <DeadlineTool/>;}
