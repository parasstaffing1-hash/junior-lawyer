import { OcrTool } from "@/components/tools/ocr-tool";

export const metadata = {
  title: "OCR — free legal tool",
  description: "Make a scanned PDF searchable, locally.",
  alternates: { canonical: "/tools/legal-ocr" },
};

export default function Page(){return <OcrTool/>;}
