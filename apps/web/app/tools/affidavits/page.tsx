import { AffidavitTool } from "@/components/tools/affidavit-tool";

export const metadata = {
  title: "Affidavit — free legal tool",
  description: "Generate an affidavit from a reviewed template.",
  alternates: { canonical: "/tools/affidavits" },
};

export default function Page(){return <AffidavitTool/>;}
