import { ParserTool } from "@/components/tools/parser-tool";

export const metadata = {
  title: "Document parser — free legal tool",
  description: "Extract structure and text from PDF/DOCX.",
  alternates: { canonical: "/tools/legal-documents" },
};

export default function Page(){return <ParserTool/>;}
