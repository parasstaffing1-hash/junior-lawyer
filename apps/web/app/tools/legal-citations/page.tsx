import { CitationsTool } from "@/components/tools/citations-tool";

export const metadata = {
  title: "Citation tools — free legal tool",
  description: "Extract and normalise legal citations from text.",
  alternates: { canonical: "/tools/legal-citations" },
};

export default function Page(){return <CitationsTool/>;}
