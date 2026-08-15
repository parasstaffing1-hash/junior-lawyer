import { TrainingWorkspace } from "@/components/training-workspace";

export const metadata = {
  title: "Articled clerk walkthrough — training for law students",
  description:
    "Take one fictional matter from intake to the first hearing in the order a district practice takes it: conflict check, limitation, valuation, plaint, evidence, hearing brief.",
  alternates: { canonical: "/learn" },
};

export default function LearnPage() {
  return <TrainingWorkspace />;
}
