import { LimitationTool } from "@/components/tools/limitation-tool";

export const metadata = {
  title: "Limitation period — free legal tool",
  description: "Compute an expiry date from a trigger, with extensions and next-business-day adjustment.",
  alternates: { canonical: "/tools/limitation-periods" },
};

export default function LimitationPeriodsPage(){return <LimitationTool/>;}
