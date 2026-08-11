"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { updateReviewItem, type ReviewItem } from "@/lib/api";

export function ReviewActions({ item }: { item: ReviewItem }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  if (item.status !== "open") return null;

  async function decide(status: "confirmed" | "dismissed") {
    setBusy(true);
    try {
      await updateReviewItem(item.id, status);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  const confirmLabel = item.item_type === "contradiction" ? "Mark reviewed" : "Confirm fact";

  return (
    <div className="review-actions">
      <button type="button" onClick={() => decide("confirmed")} disabled={busy}>{confirmLabel}</button>
      <button type="button" onClick={() => decide("dismissed")} disabled={busy}>Dismiss</button>
    </div>
  );
}
