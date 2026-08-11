import { ContractReviewWorkspace } from "@/components/contract-review-workspace";
import { ContractWorkspace } from "@/components/contract-workspace";
import {
  ContractCatalogItem,
  ContractListItem,
  ContractReviewListItem,
  getContractCatalog,
  getContractReviews,
  getContracts,
} from "@/lib/server-api";

export default async function ContractsPage() {
  let catalog: ContractCatalogItem[] = [];
  let contracts: ContractListItem[] = [];
  let reviews: ContractReviewListItem[] = [];
  try {
    [catalog, contracts, reviews] = await Promise.all([
      getContractCatalog(),
      getContracts(),
      getContractReviews(),
    ]);
  } catch {
    // Frontend-only previews stay usable when the API is not running.
  }

  return (
    <main className="page contracts-page">
      <div className="hero-row contracts-hero">
        <div>
          <div className="eyebrow">Contract intelligence · India</div>
          <h1 className="page-title">Draft from rules. Review with evidence.</h1>
          <p className="page-subtitle">
            Build English, हिन्दी or bilingual contracts from approved clause variants, then review counterparty agreements against the same playbook. AI is reserved for genuinely custom language and complex legal reasoning.
          </p>
        </div>
        <div className="contract-engine-note">
          <strong>₹0</strong>
          <span>LLM cost for baseline drafting + review</span>
        </div>
      </div>
      <ContractWorkspace initialCatalog={catalog} initialContracts={contracts} />
      <ContractReviewWorkspace catalog={catalog} initialReviews={reviews} />
    </main>
  );
}
