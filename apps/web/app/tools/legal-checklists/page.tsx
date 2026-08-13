import { ChecklistTool } from "@/components/tools/checklist-tool";

export const metadata = {
  title: "Legal checklist — free legal tool",
  description: "Evaluate a matter against a procedural checklist template.",
  alternates: { canonical: "/tools/legal-checklists" },
};

export default function Page(){return <ChecklistTool/>;}
