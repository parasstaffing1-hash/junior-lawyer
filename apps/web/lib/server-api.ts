/**
 * Server-side data access for React Server Components.
 *
 * Browser requests carry the session cookie automatically; server components do
 * not, so the incoming cookie header is read and forwarded explicitly. These
 * calls go straight to the API's internal URL rather than through the Next.js
 * rewrite, which only exists for the browser.
 *
 * Every function here is read-only. Mutations belong in client components so
 * they go through lib/client.ts and pick up CSRF handling.
 */
import { cookies } from "next/headers";

import type {
  AgentRecipeRead,
  AgentRunDetail,
  AgentRunRead,
  AIProviderStatusRead,
  AIRunRead,
  MatterMemoryRead,
  ContractCatalogItem as ContractCatalogItemSchema,
  ContractListItem as ContractListItemSchema,
  ContractReviewListItem as ContractReviewListItemSchema,
  CorpusStatsRead,
  ContradictionRead,
  DraftCatalogItem,
  DocumentRead,
  EvidenceMatrixRead,
  FactRead,
  IntelligenceSummaryRead,
  LegalDraftListItem,
  MatterRead,
  ProcedureAgendaItem,
  ProcedurePackRead,
  ProcedureStats as ProcedureStatsSchema,
  ReviewItemRead,
  StatementRead,
  TimelineEventRead,
} from "@/lib/generated-types";

const INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
const PREFIX = "/api/v1";

/** Names the UI uses, bound to the API's own response contracts. */
export type Matter = MatterRead;
export type LegalDocument = DocumentRead;
export type MatterFact = FactRead;
export type MatterStatement = StatementRead;
export type MatterContradiction = ContradictionRead;
export type TimelineEvent = TimelineEventRead;
export type EvidenceMatrix = EvidenceMatrixRead;
export type IntelligenceSummary = IntelligenceSummaryRead;
export type ReviewItem = ReviewItemRead;
export type ResearchStats = CorpusStatsRead;
export type ProcedurePack = ProcedurePackRead;
export type ProcedureStats = ProcedureStatsSchema;
export type ContractListItem = ContractListItemSchema;
export type ContractCatalogItem = ContractCatalogItemSchema;
export type ContractReviewListItem = ContractReviewListItemSchema;
export type { LegalDraftListItem };

async function cookieHeader(): Promise<string> {
  const cookieStore = await cookies();
  return cookieStore
    .getAll()
    .map((entry) => `${entry.name}=${entry.value}`)
    .join("; ");
}

/**
 * Raised when the API could not be reached at all, so a caller can tell an
 * outage apart from a genuinely empty list. `get` still swallows this; only
 * `getOrThrow` surfaces it.
 */
export class ApiUnreachableError extends Error {
  constructor(message = `API is unreachable at ${INTERNAL_URL}`) {
    super(message);
    this.name = "ApiUnreachableError";
  }
}

async function get<T>(path: string, fallback: T): Promise<T> {
  const header = await cookieHeader();

  let response: Response;
  try {
    response = await fetch(`${INTERNAL_URL}${PREFIX}${path}`, {
      headers: header ? { cookie: header } : {},
      cache: "no-store",
    });
  } catch {
    // A page should still render its shell when the API is unreachable.
    return fallback;
  }
  // 401 is the normal state for a signed-out visitor, not an error worth
  // crashing a server-rendered page over.
  if (!response.ok) return fallback;
  return (await response.json()) as T;
}

/**
 * Same request as `get`, but a dead API raises instead of masquerading as an
 * empty result. For pages that render an explicit "API not connected" notice.
 */
async function getOrThrow<T>(path: string): Promise<T> {
  const header = await cookieHeader();

  let response: Response;
  try {
    response = await fetch(`${INTERNAL_URL}${PREFIX}${path}`, {
      headers: header ? { cookie: header } : {},
      cache: "no-store",
    });
  } catch {
    throw new ApiUnreachableError();
  }
  if (!response.ok) throw new Error(`API responded ${response.status}`);
  return (await response.json()) as T;
}

export function getMatters() {
  return get<Matter[]>("/matters", []);
}

/** `getMatters`, but an unreachable API throws rather than returning []. */
export function getMattersOrThrow() {
  return getOrThrow<Matter[]>("/matters");
}

export type AgentRecipe = AgentRecipeRead;
export type AgentRun = AgentRunRead;
export type AgentRunWithSteps = AgentRunDetail;
export type CaseMemory = MatterMemoryRead;

export function getAgentRecipes() {
  return get<AgentRecipe[]>("/agent/recipes", []);
}

export function getAgentRuns(matterId?: string) {
  const query = matterId ? `?matter_id=${matterId}` : "";
  return get<AgentRun[]>(`/agent/runs${query}`, []);
}

export function getAgentRun(runId: string) {
  return get<AgentRunWithSteps | null>(`/agent/runs/${runId}`, null);
}

export function getCaseMemory(matterId: string) {
  return get<CaseMemory | null>(`/agent/matters/${matterId}/memory`, null);
}

export function getMatter(matterId: string) {
  return get<Matter | null>(`/matters/${matterId}`, null);
}

export function getDocuments(matterId: string) {
  return get<LegalDocument[]>(`/matters/${matterId}/documents`, []);
}

export function getFacts(matterId: string) {
  return get<MatterFact[]>(`/matters/${matterId}/facts`, []);
}

export function getStatements(matterId: string) {
  return get<MatterStatement[]>(`/matters/${matterId}/statements`, []);
}

export function getContradictions(matterId: string) {
  return get<MatterContradiction[]>(`/matters/${matterId}/contradictions`, []);
}

export function getTimeline(matterId: string) {
  return get<TimelineEvent[]>(`/matters/${matterId}/timeline`, []);
}

export function getEvidence(matterId: string) {
  return get<EvidenceMatrix | null>(`/matters/${matterId}/evidence`, null);
}

export function getReviewItems(matterId: string) {
  return get<ReviewItem[]>(`/matters/${matterId}/review`, []);
}

export function getIntelligenceSummary(matterId: string) {
  return get<IntelligenceSummary | null>(`/matters/${matterId}/intelligence/summary`, null);
}

export function getResearchStats() {
  return get<ResearchStats | null>("/research/stats", null);
}

export function getAIProviderStatus() {
  return get<AIProviderStatusRead | null>("/ai/providers", null);
}

export function getAIRuns() {
  return get<AIRunRead[]>("/ai/runs", []);
}

export function getAgenda(days = 7) {
  return get<ProcedureAgendaItem[]>(`/procedure/agenda?days=${days}`, []);
}

export function getProcedurePacks() {
  return get<ProcedurePack[]>("/procedure/packs", []);
}

export function getProcedureStats() {
  return get<ProcedureStats | null>("/procedure/stats", null);
}

export function getContracts() {
  return get<ContractListItem[]>("/contracts", []);
}

export function getContractCatalog() {
  return get<ContractCatalogItem[]>("/contracts/catalog", []);
}

export function getContractReviews() {
  return get<ContractReviewListItem[]>("/contract-reviews", []);
}

export function getDrafts(matterId?: string) {
  return get<LegalDraftListItem[]>(matterId ? `/drafting?matter_id=${matterId}` : "/drafting", []);
}

export function getDraftCatalog() {
  return get<DraftCatalogItem[]>("/drafting/catalog", []);
}
