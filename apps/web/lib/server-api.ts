/**
 * Server-side data access for React Server Components.
 *
 * STATUS: placeholders. Server components must forward the incoming session
 * cookie explicitly, so these cannot simply re-export the browser client.
 * See lib/api.ts for the same caveat.
 */
/* eslint-disable @typescript-eslint/no-explicit-any */

function pending(name: string): never {
  throw new Error(
    `${name}() is not implemented yet. Server-side data access is still to be ` +
      `wired up against the API's session cookie.`,
  );
}

/* Response shapes still to be typed from the OpenAPI schema. */
export type ContractCatalogItem = any;
export type ContractListItem = any;
export type ContractReviewListItem = any;
export type EvidenceMatrix = any;
export type IntelligenceSummary = any;
export type LegalDocument = any;
export type LegalDraftListItem = any;
export type Matter = any;
export type MatterContradiction = any;
export type MatterFact = any;
export type MatterStatement = any;
export type ResearchStats = any;
export type ReviewItem = any;
export type TimelineEvent = any;

export function getAIProviderStatus(...args: any[]): Promise<any> { void args; return pending('getAIProviderStatus'); }
export function getAIRuns(...args: any[]): Promise<any> { void args; return pending('getAIRuns'); }
export function getAgenda(...args: any[]): Promise<any> { void args; return pending('getAgenda'); }
export function getContractCatalog(...args: any[]): Promise<any> { void args; return pending('getContractCatalog'); }
export function getContractReviews(...args: any[]): Promise<any> { void args; return pending('getContractReviews'); }
export function getContracts(...args: any[]): Promise<any> { void args; return pending('getContracts'); }
export function getContradictions(...args: any[]): Promise<any> { void args; return pending('getContradictions'); }
export function getDocuments(...args: any[]): Promise<any> { void args; return pending('getDocuments'); }
export function getDraftCatalog(...args: any[]): Promise<any> { void args; return pending('getDraftCatalog'); }
export function getDrafts(...args: any[]): Promise<any> { void args; return pending('getDrafts'); }
export function getEvidence(...args: any[]): Promise<any> { void args; return pending('getEvidence'); }
export function getFacts(...args: any[]): Promise<any> { void args; return pending('getFacts'); }
export function getIntelligenceSummary(...args: any[]): Promise<any> { void args; return pending('getIntelligenceSummary'); }
export function getMatter(...args: any[]): Promise<any> { void args; return pending('getMatter'); }
export function getMatters(...args: any[]): Promise<any> { void args; return pending('getMatters'); }
export function getProcedurePacks(...args: any[]): Promise<any> { void args; return pending('getProcedurePacks'); }
export function getProcedureStats(...args: any[]): Promise<any> { void args; return pending('getProcedureStats'); }
export function getResearchStats(...args: any[]): Promise<any> { void args; return pending('getResearchStats'); }
export function getReviewItems(...args: any[]): Promise<any> { void args; return pending('getReviewItems'); }
export function getStatements(...args: any[]): Promise<any> { void args; return pending('getStatements'); }
export function getTimeline(...args: any[]): Promise<any> { void args; return pending('getTimeline'); }
