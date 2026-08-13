import { EvidenceIndexTool } from "@/components/tools/evidence-index-tool";

export const metadata = {
  title: "Evidence index — free legal tool",
  description: "Build a paginated evidence index for filing.",
  alternates: { canonical: "/tools/evidence-indexes" },
};

export default function Page(){return <EvidenceIndexTool/>;}
