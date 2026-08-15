/**
 * Junior Lawyer API client.
 *
 * Every export here calls a real endpoint; nothing throws NotImplementedError
 * any more. What remains partial is typing, not behaviour: a handful of
 * aliases below are still `any` because the route they describe assembles its
 * response inline and therefore contributes no schema to the OpenAPI document.
 * The fix for each is on the API — declare a response_model — not here.
 */
export * from "@/lib/client";
export * from "@/lib/tools";
import type * as G from "@/lib/generated-types";

import { API_BASE, apiFetch, jsonBody } from "@/lib/client";

export interface ActorRead {
  id: string;
  email: string;
  display_name?: string | null;
  [key: string]: unknown;
}

export interface OrganizationRead {
  id: string;
  name: string;
  slug: string;
  [key: string]: unknown;
}

export interface LoginResult {
  actor: ActorRead;
  organization: OrganizationRead;
  csrf_token: string;
  expires_at: string;
  absolute_expires_at: string;
}

export function securityLogin(payload: {
  email: string;
  password: string;
  organization_slug?: string;
  /** TOTP or recovery code; only required once the account has MFA enabled. */
  mfa_code?: string;
}): Promise<LoginResult> {
  return apiFetch<LoginResult>("/security/auth/login", jsonBody(payload));
}

export type MFAStatus = G.MFAStatusRead;
export type MFAEnrolmentStart = G.MFAEnrolmentStart;

export type Conversation = G.ConversationRead;
export type ConversationDetail = G.ConversationDetail;
export type ConversationMessage = G.ConversationMessageRead;
export type ConversationTurn = G.ConversationTurn;

export const listConversations = (params: { matter_id?: string; conversation_status?: string; limit?: number } = {}): Promise<Conversation[]> =>
  apiFetch(`/ai/conversations${query({ matter_id: params.matter_id, conversation_status: params.conversation_status, limit: params.limit })}`);
export const createConversation = (payload: { title?: string; matter_id?: string; jurisdiction?: string; output_language?: string; document_ids?: string[] }): Promise<Conversation> =>
  apiFetch("/ai/conversations", jsonBody(payload));
export const getConversation = (conversationId: string): Promise<ConversationDetail> =>
  apiFetch(`/ai/conversations/${conversationId}`);
export const renameConversation = (conversationId: string, title: string): Promise<Conversation> =>
  apiFetch(`/ai/conversations/${conversationId}`, patchBody({ title }));
export const setConversationStatus = (conversationId: string, status: "active" | "archived"): Promise<Conversation> =>
  apiFetch(`/ai/conversations/${conversationId}/status`, patchBody({ status }));
export const deleteConversation = (conversationId: string): Promise<void> =>
  apiFetch(`/ai/conversations/${conversationId}`, { method: "DELETE" });
export const postConversationMessage = (
  conversationId: string,
  payload: {
    question: string;
    task_type?: G.AITaskType;
    prefer_local?: boolean;
    allow_remote?: boolean;
    allow_local_for_high_complexity?: boolean;
    include_corpus?: boolean;
  },
): Promise<ConversationTurn> => apiFetch(`/ai/conversations/${conversationId}/messages`, jsonBody(payload));

/** Sends a recording for transcription. The audio is not stored server-side. */
export const transcribeAudio = (audio: Blob, mimeType: string): Promise<G.TranscriptRead> => {
  const form = new FormData();
  // A filename is required for the multipart part to carry its content type.
  form.append("audio", new File([audio], "dictation", { type: mimeType }));
  return apiFetch("/ai/transcribe?allow_remote=true", { method: "POST", body: form });
};

export type StatuteListItem = G.StatuteListItem;
export type StatuteBrowse = G.StatuteBrowse;
export type StatuteShelf = G.StatuteShelf;
export type StatuteSectionRecord = G.StatuteSectionRead;

export const browseStatutes = (params: { search?: string; jurisdiction?: string; state?: string; year?: number; limit?: number; offset?: number } = {}): Promise<StatuteBrowse> =>
  apiFetch(`/research/statutes${query({ search: params.search, jurisdiction: params.jurisdiction, state: params.state, year: params.year, limit: params.limit, offset: params.offset })}`);
export const getStatuteShelf = (): Promise<StatuteShelf> => apiFetch("/research/statutes-shelf");
export const getStatuteSections = (statuteId: string): Promise<StatuteSectionRecord[]> =>
  apiFetch(`/research/statutes/${statuteId}/sections`);
export const searchStatuteSections = (statuteId: string, q: string): Promise<StatuteSectionRecord[]> =>
  apiFetch(`/research/statutes/${statuteId}/sections/search${query({ q })}`);

export const getMFAStatus = (): Promise<G.MFAStatusRead> => apiFetch("/security/auth/mfa");
export const startMFAEnrolment = (): Promise<G.MFAEnrolmentStart> => apiFetch("/security/auth/mfa/enrol", { method: "POST" });
export const confirmMFAEnrolment = (code: string): Promise<G.MFAConfirmResponse> => apiFetch("/security/auth/mfa/confirm", jsonBody({ code }));
export const disableMFA = (password: string): Promise<G.MFAStatusRead> => apiFetch("/security/auth/mfa/disable", jsonBody({ password }));

export function securityLogout(): Promise<void> {
  return apiFetch<void>("/security/auth/logout", { method: "POST" });
}

export function securityBootstrap(payload: Record<string, unknown>): Promise<G.BootstrapResponse> {
  return apiFetch<G.BootstrapResponse>("/security/bootstrap", jsonBody(payload));
}


export interface ExperiencePreferences {
  ui_language: "en" | "hi" | "bilingual";
  density: string;
  contrast: string;
  font_scale: string;
  reduce_motion: boolean;
  show_keyboard_hints: boolean;
  document_page_window: number;
  document_text_zoom: number;
  remember_last_workspace: boolean;
  [key: string]: unknown;
}

export function getExperiencePreferences(): Promise<ExperiencePreferences> {
  return apiFetch<ExperiencePreferences>("/experience/preferences");
}

export function updateExperiencePreferences(
  patch: Partial<ExperiencePreferences>,
): Promise<ExperiencePreferences> {
  return apiFetch<ExperiencePreferences>("/experience/preferences", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}


function patchBody(payload: unknown): RequestInit {
  return { method: "PATCH", body: JSON.stringify(payload) };
}

/** Builds a query string, dropping keys the caller left undefined or blank. */
function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const rendered = search.toString();
  return rendered ? `?${rendered}` : "";
}

/* ------------------------------------------------------------------------ */
/* Placeholders — not yet implemented.                                       */
/* ------------------------------------------------------------------------ */
/* eslint-disable @typescript-eslint/no-explicit-any */

class NotImplementedError extends Error {
  constructor(name: string) {
    super(
      `${name}() is not implemented yet. The Junior Lawyer API client is being ` +
        `built endpoint by endpoint; this workspace is not wired up.`,
    );
    this.name = "NotImplementedError";
  }
}

function pending(name: string): Promise<never> {
  return Promise.reject(new NotImplementedError(name));
}

/* Response shapes still to be typed from the OpenAPI schema. */
export type AIPrepareResponse = G.AIPrepareResponse;
export type AIProviderStatus = G.AIProviderStatusRead;
export type AIReasoningPayload = G.AIReasoningRequest;
export type AIRun = G.AIRunRead;
export type AITaskType = G.AITaskType;
export type AgendaItem = G.ProcedureAgendaItem;
export type AnalyticsDashboardRecord = G.AnalyticsDashboard;
export type AnalyticsGoalRecord = G.GoalWithProgress;
export type AnalyticsPreferenceRecord = G.AnalyticsPreferenceRead;
export type AnalyticsRiskRecord = G.RiskSignalRead;
export type AnalyticsSnapshotRecord = G.SnapshotRead;
export type BackgroundJobDetailRecord = G.JobDetail;
export type BackgroundJobRecord = G.JobRead;
export type BackgroundQueueRecord = G.QueueRead;
export type BackupRunRecord = G.BackupRunRead;
export type BillingExpense = G.ExpenseRead;
export type BillingInvoice = G.InvoiceRead;
export type BillingOverview = G.BillingOverview;
export type BillingPayment = G.PaymentRead;
export type BillingProfile = G.BillingProfileRead;
export type CRMClient = G.ClientRead;
export type CRMClientDetail = G.ClientDetail;
export type CRMConflictCheck = G.ConflictCheckRead;
export type CRMLead = G.LeadRead;
export type CRMOverview = G.CRMOverview;
export type CRMTask = G.TaskRead;
export type CaseCandidate = G.CaseCandidateRead;
export type ClientHealthAnalyticsRecord = G.ClientHealthRead;
export type ClientMoneyAccount = G.ClientMoneyAccountRead;
export type ClientMoneyDashboard = G.ClientMoneyDashboard;
export type ClientMoneyEntry = G.ClientMoneyJournalEntryRead;
export type ClientMoneyTransfer = G.TransferRequestRead;
export type ComplianceStatus = G.ComplianceStatus;
export type ContractCatalogItem = G.ContractCatalogItem;
export type ContractDetail = G.ContractRead;
export type ContractLanguage = G.ContractLanguage;
export type ContractListItem = G.ContractListItem;
export type ContractQuestion = G.ContractQuestion;
export type ContractQuestionnaire = G.ContractQuestionnaire;
export type ContractReviewDetail = G.ContractReviewRead;
export type ContractReviewListItem = G.ContractReviewListItem;
export type ContractRiskProfile = G.ContractRiskProfile;
export type ContractRiskStatus = G.ContractRiskStatus;
export type ContractType = G.ContractType;
export type CourtChangeRecord = G.CourtChangeRead;
export type CourtLevel = G.CourtLevel;
export type CourtTrackerRecord = G.CourtTrackerRead;
export type DeploymentDashboardRecord = G.DeploymentDashboard;
export type DocumentCommentRecord = G.CommentRead;
export type DocumentPageMatch = G.DocumentPageMatchRead;
export type DocumentPageWindow = G.DocumentPageWindowRead;
export type DocumentVersionRecord = G.DocumentVersionRead;
export type DraftCatalogItem = G.DraftCatalogItem;
export type DraftContextPreview = G.DraftContextPreview;
export type DraftFindingStatus = G.DraftFindingStatus;
export type DraftSection = G.DraftSectionRead;
export type EvidenceBundleRecord = G.BundleRead;
export type EvidenceDashboard = G.EvidenceDashboard;
export type EvidenceGapRecord = G.GapRead;
export type EvidenceGraph = G.EvidenceGraphRead;
export type IssueStanding = G.IssueStandingRead;
export type EvidenceRecord = G.EvidenceItemRead;
export type EvidenceWitnessRecord = G.WitnessRead;
export type Hearing = G.HearingRead;
export type IntegrationCatalogRecord = G.IntegrationCatalogItem;
export type IntegrationConnectionCreatePayload = any;
export type IntegrationDashboardRecord = G.IntegrationDashboard;
export type IntegrationProviderKind = any;
export type JobsDashboardRecord = G.JobsDashboard;
export type JurisdictionPackRecord = G.JurisdictionPackRead;
export type KnowledgeAssetKind = G.KnowledgeAssetKind;
export type KnowledgeAssetRecord = G.KnowledgeAssetRead;
export type KnowledgeCollectionRecord = G.KnowledgeCollectionRead;
export type KnowledgeDashboard = G.KnowledgeDashboard;
export type KnowledgeSearchResultRecord = G.KnowledgeSearchResult;
export type LegacyMatter = any;
export type LegalDataAmendmentRecord = G.AmendmentRead;
export type LegalDataDashboardRecord = G.LegalDataDashboard;
export type LegalDataFeedRecord = G.LegalDataFeedRead;
export type LegalDataRunRecord = G.IngestionRunRead;
export type LegalDocument = G.DocumentRead;
export type LegalDraft = G.LegalDraftRead;
export type LegalDraftLanguage = G.LegalDraftLanguage;
export type LegalDraftListItem = G.LegalDraftListItem;
export type LegalSourceRecord = G.ResearchSourceRead;
export type LitigationIssueRecord = G.IssueRead;
export type Matter = G.MatterRead;
export type MatterAccessDecision = G.AccessDecisionRead;
export type MatterAccessLevel = G.MatterAccessLevel;
export type MatterDeadline = G.DeadlineRead;
export type MatterHealthRecord = G.MatterHealthRead;
export type MatterPlaybookRecord = G.MatterPlaybookRead;
export type MatterProcedure = G.MatterProcedureRead;
export type MatterSecurityGrant = G.MatterGrantRead;
export type MatterSecurityProfile = G.MatterSecurityProfileRead;
export type OnboardingProgress = G.OnboardingProgressRead;
export type OperationsAgendaItem = G.AgendaItem;
export type OperationsDashboard = G.OperationsDashboard;
export type OrganizationRole = G.OrganizationRole;
export type PortalClientApproval = G.PortalClientApprovalRead;
export type PortalDashboard = G.PortalDashboard;
export type PortalShare = G.PortalShareRead;
export type ProcedurePack = G.ProcedurePackRead;
export type ProcedureStats = G.ProcedureStats;
export type QADashboardRecord = G.QADashboard;
export type QARunDetail = G.EvaluationRunDetail;
export type QASuiteDetail = G.EvaluationSuiteDetail;
export type RecentSearchItem = G.RecentItemRead;
export type ReleaseDashboardRecord = G.ReleaseDashboard;
export type ReleaseRunDetailRecord = G.ReleaseRunDetail;
export type RemedyAnalysis = G.RemedyAnalysisRead;
export type RemedyCandidate = G.RemedyCandidateRead;
export type ResearchCollectionRecord = G.ResearchCollectionRead;
export type ResearchResult = any;
export type ResearchScope = any;
export type ResearchStats = G.CorpusStatsRead;
export type ReviewFindingStatus = G.ReviewFindingStatus;
export type ReviewItem = G.ReviewItemRead;
export type SavedCaseDetail = G.SavedCaseDetailRead;
export type SavedCaseSummary = G.SavedCaseSummaryRead;
export type SavedSearch = G.SavedSearchRead;
export type SearchCommand = any;
export type SearchDuplicateRecord = G.SearchDuplicateItem;
export type SearchEntityType = G.SearchEntityType;
export type SearchIndexHealth = G.SearchIndexHealth;
export type SecurityAuditEntry = G.AuditEntryRead;
export type SecurityAuditVerification = G.AuditVerifyRead;
export type SecurityMember = G.MembershipRead;
export type SecurityOverview = G.SecurityOverviewRead;
export type SystemHealthDashboardRecord = G.SystemHealthDashboard;
export type SystemHealthStatus = "healthy" | "degraded" | "down" | "unknown";
export type TeamPerformanceRecord = G.TeamPerformanceRead;
export type UniversalSearchResponse = G.UniversalSearchResponse;
export type UniversalSearchResult = G.SearchResult;
export type ValidationCampaignDetailRecord = G.ValidationCampaignDetail;
export type ValidationDashboardRecord = G.ValidationDashboard;
export type WitnessPrepQuestionRecord = G.PrepQuestionRead;
export type WorkflowTaskRecord = G.WorkflowTaskRead;
export type WorkflowTemplateRecord = G.WorkflowTemplateRead;

export const adoptLegacyMatter = (matterId: string): Promise<Record<string, unknown>> => apiFetch(`/security/matters/${matterId}/adopt`, { method: "POST" });
export const analyzeRemedies = (payload: Record<string, unknown>): Promise<G.RemedyAnalysisRead> => apiFetch("/remedies/analyze", jsonBody(payload));
export const approveContract = (contractId: string): Promise<G.DraftResult> => apiFetch(`/contracts/${contractId}/approve`, { method: "POST" });
export const approveKnowledgeAsset = (assetId: string, sanitizationStatus: string, reviewNote: string): Promise<G.KnowledgeAssetRead> => apiFetch(`/knowledge/assets/${assetId}/approve`, jsonBody({ sanitization_status: sanitizationStatus, review_note: reviewNote }));
export const approveLegalDraft = (draftId: string): Promise<G.DraftRenderResult> => apiFetch(`/drafting/${draftId}/approve`, { method: "POST" });
export const attachProcedure = (matterId: string, packId: string): Promise<G.MatterProcedureRead> => apiFetch(`/procedure/matters/${matterId}/attach`, jsonBody({ pack_id: packId }));
export const beginDraftReview = (draftId: string): Promise<G.LegalDraftRead> => apiFetch(`/drafting/${draftId}/review`, { method: "POST" });
export const cancelBackgroundJob = (jobId: string): Promise<G.JobRead> => apiFetch(`/jobs/${jobId}/cancel`, { method: "POST" });
export const captureCourtSnapshot = (trackerId: string, payload: Record<string, unknown>): Promise<G.CourtSnapshotCaptureRead> => apiFetch(`/operations/trackers/${trackerId}/snapshots`, jsonBody(payload));
export const contractDownloadUrl = (contractId: string): string => `${API_BASE}/contracts/${contractId}/download`;
export const contractRedlineDownloadUrl = (reviewId: string, redlineId: string): string => `${API_BASE}/contract-reviews/${reviewId}/redlines/${redlineId}/download`;
export const convertCRMLead = (leadId: string, payload: Record<string, unknown>): Promise<G.ClientRead> => apiFetch(`/crm/leads/${leadId}/convert`, jsonBody(payload));
export const createAnalyticsGoal = (payload: Record<string, unknown>): Promise<G.GoalWithProgress> => apiFetch("/analytics/goals", jsonBody(payload));
export const createAnalyticsSnapshot = (notes: string): Promise<G.SnapshotRead> => apiFetch("/analytics/snapshots", jsonBody({ notes }));
export const createBackgroundJob = (payload: Record<string, unknown>): Promise<G.JobRead> => apiFetch("/jobs", jsonBody(payload));
export const createBillingExpense = (payload: Record<string, unknown>): Promise<G.ExpenseRead> => apiFetch("/billing/expenses", jsonBody(payload));
export const createBillingInvoice = (payload: Record<string, unknown>): Promise<G.InvoiceRead> => apiFetch("/billing/invoices", jsonBody(payload));
export const createBillingPayment = (payload: Record<string, unknown>): Promise<G.PaymentRead> => apiFetch("/billing/payments", jsonBody(payload));
export const createCRMClient = (payload: Record<string, unknown>): Promise<G.ClientRead> => apiFetch("/crm/clients", jsonBody(payload));
export const createCRMLead = (payload: Record<string, unknown>): Promise<G.LeadRead> => apiFetch("/crm/leads", jsonBody(payload));
export const createCaseWorkspace = (savedCaseId: string): Promise<G.CaseWorkspaceResult> => apiFetch(`/case-lookup/saved/${savedCaseId}/workspace`, { method: "POST" });
export const createClientMoneyAccount = (payload: Record<string, unknown>): Promise<G.ClientMoneyAccountRead> => apiFetch("/client-money/accounts", jsonBody(payload));
export const createClientMoneyDeposit = (payload: Record<string, unknown>): Promise<G.ClientMoneyJournalEntryRead> => apiFetch("/client-money/deposits", jsonBody(payload));
export const createClientMoneyTransfer = (payload: Record<string, unknown>): Promise<G.TransferRequestRead> => apiFetch("/client-money/transfers", jsonBody(payload));
export const createConflictCheck = (payload: Record<string, unknown>): Promise<G.ConflictCheckRead> => apiFetch("/crm/conflicts", jsonBody(payload));
export const createContract = (payload: Record<string, unknown>): Promise<G.ContractRead> => apiFetch("/contracts", jsonBody(payload));
export const createCourtTracker = (payload: Record<string, unknown>): Promise<G.CourtTrackerRead> => apiFetch("/operations/trackers", jsonBody(payload));
export const createDeploymentEnvironment = (payload: Record<string, unknown>): Promise<G.DeploymentEnvironmentRead> => apiFetch("/deployment/environments", jsonBody(payload));
export const createDocumentComment = (documentId: string, body: string): Promise<G.CommentRead> => apiFetch(`/collaboration/documents/${documentId}/comments`, jsonBody({ body }));
export const createEvidenceBundle = (matterId: string, payload: Record<string, unknown>): Promise<G.BundleRead> => apiFetch(`/evidence/matters/${matterId}/bundles`, jsonBody(payload));
export const createEvidenceWitness = (matterId: string, payload: Record<string, unknown>): Promise<G.WitnessRead> => apiFetch(`/evidence/matters/${matterId}/witnesses`, jsonBody(payload));
export const createHearing = (payload: Record<string, unknown>): Promise<G.HearingRead> => apiFetch("/procedure/hearings", jsonBody(payload));
export const createIntegrationConnection = (payload: IntegrationConnectionCreatePayload): Promise<G.IntegrationConnectionRead> => apiFetch("/integrations", jsonBody(payload));
export const createJurisdictionPack = (payload: Record<string, unknown>): Promise<G.JurisdictionPackRead> => apiFetch("/legal-data/packs", jsonBody(payload));
export const createKnowledgeAsset = (payload: Record<string, unknown>): Promise<G.KnowledgeAssetRead> => apiFetch("/knowledge/assets", jsonBody(payload));
export const createKnowledgeCollection = (payload: Record<string, unknown>): Promise<G.KnowledgeCollectionRead> => apiFetch("/knowledge/collections", jsonBody(payload));
export const createLegalDataFeed = (payload: Record<string, unknown>): Promise<G.LegalDataFeedRead> => apiFetch("/legal-data/feeds", jsonBody(payload));
export const createLegalDraft = (payload: Record<string, unknown>): Promise<G.LegalDraftRead> => apiFetch("/drafting", jsonBody(payload));
export const createLitigationIssue = (matterId: string, payload: Record<string, unknown>): Promise<G.IssueRead> => apiFetch(`/evidence/matters/${matterId}/issues`, jsonBody(payload));
export const createManualDeadline = (matterId: string, payload: Record<string, unknown>): Promise<G.DeadlineRead> => apiFetch(`/procedure/matters/${matterId}/deadlines/manual`, jsonBody(payload));
export const createReleaseRun = (payload: Record<string, unknown>): Promise<G.ReleaseRunRead> => apiFetch("/release/runs", jsonBody(payload));
export const createRemedyDraft = (candidateId: string, requestedDocumentKind: string, language: "en" | "hi" | "bilingual" = "en"): Promise<G.RemedyDraftLinkRead> => apiFetch(`/remedies/candidates/${candidateId}/draft`, jsonBody({ requested_document_kind: requestedDocumentKind, language }));
export const createRemedyMemo = (candidateId: string, language: string): Promise<G.RemedyMemoRead> => apiFetch(`/remedies/candidates/${candidateId}/memo`, jsonBody({ language }));
export const createSecurityMember = (payload: Record<string, unknown>): Promise<G.MembershipRead> => apiFetch("/security/members", jsonBody(payload));
export const createValidationCampaign = (payload: Record<string, unknown>): Promise<G.ValidationCampaignRead> => apiFetch("/validation/campaigns", jsonBody(payload));
export const decideClientMoneyTransfer = (requestId: string, approve: boolean, note: string): Promise<G.TransferRequestRead> => apiFetch(`/client-money/transfers/${requestId}/decision`, jsonBody({ approve, note }));
export const decideDeployment = (rolloutId: string, decision: string, note: string): Promise<Record<string, unknown>> => apiFetch(`/deployment/rollouts/${rolloutId}`, jsonBody({ decision, note }));
export const deleteSavedSearch = (searchId: string): Promise<void> => apiFetch(`/search/saved/${searchId}`, { method: "DELETE" });
export const detectSearchDuplicates = (): Promise<SearchDuplicateRecord[]> => apiFetch("/search/index/duplicates/detect", { method: "POST" });
export const draftContract = (contractId: string): Promise<G.DraftResult> => apiFetch(`/contracts/${contractId}/draft`, { method: "POST" });
export const ensureDefaultBackupPolicy = (): Promise<G.BackupPolicyRead> => apiFetch("/system-health/backups/policies/default", { method: "POST" });
export const evaluateReleaseRun = (runId: string): Promise<G.ReleaseGateSummary> => apiFetch(`/release/runs/${runId}/evaluate`, { method: "POST" });
export const evaluateValidationCampaign = (campaignId: string): Promise<ValidationCampaignDetailRecord> => apiFetch(`/validation/campaigns/${campaignId}/evaluate`, { method: "POST" });
export const evidenceBundleDownloadUrl = (bundleId: string): string => `${API_BASE}/evidence/bundles/${bundleId}/download`;
export const executeClientMoneyTransfer = (requestId: string): Promise<G.TransferRequestRead> => apiFetch(`/client-money/transfers/${requestId}/execute`, { method: "POST" });
export const finalizeEvidenceBundle = (bundleId: string): Promise<G.BundleRead> => apiFetch(`/evidence/bundles/${bundleId}/finalize`, { method: "POST" });
export const findInDocument = (documentId: string, q: string, limit = 40): Promise<DocumentPageMatch[]> => apiFetch(`/documents/${documentId}/find${query({ q, limit })}`);
export const generateContractRedline = (reviewId: string): Promise<G.RedlineRead> => apiFetch(`/contract-reviews/${reviewId}/redlines`, { method: "POST" });
export const generateWitnessPrep = (witnessId: string): Promise<G.PrepQuestionRead[]> => apiFetch(`/evidence/witnesses/${witnessId}/prep/generate`, { method: "POST" });
export const getAgenda = (matterId?: string | null, days = 30): Promise<AgendaItem[]> => apiFetch(`/procedure/agenda${query({ matter_id: matterId ?? undefined, days })}`);
export const getAnalyticsDashboard = (): Promise<G.AnalyticsDashboard> => apiFetch("/analytics/dashboard");
export const getAnalyticsGoals = (): Promise<G.GoalWithProgress[]> => apiFetch("/analytics/goals");
export const getAnalyticsPreferences = (): Promise<G.AnalyticsPreferenceRead> => apiFetch("/analytics/preferences");
export const getAnalyticsRisks = (): Promise<G.RiskSignalRead[]> => apiFetch("/analytics/risks");
export const getAnalyticsSnapshots = (): Promise<G.SnapshotRead[]> => apiFetch("/analytics/snapshots");
export const getAuthorityCollections = (): Promise<G.ResearchCollectionRead[]> => apiFetch("/knowledge/authority-collections");
export const getBackgroundJob = (jobId: string): Promise<G.JobDetail> => apiFetch(`/jobs/${jobId}`);
export const getBackgroundJobs = (status?: string, queue?: string): Promise<G.JobRead[]> => apiFetch(`/jobs${query({ status, queue })}`);
export const getBackgroundQueues = (): Promise<G.QueueRead[]> => apiFetch("/jobs/queues");
export const getBillingExpenses = (): Promise<G.ExpenseRead[]> => apiFetch("/billing/expenses");
export const getBillingInvoices = (): Promise<G.InvoiceRead[]> => apiFetch("/billing/invoices");
export const getBillingOverview = (): Promise<BillingOverview> => apiFetch("/billing/overview");
export const getBillingPayments = (): Promise<G.PaymentRead[]> => apiFetch("/billing/payments");
export const getBillingProfile = (): Promise<G.BillingProfileRead> => apiFetch("/billing/profile");
export const getCRMClientDetail = (clientId: string): Promise<CRMClientDetail> => apiFetch(`/crm/clients/${clientId}`);
export const getCRMClients = (): Promise<G.ClientRead[]> => apiFetch("/crm/clients");
export const getCRMConflicts = (): Promise<G.ConflictCheckRead[]> => apiFetch("/crm/conflicts");
export const getCRMLeads = (): Promise<G.LeadRead[]> => apiFetch("/crm/leads");
export const getCRMOverview = (): Promise<CRMOverview> => apiFetch("/crm/overview");
export const getCRMTasks = (): Promise<G.TaskRead[]> => apiFetch("/crm/tasks");
export const getClientHealthAnalytics = (): Promise<G.ClientHealthRead[]> => apiFetch("/analytics/clients");
export const getClientMoneyAccounts = (): Promise<G.ClientMoneyAccountRead[]> => apiFetch("/client-money/accounts");
export const getClientMoneyDashboard = (): Promise<ClientMoneyDashboard> => apiFetch("/client-money/dashboard");
export const getClientMoneyEntries = (accountId: string): Promise<G.ClientMoneyJournalEntryRead[]> => apiFetch(`/client-money/accounts/${accountId}/entries`);
export const getClientMoneyTransfers = (): Promise<G.TransferRequestRead[]> => apiFetch("/client-money/transfers");
export const getContract = (contractId: string): Promise<G.ContractRead> => apiFetch(`/contracts/${contractId}`);
export const getContractQuestionnaire = (contractType: string): Promise<G.ContractQuestionnaire> => apiFetch(`/contracts/questionnaire/${contractType}`);
export const getContractReview = (reviewId: string): Promise<G.ContractReviewRead> => apiFetch(`/contract-reviews/${reviewId}`);
export const getCourtChanges = (matterId?: string, unreviewedOnly?: boolean): Promise<G.CourtChangeRead[]> => apiFetch(`/operations/court-changes${query({ matter_id: matterId, unreviewed_only: unreviewedOnly === undefined ? undefined : String(unreviewedOnly) })}`);
export const getCourtSources = (): Promise<G.CourtSourceCapabilityRead[]> => apiFetch("/operations/court-sources");
export const getCourtTrackers = (matterId?: string): Promise<G.CourtTrackerRead[]> => apiFetch(`/operations/trackers${query({ matter_id: matterId })}`);
export const getDeadlines = (matterId?: string): Promise<G.DeadlineRead[]> => apiFetch(`/procedure/deadlines${query({ matter_id: matterId })}`);
export const getDeploymentDashboard = (): Promise<G.DeploymentDashboard> => apiFetch("/deployment/dashboard");
export const getDocument = (documentId: string): Promise<G.DocumentRead> => apiFetch(`/documents/${documentId}`);
export const getDocumentComments = (documentId: string): Promise<G.CommentRead[]> => apiFetch(`/collaboration/documents/${documentId}/comments`);
export const getDocumentPageWindow = (documentId: string, startPage: number, limit: number): Promise<DocumentPageWindow> => apiFetch(`/documents/${documentId}/page-window${query({ start_page: startPage, limit })}`);
export const getDocumentVersions = (documentId: string): Promise<G.DocumentVersionRead[]> => apiFetch(`/collaboration/documents/${documentId}/versions`);
export const getDocuments = (matterId: string): Promise<G.DocumentRead[]> => apiFetch(`/matters/${matterId}/documents`);
export const getDraft = (draftId: string): Promise<G.LegalDraftRead> => apiFetch(`/drafting/${draftId}`);
export const getDraftContext = (matterId: string): Promise<DraftContextPreview> => apiFetch(`/drafting/context/${matterId}`);
export const getEvidenceBundles = (matterId: string): Promise<G.BundleRead[]> => apiFetch(`/evidence/matters/${matterId}/bundles`);
export const getEvidenceDashboard = (matterId: string): Promise<EvidenceDashboard> => apiFetch(`/evidence/matters/${matterId}/dashboard`);
export const getEvidenceGaps = (matterId: string): Promise<G.GapRead[]> => apiFetch(`/evidence/matters/${matterId}/gaps`);
export const getEvidenceGraph = (matterId: string): Promise<G.EvidenceGraphRead> => apiFetch(`/evidence/matters/${matterId}/graph`);
export const getIssueStanding = (matterId: string): Promise<G.IssueStandingRead[]> => apiFetch(`/evidence/matters/${matterId}/standing`);
export const getEvidenceItems = (matterId: string): Promise<G.EvidenceItemRead[]> => apiFetch(`/evidence/matters/${matterId}/items`);
export const getEvidenceWitnesses = (matterId: string): Promise<G.WitnessRead[]> => apiFetch(`/evidence/matters/${matterId}/witnesses`);
export const getHearings = (matterId?: string): Promise<G.HearingRead[]> => apiFetch(`/procedure/hearings${query({ matter_id: matterId })}`);
export const getIntegrationCatalog = (): Promise<G.IntegrationCatalogItem[]> => apiFetch("/integrations/catalog");
export const getIntegrationsDashboard = (): Promise<G.IntegrationDashboard> => apiFetch("/integrations/dashboard");
export const getJobsDashboard = (): Promise<G.JobsDashboard> => apiFetch("/jobs/dashboard");
export const getJurisdictionPacks = (): Promise<G.JurisdictionPackRead[]> => apiFetch("/legal-data/packs");
export const getKnowledgeAssets = (): Promise<G.KnowledgeAssetRead[]> => apiFetch("/knowledge/assets");
export const getKnowledgeCollections = (): Promise<G.KnowledgeCollectionRead[]> => apiFetch("/knowledge/collections");
export const getKnowledgeDashboard = (): Promise<KnowledgeDashboard> => apiFetch("/knowledge/dashboard");
export const getLegacyMatters = (): Promise<Record<string, unknown>[]> => apiFetch("/security/legacy-matters");
export const getLegalDataAmendments = (): Promise<G.AmendmentRead[]> => apiFetch("/legal-data/amendments");
export const getLegalDataDashboard = (): Promise<G.LegalDataDashboard> => apiFetch("/legal-data/dashboard");
export const getLegalDataFeeds = (): Promise<G.LegalDataFeedRead[]> => apiFetch("/legal-data/feeds");
export const getLegalDataRuns = (): Promise<G.IngestionRunRead[]> => apiFetch("/legal-data/runs");
export const getLitigationIssues = (matterId: string): Promise<G.IssueRead[]> => apiFetch(`/evidence/matters/${matterId}/issues`);
export const getMatterHealthAnalytics = (): Promise<G.MatterHealthRead[]> => apiFetch("/analytics/matter-health");
export const getMatterPlaybooks = (): Promise<G.MatterPlaybookRead[]> => apiFetch("/knowledge/playbooks");
export const getMatterProcedures = (matterId: string): Promise<G.MatterProcedureRead[]> => apiFetch(`/procedure/matters/${matterId}`);
export const getMatterRemedies = (matterId: string): Promise<G.RemedyAnalysisRead[]> => apiFetch(`/remedies/matters/${matterId}`);
export const getMatterSecurityAccess = (matterId: string): Promise<G.AccessDecisionRead> => apiFetch(`/security/matters/${matterId}/access`);
export const getMatterSecurityGrants = (matterId: string): Promise<G.MatterGrantRead[]> => apiFetch(`/security/matters/${matterId}/grants`);
export const getMatterSecurityProfile = (matterId: string): Promise<G.MatterSecurityProfileRead> => apiFetch(`/security/matters/${matterId}/profile`);
export const getMatters = (): Promise<G.MatterRead[]> => apiFetch("/matters");
export const getOnboardingProgress = (): Promise<G.OnboardingProgressRead> => apiFetch("/experience/onboarding");
export const getOperationsAgenda = (days = 7): Promise<OperationsAgendaItem[]> => apiFetch(`/operations/agenda${query({ days })}`);
export const getOperationsDashboard = (): Promise<OperationsDashboard> => apiFetch("/operations/dashboard");
export const getOperationsSupervision = (): Promise<G.SupervisionSummary> => apiFetch("/operations/supervision");
export const getPortalApprovals = (): Promise<G.PortalClientApprovalRead[]> => apiFetch("/portal/approvals");
export const getPortalDashboard = (): Promise<PortalDashboard> => apiFetch("/portal/dashboard");
export const getProcedurePacks = (): Promise<G.ProcedurePackRead[]> => apiFetch("/procedure/packs");
export const getProcedureStats = (): Promise<ProcedureStats> => apiFetch("/procedure/stats");
export const getQADashboard = (): Promise<G.QADashboard> => apiFetch("/qa/dashboard");
export const getQARun = (runId: string): Promise<G.EvaluationRunDetail> => apiFetch(`/qa/runs/${runId}`);
export const getQASuite = (suiteId: string): Promise<G.EvaluationSuiteDetail> => apiFetch(`/qa/suites/${suiteId}`);
export const getRecentSearchItems = (limit = 8): Promise<G.RecentItemRead[]> => apiFetch(`/search/recent${query({ limit })}`);
export const getReleaseDashboard = (): Promise<G.ReleaseDashboard> => apiFetch("/release/dashboard");
export const getReleaseRun = (runId: string): Promise<G.ReleaseRunDetail> => apiFetch(`/release/runs/${runId}`);
export const getResearchSources = (): Promise<G.ResearchSourceRead[]> => apiFetch("/research/sources");
export const getSavedCase = (savedCaseId: string): Promise<G.SavedCaseDetailRead> => apiFetch(`/case-lookup/saved/${savedCaseId}`);
export const getSavedCases = (): Promise<G.SavedCaseSummaryRead[]> => apiFetch("/case-lookup/saved");
export const getSavedSearches = (): Promise<G.SavedSearchRead[]> => apiFetch("/search/saved");
export const getSearchCommands = (q?: string): Promise<G.CommandDefinition[]> => apiFetch(`/search/commands${query({ q })}`);
export const getSearchDuplicates = (limit = 8): Promise<G.SearchDuplicateItem[]> => apiFetch(`/search/index/duplicates${query({ limit })}`);
export const getSearchIndexHealth = (): Promise<SearchIndexHealth> => apiFetch("/search/index/health");
export const getSecurityAudit = (limit = 60): Promise<G.AuditEntryRead[]> => apiFetch(`/security/audit${query({ limit })}`);
export const getSecurityMembers = (): Promise<G.MembershipRead[]> => apiFetch("/security/members");
export const getSecurityOverview = (): Promise<G.SecurityOverviewRead> => apiFetch("/security/overview");
export const getSystemHealthDashboard = (): Promise<G.SystemHealthDashboard> => apiFetch("/system-health/dashboard");
export const getTeamAnalytics = (): Promise<G.TeamPerformanceRead[]> => apiFetch("/analytics/team");
export const getValidationCampaign = (campaignId: string): Promise<G.ValidationCampaignDetail> => apiFetch(`/validation/campaigns/${campaignId}`);
export const getValidationDashboard = (): Promise<G.ValidationDashboard> => apiFetch("/validation/dashboard");
export const getWitnessPrep = (witnessId: string): Promise<G.PrepQuestionRead[]> => apiFetch(`/evidence/witnesses/${witnessId}/prep`);
export const getWorkflowTasks = (assignedToMe = false): Promise<G.WorkflowTaskRead[]> => apiFetch(`/operations/tasks${query({ assigned_to_me: String(assignedToMe) })}`);
export const getWorkflowTemplates = (): Promise<G.WorkflowTemplateRead[]> => apiFetch("/operations/templates");
export const issueBillingInvoice = (invoiceId: string): Promise<G.InvoiceRead> => apiFetch(`/billing/invoices/${invoiceId}/issue`, jsonBody({}));
export const legalDraftDownloadUrl = (draftId: string): string => `${API_BASE}/drafting/${draftId}/download`;
export const markSavedSearchRun = (searchId: string): Promise<G.SavedSearchRead> => apiFetch(`/search/saved/${searchId}/run`, { method: "POST" });
export const patchCompliance = (complianceId: string, patch: Record<string, unknown>): Promise<G.ComplianceRead> => apiFetch(`/procedure/compliances/${complianceId}`, patchBody(patch));
export const patchDeadline = (deadlineId: string, patch: Record<string, unknown>): Promise<G.DeadlineRead> => apiFetch(`/procedure/deadlines/${deadlineId}`, patchBody(patch));
export const patchDraftFinding = (draftId: string, findingId: string, status: string): Promise<G.LegalDraftRead> => apiFetch(`/drafting/${draftId}/findings/${findingId}`, patchBody({ status }));
export const patchDraftSection = (draftId: string, sectionId: string, patch: Record<string, unknown>): Promise<G.LegalDraftRead> => apiFetch(`/drafting/${draftId}/sections/${sectionId}`, patchBody(patch));
export const portalActivate = (payload: Record<string, unknown>): Promise<G.PortalSessionRead> => apiFetch("/portal/activate", jsonBody(payload));
export const portalInvoiceSnapshot = (shareId: string): Promise<Record<string, unknown>> => apiFetch(`/portal/shares/${shareId}/invoice`);
export const portalLogin = (payload: Record<string, unknown>): Promise<G.PortalSessionRead> => apiFetch("/portal/login", jsonBody(payload));
export const portalSendMessage = (payload: Record<string, unknown>): Promise<G.PortalMessageRead> => apiFetch("/portal/messages", jsonBody(payload));
export const portalUpdateRequest = (requestId: string, status: string): Promise<G.PortalRequestRead> => apiFetch(`/portal/requests/${requestId}`, patchBody({ status }));
export const prepareAIReasoning = (payload: AIReasoningPayload): Promise<AIPrepareResponse> => apiFetch("/ai/prepare", jsonBody(payload));
export const queueBackupRun = (policyId: string): Promise<BackupRunRecord> => apiFetch(`/system-health/backups/policies/${policyId}/run`, { method: "POST" });
export const queueRestoreVerification = (runId: string): Promise<G.JobRead> => apiFetch(`/system-health/backups/runs/${runId}/verify`, { method: "POST" });
export const reanalyzeContractReview = (reviewId: string): Promise<G.ContractReviewRead> => apiFetch(`/contract-reviews/${reviewId}/reanalyze`, { method: "POST" });
export const rebuildAnalyticsRisks = (): Promise<G.RiskRebuildSummary> => apiFetch("/analytics/risks/rebuild", { method: "POST" });
export const rebuildEvidence = (matterId: string): Promise<Record<string, unknown>> => apiFetch(`/evidence/matters/${matterId}/rebuild`, { method: "POST" });
export const rebuildIntelligence = (matterId: string): Promise<G.RebuildResultRead> => apiFetch(`/matters/${matterId}/intelligence/rebuild`, { method: "POST" });
export const rebuildSearchIndex = (includeCorpus = false): Promise<G.SearchIndexJobRead> => apiFetch(`/search/index/rebuild${query({ include_corpus: String(includeCorpus) })}`, { method: "POST" });
export const recordRecentSearchItem = (payload: G.RecentItemCreate): Promise<G.RecentItemRead> => apiFetch("/search/recent", jsonBody(payload));
export const regenerateLegalDraft = (draftId: string): Promise<G.LegalDraftRead> => apiFetch(`/drafting/${draftId}/regenerate`, { method: "POST" });
export const renderLegalDraft = (draftId: string): Promise<G.DraftRenderResult> => apiFetch(`/drafting/${draftId}/render`, { method: "POST" });
export const resolveDocumentComment = (commentId: string, resolved: boolean): Promise<DocumentCommentRecord> => apiFetch(`/collaboration/comments/${commentId}/resolve${query({ resolved: String(resolved) })}`, { method: "POST" });
export const respondPortalApproval = (approvalId: string, decision: string): Promise<G.PortalClientApprovalRead> => apiFetch(`/portal/approvals/${approvalId}/respond`, jsonBody({ decision }));
export const retryBackgroundJob = (jobId: string): Promise<G.JobRead> => apiFetch(`/jobs/${jobId}/retry`, { method: "POST" });
export const reviewAIRun = (runId: string, payload: Record<string, unknown>): Promise<G.AIRunRead> => apiFetch(`/ai/runs/${runId}/review`, patchBody(payload));
export const reviewBillingInvoice = (invoiceId: string, note: string): Promise<G.InvoiceRead> => apiFetch(`/billing/invoices/${invoiceId}/review`, jsonBody({ tax_treatment_reviewed: true, note }));
export const reviewCRMConflict = (checkId: string, status: string, reviewNote: string): Promise<G.ConflictCheckRead> => apiFetch(`/crm/conflicts/${checkId}`, patchBody({ status, review_note: reviewNote }));
export const reviewContract = (contractId: string): Promise<G.ContractRead> => apiFetch(`/contracts/${contractId}/review`, { method: "POST" });
export const reviewCourtChange = (changeId: string): Promise<G.CourtChangeRead> => apiFetch(`/operations/court-changes/${changeId}/review`, { method: "POST" });
export const reviewLegalDataAmendment = (amendmentId: string, status: string): Promise<G.AmendmentRead> => apiFetch(`/legal-data/amendments/${amendmentId}`, patchBody({ status }));
export const reviewRestoreDrill = (drillId: string, note: string): Promise<G.RestoreDrillRead> => apiFetch(`/system-health/restore-drills/${drillId}/review`, jsonBody({ note }));
export const runAIReasoning = (payload: AIReasoningPayload): Promise<G.AIRunRead> => apiFetch("/ai/runs", jsonBody(payload));
export const runLegalDataIntegritySweep = (): Promise<Record<string, unknown>> => apiFetch("/legal-data/integrity/sweep", { method: "POST" });
export const runOperationsSweep = (): Promise<Record<string, unknown>> => apiFetch("/operations/sweep", { method: "POST" });
export const runQASuite = (suiteId: string, triggeredBy: string): Promise<G.EvaluationRunRead> => apiFetch(`/qa/suites/${suiteId}/runs`, jsonBody({ triggered_by: triggeredBy }));
export const runSystemHealthCheck = (): Promise<G.HealthRunDetail> => apiFetch("/system-health/checks/run", { method: "POST" });
export const saveCaseCandidate = (candidateId: string): Promise<G.SavedCaseSummaryRead> => apiFetch(`/case-lookup/candidates/${candidateId}/save`, { method: "POST" });
export const saveSearch = (payload: Record<string, unknown>): Promise<G.SavedSearchRead> => apiFetch("/search/saved", jsonBody(payload));
export const searchCases = (q: string): Promise<G.CaseLookupResponse> => apiFetch("/case-lookup/search", jsonBody({ query: q, include_saved: true }));
export const searchKnowledge = (q: string): Promise<G.KnowledgeSearchResponse> => apiFetch(`/knowledge/search${query({ q })}`);
export const searchResearch = (payload: Record<string, unknown>): Promise<G.CorpusSearchResponse> => apiFetch("/research/search", jsonBody(payload));
export const seedProcedurePacks = (): Promise<Record<string, unknown>> => apiFetch("/procedure/packs/seed", { method: "POST" });
export const seedQASuite = (): Promise<G.EvaluationSuiteRead> => apiFetch("/qa/seed", { method: "POST" });
export const seedResearchSources = (): Promise<G.SourceRead[]> => apiFetch("/research/sources/seed", { method: "POST" });
export const seedValidationScenarios = (): Promise<G.ValidationScenarioRead[]> => apiFetch("/validation/seed", { method: "POST" });
export const seedWorkflowTemplates = (): Promise<G.OperationsTemplateSeedResult> => apiFetch("/operations/templates/seed", { method: "POST" });
export const signoffValidationCampaign = (campaignId: string, decision: string, note: string): Promise<G.ValidationSignoffRead> => apiFetch(`/validation/campaigns/${campaignId}/signoffs`, jsonBody({ decision, note }));
export const snapshotDocumentVersion = (documentId: string, changeNote: string): Promise<DocumentVersionRecord> => apiFetch(`/collaboration/documents/${documentId}/versions/snapshot${query({ change_note: changeNote })}`, { method: "POST" });
export const submitKnowledgeAsset = (assetId: string): Promise<G.KnowledgeAssetRead> => apiFetch(`/knowledge/assets/${assetId}/submit`, { method: "POST" });
export const syncLegalDataFeed = (feedId: string): Promise<LegalDataRunRecord> => apiFetch(`/legal-data/feeds/${feedId}/sync`, { method: "POST" });
export const testIntegrationConnection = (connectionId: string, live: boolean): Promise<G.ConnectionTestResult> => apiFetch(`/integrations/${connectionId}/test${query({ live: String(live) })}`, { method: "POST" });
export const universalSearch = (q: string, options: { scopes?: string[]; limit?: number } = {}): Promise<UniversalSearchResponse> => apiFetch(`/search${query({ q, scopes: options.scopes?.join(","), limit: options.limit })}`);
export const updateAnalyticsPreferences = (patch: Record<string, unknown>): Promise<G.AnalyticsPreferenceRead> => apiFetch("/analytics/preferences", patchBody(patch));
export const updateAnalyticsRisk = (signalId: string, status: string): Promise<G.RiskSignalRead> => apiFetch(`/analytics/risks/${signalId}`, patchBody({ status }));
export const updateBackgroundQueue = (queueId: string, patch: Record<string, unknown>): Promise<G.QueueRead> => apiFetch(`/jobs/queues/${queueId}`, patchBody(patch));
export const updateBillingProfile = (payload: Record<string, unknown>): Promise<G.BillingProfileRead> => apiFetch("/billing/profile", { method: "PUT", body: JSON.stringify(payload) });
export const updateContractReviewClauseDecision = (reviewId: string, clauseId: string, decision: string): Promise<G.ContractReviewRead> => apiFetch(`/contract-reviews/${reviewId}/clauses/${clauseId}/decision`, patchBody({ decision }));
export const updateContractReviewFinding = (reviewId: string, findingId: string, status: string): Promise<G.ContractReviewRead> => apiFetch(`/contract-reviews/${reviewId}/findings/${findingId}`, patchBody({ status }));
export const updateContractRisk = (contractId: string, riskId: string, status: string): Promise<G.ContractRead> => apiFetch(`/contracts/${contractId}/risks/${riskId}`, patchBody({ status }));
export const updateEvidenceGap = (gapId: string, status: string): Promise<G.GapRead> => apiFetch(`/evidence/gaps/${gapId}`, patchBody({ status }));
export const updateEvidenceItem = (itemId: string, patch: Record<string, unknown>): Promise<G.EvidenceItemRead> => apiFetch(`/evidence/items/${itemId}`, patchBody(patch));
export const updateMatterSecurityProfile = (matterId: string, patch: Record<string, unknown>): Promise<G.MatterSecurityProfileRead> => apiFetch(`/security/matters/${matterId}/profile`, patchBody(patch));
export const updateOnboardingProgress = (patch: Record<string, unknown>): Promise<G.OnboardingProgressRead> => apiFetch("/experience/onboarding", patchBody(patch));
export const updatePilotReadiness = (campaignId: string, checkId: string, status: string, note: string): Promise<G.PilotReadinessRead> => apiFetch(`/validation/campaigns/${campaignId}/checks/${checkId}`, patchBody({ status, note }));
export const updateRecoveryObjectives = (patch: Record<string, unknown>): Promise<G.RecoveryObjectiveRead> => apiFetch("/system-health/recovery-objectives", patchBody(patch));
export const updateReviewItem = (item: ReviewItem, status: string): Promise<Record<string, unknown>> => apiFetch(item.item_type === "contradiction" ? `/contradictions/${item.target_id}` : `/facts/${item.target_id}`, patchBody({ status }));
export const updateSecurityPolicy = (patch: Record<string, unknown>): Promise<G.SecurityPolicyRead> => apiFetch("/security/policy", patchBody(patch));
export const updateSystemIncident = (incidentId: string, patch: Record<string, unknown>): Promise<G.IncidentRead> => apiFetch(`/system-health/incidents/${incidentId}`, patchBody(patch));
export const updateWorkflowTask = (taskId: string, patch: Record<string, unknown>): Promise<G.WorkflowTaskRead> => apiFetch(`/operations/tasks/${taskId}`, patchBody(patch));
export const uploadContractReview = (form: FormData): Promise<G.ContractReviewRead> => apiFetch("/contract-reviews", { method: "POST", body: form });
export const uploadDocument = (matterId: string, file: File): Promise<LegalDocument> => { const form = new FormData(); form.append("file", file); return apiFetch(`/matters/${matterId}/documents`, { method: "POST", body: form }); };
export const uploadDocumentVersion = (documentId: string, file: File, changeNote?: string): Promise<DocumentVersionRecord> => { const form = new FormData(); form.append("file", file); if (changeNote) form.append("change_note", changeNote); return apiFetch(`/collaboration/documents/${documentId}/versions`, { method: "POST", body: form }); };
export const upsertMatterSecurityGrant = (matterId: string, payload: Record<string, unknown>): Promise<G.MatterGrantRead> => apiFetch(`/security/matters/${matterId}/grants`, jsonBody(payload));
export const verifySecurityAudit = (): Promise<G.AuditVerifyRead> => apiFetch("/security/audit/verify");
