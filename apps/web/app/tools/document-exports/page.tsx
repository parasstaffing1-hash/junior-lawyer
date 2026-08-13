import { DocumentExportTool } from "@/components/tools/document-export-tool";

export const metadata = {
  title: "Document export — free legal tool",
  description: "Render a prepared document to PDF or DOCX.",
  alternates: { canonical: "/tools/document-exports" },
};

export default function Page(){return <DocumentExportTool/>;}
