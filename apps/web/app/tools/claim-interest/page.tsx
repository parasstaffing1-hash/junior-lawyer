import { ClaimInterestTool } from "@/components/tools/claim-interest-tool";

export const metadata = {
  title: "Claim interest — free legal tool",
  description: "Simple or compound interest across day-count conventions.",
  alternates: { canonical: "/tools/claim-interest" },
};

export default function Page(){return <ClaimInterestTool/>;}
