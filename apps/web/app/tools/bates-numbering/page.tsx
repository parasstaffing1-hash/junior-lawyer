import { BatesTool } from "@/components/tools/bates-tool";

export const metadata = {
  title: "Bates numbering — free legal tool",
  description: "Stamp sequential Bates numbers onto a PDF.",
  alternates: { canonical: "/tools/bates-numbering" },
};

export default function Page(){return <BatesTool/>;}
