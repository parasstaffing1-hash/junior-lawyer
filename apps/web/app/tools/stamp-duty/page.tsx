import { StampDutyTool } from "@/components/tools/stamp-duty-tool";

export const metadata = {
  title: "Stamp duty — free legal tool",
  description: "Apply a verified stamp-duty rule pack to an instrument value.",
  alternates: { canonical: "/tools/stamp-duty" },
};

export default function Page(){return <StampDutyTool/>;}
