import { AgentWorkspace } from "@/components/agent-workspace";
import { getAgentRuns, getMattersOrThrow, type AgentRun, type Matter } from "@/lib/server-api";

export const metadata = {
  title: "Junior Lawyer Agent",
  description:
    "One instruction, several steps: the agent reads the matter, its procedural history, the limitation position, what is due and what is missing, then stops for lawyer approval.",
  alternates: { canonical: "/agent" },
};

export default async function AgentPage() {
  let matters: Matter[] = [];
  let runs: AgentRun[] = [];
  let apiReachable = true;

  try {
    matters = await getMattersOrThrow();
    runs = await getAgentRuns();
  } catch {
    apiReachable = false;
  }

  return <AgentWorkspace matters={matters} initialRuns={runs} apiReachable={apiReachable} />;
}
