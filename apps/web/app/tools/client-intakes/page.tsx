import { IntakeTool } from "@/components/tools/intake-tool";

export const metadata = {
  title: "Client intake — free legal tool",
  description: "Produce a structured intake record from a questionnaire.",
  alternates: { canonical: "/tools/client-intakes" },
};

export default function Page(){return <IntakeTool/>;}
