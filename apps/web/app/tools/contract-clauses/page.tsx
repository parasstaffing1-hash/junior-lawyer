import { ClauseExtractorTool } from "@/components/tools/clause-extractor-tool";

export const metadata = {
  title: "Clause extractor — free legal tool",
  description: "Identify and classify clauses in a contract.",
  alternates: { canonical: "/tools/contract-clauses" },
};

export default function Page(){return <ClauseExtractorTool/>;}
