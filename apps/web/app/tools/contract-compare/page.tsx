import { ContractCompareTool } from "@/components/tools/contract-compare-tool";

export const metadata = {
  title: "Contract compare — free legal tool",
  description: "Clause-level diff between two contract versions.",
  alternates: { canonical: "/tools/contract-compare" },
};

export default function Page(){return <ContractCompareTool/>;}
