"use client";

import { UploadTool } from "@/components/tools/upload-tool";
import { previewBates, stampBates } from "@/lib/tools";

export function BatesTool() {
  return (
    <UploadTool
      toolKey="bates-numbering"
      title="Bates numbering"
      intro="Stamps sequential Bates numbers onto a PDF. Preview first to check the numbering and catch collisions before writing the file."
      caveat="Once a bundle has been served with Bates numbers, renumbering breaks every reference made to it. Preview before stamping."
      accept="application/pdf"
      optionFields={[
        { key: "prefix", label: "Prefix", placeholder: "ABC" },
        { key: "start_number", label: "Start number", type: "number", placeholder: "1" },
        { key: "digits", label: "Digits", type: "number", placeholder: "6" },
      ]}
      actions={[
        { key: "preview", label: "Preview numbering", run: (file, options) => previewBates(file, options) },
        { key: "stamp", label: "Stamp PDF", run: (file, options) => stampBates(file, options), download: true },
      ]}
    />
  );
}
