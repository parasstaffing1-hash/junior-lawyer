import { CourtFeeTool } from "@/components/tools/court-fee-tool";

export const metadata = {
  title: "Court fee — free legal tool",
  description: "Apply a verified fee rule pack to a claim value.",
  alternates: { canonical: "/tools/court-fees" },
};

export default function Page(){return <CourtFeeTool/>;}
