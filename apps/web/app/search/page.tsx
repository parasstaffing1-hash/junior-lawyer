import { Suspense } from "react";
import { SearchWorkspace } from "@/components/search-workspace";

export default function SearchPage() {
  return <Suspense fallback={<main className="page"><div className="premium-panel">Loading search…</div></main>}><SearchWorkspace /></Suspense>;
}
