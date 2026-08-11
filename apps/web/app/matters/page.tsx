import Link from "next/link";
import { PlusIcon } from "@/components/icons";
import { getMatters, type Matter } from "@/lib/server-api";

export default async function MattersPage() {
  let matters: Matter[] = [];
  let apiError = "";

  try {
    matters = await getMatters();
  } catch (error) {
    apiError = error instanceof Error ? error.message : "Unable to reach the API";
  }

  return (
    <main className="page">
      <div className="hero-row">
        <div>
          <div className="eyebrow">Matter workspace</div>
          <h1 className="page-title">Matters</h1>
          <p className="page-subtitle">
            Every fact, document, hearing, contract and research result stays attached to a source-backed legal matter.
          </p>
        </div>
        <button className="primary-button" type="button"><PlusIcon /> New matter</button>
      </div>

      {apiError ? (
        <div className="notice-panel">
          <strong>API is not connected.</strong>
          <span>{apiError}. Start the FastAPI server on port 8000 to load live matters.</span>
        </div>
      ) : null}

      <section className="card">
        <div className="card-header">
          <div className="card-title">Open matters</div>
          <div className="card-action">{matters.length} total</div>
        </div>
        {matters.length ? matters.map((matter) => (
          <Link className="matter-row matter-link" href={`/matters/${matter.id}`} key={matter.id}>
            <div>
              <div className="matter-title">{matter.title}</div>
              <div className="matter-meta">
                {matter.case_number ?? matter.reference_number ?? "No case number"} · {matter.document_count} documents
              </div>
            </div>
            <div className="matter-court">{matter.court_name ?? matter.jurisdiction}</div>
            <div className="status">{matter.status.replace("_", " ")}</div>
          </Link>
        )) : (
          <div className="empty-state">
            <div className="empty-state-title">No matters yet</div>
            <div className="empty-state-copy">Create a matter first, then upload pleadings, orders, contracts and evidence into its document workspace.</div>
          </div>
        )}
      </section>
    </main>
  );
}
