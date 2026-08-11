"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { rebuildIntelligence } from "@/lib/api";

export function RebuildIntelligenceButton({ matterId }: { matterId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function rebuild() {
    setBusy(true);
    setMessage("");
    try {
      await rebuildIntelligence(matterId);
      setMessage("Intelligence refreshed");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to rebuild intelligence");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rebuild-control">
      <button className="secondary-button" onClick={rebuild} disabled={busy} type="button">
        {busy ? "Rebuilding…" : "Rebuild intelligence"}
      </button>
      {message ? <span className="rebuild-message">{message}</span> : null}
    </div>
  );
}
