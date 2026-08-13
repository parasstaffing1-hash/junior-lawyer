import { LegalNoticeTool } from "@/components/tools/legal-notice-tool";

export const metadata = {
  title: "Legal notice — free legal tool",
  description: "Generate a notice from a reviewed template.",
  alternates: { canonical: "/tools/legal-notices" },
};

export default function Page(){return <LegalNoticeTool/>;}
