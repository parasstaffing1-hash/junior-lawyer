"use client";

import { DragEvent, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { DocumentIcon, PlusIcon } from "@/components/icons";
import { uploadDocument } from "@/lib/api";

export function DocumentUploadPanel({ matterId }: { matterId: string }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(file?: File) {
    if (!file || busy) return;
    setBusy(true);
    setError("");
    setMessage(`Processing ${file.name}…`);
    try {
      const document = await uploadDocument(matterId, file);
      setMessage(
        document.processing_status === "ready"
          ? `${file.name} indexed successfully.`
          : `${file.name} uploaded; review processing status.`,
      );
      router.refresh();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed");
      setMessage("");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    void submit(event.dataTransfer.files?.[0]);
  }

  return (
    <section className="upload-card">
      <div
        className={`upload-dropzone${dragging ? " dragging" : ""}`}
        onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <div className="upload-icon"><DocumentIcon /></div>
        <div>
          <div className="upload-title">Add legal documents</div>
          <div className="upload-copy">Drop a file here. Searchable text is extracted directly; scans use local English + हिन्दी OCR.</div>
        </div>
        <button className="secondary-button upload-button" type="button" disabled={busy} onClick={() => inputRef.current?.click()}>
          <PlusIcon /> {busy ? "Processing…" : "Choose file"}
        </button>
        <input
          ref={inputRef}
          className="visually-hidden"
          type="file"
          accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp"
          onChange={(event) => void submit(event.target.files?.[0])}
        />
      </div>
      {message ? <div className="upload-message success">{message}</div> : null}
      {error ? <div className="upload-message error">{error}</div> : null}
    </section>
  );
}
