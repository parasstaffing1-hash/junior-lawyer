import { ToolsWorkspace } from "@/components/tools-workspace";

export const metadata = {
  title: "Free legal tools",
  description: "Deadline, limitation, court fee, stamp duty, notice, affidavit and contract tools. Deterministic calculators — same input, same output.",
  alternates: { canonical: "/tools" },
};

export default function ToolsPage(){return <ToolsWorkspace/>;}
