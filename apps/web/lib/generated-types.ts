/**
 * GENERATED FILE — do not edit by hand.
 *
 * Produced by apps/api/scripts/generate_web_types.py from the API's OpenAPI
 * schema. Regenerate after changing any Pydantic model the web app consumes:
 *
 *     cd apps/api && python scripts/generate_web_types.py ../web/lib/generated-types.ts
 */
/* eslint-disable @typescript-eslint/no-explicit-any */

export interface AIBudget {
  max_input_tokens: number;
  max_output_tokens: number;
  estimated_input_tokens: number;
  within_budget: boolean;
  retrieval?: Record<string, unknown>;
}

export interface AICitationRead {
  id: string;
  raw_citation: string;
  normalized_citation: string | null;
  status: AICitationStatus;
  matched_judgment_id: string | null;
  cited_source_keys_json: unknown[];
  metadata_json: Record<string, unknown>;
}

export type AICitationStatus = "resolved" | "ambiguous" | "unresolved" | "unparsed";

export interface AIClaimRead {
  id: string;
  ordinal: number;
  claim_text: string;
  substantive: boolean;
  cited_source_keys_json: unknown[];
  support_score: number;
  status: AIClaimStatus;
  explanation: string | null;
}

export type AIClaimStatus = "supported" | "weak_support" | "uncited" | "invalid_source" | "non_substantive";

export interface AIPrepareResponse {
  routing: AIRouteDecisionRead;
  sources: AISourceRead[];
  prompt_preview: string;
  budget: AIBudget;
}

export interface AIProviderStatusRead {
  ai_enabled: boolean;
  local_enabled: boolean;
  local_model: string | null;
  remote_enabled: boolean;
  remote_model: string | null;
  remote_calls_require_explicit_opt_in: boolean;
  secrets_persisted: boolean;
}

export interface AIReasoningRequest {
  matter_id?: string | null;
  task_type: AITaskType;
  query: string;
  output_language: string;
  prefer_local: boolean;
  allow_remote: boolean;
  allow_local_for_high_complexity: boolean;
  include_corpus: boolean;
  max_sources: number;
  max_input_tokens: number;
  max_output_tokens: number;
}

export interface AIReviewRequest {
  status: AIReviewStatus;
  reviewed_by: string;
  notes?: string | null;
}

export type AIReviewStatus = "pending" | "reviewed" | "rejected";

export interface AIRouteDecisionRead {
  tier: AIRouteTier;
  ai_required: boolean;
  provider_key?: string | null;
  model_name?: string | null;
  reason: string;
  quality_warning?: string | null;
  estimated_input_tokens: number;
  source_count: number;
}

export type AIRouteTier = "deterministic" | "local" | "strong" | "blocked";

export interface AIRunRead {
  id: string;
  matter_id: string | null;
  task_type: AITaskType;
  query: string;
  output_language: string;
  route_tier: AIRouteTier;
  status: AIRunStatus;
  provider_key: string | null;
  model_name: string | null;
  max_input_tokens: number;
  max_output_tokens: number;
  estimated_input_tokens: number;
  actual_input_tokens: number | null;
  actual_output_tokens: number | null;
  routing_json: Record<string, unknown>;
  retrieval_json: Record<string, unknown>;
  response_text: string | null;
  verification_status: AIVerificationStatus;
  verification_summary_json: Record<string, unknown>;
  review_status: AIReviewStatus;
  review_notes: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  error_message: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  sources?: AISourceRead[];
  claims?: AIClaimRead[];
  citations?: AICitationRead[];
  usage_events?: AIUsageRead[];
}

export type AIRunStatus = "prepared" | "running" | "completed" | "verification_failed" | "blocked" | "failed";

export interface AISourceRead {
  id?: string | null;
  ordinal: number;
  source_key: string;
  source_type: AISourceType;
  source_record_id: string;
  title: string;
  locator: string | null;
  text: string;
  source_url: string | null;
  official: boolean;
  verified: boolean;
  relevance_score: number;
  metadata_json: Record<string, unknown>;
}

export type AISourceType = "matter_fact" | "timeline_event" | "statement" | "contradiction" | "document_page" | "statute_section" | "judgment_paragraph";

export type AITaskType = "extract_entities" | "search_cases" | "lookup_statute" | "calculate_deadline" | "build_chronology" | "compare_documents" | "verify_citation" | "matter_summary" | "document_summary" | "client_update" | "research_synthesis" | "issue_spotting" | "argument_analysis" | "counterargument" | "custom_drafting" | "custom_clause" | "hearing_questions";

export interface AIUsageRead {
  id: string;
  provider_key: string;
  model_name: string;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  latency_ms: number | null;
  provider_reported_cost_microunits: number | null;
  currency: string | null;
  metadata_json: Record<string, unknown>;
}

export type AIVerificationStatus = "not_run" | "passed" | "warnings" | "failed";

export interface AccessDecisionRead {
  allowed: boolean;
  reason: string;
  matter_access_level?: MatterAccessLevel | null;
  remote_ai_allowed?: boolean | null;
  export_allowed?: boolean | null;
  classification?: ConfidentialityLevel | null;
}

export type AccessEffect = "allow" | "deny";

export interface ActorRead {
  user_id: string;
  membership_id: string;
  organization_id: string;
  email: string;
  display_name: string;
  role: OrganizationRole;
  mfa_enrolled: boolean;
}

export type AffidavitFieldKind = "text" | "multiline" | "date" | "integer";

export interface AffidavitGenerationRequest {
  template_id: string;
  generation_date: string;
  fields?: Record<string, string>;
  statements: AffidavitStatement[];
  annexures?: AnnexureReference[];
}

export interface AffidavitGenerationResponse {
  template_id: string;
  template_version: string;
  title: string;
  affidavit_type: string;
  jurisdiction: string;
  generation_date: string;
  sections: RenderedAffidavitSection[];
  statements: RenderedAffidavitStatement[];
  annexures: AnnexureReference[];
  rendered_text: string;
  fields_used: Record<string, string>;
  warnings: string[];
  source_note: string;
  disclaimer: string;
}

export interface AffidavitStatement {
  text: string;
  source_reference?: string | null;
}

export interface AffidavitTemplateField {
  key: string;
  label: string;
  kind: AffidavitFieldKind;
  required: boolean;
  max_length: number;
  help_text?: string | null;
}

export interface AffidavitTemplateSummary {
  id: string;
  version: string;
  title: string;
  affidavit_type: string;
  jurisdiction: string;
  effective_from: string;
  effective_to: string | null;
  fields: AffidavitTemplateField[];
  source_note: string;
}

export interface AgendaItem {
  kind: string;
  id: string;
  matter_id: string | null;
  matter_title: string | null;
  when: string | null;
  title: string;
  status: string;
  priority?: string | null;
  requires_action: boolean;
  detail?: string | null;
}

export interface AlertStatusRequest {
  status: LegalDataAlertStatus;
}

export interface AmendmentRead {
  id: string;
  statute_id: string;
  section_id: string | null;
  ingestion_item_id: string | null;
  event_kind: string;
  section_number: string | null;
  previous_sha256: string | null;
  new_sha256: string | null;
  effective_date: string | null;
  before_json: Record<string, unknown>;
  after_json: Record<string, unknown>;
  review_status: string;
  detected_at: string;
  reviewed_at: string | null;
  reviewed_by_membership_id: string | null;
  review_note: string | null;
}

export interface AmendmentReviewRequest {
  status: AmendmentReviewStatus;
  note?: string | null;
}

export type AmendmentReviewStatus = "pending" | "reviewed" | "dismissed";

export interface AnalyticsDashboard {
  active_matters: number;
  matter_health_avg: number;
  at_risk_matters: number;
  overdue_tasks: number;
  upcoming_hearings_7d: number;
  deadlines_due_7d: number;
  quality: QualitySummary;
  financials: FinancialSummary | null;
  formula_note: string;
}

export type AnalyticsGoalStatus = "active" | "completed" | "archived";

export interface AnalyticsPreferenceRead {
  id: string;
  organization_id: string;
  rolling_window_days: number;
  currency: string;
  health_weights_json: Record<string, number>;
  thresholds_json: Record<string, number>;
  enable_risk_detection: boolean;
  show_financials_to_partners: boolean;
  metadata_json: Record<string, unknown>;
}

export interface AnalyticsPreferenceUpdate {
  rolling_window_days?: number | null;
  currency?: string | null;
  health_weights_json?: Record<string, number> | null;
  thresholds_json?: Record<string, number> | null;
  enable_risk_detection?: boolean | null;
  show_financials_to_partners?: boolean | null;
  metadata_json?: Record<string, unknown> | null;
}

export type AnalyticsRiskSeverity = "info" | "low" | "medium" | "high" | "critical";

export type AnalyticsRiskStatus = "open" | "acknowledged" | "resolved" | "dismissed";

export type AnalyticsScope = "organization" | "matter" | "member" | "client";

export interface AnnexureReference {
  label: string;
  title: string;
  document_date?: string | null;
  description?: string | null;
}

export interface AnnotationCreate {
  kind: KnowledgeAnnotationKind;
  body: string;
  anchor_json?: Record<string, unknown>;
}

export interface AnnotationRead {
  id: string;
  asset_id: string;
  membership_id: string | null;
  kind: KnowledgeAnnotationKind;
  body: string;
  anchor_json: Record<string, unknown>;
  resolved: boolean;
  created_at: string;
}

export interface ApprovalCreate {
  document_version_id?: string | null;
  review_request_id?: string | null;
  decision: ApprovalDecision;
  comment?: string | null;
}

export type ApprovalDecision = "approved" | "changes_requested" | "rejected";

export interface ApprovalRead {
  id: string;
  document_id: string;
  document_version_id: string | null;
  review_request_id: string | null;
  matter_id: string;
  reviewer_user_id: string;
  decision: ApprovalDecision;
  comment: string | null;
  created_at: string;
}

export interface ArtifactRead {
  id: string;
  job_id: string;
  kind: string;
  storage_key: string | null;
  filename: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  sha256: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AttachProcedureRequest {
  pack_id: string;
  started_on?: string | null;
  notes?: string | null;
}

export interface AttemptRead {
  id: string;
  job_id: string;
  worker_id: string | null;
  attempt_number: number;
  status: string;
  leased_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_type: string | null;
  error_message: string | null;
}

export interface AuditEntryRead {
  id: string;
  organization_id: string;
  sequence: number;
  occurred_at: string;
  actor_user_id: string | null;
  actor_membership_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  outcome: AuditOutcome;
  reason: string | null;
  request_id: string | null;
  metadata_json: Record<string, unknown>;
  previous_hash: string;
  event_hash: string;
  signature_mode: string;
}

export type AuditOutcome = "success" | "failure" | "allowed" | "denied";

export interface AuditVerifyRead {
  valid: boolean;
  checked_entries: number;
  first_invalid_sequence?: number | null;
  reason?: string | null;
  signed: boolean;
}

export interface AuthorityReference {
  source_type: DraftSourceType;
  source_id: string;
}

export interface BackupArtifactRead {
  id: string;
  kind: string;
  filename: string;
  size_bytes: number;
  sha256: string;
  encrypted: boolean;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface BackupPolicyCreate {
  name: string;
  enabled: boolean;
  include_database: boolean;
  include_documents: boolean;
  schedule_rrule?: string | null;
  retention_days: number;
  max_backups: number;
  destination_kind: string;
  destination_path?: string | null;
  encryption_mode: string;
  rpo_minutes: number;
  rto_minutes: number;
}

export interface BackupPolicyRead {
  id: string;
  organization_id: string;
  name: string;
  enabled: boolean;
  include_database: boolean;
  include_documents: boolean;
  schedule_rrule: string | null;
  retention_days: number;
  max_backups: number;
  destination_kind: string;
  destination_path: string | null;
  encryption_mode: string;
  rpo_minutes: number;
  rto_minutes: number;
  last_run_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface BackupPolicyUpdate {
  enabled?: boolean | null;
  include_database?: boolean | null;
  include_documents?: boolean | null;
  schedule_rrule?: string | null;
  retention_days?: number | null;
  max_backups?: number | null;
  destination_kind?: string | null;
  destination_path?: string | null;
  encryption_mode?: string | null;
  rpo_minutes?: number | null;
  rto_minutes?: number | null;
}

export interface BackupRunDetail {
  run: BackupRunRead;
  artifacts: BackupArtifactRead[];
}

export interface BackupRunRead {
  id: string;
  organization_id: string;
  policy_id: string | null;
  trigger: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  total_bytes: number;
  manifest_sha256: string | null;
  database_status: string | null;
  documents_status: string | null;
  error: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface BatesAssignment {
  page_number: number;
  bates_number: string;
  collision_detected: boolean;
}

export interface BatesPreviewResponse {
  original_filename: string | null;
  page_count: number;
  stamped_page_count: number;
  skipped_page_count: number;
  first_bates_number: string | null;
  last_bates_number: string | null;
  assignments: BatesAssignment[];
  collision_pages: number[];
  warnings: string[];
  disclaimer: string;
}

export interface BillingOverview {
  draft_invoices: number;
  issued_invoices: number;
  overdue_invoices: number;
  outstanding_amount: string;
  unbilled_minutes: number;
  approved_expenses: string;
}

export interface BillingProfileRead {
  id: string;
  organization_id: string;
  legal_name: string | null;
  billing_address: string | null;
  city: string | null;
  state: string | null;
  state_code: string | null;
  country: string;
  gstin: string | null;
  pan_last4: string | null;
  email: string | null;
  phone: string | null;
  default_currency: string;
  invoice_prefix: string;
  next_invoice_sequence: number;
  default_payment_terms_days: number;
  bank_details_json: Record<string, unknown>;
  tax_configuration_json: Record<string, unknown>;
}

export interface BillingProfileUpdate {
  legal_name?: string | null;
  billing_address?: string | null;
  city?: string | null;
  state?: string | null;
  state_code?: string | null;
  country: string;
  gstin?: string | null;
  pan_last4?: string | null;
  email?: string | null;
  phone?: string | null;
  default_currency: string;
  invoice_prefix: string;
  default_payment_terms_days: number;
  bank_details?: Record<string, unknown>;
  tax_configuration?: Record<string, unknown>;
}

export type BlockType = "heading" | "paragraph" | "table";

export interface Body_analyze_api_v1_tools_legal_ocr_analyze_post {
  file: string;
  options_json: string;
}

export interface Body_create_review_api_v1_contract_reviews_post {
  file: string;
  contract_type: ContractType;
  title: string;
  counterparty_name?: string | null;
  matter_id?: string | null;
  internal_contract_id?: string | null;
  playbook_id?: string | null;
}

export interface Body_parse_document_api_v1_tools_legal_documents_parse_post {
  file: string;
  options_json: string;
}

export interface Body_preview_api_v1_tools_bates_numbering_preview_post {
  file: string;
  options_json: string;
}

export interface Body_process_api_v1_tools_legal_ocr_process_post {
  file: string;
  options_json: string;
}

export interface Body_stamp_api_v1_tools_bates_numbering_stamp_post {
  file: string;
  options_json: string;
}

export interface BootstrapAdmin {
  id: string;
  email: string;
  display_name: string;
  membership_id: string;
  role: string;
}

export interface BootstrapRequest {
  organization_name: string;
  organization_slug: string;
  admin_email: string;
  admin_name: string;
  password: string;
  bootstrap_secret?: string | null;
}

export interface BootstrapResponse {
  organization: OrganizationRead;
  admin: BootstrapAdmin;
  message: string;
}

export interface BundleCreate {
  title: string;
  bundle_type: string;
  evidence_item_ids?: string[];
  issue_ids?: string[];
  description?: string | null;
}

export interface BundleRead {
  id: string;
  matter_id: string;
  title: string;
  bundle_type: string;
  status: BundleStatus;
  created_by_user_id: string | null;
  description: string | null;
  sha256: string | null;
  storage_key: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export type BundleStatus = "draft" | "final";

export interface CRMOverview {
  leads_open: number;
  clients_active: number;
  conflict_reviews: number;
  onboarding_open: number;
  tasks_due: number;
  unbilled_minutes: number;
}

export type CRMTaskPriority = "low" | "medium" | "high" | "urgent";

export type CRMTaskStatus = "todo" | "in_progress" | "done" | "cancelled";

export interface CalendarEventRequest {
  summary: string;
  start: string;
  end: string;
  timezone: string;
  description?: string | null;
  location?: string | null;
  attendees?: string[];
  send_updates: string;
  internal_resource_type?: string | null;
  internal_resource_id?: string | null;
}

export interface CaseActData {
  act_name: string;
  sections?: string[];
  source_text?: string | null;
}

export interface CaseAdvocateData {
  name: string;
  side: CaseSide;
  enrollment_or_reference?: string | null;
}

export interface CaseCandidateRead {
  id: string;
  saved_case_id: string | null;
  source_kind: CaseSourceKind;
  case_record: CaseRecordData;
  rank_score: number;
  exact_match: boolean;
  requires_user_verification: boolean;
}

export interface CaseHearingData {
  hearing_date: string;
  purpose_or_stage?: string | null;
  judge_or_bench?: string | null;
  result_or_note?: string | null;
  source_reference?: string | null;
  metadata_json?: Record<string, unknown>;
}

export interface CaseJudgmentData {
  decision_date?: string | null;
  title?: string | null;
  citation?: string | null;
  document_url?: string | null;
  source_url?: string | null;
  checksum_sha256?: string | null;
  metadata_json?: Record<string, unknown>;
}

export interface CaseLookupPreferenceRead {
  preferred_state?: string | null;
  preferred_district?: string | null;
  preferred_high_court?: string | null;
  preferred_courts_json?: string[];
  default_refresh_minutes: number;
  id: string;
  organization_id: string;
  membership_id: string;
  recent_courts_json?: string[];
}

export interface CaseLookupPreferenceUpdate {
  preferred_state?: string | null;
  preferred_district?: string | null;
  preferred_high_court?: string | null;
  preferred_courts_json?: string[];
  default_refresh_minutes: number;
}

export interface CaseLookupRequest {
  query: string;
  state?: string | null;
  district?: string | null;
  court?: string | null;
  include_saved: boolean;
}

export interface CaseLookupResponse {
  run_id: string;
  status: CaseLookupStatus;
  detected_kind: string;
  parsed: Record<string, unknown>;
  message: string | null;
  candidates: CaseCandidateRead[];
}

export type CaseLookupStatus = "pending" | "matched" | "ambiguous" | "not_found" | "user_verification_required" | "failed";

export interface CaseOrderData {
  order_date?: string | null;
  title?: string | null;
  order_type?: string | null;
  document_url?: string | null;
  source_url?: string | null;
  checksum_sha256?: string | null;
  metadata_json?: Record<string, unknown>;
}

export interface CasePartyData {
  name: string;
  side: CaseSide;
  sequence: number;
  metadata_json?: Record<string, unknown>;
}

export interface CaseRecordData {
  cnr?: string | null;
  case_type?: string | null;
  case_number: string;
  year?: number | null;
  case_title?: string | null;
  court_name: string;
  court_code?: string | null;
  court_number?: string | null;
  court_level?: string | null;
  district?: string | null;
  state?: string | null;
  filing_date?: string | null;
  registration_date?: string | null;
  judge?: string | null;
  bench?: string | null;
  status?: string | null;
  case_stage?: string | null;
  previous_hearing_date?: string | null;
  next_hearing_date?: string | null;
  parties?: CasePartyData[];
  advocates?: CaseAdvocateData[];
  acts?: CaseActData[];
  hearing_history?: CaseHearingData[];
  orders?: CaseOrderData[];
  judgments?: CaseJudgmentData[];
  source_kind: CaseSourceKind;
  source_name: string;
  source_url?: string | null;
  source_reference?: string | null;
  fetched_at: string;
  source_updated_at?: string | null;
}

export type CaseSide = "petitioner" | "respondent";

export type CaseSourceKind = "saved" | "district_court" | "high_court" | "supreme_court" | "official_import" | "user_assisted";

export interface CaseTimelineRequest {
  case_reference?: string | null;
  title: string;
  events: TimelineEvent[];
  include_day_gaps: boolean;
}

export interface CaseTimelineResponse {
  case_reference: string | null;
  title: string;
  events: RenderedTimelineEvent[];
  summary: TimelineSummary;
  markdown: string;
  csv: string;
  warnings: string[];
  disclaimer: string;
}

export interface CaseWorkspaceResult {
  matter_id: string;
  title: string;
}

export type ChangeSeverity = "info" | "medium" | "high";

export interface ChecklistItemInput {
  key: string;
  status: ItemStatus;
  file_reference?: string | null;
  document_date?: string | null;
  notes?: string | null;
}

export type ChecklistItemKind = "document" | "task" | "information";

export interface ChecklistSummary {
  total_items: number;
  applicable_items: number;
  required_items: number;
  required_satisfied: number;
  required_outstanding: number;
  recommended_items: number;
  completed_applicable_items: number;
  completion_percent: number;
  required_completion_percent: number;
  category_counts: Record<string, number>;
  outstanding_required_keys: string[];
}

export interface ChecklistTemplateSummary {
  id: string;
  version: string;
  title: string;
  matter_type: string;
  jurisdiction: string;
  effective_from: string;
  effective_to: string | null;
  context_fields: ContextFieldDefinition[];
  item_count: number;
  source_note: string;
}

export interface CitationExtractRequest {
  text: string;
  kinds?: CitationKind[] | null;
  deduplicate: boolean;
}

export interface CitationExtractResponse {
  matches: CitationMatch[];
  match_count: number;
  unique_count: number;
  kinds_found: Record<string, number>;
  warnings: string[];
  disclaimer: string;
}

export interface CitationFormatRequest {
  kind: CitationKind;
  year: number;
  volume?: number | null;
  page_or_number: number;
  court_code?: string | null;
  division?: string | null;
  case_name?: string | null;
}

export interface CitationFormatResponse {
  kind: CitationKind;
  citation: string;
  citation_with_case_name: string;
  normalized_fields: Record<string, string | number | null>;
  warnings: string[];
  disclaimer: string;
}

export interface CitationGraphEdgeRead {
  citation_id: string;
  citing_judgment_id: string;
  citing_case_title: string;
  citing_court_name: string;
  citing_decision_date: string | null;
  paragraph_id: string | null;
  raw_citation: string;
  normalized_citation: string;
  source_url: string | null;
}

export type CitationKind = "scc" | "air" | "scc_online" | "india_neutral" | "uk_neutral";

export interface CitationMatch {
  kind: CitationKind;
  raw: string;
  normalized: string;
  start: number;
  end: number;
  line: number;
  column: number;
  fields: Record<string, string | number | null>;
}

export interface CitationMatchRead {
  judgment_id: string;
  case_title: string;
  court_name: string;
  decision_date: string | null;
  neutral_citation: string | null;
  reported_citations: string[];
  source_url: string | null;
}

export interface CitationRead {
  id: string;
  citing_judgment_id: string;
  paragraph_id: string | null;
  cited_judgment_id: string | null;
  raw_citation: string;
  normalized_citation: string;
  status: string;
  confidence: number;
  metadata_json: Record<string, unknown>;
}

export interface CitationVerifyRequest {
  citation: string;
}

export interface CitationVerifyResponse {
  raw: string;
  normalized: string | null;
  parsed_reporter: string | null;
  status: string;
  matches: CitationMatchRead[];
}

export interface ClaimInterestCalculationRequest {
  principal: number | string;
  annual_rate_percent: number | string;
  start_date: string;
  end_date: string;
  method: InterestMethod;
  day_count_convention: DayCountConvention;
  compounding_frequency: CompoundingFrequency;
  principal_adjustments?: PrincipalAdjustment[];
  currency: string;
}

export interface ClaimInterestCalculationResponse {
  currency: string;
  principal: string;
  annual_rate_percent: string;
  start_date: string;
  end_date: string;
  method: InterestMethod;
  day_count_convention: DayCountConvention;
  compounding_frequency: CompoundingFrequency | null;
  total_days: number;
  total_adjustments: string;
  total_interest: string;
  final_principal: string;
  total_amount: string;
  breakdown: InterestBreakdownLine[];
  disclaimer: string;
}

export interface ClauseChange {
  change_type: ContractChangeType;
  original_index?: number | null;
  revised_index?: number | null;
  original_clause_id?: string | null;
  revised_clause_id?: string | null;
  original_title?: string | null;
  revised_title?: string | null;
  original_text?: string | null;
  revised_text?: string | null;
  similarity: number;
  token_diff?: TokenDiff[];
  redline: string;
}

export interface ClauseDecisionUpdate {
  decision: string;
}

export type ClauseDeviationStatus = "matched" | "modified" | "unknown";

export interface ClauseExtractRequest {
  text: string;
  options?: ClauseExtractionOptions;
}

export interface ClauseExtractResponse {
  matches: ExtractedClause[];
  summary: ClauseExtractSummary;
  warnings: string[];
  disclaimer: string;
}

export interface ClauseExtractSummary {
  sections_detected: number;
  clauses_returned: number;
  clause_type_counts: Record<string, number>;
  heading_based: number;
  body_based: number;
  heading_and_body: number;
}

export interface ClauseExtractionOptions {
  clause_types?: ClauseType[] | null;
  minimum_confidence: number;
  use_body_fallback: boolean;
  include_heading_in_text: boolean;
  max_results: number;
  deduplicate: boolean;
}

export interface ClauseLibraryRead {
  id: string;
  code: string;
  clause_type: string;
  variant_key: string;
  title_en: string;
  title_hi: string | null;
  contract_types_json: string[];
  variables_json: string[];
  version: number;
  active: boolean;
}

export interface ClauseRead {
  id: string;
  clause_template_id: string | null;
  clause_code: string;
  clause_type: string;
  variant_key: string;
  title_en: string;
  title_hi: string | null;
  body_en: string;
  body_hi: string | null;
  position: number;
  source: ClauseSource;
  is_modified: boolean;
  metadata_json: Record<string, unknown>;
}

export interface ClauseSignal {
  kind: string;
  value: string;
}

export type ClauseSource = "builtin" | "custom";

export type ClauseType = "confidentiality" | "termination" | "indemnity" | "limitation_of_liability" | "governing_law" | "dispute_resolution" | "payment" | "term_renewal" | "intellectual_property" | "data_protection" | "force_majeure" | "non_compete" | "assignment" | "notices" | "warranties" | "representations" | "insurance" | "audit" | "compliance";

export interface ClauseTypesResponse {
  clause_types: SupportedClauseType[];
  disclaimer: string;
}

export interface ClauseUpdate {
  title_en?: string | null;
  title_hi?: string | null;
  body_en?: string | null;
  body_hi?: string | null;
  position?: number | null;
}

export interface ClientApprovalRead {
  id: string;
  portal_access_id: string;
  client_id: string;
  matter_id: string;
  document_id: string;
  document_version_id: string;
  title: string;
  message: string | null;
  status: ClientDocumentApprovalStatus;
  responded_at: string | null;
  response_note: string | null;
  created_at: string;
}

export interface ClientApprovalRequestCreate {
  portal_access_id: string;
  document_version_id: string;
  title: string;
  message?: string | null;
}

export interface ClientCommunicationRead {
  id: string;
  type: string;
  occurred_at: string;
  direction: string;
  subject: string | null;
  summary: string;
  matter_id: string | null;
}

export interface ClientCreate {
  display_name: string;
  legal_name?: string | null;
  client_type: ClientType;
  email?: string | null;
  phone?: string | null;
  preferred_language: string;
  billing_address?: string | null;
  city?: string | null;
  state?: string | null;
  country: string;
  tax_id_last4?: string | null;
  source_lead_id?: string | null;
}

export interface ClientDetail {
  client: ClientRead;
  onboarding: OnboardingRead;
  contacts: ContactRead[];
  kyc: KYCRecordRead[];
  engagements: EngagementRead[];
  matters: ClientMatterSummary[];
  notes: ClientNoteRead[];
  communications: ClientCommunicationRead[];
  portal_access: PortalAccessRead[];
}

export type ClientDocumentApprovalStatus = "pending" | "approved" | "changes_requested" | "declined" | "revoked";

export interface ClientGrantCreate {
  membership_id: string;
  effect: AccessEffect;
  access_level: MatterAccessLevel;
  reason?: string | null;
}

export interface ClientGrantRead {
  id: string;
  client_id: string;
  membership_id: string;
  effect: AccessEffect;
  access_level: MatterAccessLevel;
  reason: string | null;
  expires_at: string | null;
}

export interface ClientHealthRead {
  client_id: string;
  client_name: string;
  outstanding_amount: number;
  overdue_amount: number;
  open_portal_requests: number;
  active_matters: number;
  last_communication_at: string | null;
  health_score: number;
  reasons: string[];
}

export interface ClientMatterIntakeRequest {
  template_id: string;
  intake_date: string;
  values?: Record<string, unknown>;
  conflict_parties?: ConflictPartyInput[];
  consents?: ConsentInput[];
}

export interface ClientMatterIntakeResponse {
  template_id: string;
  template_version: string;
  title: string;
  matter_type: string;
  client_type: string;
  jurisdiction: string;
  intake_date: string;
  fields: EvaluatedIntakeField[];
  normalized_values: Record<string, unknown>;
  conflict_parties: NormalizedConflictParty[];
  conflict_search_terms: string[];
  consents: EvaluatedConsent[];
  summary: IntakeSummary;
  warnings: string[];
  markdown: string;
  audit_hash_sha256: string;
  source_note: string;
  disclaimer: string;
}

export interface ClientMatterSummary {
  id: string;
  title: string;
  status: string;
  reference_number: string | null;
}

export interface ClientMoneyAccountCreate {
  name: string;
  currency: string;
  bank_name?: string | null;
  bank_account_last4?: string | null;
  bank_reference?: string | null;
  require_separate_approver: boolean;
  notes?: string | null;
}

export interface ClientMoneyAccountRead {
  id: string;
  name: string;
  currency: string;
  status: ClientMoneyAccountStatus;
  bank_name: string | null;
  bank_account_last4: string | null;
  bank_reference: string | null;
  require_separate_approver: boolean;
  notes: string | null;
  created_at: string;
}

export type ClientMoneyAccountStatus = "active" | "frozen" | "closed";

export interface ClientMoneyDashboard {
  total_bank_balance: string;
  pending_transfer_total: string;
  unreconciled_difference: string;
  account_count: number;
  pending_transfer_count: number;
}

export interface ClientMoneyDepositCreate {
  account_id: string;
  client_id: string;
  matter_id?: string | null;
  amount: number | string;
  currency: string;
  entry_date: string;
  reference?: string | null;
  description: string;
}

export interface ClientMoneyJournalEntryRead {
  id: string;
  account_id: string;
  client_id: string;
  matter_id: string | null;
  entry_type: JournalEntryType;
  status: JournalEntryStatus;
  entry_date: string;
  amount: string;
  currency: string;
  reference: string | null;
  description: string;
  invoice_id: string | null;
  reverses_entry_id: string | null;
  content_hash: string;
  created_at: string;
}

export interface ClientNoteRead {
  id: string;
  title: string | null;
  body: string;
  matter_id: string | null;
  is_private: boolean;
  created_at: string;
}

export interface ClientRead {
  id: string;
  organization_id: string;
  client_number: string;
  client_type: ClientType;
  status: ClientStatus;
  display_name: string;
  legal_name: string | null;
  email: string | null;
  phone: string | null;
  preferred_language: string;
  billing_address: string | null;
  city: string | null;
  state: string | null;
  country: string;
  source_lead_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClientSecurityRead {
  id: string;
  client_id: string;
  classification: ConfidentialityLevel;
  access_mode: MatterAccessMode;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClientSecurityUpdate {
  classification: ConfidentialityLevel;
  access_mode: MatterAccessMode;
  notes?: string | null;
}

export interface ClientStatement {
  client_id: string;
  currency: string;
  opening_balance: string;
  closing_balance: string;
  rows: LedgerRow[];
}

export type ClientStatus = "prospect" | "active" | "inactive" | "closed";

export type ClientType = "individual" | "organization";

export interface ClientUpdate {
  status?: ClientStatus | null;
  display_name?: string | null;
  legal_name?: string | null;
  email?: string | null;
  phone?: string | null;
  preferred_language?: string | null;
  billing_address?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
}

export interface CommandDefinition {
  id: string;
  title: string;
  description: string;
  keywords: string[];
  href: string;
  shortcut?: string | null;
  write_action: boolean;
}

export interface CommentCreate {
  document_version_id?: string | null;
  parent_comment_id?: string | null;
  body: string;
  anchor?: Record<string, unknown>;
}

export interface CommentRead {
  id: string;
  document_id: string;
  document_version_id: string | null;
  matter_id: string;
  parent_comment_id: string | null;
  author_user_id: string;
  body: string;
  anchor_json: Record<string, unknown>;
  status: CommentStatus;
  resolved_by_user_id: string | null;
  resolved_at: string | null;
  created_at: string;
}

export type CommentStatus = "open" | "resolved";

export interface CommunicationCreate {
  communication_type: CommunicationType;
  occurred_at: string;
  direction: string;
  subject?: string | null;
  summary: string;
  matter_id?: string | null;
  external_reference?: string | null;
}

export type CommunicationType = "email" | "phone" | "meeting" | "whatsapp" | "letter" | "other";

export interface ComparisonClause {
  clause_type: string;
  status: string;
  similarity: number;
  left_title?: string | null;
  right_title?: string | null;
  left_text?: string | null;
  right_text?: string | null;
}

export interface ComplianceRead {
  id: string;
  procedure_step_id: string | null;
  title: string;
  description: string | null;
  status: ComplianceStatus;
  due_date: string | null;
  assigned_to: string | null;
  completed_at: string | null;
  source_document_id: string | null;
  notes: string | null;
  metadata_json: Record<string, unknown>;
}

export type ComplianceStatus = "pending" | "in_progress" | "completed" | "waived";

export interface ComplianceUpdate {
  status?: ComplianceStatus | null;
  due_date?: string | null;
  assigned_to?: string | null;
  notes?: string | null;
}

export type CompoundingFrequency = "annual" | "semiannual" | "quarterly" | "monthly" | "daily";

export type ConfidentialityLevel = "internal" | "confidential" | "highly_confidential" | "ethical_wall";

export interface ConflictCandidateRead {
  id: string;
  candidate_type: string;
  candidate_id: string | null;
  candidate_name: string;
  reason: string;
  match_score: number;
  metadata_json: Record<string, unknown>;
}

export interface ConflictCheckCreate {
  subject_name: string;
  related_parties?: string[];
  lead_id?: string | null;
  client_id?: string | null;
}

export interface ConflictCheckRead {
  id: string;
  organization_id: string;
  lead_id: string | null;
  client_id: string | null;
  subject_name: string;
  related_parties_json: unknown[];
  status: ConflictCheckStatus;
  review_note: string | null;
  reviewed_at: string | null;
  created_at: string;
  candidates?: ConflictCandidateRead[];
}

export type ConflictCheckStatus = "pending" | "review_required" | "cleared" | "conflict_found" | "overridden";

export interface ConflictDecision {
  status: ConflictCheckStatus;
  review_note: string;
}

export interface ConflictPartyInput {
  name: string;
  role: ConflictPartyRole;
  organization?: string | null;
  aliases?: string[];
  notes?: string | null;
}

export type ConflictPartyRole = "client" | "prospective_client" | "adverse_party" | "counterparty" | "related_party" | "witness" | "other";

export interface ConnectionTestRequest {
  live_probe: boolean;
}

export interface ConnectionTestResult {
  connection_id: string;
  status: IntegrationStatus;
  live_probe: boolean;
  checks: Record<string, unknown>[];
  latency_ms?: number | null;
  error?: string | null;
}

export interface ConsentDefinition {
  key: string;
  label: string;
  text: string;
  required: boolean;
  applies_if_all?: MatchCondition[];
  applies_if_any?: MatchCondition[];
}

export interface ConsentInput {
  key: string;
  accepted: boolean;
  accepted_at?: string | null;
}

export interface ContactCreate {
  name: string;
  role_title?: string | null;
  email?: string | null;
  phone?: string | null;
  is_primary: boolean;
  notes?: string | null;
}

export interface ContactRead {
  id: string;
  client_id: string;
  name: string;
  role_title: string | null;
  email: string | null;
  phone: string | null;
  is_primary: boolean;
  notes: string | null;
}

export interface ContextFieldDefinition {
  key: string;
  label: string;
  required: boolean;
  allowed_values?: string[];
  help_text?: string | null;
}

export interface ContractCatalogItem {
  contract_type: ContractType;
  name_en: string;
  name_hi: string;
  description: string;
  required_fields?: string[];
}

export type ContractChangeType = "unchanged" | "added" | "removed" | "modified";

export interface ContractClause {
  clause_id?: string | null;
  title?: string | null;
  text: string;
}

export interface ContractCompareOptions {
  ignore_case: boolean;
  normalize_whitespace: boolean;
  include_unchanged: boolean;
  similarity_threshold: number;
  max_diff_tokens_per_clause: number;
}

export interface ContractCompareRequest {
  original_text?: string | null;
  revised_text?: string | null;
  original_clauses?: ContractClause[] | null;
  revised_clauses?: ContractClause[] | null;
  options?: ContractCompareOptions;
}

export interface ContractCompareResponse {
  summary: ContractCompareSummary;
  changes: ClauseChange[];
  redline_markdown: string;
  warnings: string[];
  disclaimer: string;
}

export interface ContractCompareSummary {
  original_clause_count: number;
  revised_clause_count: number;
  added: number;
  removed: number;
  modified: number;
  unchanged: number;
  returned_changes: number;
  original_word_count: number;
  revised_word_count: number;
  word_count_delta: number;
}

export interface ContractComparison {
  left_contract_id: string;
  right_contract_id: string;
  summary: Record<string, number>;
  clauses: ComparisonClause[];
}

export interface ContractCreate {
  matter_id?: string | null;
  title: string;
  contract_type: ContractType;
  language: ContractLanguage;
  risk_profile: ContractRiskProfile;
  jurisdiction: string;
  governing_state?: string | null;
  party_a_name: string;
  party_b_name: string;
  effective_date?: string | null;
  questionnaire_json?: Record<string, unknown>;
}

export type ContractLanguage = "en" | "hi" | "bilingual";

export interface ContractListItem {
  id: string;
  title: string;
  contract_type: ContractType;
  language: ContractLanguage;
  status: ContractStatus;
  risk_profile: ContractRiskProfile;
  party_a_name: string;
  party_b_name: string;
  health_score: number;
  clause_count: number;
  open_high_risks: number;
  updated_at: string;
}

export interface ContractQuestion {
  key: string;
  label_en: string;
  label_hi: string;
  kind: string;
  required: boolean;
  placeholder?: string | null;
  options?: Record<string, string>[];
  default?: unknown;
}

export interface ContractQuestionnaire {
  contract_type: ContractType;
  name_en: string;
  name_hi: string;
  description: string;
  questions: ContractQuestion[];
  default_clauses: string[];
}

export interface ContractRead {
  id: string;
  matter_id: string | null;
  title: string;
  contract_type: ContractType;
  language: ContractLanguage;
  status: ContractStatus;
  risk_profile: ContractRiskProfile;
  jurisdiction: string;
  governing_state: string | null;
  party_a_name: string;
  party_b_name: string;
  effective_date: string | null;
  questionnaire_json: Record<string, unknown>;
  health_score: number;
  generated_filename: string | null;
  approved_at: string | null;
  metadata_json: Record<string, unknown>;
  clauses?: ClauseRead[];
  risks?: RiskRead[];
  created_at: string;
  updated_at: string;
}

export interface ContractReviewListItem {
  id: string;
  title: string;
  counterparty_name: string | null;
  contract_type: ContractType;
  status: ContractReviewStatus;
  language: string;
  health_score: number;
  clause_count: number;
  open_high_risks: number;
  source_filename: string;
  updated_at: string;
}

export interface ContractReviewRead {
  id: string;
  matter_id: string | null;
  internal_contract_id: string | null;
  playbook_id: string | null;
  title: string;
  counterparty_name: string | null;
  contract_type: ContractType;
  status: ContractReviewStatus;
  source_format: string;
  source_filename: string;
  source_sha256: string;
  language: string;
  text_length: number;
  health_score: number;
  metadata_json: Record<string, unknown>;
  clauses?: ReviewClauseRead[];
  findings?: ReviewFindingRead[];
  redlines?: RedlineRead[];
  created_at: string;
  updated_at: string;
}

export type ContractReviewStatus = "uploaded" | "analyzed" | "in_negotiation" | "approved" | "archived";

export type ContractRiskLevel = "low" | "medium" | "high";

export type ContractRiskProfile = "balanced" | "pro_party_a" | "pro_party_b";

export type ContractRiskStatus = "open" | "resolved" | "ignored";

export type ContractStatus = "draft" | "in_review" | "approved" | "superseded";

export type ContractType = "nda" | "employment" | "consulting" | "freelance" | "vendor" | "services" | "saas" | "software_development";

export interface ContractUpdate {
  title?: string | null;
  language?: ContractLanguage | null;
  risk_profile?: ContractRiskProfile | null;
  jurisdiction?: string | null;
  governing_state?: string | null;
  party_a_name?: string | null;
  party_b_name?: string | null;
  effective_date?: string | null;
  questionnaire_json?: Record<string, unknown> | null;
}

export interface ContractVersionRead {
  id: string;
  version_number: number;
  label: string;
  health_score: number;
  sha256: string | null;
  generated_filename: string | null;
  created_at: string;
}

export interface ContradictionRead {
  id: string;
  matter_id: string;
  contradiction_key: string;
  fact_key: string;
  label: string;
  explanation: string;
  severity: ContradictionSeverity;
  status: ContradictionStatus;
  values_json: ContradictionValue[];
  fact_ids_json: string[];
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type ContradictionSeverity = "low" | "medium" | "high";

export type ContradictionStatus = "open" | "resolved" | "dismissed";

export interface ContradictionUpdate {
  status: ContradictionStatus;
}

export interface ContradictionValue {
  fact_id: string;
  value: string;
  display: string;
  confidence: number;
}

export interface ConvertLeadRequest {
  client_type: ClientType;
  legal_name?: string | null;
}

export interface CorpusCheckpointRead {
  id: string;
  run_id: string | null;
  statutes: number;
  sections: number;
  judgments: number;
  paragraphs: number;
  citations: number;
  aggregate_sha256: string;
  captured_at: string;
  metadata_json: Record<string, unknown>;
}

export type CorpusLanguage = "en" | "hi" | "mixed" | "other";

export interface CorpusSearchRequest {
  query: string;
  scope: SearchScope;
  jurisdiction?: string | null;
  court_level?: CourtLevel | null;
  court_name?: string | null;
  act?: string | null;
  section?: string | null;
  language?: CorpusLanguage | null;
  date_from?: string | null;
  date_to?: string | null;
  as_of_date?: string | null;
  limit: number;
}

export interface CorpusSearchResponse {
  query: string;
  normalized_query: string;
  expanded_terms: string[];
  total: number;
  results: SearchResultRead[];
}

export interface CorpusStatsRead {
  sources: number;
  statutes: number;
  statute_sections: number;
  judgments: number;
  judgment_paragraphs: number;
  citations: number;
  resolved_citations: number;
}

export type CountMode = "calendar_days" | "business_days";

export interface CourtChangeRead {
  id: string;
  matter_id: string;
  tracker_id: string;
  previous_snapshot_id: string | null;
  current_snapshot_id: string;
  change_type: CourtChangeType;
  severity: ChangeSeverity;
  summary: string;
  old_value: string | null;
  new_value: string | null;
  detected_at: string;
  reviewed_at: string | null;
  workflow_event_id: string | null;
}

export type CourtChangeType = "new_order" | "hearing_date_changed" | "case_status_changed" | "stage_changed" | "judge_changed";

export interface CourtFeeCalculationRequest {
  rule_pack_id: string;
  filing_date: string;
  claim_value?: number | string | null;
  include_additional_fee_codes?: string[];
}

export interface CourtFeeCalculationResponse {
  rule_pack_id: string;
  rule_pack_version: string;
  jurisdiction: string;
  court: string;
  case_type: string;
  currency: string;
  filing_date: string;
  claim_value: string | null;
  base_fee: string;
  additional_fee_total: string;
  subtotal_before_limits: string;
  subtotal_after_limits: string;
  final_fee: string;
  breakdown: FeeBreakdownLine[];
  adjustments: string[];
  source_note: string;
  disclaimer: string;
}

export interface CourtFeeRulePackSummary {
  id: string;
  version: string;
  jurisdiction: string;
  court: string;
  case_type: string;
  currency: string;
  effective_from: string;
  effective_to: string | null;
  method: FeeMethod;
  source_note: string;
}

export type CourtLevel = "supreme_court" | "high_court" | "appellate_tribunal" | "tribunal" | "district_court" | "other";

export interface CourtSnapshotCaptureRead {
  snapshot: CourtSnapshotRead;
  changes: CourtChangeRead[];
}

export interface CourtSnapshotCreate {
  case_status?: string | null;
  stage?: string | null;
  next_hearing_date?: string | null;
  judge_or_bench?: string | null;
  order_count: number;
  latest_order_date?: string | null;
  latest_order_reference?: string | null;
  source_payload_json?: Record<string, unknown>;
  captured_at?: string | null;
}

export interface CourtSnapshotRead {
  id: string;
  tracker_id: string;
  captured_at: string;
  case_status: string | null;
  stage: string | null;
  next_hearing_date: string | null;
  judge_or_bench: string | null;
  order_count: number;
  latest_order_date: string | null;
  latest_order_reference: string | null;
  content_hash: string;
  source_payload_json: Record<string, unknown>;
}

export interface CourtSourceCapabilityRead {
  source_kind: CourtSourceKind;
  automatic_fetch: boolean;
  requires_user_or_approved_connector: boolean;
  note: string;
}

export type CourtSourceKind = "manual" | "ecourts_manual" | "official_import" | "mock";

export interface CourtTrackerCreate {
  matter_id: string;
  source_kind: CourtSourceKind;
  cnr_number?: string | null;
  case_number?: string | null;
  court_name?: string | null;
  bench_name?: string | null;
  source_url?: string | null;
  config_json?: Record<string, unknown>;
}

export interface CourtTrackerRead {
  id: string;
  organization_id: string;
  matter_id: string;
  source_kind: CourtSourceKind;
  cnr_number: string | null;
  case_number: string | null;
  court_name: string | null;
  bench_name: string | null;
  source_url: string | null;
  status: CourtTrackerStatus;
  last_checked_at: string | null;
  next_check_at: string | null;
  config_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type CourtTrackerStatus = "active" | "paused" | "closed";

export type DateKind = "effective_date" | "execution_date" | "commencement_date" | "expiry_date" | "renewal_date" | "payment_due" | "notice_deadline" | "termination_date" | "delivery_date" | "reporting_date" | "other";

export type DateRelation = "on" | "by" | "within" | "before" | "after" | "from";

export type DayBasis = "calendar" | "business";

export type DayCountConvention = "actual_365" | "actual_366" | "actual_360" | "actual_actual" | "30_360";

export type DeadlineAdjustment = "none" | "next_working_day" | "previous_working_day";

export type DeadlineAdjustmentInput = "none" | "next_working_day" | "previous_working_day";

export interface DeadlineCalculationRead {
  trigger_date: string;
  calculated_date: string;
  due_date: string;
  offset_days: number;
  day_basis: DayBasis;
  count_from_next_day: boolean;
  adjustment: DeadlineAdjustment;
  skipped_weekends: number;
  skipped_holidays: number;
  adjustment_days: number;
}

export interface DeadlineCalculationRequest {
  trigger_date: string;
  offset_days: number;
  day_basis: DayBasis;
  count_from_next_day: boolean;
  adjustment: DeadlineAdjustmentInput;
  holidays?: string[];
}

export interface DeadlineRead {
  id: string;
  matter_id: string;
  matter_procedure_id: string | null;
  deadline_rule_id: string | null;
  title: string;
  trigger_type: string;
  trigger_id: string | null;
  trigger_date: string;
  calculated_date: string;
  due_date: string;
  status: DeadlineStatus;
  reviewed_by_lawyer: boolean;
  completed_at: string | null;
  calculation_json: Record<string, unknown>;
  authority_json: Record<string, unknown>;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeadlineRuleInput {
  code: string;
  name_en: string;
  name_hi?: string | null;
  trigger_code: string;
  offset_days: number;
  day_basis: DayBasis;
  count_from_next_day: boolean;
  adjustment: DeadlineAdjustmentInput;
  requires_lawyer_review: boolean;
  source_name?: string | null;
  source_url?: string | null;
  source_citation?: string | null;
  effective_from?: string | null;
  effective_to?: string | null;
  verified: boolean;
  metadata_json?: Record<string, unknown>;
}

export interface DeadlineRuleRead {
  id: string;
  code: string;
  name_en: string;
  name_hi: string | null;
  trigger_code: string;
  offset_days: number;
  day_basis: DayBasis;
  count_from_next_day: boolean;
  adjustment: DeadlineAdjustment;
  requires_lawyer_review: boolean;
  source_name: string | null;
  source_url: string | null;
  source_citation: string | null;
  effective_from: string | null;
  effective_to: string | null;
  verified: boolean;
  metadata_json: Record<string, unknown>;
}

export type DeadlineStatus = "upcoming" | "due_today" | "overdue" | "completed" | "review";

export interface DeadlineUpdate {
  reviewed_by_lawyer?: boolean | null;
  completed?: boolean | null;
  due_date?: string | null;
  notes?: string | null;
}

export interface DeletionDecisionRequest {
  approve: boolean;
  reason?: string | null;
}

export interface DeletionRequestCreate {
  resource_type: RetentionResourceType;
  resource_id: string;
  reason: string;
}

export interface DeletionRequestRead {
  id: string;
  organization_id: string;
  requested_by_user_id: string;
  resource_type: RetentionResourceType;
  resource_id: string;
  reason: string;
  status: DeletionStatus;
  hold_id: string | null;
  decision_reason: string | null;
  approved_by_user_id: string | null;
  approved_at: string | null;
  executed_at: string | null;
  created_at: string;
  updated_at: string;
}

export type DeletionStatus = "requested" | "blocked" | "approved" | "cancelled" | "executed";

export interface DeliveryResult {
  provider: IntegrationProvider;
  operation: string;
  external_resource_id?: string | null;
  external_url?: string | null;
  metadata?: Record<string, unknown>;
}

export interface DeploymentApprovalCreate {
  decision: string;
  note?: string | null;
}

export interface DeploymentApprovalRead {
  id: string;
  membership_id: string;
  decision: string;
  note: string | null;
  decided_at: string;
}

export interface DeploymentChangeWindowCreate {
  environment_id: string;
  starts_at: string;
  ends_at: string;
  reason: string;
  emergency: boolean;
}

export interface DeploymentChangeWindowRead {
  id: string;
  environment_id: string;
  approved_by_membership_id: string;
  starts_at: string;
  ends_at: string;
  reason: string;
  emergency: boolean;
}

export interface DeploymentDashboard {
  environments: DeploymentEnvironmentRead[];
  services: DeploymentServiceRead[];
  rollouts: DeploymentRolloutRead[];
  change_windows: DeploymentChangeWindowRead[];
  secrets: DeploymentSecretReferenceRead[];
  runtime_readiness: RuntimeReadiness;
}

export interface DeploymentEnvironmentCreate {
  environment_key: string;
  name: string;
  kind: DeploymentEnvironmentKind;
  base_url: string;
  strategy: DeploymentStrategy;
  tls_required: boolean;
  object_storage_required: boolean;
  change_window_required: boolean;
}

export type DeploymentEnvironmentKind = "staging" | "production";

export interface DeploymentEnvironmentRead {
  id: string;
  organization_id: string;
  environment_key: string;
  name: string;
  kind: DeploymentEnvironmentKind;
  base_url: string;
  strategy: DeploymentStrategy;
  enabled: boolean;
  tls_required: boolean;
  object_storage_required: boolean;
  change_window_required: boolean;
  current_release_run_id: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DeploymentRolloutCreate {
  environment_id: string;
  release_run_id: string;
  rollback_point_id: string;
  change_window_id?: string | null;
  notes?: string | null;
}

export interface DeploymentRolloutDetail {
  rollout: DeploymentRolloutRead;
  steps: DeploymentRolloutStepRead[];
}

export interface DeploymentRolloutRead {
  id: string;
  organization_id: string;
  environment_id: string;
  release_run_id: string;
  rollback_point_id: string;
  change_window_id: string | null;
  requested_by_membership_id: string;
  status: DeploymentRolloutStatus;
  started_at: string | null;
  finished_at: string | null;
  snapshot_hash: string | null;
  notes: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export type DeploymentRolloutStatus = "planned" | "running" | "succeeded" | "failed" | "rolled_back" | "cancelled";

export interface DeploymentRolloutStepRead {
  id: string;
  rollout_id: string;
  step_key: string;
  kind: DeploymentStepKind;
  sequence: number;
  status: DeploymentStepStatus;
  started_at: string | null;
  finished_at: string | null;
  message: string | null;
  evidence_json: Record<string, unknown>;
}

export interface DeploymentSecretReferenceCreate {
  environment_id: string;
  secret_key: string;
  provider: SecretReferenceProvider;
  reference: string;
  required: boolean;
}

export interface DeploymentSecretReferenceRead {
  id: string;
  environment_id: string;
  secret_key: string;
  provider: SecretReferenceProvider;
  reference: string;
  required: boolean;
  last_verified_at: string | null;
}

export interface DeploymentServiceRead {
  id: string;
  environment_id: string;
  service_key: string;
  image_ref: string | null;
  replicas: number;
  enabled: boolean;
  health_path: string | null;
  queue_names: string | null;
  metadata_json: Record<string, unknown>;
}

export type DeploymentStepKind = "preflight" | "backup" | "migration" | "api" | "workers" | "web" | "health" | "traffic" | "postcheck";

export type DeploymentStepStatus = "pending" | "running" | "passed" | "failed" | "skipped";

export interface DeploymentStepUpdate {
  status: DeploymentStepStatus;
  message?: string | null;
  evidence_json?: Record<string, unknown>;
}

export type DeploymentStrategy = "rolling" | "blue_green" | "recreate";

export type DiffOperation = "equal" | "insert" | "delete" | "replace";

export interface DirectionCreate {
  text: string;
  due_date?: string | null;
  source_document_id?: string | null;
  page_number?: number | null;
  requires_review: boolean;
}

export interface DirectionExtractionRequest {
  document_id: string;
  order_date?: string | null;
}

export interface DirectionRead {
  id: string;
  hearing_id: string;
  matter_id: string;
  text: string;
  due_date: string | null;
  status: DirectionStatus;
  source_document_id: string | null;
  page_number: number | null;
  extracted: boolean;
  confidence: number;
  requires_review: boolean;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type DirectionStatus = "open" | "complied" | "waived";

export interface DirectionUpdate {
  status?: DirectionStatus | null;
  due_date?: string | null;
  requires_review?: boolean | null;
}

export type DocumentAccessLevel = "view" | "download" | "edit";

export interface DocumentEntityRead {
  id: string;
  document_id: string;
  page_id: string | null;
  page_number: number | null;
  entity_type: EntityType;
  raw_text: string;
  normalized_value: string | null;
  confidence: number;
  start_char: number | null;
  end_char: number | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DocumentExportPreview {
  source_type: ExportSourceType;
  output_format: ExportFormat;
  title: string;
  filename: string;
  section_count: number;
  table_count: number;
  paragraph_count: number;
  page_size: PageSize;
  warnings: string[];
}

export interface DocumentExportRequest {
  source_type: ExportSourceType;
  output_format: ExportFormat;
  source: Record<string, unknown>;
  options?: ExportOptions;
}

export type DocumentFormat = "pdf" | "docx";

export interface DocumentGrantCreate {
  membership_id: string;
  effect: AccessEffect;
  access_level: DocumentAccessLevel;
  expires_at?: string | null;
  reason?: string | null;
}

export interface DocumentGrantRead {
  id: string;
  document_id: string;
  membership_id: string;
  effect: AccessEffect;
  access_level: DocumentAccessLevel;
  expires_at: string | null;
  reason: string | null;
  granted_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export type DocumentLanguage = "en" | "hi" | "mixed" | "hinglish" | "unknown";

export interface DocumentMetadata {
  original_filename: string | null;
  detected_format: DocumentFormat;
  mime_type: string;
  file_size_bytes: number;
  sha256: string;
  title?: string | null;
  author?: string | null;
  subject?: string | null;
  created_at?: string | null;
  modified_at?: string | null;
  page_count?: number | null;
  paragraph_count: number;
  table_count: number;
  heading_count: number;
  word_count: number;
  character_count: number;
}

export interface DocumentPageMatchRead {
  page_number: number;
  snippet: string;
  match_count: number;
}

export interface DocumentPageRead {
  id: string;
  document_id: string;
  page_number: number;
  text: string;
  text_sha256: string | null;
  char_count: number;
  detected_language: DocumentLanguage;
  extraction_method: ExtractionMethod;
  is_scanned: boolean;
  created_at: string;
  updated_at: string;
}

export interface DocumentPageWindowRead {
  document_id: string;
  filename: string;
  total_pages: number;
  start_page: number;
  end_page: number;
  has_previous: boolean;
  has_next: boolean;
  pages: DocumentPageRead[];
}

export interface DocumentRead {
  id: string;
  matter_id: string;
  filename: string;
  display_name: string | null;
  file_extension: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  sha256: string | null;
  page_count: number | null;
  text_char_count: number;
  detected_language: DocumentLanguage;
  extraction_method: ExtractionMethod;
  is_scanned: boolean;
  ocr_used: boolean;
  extracted_at: string | null;
  processing_status: ProcessingStatus;
  processing_error: string | null;
  entity_counts?: Record<string, number>;
  created_at: string;
  updated_at: string;
}

export interface DocumentSuggestionRead {
  cnr_numbers?: string[];
  case_numbers?: string[];
  case_titles?: string[];
  courts?: string[];
  judges?: string[];
  acts?: string[];
  statute_references?: string[];
  citations?: string[];
}

export interface DocumentTextRead {
  document_id: string;
  filename: string;
  page_count: number;
  text: string;
}

export interface DocumentVersionRead {
  id: string;
  document_id: string;
  matter_id: string;
  version_number: number;
  source: VersionSource;
  filename: string;
  sha256: string;
  size_bytes: number;
  change_note: string | null;
  created_by_user_id: string | null;
  created_at: string;
}

export interface DocusignEnvelopeRequest {
  document_version_id: string;
  document_name?: string | null;
  signer_name: string;
  signer_email: string;
  email_subject: string;
  status: string;
  internal_resource_type: string | null;
  internal_resource_id?: string | null;
}

export interface DraftCatalogItem {
  draft_type: string;
  name_en: string;
  name_hi: string;
  description: string;
  section_count: number;
  questions: DraftQuestion[];
}

export interface DraftContextPreview {
  matter_id: string;
  matter_title: string;
  court_name: string | null;
  case_number: string | null;
  available_facts: number;
  safe_facts: number;
  excluded_conflicting_facts: number;
  timeline_events: number;
  documents: number;
  admissions: number;
  denials: number;
  open_contradictions: number;
}

export type DraftFindingLevel = "low" | "medium" | "high";

export interface DraftFindingRead {
  id: string;
  rule_code: string;
  section_key: string | null;
  title: string;
  explanation: string;
  level: DraftFindingLevel;
  status: DraftFindingStatus;
  metadata_json: Record<string, unknown>;
}

export type DraftFindingStatus = "open" | "resolved" | "accepted";

export interface DraftFindingUpdate {
  status: DraftFindingStatus;
}

export interface DraftQuestion {
  key: string;
  label_en: string;
  label_hi: string;
  required: boolean;
  kind: string;
}

export interface DraftQuestionnaire {
  draft_type: string;
  name_en: string;
  name_hi: string;
  description: string;
  questions: DraftQuestion[];
  sections: DraftSectionDefinition[];
}

export interface DraftRenderResult {
  draft: LegalDraftRead;
  version: LegalDraftVersionRead;
}

export interface DraftResult {
  contract: ContractRead;
  version: ContractVersionRead;
}

export interface DraftSectionDefinition {
  key: string;
  title_en: string;
  title_hi: string;
}

export interface DraftSectionRead {
  id: string;
  section_key: string;
  title_en: string;
  title_hi: string | null;
  body_en: string;
  body_hi: string | null;
  position: number;
  source: DraftSectionSource;
  reviewed: boolean;
  locked: boolean;
  metadata_json: Record<string, unknown>;
  sources?: DraftSourceRead[];
}

export type DraftSectionSource = "deterministic" | "manual" | "ai";

export interface DraftSectionUpdate {
  title_en?: string | null;
  title_hi?: string | null;
  body_en?: string | null;
  body_hi?: string | null;
  position?: number | null;
  reviewed?: boolean | null;
  locked?: boolean | null;
}

export interface DraftSourceRead {
  id: string;
  source_type: DraftSourceType;
  source_id: string | null;
  label: string;
  locator: string | null;
  excerpt: string | null;
  verified: boolean;
  metadata_json: Record<string, unknown>;
}

export type DraftSourceType = "fact" | "timeline" | "document" | "statement" | "contradiction" | "statute_section" | "judgment_paragraph" | "manual";

export interface DraftTemplateRead {
  id: string;
  code: string;
  draft_type: LegalDraftType;
  name_en: string;
  name_hi: string | null;
  description: string | null;
  structure_json: Record<string, unknown>[];
  questions_json: Record<string, unknown>[];
  version: number;
  active: boolean;
}

export interface DutyBreakdownLine {
  label: string;
  basis: string;
  amount: string;
}

export type DutyMethod = "fixed" | "percentage" | "progressive";

export type ESignatureEnvelopeStatus = "draft" | "sent" | "viewed" | "completed" | "declined" | "voided";

export type ESignatureProvider = "manual" | "mock" | "docusign" | "adobe_sign" | "other";

export type ESignatureSignerStatus = "pending" | "sent" | "viewed" | "signed" | "declined";

export interface EngagementCreate {
  title: string;
  matter_id?: string | null;
  scope?: string | null;
  fee_structure?: string | null;
  currency: string;
  agreed_fee?: number | null;
  status: EngagementStatus;
}

export interface EngagementRead {
  id: string;
  client_id: string;
  matter_id: string | null;
  title: string;
  scope: string | null;
  fee_structure: string | null;
  currency: string;
  agreed_fee: number | null;
  status: EngagementStatus;
  signed_at: string | null;
  created_at: string;
}

export type EngagementStatus = "draft" | "pending_signature" | "active" | "on_hold" | "closed";

export type EntityType = "cnr_number" | "case_number" | "case_title" | "party" | "court" | "judge" | "date" | "act" | "statute_reference" | "citation";

export interface EnvelopeCreate {
  document_version_id: string;
  provider: ESignatureProvider;
  title: string;
  signers: SignerCreate[];
  metadata?: Record<string, unknown>;
}

export interface EnvelopeRead {
  id: string;
  document_id: string;
  document_version_id: string;
  matter_id: string;
  provider: ESignatureProvider;
  status: ESignatureEnvelopeStatus;
  title: string;
  provider_reference: string | null;
  sent_at: string | null;
  completed_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  signers?: SignerRead[];
}

export interface EvaluatedChecklistItem {
  sequence: number;
  key: string;
  title: string;
  category: string;
  kind: ChecklistItemKind;
  description: string | null;
  applicable: boolean;
  requirement: RequirementLevel;
  required: boolean;
  status: ItemStatus;
  satisfied: boolean;
  file_reference: string | null;
  document_date: string | null;
  notes: string | null;
  evidence_hint: string | null;
  reasons: string[];
}

export interface EvaluatedConsent {
  key: string;
  label: string;
  text: string;
  applicable: boolean;
  required: boolean;
  accepted: boolean;
  accepted_at: string | null;
}

export interface EvaluatedIntakeField {
  sequence: number;
  key: string;
  label: string;
  section: string;
  field_type: IntakeFieldType;
  applicable: boolean;
  required: boolean;
  provided: boolean;
  valid: boolean;
  normalized_value?: unknown | null;
  validation_messages: string[];
  help_text: string | null;
}

export interface EvaluationCaseCreate {
  case_key: string;
  title: string;
  category: string;
  evaluator: string;
  weight: number;
  critical: boolean;
  input_json?: Record<string, unknown>;
  expected_json?: Record<string, unknown>;
  source_note?: string | null;
  tags_json?: unknown[];
  metadata_json?: Record<string, unknown>;
}

export interface EvaluationCaseRead {
  id: string;
  suite_id: string;
  case_key: string;
  title: string;
  category: string;
  evaluator: string;
  status: string;
  weight: number;
  critical: boolean;
  input_json: Record<string, unknown>;
  expected_json: Record<string, unknown>;
  source_note: string | null;
  source_hash: string | null;
  tags_json: unknown[];
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface EvaluationCaseRunRead {
  id: string;
  run_id: string;
  case_id: string;
  status: string;
  score: number;
  duration_ms: number;
  actual_json: Record<string, unknown>;
  expected_json: Record<string, unknown>;
  details_json: Record<string, unknown>;
  error: string | null;
}

export interface EvaluationRunCreate {
  build_ref?: string | null;
}

export interface EvaluationRunDetail {
  run: EvaluationRunRead;
  case_runs: EvaluationCaseRunRead[];
  findings: QAFindingRead[];
  metrics: Record<string, unknown>[];
  gate?: Record<string, unknown> | null;
}

export interface EvaluationRunRead {
  id: string;
  organization_id: string;
  suite_id: string;
  status: string;
  trigger: string;
  app_version: string | null;
  build_ref: string | null;
  started_at: string | null;
  finished_at: string | null;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  skipped_cases: number;
  critical_failures: number;
  overall_score: number;
  duration_ms: number;
  snapshot_hash: string | null;
  summary_json: Record<string, unknown>;
  created_at: string;
}

export interface EvaluationSuiteDetail {
  suite: EvaluationSuiteRead;
  cases: EvaluationCaseRead[];
}

export interface EvaluationSuiteRead {
  id: string;
  organization_id: string;
  suite_key: string;
  name: string;
  description: string | null;
  version: number;
  enabled: boolean;
  default_gate: boolean;
  tags_json: unknown[];
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface EventRead {
  id: string;
  job_id: string;
  event_type: string;
  level: string;
  message: string;
  progress_current: number | null;
  progress_total: number | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface EvidenceDashboard {
  evidence_items: number;
  issues: number;
  witnesses: number;
  open_gaps: number;
  contradictions: number;
  proposed_exhibits: number;
  reviewed_items: number;
}

export interface EvidenceFactRead {
  fact: FactRead;
  contradiction_id?: string | null;
  contradiction_severity?: ContradictionSeverity | null;
}

export interface EvidenceGraphEdge {
  source: string;
  target: string;
  type: string;
  metadata?: Record<string, unknown>;
}

export interface EvidenceGraphNode {
  id: string;
  type: string;
  label: string;
  metadata?: Record<string, unknown>;
}

export interface EvidenceGraphRead {
  nodes: EvidenceGraphNode[];
  edges: EvidenceGraphEdge[];
}

export interface EvidenceIndexRequest {
  case_reference?: string | null;
  title: string;
  index_type: IndexType;
  documents: IndexDocument[];
  numbering_style: NumberingStyle;
  label_prefix?: string | null;
  numbering_start: number;
  zero_pad: number;
  pagination_mode: PaginationMode;
  first_page: number;
}

export interface EvidenceIndexResponse {
  case_reference: string | null;
  title: string;
  index_type: IndexType;
  documents: RenderedIndexDocument[];
  summary: EvidenceIndexSummary;
  markdown: string;
  csv: string;
  warnings: string[];
  disclaimer: string;
}

export interface EvidenceIndexSummary {
  document_count: number;
  confidential_count: number;
  dated_document_count: number;
  total_pages: number | null;
  first_page: number | null;
  last_page: number | null;
  page_gaps: string[];
  category_counts: Record<string, number>;
}

export interface EvidenceItemRead {
  id: string;
  matter_id: string;
  document_id: string | null;
  title: string;
  kind: EvidenceKind;
  strength: EvidenceStrength;
  review_status: EvidenceReviewStatus;
  authenticity_checked: boolean;
  admissibility_checked: boolean;
  original_available: boolean | null;
  confidence: number;
  summary: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface EvidenceItemUpdate {
  kind?: EvidenceKind | null;
  strength?: EvidenceStrength | null;
  review_status?: EvidenceReviewStatus | null;
  authenticity_checked?: boolean | null;
  admissibility_checked?: boolean | null;
  original_available?: boolean | null;
  summary?: string | null;
}

export type EvidenceKind = "court_filing" | "court_order" | "contract" | "correspondence" | "financial" | "identity" | "property" | "electronic" | "photo_video" | "witness_statement" | "expert" | "other";

export type EvidenceLinkType = "supports" | "contradicts" | "context";

export interface EvidenceMatrixRead {
  matter_id: string;
  facts?: EvidenceFactRead[];
  statement_counts?: Record<string, number>;
}

export type EvidenceReviewStatus = "auto" | "reviewed" | "rejected";

export type EvidenceStrength = "unknown" | "low" | "medium" | "high";

export interface ExhibitCreate {
  evidence_item_id: string;
  label: string;
  notes?: string | null;
}

export interface ExhibitRead {
  id: string;
  matter_id: string;
  evidence_item_id: string;
  label: string;
  status: ExhibitStatus;
  marked_date: string | null;
  court_reference: string | null;
  notes: string | null;
}

export type ExhibitStatus = "proposed" | "marked" | "admitted" | "rejected";

export interface ExhibitUpdate {
  status?: ExhibitStatus | null;
  marked_date?: string | null;
  court_reference?: string | null;
  notes?: string | null;
}

export interface ExpenseCreate {
  client_id?: string | null;
  matter_id?: string | null;
  expense_date: string;
  description: string;
  category?: string | null;
  amount: number | string;
  tax_amount: number | string;
  currency: string;
  billable: boolean;
  receipt_document_id?: string | null;
  notes?: string | null;
}

export interface ExpenseRead {
  id: string;
  client_id: string | null;
  matter_id: string | null;
  expense_date: string;
  description: string;
  category: string | null;
  amount: string;
  tax_amount: string;
  currency: string;
  billable: boolean;
  status: ExpenseStatus;
  receipt_document_id: string | null;
  notes: string | null;
  created_at: string;
}

export type ExpenseStatus = "draft" | "submitted" | "approved" | "billed" | "rejected";

export interface ExperiencePreferenceRead {
  id: string;
  ui_language: UILanguage;
  density: UIDensity;
  contrast: UIContrast;
  font_scale: UIFontScale;
  reduce_motion: boolean;
  show_keyboard_hints: boolean;
  document_page_window: number;
  document_text_zoom: number;
  remember_last_workspace: boolean;
  metadata_json: Record<string, unknown>;
  updated_at: string;
}

export interface ExperiencePreferenceUpdate {
  ui_language?: UILanguage | null;
  density?: UIDensity | null;
  contrast?: UIContrast | null;
  font_scale?: UIFontScale | null;
  reduce_motion?: boolean | null;
  show_keyboard_hints?: boolean | null;
  document_page_window?: number | null;
  document_text_zoom?: number | null;
  remember_last_workspace?: boolean | null;
}

export type ExpiryAdjustment = "none" | "next_business_day";

export interface ExpiryAdjustmentResult {
  original_date: string;
  adjusted_date: string;
  reason: string;
}

export type ExportFormat = "docx" | "pdf";

export interface ExportOptions {
  page_size: PageSize;
  margin_mm: number;
  include_disclaimer: boolean;
  include_generated_footer: boolean;
  header_text?: string | null;
  footer_text?: string | null;
  filename?: string | null;
}

export type ExportSourceType = "legal_notice" | "affidavit" | "case_timeline" | "evidence_index" | "legal_checklist" | "client_intake" | "generic";

export interface ExtractOptions {
  date_kinds?: DateKind[] | null;
  obligation_types?: ObligationType[] | null;
  include_other_dates: boolean;
  include_other_obligations: boolean;
  deduplicate: boolean;
  context_chars: number;
  max_dates: number;
  max_obligations: number;
}

export interface ExtractRequest {
  text: string;
  options?: ExtractOptions;
}

export interface ExtractResponse {
  dates: ExtractedDate[];
  obligations: ExtractedObligation[];
  summary: ExtractionSummary;
  warnings: string[];
  disclaimer: string;
}

export interface ExtractedClause {
  clause_type: ClauseType;
  confidence: number;
  match_basis: MatchBasis;
  heading?: string | null;
  normalized_heading?: string | null;
  text: string;
  start: number;
  end: number;
  line: number;
  column: number;
  signals?: ClauseSignal[];
}

export interface ExtractedDate {
  date_kind: DateKind;
  raw_text: string;
  normalized_date?: string | null;
  relation?: DateRelation | null;
  relative_value?: number | null;
  relative_unit?: RelativeUnit | null;
  anchor?: string | null;
  context: string;
  start: number;
  end: number;
  line: number;
  column: number;
  signals?: ExtractionSignal[];
}

export interface ExtractedObligation {
  obligation_type: ObligationType;
  actor?: string | null;
  action: string;
  frequency: Frequency;
  deadline_expression?: string | null;
  text: string;
  start: number;
  end: number;
  line: number;
  column: number;
  signals?: ExtractionSignal[];
}

export type ExtractionMethod = "native_pdf" | "ocr" | "mixed_pdf" | "docx" | "text" | "image_ocr" | "unknown";

export interface ExtractionSignal {
  kind: string;
  value: string;
}

export interface ExtractionSummary {
  dates_returned: number;
  obligations_returned: number;
  absolute_dates: number;
  relative_dates: number;
  date_kind_counts: Record<string, number>;
  obligation_type_counts: Record<string, number>;
}

export interface FactRead {
  id: string;
  matter_id: string;
  fact_key: string;
  fact_type: FactType;
  category: string;
  label: string;
  value_text: string;
  normalized_value: string;
  confidence: number;
  status: FactStatus;
  metadata_json: Record<string, unknown>;
  sources?: SourceRead[];
  created_at: string;
  updated_at: string;
}

export type FactStatus = "auto" | "confirmed" | "rejected";

export type FactType = "date" | "money" | "identifier" | "text";

export interface FactUpdate {
  status: FactStatus;
}

export interface FeeArrangementCreate {
  client_id: string;
  matter_id?: string | null;
  engagement_id?: string | null;
  rate_card_id?: string | null;
  name: string;
  fee_model: FeeModel;
  status: FeeArrangementStatus;
  currency: string;
  default_hourly_rate?: number | string | null;
  fixed_fee?: number | string | null;
  retainer_amount?: number | string | null;
  fee_cap?: number | string | null;
  contingency_percent?: number | string | null;
  billing_frequency?: string | null;
  tax_treatment?: Record<string, unknown>;
  notes?: string | null;
}

export interface FeeArrangementRead {
  id: string;
  client_id: string;
  matter_id: string | null;
  engagement_id: string | null;
  rate_card_id: string | null;
  name: string;
  fee_model: FeeModel;
  status: FeeArrangementStatus;
  currency: string;
  default_hourly_rate: string | null;
  fixed_fee: string | null;
  retainer_amount: string | null;
  fee_cap: string | null;
  contingency_percent: string | null;
  billing_frequency: string | null;
  tax_treatment_json: Record<string, unknown>;
  notes: string | null;
  created_at: string;
}

export type FeeArrangementStatus = "draft" | "active" | "closed";

export interface FeeBreakdownLine {
  label: string;
  basis: string;
  amount: string;
}

export type FeeMethod = "fixed" | "progressive";

export type FeeModel = "hourly" | "fixed" | "retainer" | "capped" | "contingency" | "custom";

export type FieldKind = "text" | "multiline" | "date" | "money" | "integer";

export interface FinancialSummary {
  currency: string;
  window_days?: number | null;
  outstanding_amount: number;
  overdue_amount: number;
  issued_window: number;
  collected_window: number;
  collection_rate: number;
  ageing: Record<string, number>;
}

export interface FindingUpdate {
  status: ReviewFindingStatus;
}

export type Frequency = "once" | "daily" | "weekly" | "monthly" | "quarterly" | "annually" | "continuous" | "event_based" | "unknown";

export interface GapRead {
  id: string;
  matter_id: string;
  issue_id: string | null;
  gap_key: string;
  title: string;
  explanation: string;
  severity: string;
  status: GapStatus;
  suggested_action: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export type GapStatus = "open" | "resolved" | "dismissed";

export interface GapUpdate {
  status: GapStatus;
}

export interface GmailSendRequest {
  to: string[];
  cc?: string[];
  bcc?: string[];
  subject: string;
  text_body: string;
  html_body?: string | null;
  reply_to?: string | null;
  internal_resource_type?: string | null;
  internal_resource_id?: string | null;
}

export type GoalComparison = "at_least" | "at_most" | "exact";

export interface GoalCreate {
  name: string;
  metric_key: string;
  scope_type: AnalyticsScope;
  scope_id?: string | null;
  comparison: GoalComparison;
  target_value: number;
  start_date: string;
  end_date: string;
  notes?: string | null;
}

export interface GoalProgressRead {
  id: string;
  goal_id: string;
  recorded_at: string;
  actual_value: number;
  target_value: number;
  progress_percent: number;
  target_met: boolean;
}

export interface GoalRead {
  id: string;
  name: string;
  metric_key: string;
  scope_type: AnalyticsScope;
  scope_id: string | null;
  comparison: GoalComparison;
  target_value: number;
  start_date: string;
  end_date: string;
  status: AnalyticsGoalStatus;
  notes: string | null;
  created_at: string;
}

export interface GoalWithProgress {
  goal: GoalRead;
  progress: GoalProgressRead | null;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export type HeadingMethod = "docx_style" | "pdf_font_heuristic";

export interface HealthComponentRead {
  id: string;
  component_key: string;
  category: string;
  status: string;
  latency_ms: number | null;
  message_en: string;
  message_hi: string | null;
  metrics_json: Record<string, unknown>;
  checked_at: string;
}

export interface HealthRunDetail {
  run: HealthRunRead;
  components: HealthComponentRead[];
}

export interface HealthRunRead {
  id: string;
  organization_id: string;
  trigger: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  summary_json: Record<string, unknown>;
  snapshot_hash: string | null;
  created_at: string;
}

export interface HearingBrief {
  matter_id: string;
  matter_title: string;
  hearing: HearingRead;
  previous_hearing: HearingRead | null;
  open_directions: DirectionRead[];
  upcoming_deadlines: DeadlineRead[];
  pending_compliances: Record<string, unknown>[];
  key_facts: Record<string, unknown>[];
  open_contradictions: Record<string, unknown>[];
  disclaimer: string;
}

export interface HearingCreate {
  matter_id: string;
  scheduled_for: string;
  court_name?: string | null;
  courtroom?: string | null;
  judge_or_bench?: string | null;
  purpose?: string | null;
  source_document_id?: string | null;
  source_url?: string | null;
  notes?: string | null;
}

export interface HearingRead {
  id: string;
  matter_id: string;
  scheduled_for: string;
  court_name: string | null;
  courtroom: string | null;
  judge_or_bench: string | null;
  purpose: string | null;
  status: HearingStatus;
  source_document_id: string | null;
  source_url: string | null;
  notes: string | null;
  metadata_json: Record<string, unknown>;
  directions?: DirectionRead[];
  created_at: string;
  updated_at: string;
}

export type HearingStatus = "scheduled" | "completed" | "adjourned" | "cancelled";

export interface HearingUpdate {
  scheduled_for?: string | null;
  court_name?: string | null;
  courtroom?: string | null;
  judge_or_bench?: string | null;
  purpose?: string | null;
  status?: HearingStatus | null;
  notes?: string | null;
}

export interface IncidentRead {
  id: string;
  component_key: string;
  fingerprint: string;
  severity: string;
  status: string;
  title: string;
  description: string;
  first_seen_at: string;
  last_seen_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface IncidentUpdate {
  action: string;
  note?: string | null;
}

export interface IndexDocument {
  title: string;
  document_date?: string | null;
  description?: string | null;
  category?: string | null;
  label?: string | null;
  source_file?: string | null;
  page_count?: number | null;
  start_page?: number | null;
  end_page?: number | null;
  notes?: string | null;
  confidential: boolean;
}

export type IndexType = "evidence" | "exhibit" | "annexure" | "bundle";

export interface IngestionItemRead {
  id: string;
  run_id: string;
  position: number;
  kind: string;
  external_id: string;
  source_url: string;
  declared_sha256: string | null;
  actual_sha256: string;
  status: string;
  change_kind: string;
  resource_type: string | null;
  resource_id: string | null;
  before_sha256: string | null;
  after_sha256: string | null;
  error_message: string | null;
  metadata_json: Record<string, unknown>;
}

export interface IngestionRunDetail {
  run: IngestionRunRead;
  items: IngestionItemRead[];
}

export interface IngestionRunRead {
  id: string;
  organization_id: string;
  feed_id: string;
  initiated_by_membership_id: string | null;
  trigger: string;
  status: string;
  manifest_sha256: string | null;
  source_label: string | null;
  started_at: string;
  finished_at: string | null;
  items_total: number;
  items_succeeded: number;
  items_failed: number;
  items_unchanged: number;
  items_changed: number;
  error_message: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface IntakeFieldDefinition {
  key: string;
  label: string;
  section: string;
  field_type: IntakeFieldType;
  required: boolean;
  allowed_values?: string[];
  max_length: number;
  pattern?: string | null;
  placeholder?: string | null;
  help_text?: string | null;
  include_in_conflict_terms: boolean;
  applies_if_all?: MatchCondition[];
  applies_if_any?: MatchCondition[];
  required_if_all?: MatchCondition[];
  required_if_any?: MatchCondition[];
}

export type IntakeFieldType = "text" | "textarea" | "email" | "phone" | "date" | "number" | "boolean" | "choice" | "multichoice";

export interface IntakeSectionDefinition {
  key: string;
  title: string;
  description?: string | null;
}

export interface IntakeSummary {
  total_fields: number;
  applicable_fields: number;
  required_fields: number;
  valid_provided_fields: number;
  invalid_fields: number;
  missing_required_fields: string[];
  required_consents: number;
  accepted_required_consents: number;
  missing_required_consents: string[];
  conflict_parties: number;
  conflict_search_terms: number;
  completion_percent: number;
  required_completion_percent: number;
  ready_for_review: boolean;
}

export interface IntakeTemplateSummary {
  id: string;
  version: string;
  title: string;
  matter_type: string;
  client_type: string;
  jurisdiction: string;
  effective_from: string;
  effective_to: string | null;
  sections: IntakeSectionDefinition[];
  fields: IntakeFieldDefinition[];
  consents: ConsentDefinition[];
  source_note: string;
}

export interface IntegrationCatalogItem {
  provider: IntegrationProvider;
  title: string;
  description: string;
  capabilities: string[];
  required_config: string[];
  optional_config: string[];
  required_secrets: string[];
  official_docs: string[];
}

export interface IntegrationCheckResult {
  key: string;
  passed: boolean;
  message: string;
}

export interface IntegrationConnectionCreate {
  connection_key: string;
  display_name: string;
  provider: IntegrationProvider;
  capabilities?: string[];
  config?: Record<string, unknown>;
  secrets?: SecretReferenceInput[];
}

export interface IntegrationConnectionRead {
  id: string;
  organization_id: string;
  connection_key: string;
  display_name: string;
  provider: IntegrationProvider;
  status: IntegrationStatus;
  enabled: boolean;
  capabilities_json: unknown[];
  config_json: Record<string, unknown>;
  last_connected_at: string | null;
  last_error: string | null;
  created_by_membership_id: string;
  created_at: string;
  updated_at: string;
}

export interface IntegrationDashboard {
  connections: IntegrationConnectionRead[];
  health: IntegrationHealthRead[];
  provider_counts: Record<string, number>;
  connected_count: number;
  degraded_count: number;
}

export interface IntegrationHealthRead {
  id: string;
  connection_id: string;
  status: IntegrationStatus;
  checked_at: string;
  live_probe: boolean;
  latency_ms: number | null;
  checks_json: IntegrationCheckResult[];
  error_message: string | null;
}

export type IntegrationProvider = "google_workspace" | "razorpay" | "docusign" | "generic_webhook" | "official_legal_import";

export type IntegrationStatus = "draft" | "configured" | "connected" | "degraded" | "disabled";

export interface IntegrityCheckRead {
  id: string;
  feed_id: string | null;
  run_id: string | null;
  ingestion_item_id: string | null;
  check_kind: string;
  status: string;
  source_url: string | null;
  expected_value: string | null;
  actual_value: string | null;
  checked_at: string;
  details_json: Record<string, unknown>;
}

export interface IntelligenceSummaryRead {
  matter_id: string;
  facts: number;
  timeline_events: number;
  claims: number;
  admissions: number;
  denials: number;
  contradictions: number;
  open_review_items: number;
  source_documents: number;
  source_pages: number;
}

export interface InterestBreakdownLine {
  period_start: string;
  period_end: string;
  days: number;
  year_fraction: string;
  opening_principal: string;
  annual_rate_percent: string;
  method: InterestMethod;
  interest: string;
  adjustment_at_period_end: string;
  closing_principal: string;
  note?: string | null;
}

export type InterestMethod = "simple" | "compound";

export interface InvoiceCreate {
  client_id: string;
  matter_id?: string | null;
  fee_arrangement_id?: string | null;
  issue_date?: string | null;
  due_date?: string | null;
  currency: string;
  client_address?: string | null;
  client_gstin?: string | null;
  client_state_code?: string | null;
  place_of_supply?: string | null;
  reverse_charge: boolean;
  notes?: string | null;
  metadata?: Record<string, unknown>;
  lines?: InvoiceLineCreate[];
}

export interface InvoiceIssueRequest {
  irn?: string | null;
  acknowledgement_number?: string | null;
  acknowledgement_date?: string | null;
}

export interface InvoiceLineCreate {
  kind: InvoiceLineKind;
  source_time_entry_id?: string | null;
  source_expense_id?: string | null;
  description: string;
  service_code?: string | null;
  quantity: number | string;
  unit_price: number | string;
  discount_amount: number | string;
  cgst_rate: number | string;
  sgst_rate: number | string;
  igst_rate: number | string;
  cess_rate: number | string;
  metadata?: Record<string, unknown>;
}

export type InvoiceLineKind = "time" | "expense" | "fee" | "adjustment";

export interface InvoiceLineRead {
  id: string;
  kind: InvoiceLineKind;
  source_time_entry_id: string | null;
  source_expense_id: string | null;
  description: string;
  service_code: string | null;
  quantity: string;
  unit_price: string;
  discount_amount: string;
  taxable_amount: string;
  cgst_rate: string;
  sgst_rate: string;
  igst_rate: string;
  cess_rate: string;
  cgst_amount: string;
  sgst_amount: string;
  igst_amount: string;
  cess_amount: string;
  line_total: string;
  sort_order: number;
}

export interface InvoiceRead {
  id: string;
  client_id: string;
  matter_id: string | null;
  invoice_number: string;
  status: InvoiceStatus;
  issue_date: string | null;
  due_date: string | null;
  currency: string;
  supplier_name: string | null;
  supplier_address: string | null;
  supplier_gstin: string | null;
  supplier_state_code: string | null;
  client_name: string;
  client_address: string | null;
  client_gstin: string | null;
  client_state_code: string | null;
  place_of_supply: string | null;
  reverse_charge: boolean;
  subtotal: string;
  discount_total: string;
  taxable_total: string;
  cgst_total: string;
  sgst_total: string;
  igst_total: string;
  cess_total: string;
  tax_total: string;
  grand_total: string;
  amount_paid: string;
  amount_due: string;
  tax_treatment_reviewed: boolean;
  reviewed_at: string | null;
  issued_at: string | null;
  irn: string | null;
  acknowledgement_number: string | null;
  notes: string | null;
  lines?: InvoiceLineRead[];
  created_at: string;
}

export interface InvoiceReviewRequest {
  tax_treatment_reviewed: boolean;
  note?: string | null;
}

export type InvoiceStatus = "draft" | "review" | "issued" | "partially_paid" | "paid" | "void";

export interface IssueCreate {
  code: string;
  title: string;
  description?: string | null;
  burden_side?: string | null;
  priority: number;
}

export interface IssueLinkCreate {
  issue_id: string;
  link_type: EvidenceLinkType;
  rationale?: string | null;
}

export interface IssueLinkRead {
  id: string;
  matter_id: string;
  evidence_item_id: string;
  issue_id: string;
  link_type: EvidenceLinkType;
  confidence: number;
  rationale: string | null;
  source: string;
}

export interface IssueRead {
  id: string;
  matter_id: string;
  code: string;
  title: string;
  description: string | null;
  burden_side: string | null;
  priority: number;
  source: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export type ItemStatus = "present" | "completed" | "pending" | "missing" | "not_applicable";

export interface JobCreate {
  kind: JobKind;
  payload?: Record<string, unknown>;
  priority: JobPriority;
  queue_name?: string | null;
  matter_id?: string | null;
  resource_type?: string | null;
  resource_id?: string | null;
  idempotency_key?: string | null;
  max_attempts?: number | null;
  scheduled_at?: string | null;
  depends_on?: string[];
}

export interface JobDetail {
  job: JobRead;
  attempts: AttemptRead[];
  events: EventRead[];
  artifacts: ArtifactRead[];
}

export type JobKind = "document.reprocess" | "search.document_reindex" | "search.organization_rebuild" | "search.duplicate_scan" | "matter.intelligence_rebuild" | "evidence.matter_rebuild" | "analytics.snapshot" | "analytics.risk_rebuild" | "operations.due_sweep" | "corpus.resolve_citations" | "legal_data.feed_sync" | "legal_data.integrity_sweep" | "evidence.bundle_build" | "evidence.bundle_finalize" | "system.health_check" | "system.backup_run" | "system.restore_verify";

export type JobPriority = "low" | "normal" | "high" | "urgent";

export interface JobRead {
  id: string;
  organization_id: string;
  queue_name: string;
  kind: string;
  status: string;
  priority: string;
  priority_value: number;
  matter_id: string | null;
  resource_type: string | null;
  resource_id: string | null;
  payload_json: Record<string, unknown>;
  result_json: Record<string, unknown>;
  attempt_count: number;
  max_attempts: number;
  scheduled_at: string;
  started_at: string | null;
  finished_at: string | null;
  cancellation_requested_at: string | null;
  progress_current: number;
  progress_total: number;
  progress_message: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export type JobStatus = "queued" | "leased" | "running" | "retry_wait" | "succeeded" | "failed" | "cancelled" | "dead_letter";

export interface JobsDashboard {
  total: number;
  by_status: Record<string, number>;
  by_queue: Record<string, number>;
  online_workers: number;
  dead_letter: number;
  workers: WorkerRead[];
}

export type JournalEntryStatus = "posted" | "reversed";

export type JournalEntryType = "deposit" | "refund" | "disbursement" | "fee_transfer" | "adjustment" | "reversal";

export interface JudgmentImportParagraph {
  paragraph_number?: string | null;
  text: string;
  language: CorpusLanguage;
  metadata?: Record<string, unknown>;
}

export interface JudgmentImportRequest {
  source_code: string;
  external_id: string;
  case_title: string;
  case_number?: string | null;
  neutral_citation?: string | null;
  reported_citations?: string[];
  court_name: string;
  court_level: CourtLevel;
  jurisdiction: string;
  decision_date?: string | null;
  judges?: string[];
  bench_strength?: number | null;
  acts?: string[];
  sections?: string[];
  language: CorpusLanguage;
  source_url?: string | null;
  metadata?: Record<string, unknown>;
  paragraphs?: JudgmentImportParagraph[];
}

export interface JudgmentParagraphRead {
  id: string;
  paragraph_number: string | null;
  position: number;
  text: string;
  language: CorpusLanguage;
  metadata_json: Record<string, unknown>;
}

export interface JudgmentRead {
  id: string;
  external_id: string;
  case_title: string;
  case_number: string | null;
  neutral_citation: string | null;
  reported_citations_json: unknown[];
  court_name: string;
  court_level: CourtLevel;
  jurisdiction: string;
  decision_date: string | null;
  judges_json: unknown[];
  bench_strength: number | null;
  acts_json: unknown[];
  sections_json: unknown[];
  language: CorpusLanguage;
  source_url: string | null;
  metadata_json: Record<string, unknown>;
}

export interface JurisdictionPackCreate {
  pack_key: string;
  name: string;
  jurisdiction: string;
  state?: string | null;
  languages?: string[];
  description?: string | null;
  metadata?: Record<string, unknown>;
}

export interface JurisdictionPackRead {
  id: string;
  organization_id: string;
  pack_key: string;
  name: string;
  jurisdiction: string;
  state: string | null;
  languages_json: unknown[];
  status: string;
  active_release_version: string | null;
  description: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface JurisdictionPackSourceInput {
  source_id: string;
  feed_id?: string | null;
  required: boolean;
  maximum_age_hours: number;
  metadata?: Record<string, unknown>;
}

export interface JurisdictionReleaseCreate {
  version: string;
  effective_from?: string | null;
  effective_to?: string | null;
  notes?: string | null;
  sources: JurisdictionPackSourceInput[];
  metadata?: Record<string, unknown>;
}

export interface JurisdictionReleaseRead {
  id: string;
  pack_id: string;
  version: string;
  status: string;
  effective_from: string | null;
  effective_to: string | null;
  manifest_sha256: string;
  notes: string | null;
  approved_by_membership_id: string | null;
  activated_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface KYCRecordCreate {
  document_type: string;
  document_reference?: string | null;
  identifier_last4?: string | null;
  expires_on?: string | null;
  notes?: string | null;
}

export interface KYCRecordRead {
  id: string;
  client_id: string;
  document_type: string;
  status: KYCStatus;
  document_reference: string | null;
  identifier_last4: string | null;
  verified_at: string | null;
  expires_on: string | null;
  notes: string | null;
  created_at: string;
}

export type KYCStatus = "not_started" | "pending" | "verified" | "rejected" | "expired";

export interface KYCVerifyRequest {
  status: KYCStatus;
  notes?: string | null;
}

export type KnowledgeAnnotationKind = "note" | "warning" | "tip" | "outcome";

export interface KnowledgeAssetCreate {
  collection_id?: string | null;
  source_matter_id?: string | null;
  title: string;
  kind: KnowledgeAssetKind;
  language: KnowledgeLanguage;
  body_en?: string | null;
  body_hi?: string | null;
  summary?: string | null;
  jurisdiction: string | null;
  practice_area?: string | null;
  matter_type?: string | null;
  outcome_label?: string | null;
  tags?: string[];
  sources?: KnowledgeSourceCreate[];
  metadata_json?: Record<string, unknown>;
}

export interface KnowledgeAssetDetail {
  id: string;
  organization_id: string;
  collection_id: string | null;
  source_matter_id: string | null;
  title: string;
  kind: KnowledgeAssetKind;
  language: KnowledgeLanguage;
  status: KnowledgeAssetStatus;
  sanitization_status: SanitizationStatus;
  body_en: string | null;
  body_hi: string | null;
  summary: string | null;
  jurisdiction: string | null;
  practice_area: string | null;
  matter_type: string | null;
  outcome_label: string | null;
  quality_score: number;
  usage_count: number;
  content_hash: string;
  approved_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  sources?: KnowledgeSourceRead[];
  tags?: string[];
  source_access_restricted: boolean;
}

export type KnowledgeAssetKind = "pleading_section" | "contract_clause" | "argument" | "research_memo" | "authority_note" | "checklist" | "template" | "practice_note";

export interface KnowledgeAssetRead {
  id: string;
  organization_id: string;
  collection_id: string | null;
  source_matter_id: string | null;
  title: string;
  kind: KnowledgeAssetKind;
  language: KnowledgeLanguage;
  status: KnowledgeAssetStatus;
  sanitization_status: SanitizationStatus;
  body_en: string | null;
  body_hi: string | null;
  summary: string | null;
  jurisdiction: string | null;
  practice_area: string | null;
  matter_type: string | null;
  outcome_label: string | null;
  quality_score: number;
  usage_count: number;
  content_hash: string;
  approved_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type KnowledgeAssetStatus = "draft" | "in_review" | "approved" | "retired";

export interface KnowledgeAssetUpdate {
  collection_id?: string | null;
  title?: string | null;
  language?: KnowledgeLanguage | null;
  body_en?: string | null;
  body_hi?: string | null;
  summary?: string | null;
  jurisdiction?: string | null;
  practice_area?: string | null;
  matter_type?: string | null;
  outcome_label?: string | null;
  quality_score?: number | null;
  sanitization_status?: SanitizationStatus | null;
  metadata_json?: Record<string, unknown> | null;
}

export interface KnowledgeCollectionCreate {
  name: string;
  description?: string | null;
  practice_area?: string | null;
}

export interface KnowledgeCollectionRead {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  status: KnowledgeCollectionStatus;
  practice_area: string | null;
  created_at: string;
  updated_at: string;
}

export type KnowledgeCollectionStatus = "active" | "archived";

export interface KnowledgeDashboard {
  approved_assets: number;
  drafts_in_review: number;
  collections: number;
  approved_playbooks: number;
  authority_collections: number;
  total_reuse_count: number;
}

export type KnowledgeLanguage = "en" | "hi" | "bilingual";

export interface KnowledgeReviewRequest {
  sanitization_status: SanitizationStatus;
  review_note?: string | null;
}

export interface KnowledgeSearchResponse {
  query: string;
  normalized_query: string;
  result_count: number;
  results: KnowledgeSearchResult[];
}

export interface KnowledgeSearchResult {
  asset: KnowledgeAssetRead;
  score: number;
  lexical_score: number;
  quality_score: number;
  snippet: string;
  tags?: string[];
}

export interface KnowledgeSourceCreate {
  source_type: KnowledgeSourceType;
  source_id?: string | null;
  source_matter_id?: string | null;
  label: string;
  locator?: string | null;
  excerpt?: string | null;
  verified: boolean;
  metadata_json?: Record<string, unknown>;
}

export interface KnowledgeSourceRead {
  id: string;
  asset_id: string;
  source_type: KnowledgeSourceType;
  source_id: string | null;
  source_matter_id: string | null;
  label: string;
  locator: string | null;
  excerpt: string | null;
  verified: boolean;
  metadata_json: Record<string, unknown>;
}

export type KnowledgeSourceType = "matter" | "document" | "draft" | "draft_section" | "contract" | "contract_clause" | "judgment" | "judgment_paragraph" | "statute_section" | "manual";

export interface KnowledgeVersionRead {
  id: string;
  asset_id: string;
  version_number: number;
  label: string;
  title: string;
  body_en: string | null;
  body_hi: string | null;
  summary: string | null;
  content_hash: string;
  created_at: string;
}

export interface LanguageAnalyzeRequest {
  text: string;
}

export interface LanguageAnalyzeResponse {
  language: string;
  devanagari_ratio: number;
  latin_ratio: number;
  normalized_text: string;
  legal_references: LegalReference[];
}

export interface LeadCreate {
  name: string;
  company_name?: string | null;
  email?: string | null;
  phone?: string | null;
  source?: string | null;
  practice_area?: string | null;
  language: string;
  summary?: string | null;
  next_action?: string | null;
  next_action_at?: string | null;
  owner_membership_id?: string | null;
}

export interface LeadRead {
  id: string;
  organization_id: string;
  name: string;
  company_name: string | null;
  email: string | null;
  phone: string | null;
  source: string | null;
  practice_area: string | null;
  language: string;
  status: LeadStatus;
  summary: string | null;
  next_action: string | null;
  next_action_at: string | null;
  owner_membership_id: string | null;
  created_at: string;
  updated_at: string;
}

export type LeadStatus = "new" | "qualifying" | "conflict_check" | "onboarding" | "converted" | "lost";

export interface LeadUpdate {
  status?: LeadStatus | null;
  owner_membership_id?: string | null;
  next_action?: string | null;
  next_action_at?: string | null;
  summary?: string | null;
}

export interface LedgerRow {
  id: string;
  entry_date: string;
  entry_type: string;
  description: string;
  debit: string;
  credit: string;
  balance: string;
  currency: string;
  invoice_id?: string | null;
  payment_id?: string | null;
}

export interface LegalChecklistRequest {
  template_id: string;
  assessment_date: string;
  context?: Record<string, string>;
  items?: ChecklistItemInput[];
}

export interface LegalChecklistResponse {
  template_id: string;
  template_version: string;
  title: string;
  matter_type: string;
  jurisdiction: string;
  assessment_date: string;
  context_used: Record<string, string>;
  items: EvaluatedChecklistItem[];
  summary: ChecklistSummary;
  warnings: string[];
  markdown: string;
  source_note: string;
  disclaimer: string;
}

export interface LegalDataAlertRead {
  id: string;
  feed_id: string | null;
  run_id: string | null;
  kind: string;
  severity: string;
  status: string;
  dedupe_key: string;
  title: string;
  message: string;
  first_seen_at: string;
  last_seen_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  metadata_json: Record<string, unknown>;
}

export type LegalDataAlertStatus = "open" | "acknowledged" | "resolved";

export type LegalDataContentKind = "statute" | "judgment" | "mixed";

export interface LegalDataDashboard {
  feeds: number;
  stale_feeds: number;
  open_alerts: number;
  pending_amendments: number;
  runs_24h: number;
  failed_runs_24h: number;
  active_packs: number;
  latest_checkpoint: CorpusCheckpointRead | null;
  recent_runs: IngestionRunRead[];
  alerts: LegalDataAlertRead[];
}

export interface LegalDataFeedCreate {
  source_id: string;
  connection_id?: string | null;
  code: string;
  name: string;
  jurisdiction: string;
  state?: string | null;
  content_kind: LegalDataContentKind;
  mode: LegalDataFeedMode;
  allowed_domains?: string[];
  schedule_interval_minutes: number;
  stale_after_hours: number;
  import_path?: string | null;
  metadata?: Record<string, unknown>;
}

export type LegalDataFeedMode = "manual_manifest" | "filesystem_drop" | "integration_push";

export interface LegalDataFeedRead {
  id: string;
  organization_id: string;
  source_id: string;
  connection_id: string | null;
  code: string;
  name: string;
  jurisdiction: string;
  state: string | null;
  content_kind: string;
  mode: string;
  enabled: boolean;
  allowed_domains_json: unknown[];
  schedule_interval_minutes: number;
  stale_after_hours: number;
  import_path: string | null;
  cursor_json: Record<string, unknown>;
  last_checked_at: string | null;
  last_success_at: string | null;
  last_manifest_sha256: string | null;
  next_due_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface LegalDataFeedUpdate {
  enabled?: boolean | null;
  name?: string | null;
  allowed_domains?: string[] | null;
  schedule_interval_minutes?: number | null;
  stale_after_hours?: number | null;
  import_path?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface LegalDataManifest {
  source_label?: string | null;
  manifest_sha256?: string | null;
  items: LegalDataManifestItem[];
  metadata?: Record<string, unknown>;
}

export interface LegalDataManifestItem {
  kind: string;
  source_url: string;
  payload: Record<string, unknown>;
  source_sha256?: string | null;
}

// NOTE: app__tools__legal_deadline__models__DeadlineAdjustment shares a class name with app__models__procedure__DeadlineAdjustment; emitted as LegalDeadlineDeadlineAdjustment.

export interface LegalDeadlineDeadlineAdjustment {
  original_date: string;
  adjusted_date: string;
  reason: string;
}

export interface LegalDeadlineRequest {
  start_date: string;
  days: number;
  count_mode: CountMode;
  include_start_date: boolean;
  roll_if_non_business: boolean;
  excluded_dates?: string[];
  weekend_weekdays?: number[];
}

export interface LegalDeadlineResponse {
  start_date: string;
  due_date: string;
  days: number;
  count_mode: CountMode;
  include_start_date: boolean;
  excluded_dates_used: string[];
  adjustment?: LegalDeadlineDeadlineAdjustment | null;
  disclaimer: string;
}

export interface LegalDraftCreate {
  matter_id: string;
  draft_type: LegalDraftType;
  language: LegalDraftLanguage;
  title?: string | null;
  questionnaire_json?: Record<string, unknown>;
  selected_fact_ids?: string[];
  selected_timeline_event_ids?: string[];
  authority_refs?: AuthorityReference[];
}

export type LegalDraftLanguage = "en" | "hi" | "bilingual";

export interface LegalDraftListItem {
  id: string;
  matter_id: string;
  matter_title: string;
  title: string;
  draft_type: LegalDraftType;
  language: LegalDraftLanguage;
  status: LegalDraftStatus;
  health_score: number;
  open_high_findings: number;
  reviewed_sections: number;
  section_count: number;
  updated_at: string;
}

export interface LegalDraftRead {
  id: string;
  matter_id: string;
  template_id: string | null;
  title: string;
  draft_type: LegalDraftType;
  language: LegalDraftLanguage;
  status: LegalDraftStatus;
  court_name: string | null;
  case_number: string | null;
  questionnaire_json: Record<string, unknown>;
  health_score: number;
  generated_filename: string | null;
  approved_at: string | null;
  metadata_json: Record<string, unknown>;
  sections?: DraftSectionRead[];
  findings?: DraftFindingRead[];
  created_at: string;
  updated_at: string;
}

export type LegalDraftStatus = "draft" | "in_review" | "approved" | "superseded";

export type LegalDraftType = "legal_notice" | "notice_reply" | "affidavit" | "application" | "petition" | "written_statement" | "rejoinder" | "written_submissions" | "chronology" | "annexure_index" | "case_synopsis" | "hearing_note";

export interface LegalDraftUpdate {
  title?: string | null;
  language?: LegalDraftLanguage | null;
  questionnaire_json?: Record<string, unknown> | null;
}

export interface LegalDraftVersionRead {
  id: string;
  version_number: number;
  label: string;
  health_score: number;
  sha256: string | null;
  generated_filename: string | null;
  created_at: string;
}

export interface LegalHoldCreate {
  matter_id: string;
  label: string;
  reason: string;
}

export interface LegalHoldRead {
  id: string;
  organization_id: string;
  matter_id: string;
  label: string;
  reason: string;
  status: LegalHoldStatus;
  created_by_user_id: string | null;
  released_by_user_id: string | null;
  released_at: string | null;
  created_at: string;
  updated_at: string;
}

export type LegalHoldStatus = "active" | "released";

export interface LegalNoticeGenerationRequest {
  template_id: string;
  generation_date: string;
  fields?: Record<string, string>;
}

export interface LegalNoticeGenerationResponse {
  template_id: string;
  template_version: string;
  title: string;
  notice_type: string;
  jurisdiction: string;
  generation_date: string;
  subject: string;
  sections: RenderedNoticeSection[];
  rendered_text: string;
  fields_used: Record<string, string>;
  warnings: string[];
  source_note: string;
  disclaimer: string;
}

export interface LegalNoticeTemplateSummary {
  id: string;
  version: string;
  title: string;
  notice_type: string;
  jurisdiction: string;
  effective_from: string;
  effective_to: string | null;
  fields: TemplateField[];
  source_note: string;
}

export interface LegalReference {
  raw: string;
  normalized_type: string;
  number: string;
  canonical: string;
}

export interface LimitationExtension {
  days: number;
  reason?: string | null;
}

export interface LimitationPeriodRequest {
  trigger_date: string;
  period_value: number;
  period_unit: PeriodUnit;
  extension_periods?: LimitationExtension[];
  expiry_adjustment: ExpiryAdjustment;
  excluded_dates?: string[];
  weekend_weekdays?: number[];
}

export interface LimitationPeriodResponse {
  trigger_date: string;
  period_value: number;
  period_unit: PeriodUnit;
  base_expiry_date: string;
  total_extension_days: number;
  expiry_before_business_day_adjustment: string;
  final_expiry_date: string;
  expiry_adjustment?: ExpiryAdjustmentResult | null;
  excluded_dates_used: string[];
  calculation_notes: string[];
  disclaimer: string;
}

export interface LinkCaseMatterRequest {
  matter_id?: string | null;
  create_workspace: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
  organization_slug?: string | null;
  mfa_code?: string | null;
}

export interface LoginResponse {
  actor: ActorRead;
  organization: OrganizationRead;
  csrf_token: string;
  expires_at: string;
  absolute_expires_at: string;
}

export interface MFAConfirmRequest {
  code: string;
}

export interface MFAConfirmResponse {
  enabled: boolean;
  recovery_codes: string[];
}

export interface MFADisableRequest {
  password: string;
}

export interface MFAEnrolmentStart {
  secret: string;
  provisioning_uri: string;
  digits: number;
  period_seconds: number;
}

export interface MFAStatusRead {
  enabled: boolean;
  enrolment_started: boolean;
  confirmed_at?: string | null;
  last_used_at?: string | null;
  recovery_codes_remaining: number;
}

export type MatchBasis = "heading" | "body" | "heading_and_body";

export interface MatchCondition {
  field: string;
  values: string[];
}

export type MatterAccessLevel = "view" | "work" | "manage";

export type MatterAccessMode = "organization" | "explicit";

export interface MatterCreate {
  title: string;
  reference_number?: string | null;
  client_name?: string | null;
  court_name?: string | null;
  case_number?: string | null;
  cnr_number?: string | null;
  jurisdiction: string;
  description?: string | null;
  status: MatterStatus;
  primary_language: MatterLanguage;
}

export interface MatterDeadlineCreate {
  trigger_date: string;
  offset_days: number;
  day_basis: DayBasis;
  count_from_next_day: boolean;
  adjustment: DeadlineAdjustmentInput;
  holidays?: string[];
  title: string;
  matter_procedure_id?: string | null;
  trigger_type: string;
  trigger_id?: string | null;
  source_name?: string | null;
  source_url?: string | null;
  source_citation?: string | null;
  notes?: string | null;
}

export interface MatterGrantCreate {
  membership_id: string;
  effect: AccessEffect;
  access_level: MatterAccessLevel;
  allow_remote_ai?: boolean | null;
  allow_export?: boolean | null;
  expires_at?: string | null;
  reason?: string | null;
}

export interface MatterGrantRead {
  id: string;
  matter_id: string;
  membership_id: string;
  effect: AccessEffect;
  access_level: MatterAccessLevel;
  allow_remote_ai: boolean | null;
  allow_export: boolean | null;
  expires_at: string | null;
  reason: string | null;
  granted_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface MatterHealthRead {
  matter_id: string;
  title: string;
  reference_number: string | null;
  client_name: string | null;
  score: number;
  risk_level: string;
  overdue_tasks: number;
  high_priority_tasks: number;
  deadlines_due_7d: number;
  open_contradictions: number;
  open_high_draft_findings: number;
  unreviewed_court_changes: number;
  open_evidence_gaps: number;
  reasons: MatterHealthReason[];
}

export interface MatterHealthReason {
  key: string;
  count: number;
  weight: number;
  penalty: number;
  label: string;
}

export type MatterLanguage = "en" | "hi" | "bilingual";

export interface MatterOpenRequest {
  title: string;
  description?: string | null;
  practice_area?: string | null;
  primary_language: string;
  engagement_id?: string | null;
  team_membership_ids?: string[];
}

export interface MatterPlaybookCreate {
  code: string;
  name_en: string;
  name_hi?: string | null;
  description?: string | null;
  practice_area?: string | null;
  matter_type?: string | null;
  version: number;
}

export interface MatterPlaybookItemCreate {
  asset_id?: string | null;
  step_code: string;
  title_en: string;
  title_hi?: string | null;
  stage?: string | null;
  position: number;
  required: boolean;
  instructions?: string | null;
  metadata_json?: Record<string, unknown>;
}

export interface MatterPlaybookItemRead {
  id: string;
  playbook_id: string;
  asset_id: string | null;
  step_code: string;
  title_en: string;
  title_hi: string | null;
  stage: string | null;
  position: number;
  required: boolean;
  instructions: string | null;
  metadata_json: Record<string, unknown>;
}

export interface MatterPlaybookRead {
  id: string;
  organization_id: string;
  code: string;
  name_en: string;
  name_hi: string | null;
  description: string | null;
  practice_area: string | null;
  matter_type: string | null;
  version: number;
  status: MatterPlaybookStatus;
  approved_at: string | null;
  created_at: string;
}

export type MatterPlaybookStatus = "draft" | "approved" | "retired";

export interface MatterProcedureRead {
  id: string;
  matter_id: string;
  pack_id: string;
  pack_name: string;
  pack_version: number;
  status: MatterProcedureStatus;
  started_on: string | null;
  completed_on: string | null;
  notes: string | null;
  compliances?: ComplianceRead[];
  created_at: string;
  updated_at: string;
}

export type MatterProcedureStatus = "not_started" | "active" | "completed" | "closed";

export interface MatterRead {
  title: string;
  reference_number?: string | null;
  client_name?: string | null;
  court_name?: string | null;
  case_number?: string | null;
  cnr_number?: string | null;
  jurisdiction: string;
  description?: string | null;
  status: MatterStatus;
  primary_language: MatterLanguage;
  id: string;
  organization_id?: string | null;
  created_by_user_id?: string | null;
  created_at: string;
  updated_at: string;
  document_count: number;
}

export interface MatterSecurityProfileRead {
  id: string;
  matter_id: string;
  classification: ConfidentialityLevel;
  access_mode: MatterAccessMode;
  remote_ai_policy: PolicyDecision;
  export_policy: PolicyDecision;
  notes: string | null;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface MatterSecurityProfileUpdate {
  classification?: ConfidentialityLevel | null;
  access_mode?: MatterAccessMode | null;
  remote_ai_policy?: PolicyDecision | null;
  export_policy?: PolicyDecision | null;
  notes?: string | null;
}

export type MatterStatus = "active" | "on_hold" | "closed" | "archived";

export interface MatterUpdate {
  title?: string | null;
  reference_number?: string | null;
  client_name?: string | null;
  court_name?: string | null;
  case_number?: string | null;
  cnr_number?: string | null;
  jurisdiction?: string | null;
  description?: string | null;
  status?: MatterStatus | null;
  primary_language?: MatterLanguage | null;
}

export interface MembershipRead {
  id: string;
  organization_id: string;
  user_id: string;
  role: OrganizationRole;
  status: MembershipStatus;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  user?: SecurityUserRead | null;
}

export type MembershipStatus = "active" | "invited" | "suspended";

export interface MembershipUpdateRequest {
  role?: OrganizationRole | null;
  status?: MembershipStatus | null;
}

export interface MetricDefinitionRead {
  id: string;
  metric_key: string;
  name_en: string;
  name_hi: string | null;
  description: string | null;
  unit: string;
  direction: MetricDirection;
  formula_json: Record<string, unknown>;
}

export type MetricDirection = "higher_better" | "lower_better" | "neutral";

export interface MetricSnapshotRead {
  id: string;
  captured_at: string;
  overall_status: string;
  database_latency_ms: number | null;
  storage_free_bytes: number | null;
  storage_total_bytes: number | null;
  queue_oldest_age_seconds: number;
  dead_letter_count: number;
  slow_job_count: number;
  online_worker_count: number;
  stale_worker_count: number;
  search_index_age_seconds: number | null;
  tesseract_available: boolean;
  local_ai_configured: boolean;
  remote_ai_configured: boolean;
  snapshot_hash: string;
  metrics_json: Record<string, unknown>;
}

export interface NormalizedConflictParty {
  name: string;
  role: ConflictPartyRole;
  organization: string | null;
  aliases: string[];
  notes: string | null;
}

export interface NoteCreate {
  title?: string | null;
  body: string;
  matter_id?: string | null;
  is_private: boolean;
}

export type NotificationChannel = "in_app" | "email" | "console";

export interface NotificationRead {
  id: string;
  matter_id: string | null;
  task_id: string | null;
  recipient_membership_id: string | null;
  channel: NotificationChannel;
  status: NotificationStatus;
  subject: string;
  body: string;
  scheduled_at: string;
  sent_at: string | null;
}

export type NotificationStatus = "pending" | "sent" | "failed" | "cancelled";

export type NumberingStyle = "numeric" | "alphabetic";

export interface OAuthStartRequest {
  redirect_uri: string;
  scopes?: string[];
}

export interface OAuthStartResult {
  authorization_url: string;
  expires_at: string;
  note: string;
}

export type ObligationType = "payment" | "notice" | "delivery" | "reporting" | "insurance" | "confidentiality" | "renewal" | "audit" | "compliance" | "performance" | "other";

export interface OcrAnalysisResponse {
  original_filename: string | null;
  page_count: number;
  selected_page_count: number;
  pages_planned_for_ocr: number;
  pages_with_existing_text: number;
  pages: OcrPagePlan[];
  tesseract_available: boolean;
  requested_languages: string[];
  missing_languages: string[];
  warnings: string[];
  disclaimer: string;
}

export interface OcrPagePlan {
  page_number: number;
  existing_text_chars: number;
  status: OcrPagePlanStatus;
}

export type OcrPagePlanStatus = "ocr" | "skip_existing_text" | "skip_not_selected";

export interface OfficialCaseImportRequest {
  record: CaseRecordData;
  save_case: boolean;
}

export interface OfficialLegalImportRequest {
  kind: string;
  source_url: string;
  payload: Record<string, unknown>;
  source_sha256?: string | null;
  feed_id?: string | null;
}

export interface OnboardingProgressRead {
  id: string;
  completed_steps_json: string[];
  current_step: string | null;
  completed_at: string | null;
  dismissed_at: string | null;
  updated_at: string;
}

export interface OnboardingProgressUpdate {
  completed_steps?: string[] | null;
  current_step?: string | null;
  complete: boolean;
  dismiss: boolean;
}

export interface OnboardingRead {
  id: string;
  client_id: string;
  status: string;
  conflict_check_id: string | null;
  identity_complete: boolean;
  address_complete: boolean;
  engagement_complete: boolean;
  conflict_cleared: boolean;
  notes: string | null;
  completed_at: string | null;
}

export interface OnboardingUpdate {
  address_complete?: boolean | null;
  engagement_complete?: boolean | null;
  notes?: string | null;
  mark_complete: boolean;
}

export interface OperationsDashboard {
  open_tasks: number;
  overdue_tasks: number;
  upcoming_hearings: number;
  unreviewed_court_changes: number;
  pending_notifications: number;
  active_trackers: number;
  high_priority_items: number;
}

export interface OperationsPreferenceRead {
  daily_agenda_enabled: boolean;
  daily_agenda_hour_local: number;
  due_soon_hours: number;
  overdue_escalation_hours: number;
  channels_json: unknown[];
}

export interface OperationsPreferenceUpdate {
  daily_agenda_enabled?: boolean | null;
  daily_agenda_hour_local?: number | null;
  due_soon_hours?: number | null;
  overdue_escalation_hours?: number | null;
  channels_json?: string[] | null;
}

// NOTE: app__schemas__operations__TemplateSeedResult shares a class name with app__schemas__drafting__TemplateSeedResult; emitted as OperationsTemplateSeedResult.

export interface OperationsTemplateSeedResult {
  created: number;
}

export interface OrganizationRead {
  id: string;
  name: string;
  slug: string;
  status: OrganizationStatus;
  default_language: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type OrganizationRole = "owner" | "admin" | "partner" | "lawyer" | "junior" | "paralegal" | "billing" | "read_only";

export type OrganizationStatus = "active" | "suspended";

export interface OutboundWebhookRequest {
  url: string;
  event_type: string;
  payload: Record<string, unknown>;
  idempotency_key?: string | null;
}

export type PageSize = "a4" | "letter";

export type PaginationMode = "none" | "auto" | "provided";

export interface ParseResponse {
  metadata: DocumentMetadata;
  text: string | null;
  pages: ParsedPage[];
  blocks: ParsedBlock[];
  headings: ParsedHeading[];
  tables: ParsedTable[];
  warnings: string[];
  disclaimer: string;
}

export interface ParsedBlock {
  block_index: number;
  block_type: BlockType;
  text: string;
  char_start: number;
  char_end: number;
  page_number?: number | null;
  paragraph_index?: number | null;
  table_index?: number | null;
  heading_level?: number | null;
}

export interface ParsedHeading {
  text: string;
  level: number | null;
  method: HeadingMethod;
  block_index: number;
  char_start: number;
  char_end: number;
  page_number?: number | null;
}

export interface ParsedPage {
  page_number: number;
  text: string;
  char_start: number;
  char_end: number;
}

export interface ParsedTable {
  table_index: number;
  rows: string[][];
  row_count: number;
  column_count: number;
  char_start: number;
  char_end: number;
}

export interface PaymentCreate {
  client_id: string;
  invoice_id?: string | null;
  amount: number | string;
  currency: string;
  payment_date: string;
  method: PaymentMethod;
  status: PaymentStatus;
  reference?: string | null;
  notes?: string | null;
}

export interface PaymentIntentCreate {
  provider_connection_id?: string | null;
  client_id: string;
  matter_id?: string | null;
  invoice_id?: string | null;
  amount: number | string;
  currency: string;
  expires_at?: string | null;
  metadata?: Record<string, unknown>;
}

export interface PaymentIntentRead {
  id: string;
  provider_connection_id: string | null;
  client_id: string;
  matter_id: string | null;
  invoice_id: string | null;
  amount: string;
  currency: string;
  status: PaymentIntentStatus;
  provider_reference: string | null;
  checkout_url: string | null;
  expires_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export type PaymentIntentStatus = "created" | "pending" | "succeeded" | "failed" | "cancelled" | "expired";

export interface PaymentLinkRequest {
  amount_paise: number;
  currency: string;
  description: string;
  reference_id?: string | null;
  customer_name?: string | null;
  customer_email?: string | null;
  customer_phone?: string | null;
  expire_by?: number | null;
  notify_email: boolean;
  notify_sms: boolean;
  allow_partial: boolean;
  internal_resource_type: string | null;
  internal_resource_id?: string | null;
}

export type PaymentMethod = "bank_transfer" | "upi" | "cheque" | "cash" | "card" | "other";

export interface PaymentProviderCreate {
  provider: PaymentProviderKind;
  enabled: boolean;
  mode: string;
  public_config?: Record<string, unknown>;
  secret_env_prefix?: string | null;
  notes?: string | null;
}

export type PaymentProviderKind = "manual" | "mock" | "razorpay" | "stripe" | "other";

export interface PaymentProviderRead {
  id: string;
  provider: PaymentProviderKind;
  enabled: boolean;
  mode: string;
  public_config_json: Record<string, unknown>;
  secret_env_prefix: string | null;
  notes: string | null;
}

export interface PaymentRead {
  id: string;
  client_id: string;
  invoice_id: string | null;
  amount: string;
  currency: string;
  payment_date: string;
  method: PaymentMethod;
  status: PaymentStatus;
  reference: string | null;
  notes: string | null;
  created_at: string;
}

export type PaymentStatus = "pending" | "cleared" | "failed" | "reversed";

export interface PerformanceResultCreate {
  scenario_id: string;
  latencies_ms?: number[];
  success_count: number;
  failure_count: number;
  duration_seconds: number;
  details_json?: Record<string, unknown>;
}

export interface PerformanceRunRead {
  id: string;
  scenario_id: string;
  status: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  requests_per_second: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  max_ms: number;
  error_rate: number;
  result_json: Record<string, unknown>;
  snapshot_hash: string | null;
  created_at: string;
}

export interface PerformanceScenarioRead {
  id: string;
  scenario_key: string;
  name: string;
  kind: string;
  enabled: boolean;
  critical: boolean;
  method: string;
  path: string;
  concurrency: number;
  request_count: number;
  timeout_seconds: number;
  max_p95_ms: number;
  min_success_rate: number;
  max_error_rate: number;
}

export type PeriodUnit = "days" | "weeks" | "months" | "years";

export type PilotCheckStatus = "pending" | "passed" | "failed" | "waived";

export interface PilotReadinessRead {
  id: string;
  campaign_id: string;
  check_key: string;
  category: string;
  label: string;
  required: boolean;
  status: PilotCheckStatus;
  evidence_json: Record<string, unknown>;
  note: string | null;
  reviewed_by_membership_id: string | null;
  reviewed_at: string | null;
}

export interface PilotReadinessUpdate {
  status: PilotCheckStatus;
  note?: string | null;
  evidence_json?: Record<string, unknown>;
}

export interface PlaybookCreate {
  name: string;
  owner_label: string;
  contract_type: ContractType;
  risk_profile: ContractRiskProfile;
  settings_json?: Record<string, unknown>;
  rules?: PlaybookRuleCreate[];
}

export interface PlaybookRead {
  id: string;
  name: string;
  owner_label: string;
  contract_type: ContractType;
  risk_profile: ContractRiskProfile;
  active: boolean;
  settings_json: Record<string, unknown>;
  rules?: PlaybookRuleRead[];
}

export type PlaybookRequirement = "required" | "optional" | "prohibited";

export interface PlaybookRuleCreate {
  code: string;
  clause_type: string;
  requirement: PlaybookRequirement;
  preferred_variant: string;
  risk_level: ContractRiskLevel;
  guidance_en: string;
  guidance_hi?: string | null;
  config_json?: Record<string, unknown>;
}

export interface PlaybookRuleRead {
  id: string;
  code: string;
  clause_type: string;
  requirement: PlaybookRequirement;
  preferred_variant: string;
  risk_level: ContractRiskLevel;
  guidance_en: string;
  guidance_hi: string | null;
  config_json: Record<string, unknown>;
}

export type PolicyDecision = "inherit" | "allow" | "deny";

export interface PortalAccessRead {
  id: string;
  client_id: string;
  contact_id: string | null;
  email: string;
  status: PortalAccessStatus;
  invited_at: string | null;
  activated_at: string | null;
  revoked_at: string | null;
  permissions_json: Record<string, unknown>;
}

export type PortalAccessStatus = "invited" | "active" | "revoked";

export interface PortalActivationRequest {
  invite_token: string;
  password: string;
}

export interface PortalClientApprovalDecision {
  status: ClientDocumentApprovalStatus;
  note?: string | null;
}

export interface PortalClientApprovalRead {
  id: string;
  matter_id: string;
  document_id: string;
  document_version_id: string;
  title: string;
  message: string | null;
  status: ClientDocumentApprovalStatus;
  responded_at: string | null;
  response_note: string | null;
  created_at: string;
}

export interface PortalDashboard {
  client_id: string;
  client_name: string;
  shares: PortalShareRead[];
  messages: PortalMessageRead[];
  requests: PortalRequestRead[];
  outstanding_invoice_count: number;
  outstanding_amount: string;
}

export interface PortalInviteCreate {
  contact_id?: string | null;
  email: string;
  permissions?: Record<string, unknown>;
}

export interface PortalLoginRequest {
  organization_slug: string;
  email: string;
  password: string;
}

export interface PortalMessageCreate {
  portal_access_id?: string | null;
  matter_id?: string | null;
  body: string;
}

export interface PortalMessageRead {
  id: string;
  matter_id: string | null;
  sender_type: string;
  body: string;
  sent_at: string;
  read_at: string | null;
}

export interface PortalRequestCreate {
  portal_access_id: string;
  matter_id?: string | null;
  request_type: string;
  title: string;
  description?: string | null;
  due_at?: string | null;
}

export interface PortalRequestRead {
  id: string;
  matter_id: string | null;
  request_type: string;
  title: string;
  description: string | null;
  status: PortalRequestStatus;
  due_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export type PortalRequestStatus = "open" | "in_progress" | "completed" | "cancelled";

export interface PortalRequestUpdate {
  status: PortalRequestStatus;
}

export interface PortalSessionRead {
  email: string;
  client_id: string;
  client_name: string;
  csrf_token: string;
  expires_at: string;
}

export interface PortalShareCreate {
  portal_access_id: string;
  matter_id?: string | null;
  share_type: PortalShareType;
  resource_id?: string | null;
  title: string;
  message?: string | null;
  can_download: boolean;
  metadata?: Record<string, unknown>;
}

export interface PortalShareRead {
  id: string;
  client_id: string;
  matter_id: string | null;
  share_type: PortalShareType;
  resource_id: string | null;
  title: string;
  message: string | null;
  can_download: boolean;
  shared_at: string;
  metadata_json: Record<string, unknown>;
}

export type PortalShareType = "document" | "invoice" | "matter_update";

export interface PrepQuestionCreate {
  issue_id?: string | null;
  evidence_item_id?: string | null;
  question: string;
  purpose?: string | null;
  question_type: string;
}

export interface PrepQuestionRead {
  id: string;
  matter_id: string;
  witness_id: string;
  issue_id: string | null;
  evidence_item_id: string | null;
  question: string;
  purpose: string | null;
  question_type: string;
  status: WitnessPrepStatus;
  source: string;
  metadata_json: Record<string, unknown>;
}

export interface PrincipalAdjustment {
  date: string;
  amount: number | string;
  note?: string | null;
}

// NOTE: app__schemas__procedure__AgendaItem shares a class name with app__schemas__operations__AgendaItem; emitted as ProcedureAgendaItem.

export interface ProcedureAgendaItem {
  kind: string;
  id: string;
  matter_id: string;
  title: string;
  when: string;
  status: string;
  requires_review: boolean;
  metadata?: Record<string, unknown>;
}

export interface ProcedurePackCreate {
  code: string;
  name_en: string;
  name_hi?: string | null;
  jurisdiction: string;
  proceeding_type: string;
  court_level?: string | null;
  description?: string | null;
  version: number;
  status: ProcedurePackStatus;
  effective_from?: string | null;
  effective_to?: string | null;
  source_name?: string | null;
  source_url?: string | null;
  source_citation?: string | null;
  verified: boolean;
  metadata_json?: Record<string, unknown>;
  steps?: ProcedureStepInput[];
  deadline_rules?: DeadlineRuleInput[];
}

export interface ProcedurePackRead {
  id: string;
  code: string;
  name_en: string;
  name_hi: string | null;
  jurisdiction: string;
  proceeding_type: string;
  court_level: string | null;
  description: string | null;
  version: number;
  status: ProcedurePackStatus;
  effective_from: string | null;
  effective_to: string | null;
  source_name: string | null;
  source_url: string | null;
  source_citation: string | null;
  verified: boolean;
  metadata_json: Record<string, unknown>;
  steps?: ProcedureStepRead[];
  deadline_rules?: DeadlineRuleRead[];
}

export type ProcedurePackStatus = "draft" | "active" | "deprecated";

export interface ProcedureStats {
  active_procedures: number;
  pending_compliances: number;
  upcoming_deadlines: number;
  overdue_deadlines: number;
  unreviewed_deadlines: number;
  upcoming_hearings: number;
  open_directions: number;
}

export interface ProcedureStepInput {
  code: string;
  sequence: number;
  name_en: string;
  name_hi?: string | null;
  description?: string | null;
  required: boolean;
  dependency_codes_json?: string[];
  checklist_json?: string[];
  metadata_json?: Record<string, unknown>;
}

export interface ProcedureStepRead {
  id: string;
  code: string;
  sequence: number;
  name_en: string;
  name_hi: string | null;
  description: string | null;
  required: boolean;
  dependency_codes_json: string[];
  checklist_json: string[];
  metadata_json: Record<string, unknown>;
}

export type ProcessingStatus = "pending" | "processing" | "ready" | "failed";

export interface PromoteContractClauseRequest {
  clause_id: string;
  collection_id?: string | null;
  title?: string | null;
  practice_area?: string | null;
  matter_type?: string | null;
  tags?: string[];
}

export interface PromoteDraftSectionRequest {
  section_id: string;
  collection_id?: string | null;
  title?: string | null;
  kind: KnowledgeAssetKind;
  practice_area?: string | null;
  matter_type?: string | null;
  tags?: string[];
}

export interface QADashboard {
  suites: EvaluationSuiteRead[];
  latest_runs: EvaluationRunRead[];
  default_gate: ReleaseGateRead | null;
  latest_gate_result: Record<string, unknown> | null;
  summary: Record<string, unknown>;
}

export interface QAFindingRead {
  id: string;
  run_id: string;
  case_run_id: string | null;
  category: string;
  severity: string;
  code: string;
  message: string;
  details_json: Record<string, unknown>;
  resolved: boolean;
  created_at: string;
}

export interface QualitySummary {
  draft_health_avg: number;
  approved_drafts_window: number;
  open_high_draft_findings: number;
  contract_health_avg: number;
  open_high_contract_risks: number;
  approved_knowledge_assets: number;
  knowledge_reuse: number;
  window_days?: number | null;
}

export interface QueueRead {
  id: string;
  organization_id: string;
  name: string;
  enabled: boolean;
  max_concurrency: number;
  max_per_minute: number;
  default_max_attempts: number;
  lease_seconds: number;
  metadata_json: Record<string, unknown>;
}

export interface QueueUpdate {
  enabled?: boolean | null;
  max_concurrency?: number | null;
  max_per_minute?: number | null;
  default_max_attempts?: number | null;
  lease_seconds?: number | null;
}

export interface RateCardCreate {
  name: string;
  currency: string;
  is_default: boolean;
  notes?: string | null;
}

export interface RateCreate {
  membership_id?: string | null;
  role_label?: string | null;
  hourly_rate: number | string;
  active_from?: string | null;
  active_to?: string | null;
}

export interface ReadinessCheck {
  key: string;
  passed: boolean;
  critical: boolean;
  message: string;
}

export interface RebuildResultRead {
  matter_id: string;
  facts: number;
  timeline_events: number;
  claims: number;
  admissions: number;
  denials: number;
  contradictions: number;
  open_review_items: number;
  source_documents: number;
  source_pages: number;
  rebuilt: boolean;
}

export interface RecentItemCreate {
  entity_type: SearchEntityType;
  entity_id: string;
  title: string;
  subtitle?: string | null;
  href: string;
  matter_id?: string | null;
  client_id?: string | null;
}

export interface RecentItemRead {
  id: string;
  entity_type: SearchEntityType;
  entity_id: string;
  title_snapshot: string;
  subtitle_snapshot: string | null;
  href: string;
  matter_id: string | null;
  client_id: string | null;
  opened_at: string;
  open_count: number;
}

export interface ReconciliationCreate {
  account_id: string;
  period_start: string;
  period_end: string;
  statement_ending_balance: number | string;
  notes?: string | null;
}

export interface ReconciliationRead {
  id: string;
  account_id: string;
  period_start: string;
  period_end: string;
  statement_ending_balance: string;
  ledger_ending_balance: string;
  difference: string;
  status: ReconciliationStatus;
  reviewed_by_user_id: string | null;
  reviewed_at: string | null;
  notes: string | null;
  created_at: string;
}

export type ReconciliationStatus = "draft" | "reviewed" | "locked";

export interface RecoveryObjectiveRead {
  id: string;
  target_rpo_minutes: number;
  target_rto_minutes: number;
  restore_verification_days: number;
  max_queue_lag_seconds: number;
  worker_stale_seconds: number;
  slow_job_seconds: number;
  min_storage_free_percent: number;
  max_database_latency_ms: number;
  metadata_json: Record<string, unknown>;
  updated_at: string;
}

export interface RecoveryObjectiveUpdate {
  target_rpo_minutes?: number | null;
  target_rto_minutes?: number | null;
  restore_verification_days?: number | null;
  max_queue_lag_seconds?: number | null;
  worker_stale_seconds?: number | null;
  slow_job_seconds?: number | null;
  min_storage_free_percent?: number | null;
  max_database_latency_ms?: number | null;
}

export interface RedlineRead {
  id: string;
  version_number: number;
  label: string;
  status: RedlineStatus;
  changes_json: Record<string, unknown>[];
  generated_filename: string;
  sha256: string;
  created_at: string;
}

export type RedlineStatus = "generated" | "superseded";

export type RelativeUnit = "business_days" | "days" | "weeks" | "months" | "years";

export interface ReleaseArtifactCreate {
  kind: string;
  filename: string;
  sha256: string;
  size_bytes: number;
  storage_path?: string | null;
  metadata_json?: Record<string, unknown>;
}

export interface ReleaseArtifactRead {
  id: string;
  kind: string;
  filename: string;
  sha256: string;
  size_bytes: number;
  metadata_json: Record<string, unknown>;
}

export interface ReleaseCandidateManifestRead {
  id: string;
  campaign_id: string;
  release_run_id: string | null;
  environment_id: string | null;
  candidate_version: string;
  database_revision: string | null;
  artifact_sha256: string | null;
  status: ReleaseCandidateStatus;
  gate_json: Record<string, unknown>;
  manifest_json: Record<string, unknown>;
  snapshot_hash: string;
  created_at: string;
}

export type ReleaseCandidateStatus = "draft" | "held" | "ready" | "approved";

export interface ReleaseDashboard {
  pipeline: ReleasePipelineRead;
  latest_runs: ReleaseRunRead[];
  performance_scenarios: PerformanceScenarioRead[];
  security_cases: SecurityCaseRead[];
  summary: Record<string, unknown>;
}

export interface ReleaseGateRead {
  id: string;
  organization_id: string;
  name: string;
  enabled: boolean;
  min_overall_score: number;
  max_critical_failures: number;
  require_security_zero_failures: boolean;
  require_citation_zero_failures: boolean;
  category_thresholds_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ReleaseGateSummary {
  passed: boolean;
  reasons: string[];
  critical_security_failures: number;
  stage_status: Record<string, string>;
  performance_runs: number;
  security_runs: number;
  rollback_ready: boolean;
  artifact_passed: boolean;
}

export interface ReleaseGateUpdate {
  min_overall_score?: number | null;
  max_critical_failures?: number | null;
  require_security_zero_failures?: boolean | null;
  require_citation_zero_failures?: boolean | null;
  category_thresholds_json?: Record<string, unknown> | null;
}

export interface ReleasePipelineRead {
  id: string;
  pipeline_key: string;
  name: string;
  version: number;
  enabled: boolean;
  require_qa_gate: boolean;
  require_security_zero_critical: boolean;
  require_migration_roundtrip: boolean;
  require_frontend_static: boolean;
  require_load_gate: boolean;
  thresholds_json: Record<string, unknown>;
}

export interface ReleaseRunCreate {
  build_ref?: string | null;
  commit_ref?: string | null;
  environment: string;
}

export interface ReleaseRunDetail {
  run: ReleaseRunRead;
  stages: ReleaseStageRead[];
  performance: PerformanceRunRead[];
  security: SecurityRunRead[];
  artifacts: ReleaseArtifactRead[];
  rollback_points: RollbackPointRead[];
  approvals: DeploymentApprovalRead[];
  gate: Record<string, unknown>;
}

export interface ReleaseRunRead {
  id: string;
  pipeline_id: string;
  status: string;
  app_version: string;
  build_ref: string | null;
  commit_ref: string | null;
  environment: string;
  qa_passed: boolean | null;
  security_passed: boolean | null;
  load_passed: boolean | null;
  migration_passed: boolean | null;
  frontend_passed: boolean | null;
  started_at: string | null;
  finished_at: string | null;
  summary_json: Record<string, unknown>;
  snapshot_hash: string | null;
  created_at: string;
}

export interface ReleaseStageRead {
  id: string;
  stage_key: string;
  kind: string;
  status: string;
  duration_ms: number;
  details_json: Record<string, unknown>;
  error: string | null;
}

export interface RemedyAnalysisRead {
  id: string;
  organization_id: string;
  matter_id: string | null;
  saved_case_id: string | null;
  language: string;
  status: RemedyAnalysisStatus;
  case_snapshot_json: Record<string, unknown>;
  context_json: Record<string, unknown>;
  disclaimer: string;
  analyzed_at: string;
  candidates?: RemedyCandidateRead[];
  coverage_warnings?: string[];
}

export interface RemedyAnalysisRequest {
  matter_id?: string | null;
  saved_case_id?: string | null;
  language: string;
  as_of_date?: string | null;
}

export type RemedyAnalysisStatus = "draft" | "review_required" | "reviewed" | "superseded";

export interface RemedyAuthorityInput {
  authority_type: RemedyAuthorityType;
  statute_section_id?: string | null;
  judgment_id?: string | null;
  citation?: string | null;
  proposition: string;
  source_url?: string | null;
  verified: boolean;
}

export interface RemedyAuthorityRead {
  id: string;
  authority_type: RemedyAuthorityType;
  statute_section_id: string | null;
  judgment_id: string | null;
  citation: string | null;
  proposition: string;
  source_url: string | null;
  verified: boolean;
}

export type RemedyAuthorityType = "statute" | "rule" | "judgment" | "constitution" | "procedure" | "other";

export interface RemedyCandidateRead {
  id: string;
  rule_id: string | null;
  remedy_code: string;
  remedy_name_en: string;
  remedy_name_hi: string | null;
  status: RemedyCandidateStatus;
  applicability_score: number;
  why_applicable_json: unknown[];
  forum_json: Record<string, unknown>;
  deadline_json: Record<string, unknown>;
  maintainability_json: Record<string, unknown>;
  required_documents_json: RemedyDocumentRequirement[];
  procedural_steps_json: unknown[];
  risks_json: unknown[];
  drafting_json: Record<string, unknown>;
  lawyer_note: string | null;
  reviewed_by_membership_id: string | null;
  reviewed_at: string | null;
  authorities?: RemedyAuthorityRead[];
}

export interface RemedyCandidateReview {
  status?: RemedyCandidateStatus | null;
  lawyer_note?: string | null;
}

export type RemedyCandidateStatus = "possible" | "conditional" | "not_maintainable" | "needs_research" | "selected" | "dismissed";

export interface RemedyDocumentRequirement {
  name: string;
  available: boolean;
}

export interface RemedyDraftCreate {
  requested_document_kind: string;
  language: string;
  relief_requested?: string | null;
  additional_instructions?: string | null;
}

export interface RemedyDraftLinkRead {
  id: string;
  candidate_id: string;
  legal_draft_id: string;
  requested_document_kind: string;
}

export interface RemedyMemoCreate {
  language: string;
}

export interface RemedyMemoRead {
  id: string;
  candidate_id: string;
  language: string;
  status: RemedyMemoStatus;
  content: string;
  source_snapshot_json: Record<string, unknown>;
  generated_deterministically: boolean;
  ai_run_id: string | null;
  reviewed_by_membership_id: string | null;
  reviewed_at: string | null;
}

export type RemedyMemoStatus = "draft" | "review_required" | "approved";

export type RemedyPackStatus = "draft" | "active" | "deprecated";

export interface RemedyRuleInput {
  code: string;
  remedy_name_en: string;
  remedy_name_hi?: string | null;
  description_en: string;
  description_hi?: string | null;
  priority: number;
  case_stage_patterns_json?: string[];
  status_patterns_json?: string[];
  court_level_patterns_json?: string[];
  order_type_patterns_json?: string[];
  act_patterns_json?: string[];
  section_patterns_json?: string[];
  requires_final_order: boolean;
  requires_latest_order: boolean;
  forum_json?: Record<string, unknown>;
  limitation_json?: Record<string, unknown>;
  maintainability_json?: Record<string, unknown>;
  required_documents_json?: Record<string, unknown> | string[];
  procedural_steps_json?: string[];
  risks_json?: string[];
  drafting_json?: Record<string, unknown>;
  verified: boolean;
  metadata_json?: Record<string, unknown>;
  authorities?: RemedyAuthorityInput[];
}

export interface RemedyRulePackCreate {
  code: string;
  name_en: string;
  name_hi?: string | null;
  jurisdiction: string;
  proceeding_type?: string | null;
  court_level?: string | null;
  version: number;
  status: RemedyPackStatus;
  effective_from?: string | null;
  effective_to?: string | null;
  source_name?: string | null;
  source_url?: string | null;
  source_citation?: string | null;
  verified: boolean;
  metadata_json?: Record<string, unknown>;
  rules?: RemedyRuleInput[];
}

export interface RenderedAffidavitSection {
  id: string;
  heading: string | null;
  body: string;
}

export interface RenderedAffidavitStatement {
  number: number;
  text: string;
  source_reference: string | null;
}

export interface RenderedIndexDocument {
  sequence: number;
  label: string;
  title: string;
  document_date: string | null;
  description: string | null;
  category: string | null;
  source_file: string | null;
  page_count: number | null;
  start_page: number | null;
  end_page: number | null;
  page_range: string | null;
  notes: string | null;
  confidential: boolean;
}

export interface RenderedNoticeSection {
  id: string;
  heading: string | null;
  body: string;
}

export interface RenderedTimelineEvent {
  sequence: number;
  sort_date: string;
  display_date: string;
  start_date: string;
  end_date: string | null;
  title: string;
  description: string | null;
  event_type: TimelineEventType;
  importance: TimelineImportance;
  parties: string[];
  source_references: TimelineSourceReference[];
  tags: string[];
  days_since_previous: number | null;
}

export type RequirementLevel = "required" | "recommended" | "optional";

export interface ResearchCollectionCreate {
  name: string;
  description?: string | null;
  practice_area?: string | null;
  issue_key?: string | null;
}

export interface ResearchCollectionItemCreate {
  judgment_id: string;
  paragraph_id?: string | null;
  position: number;
  proposition?: string | null;
  note?: string | null;
  verified: boolean;
}

export interface ResearchCollectionItemRead {
  id: string;
  collection_id: string;
  judgment_id: string;
  paragraph_id: string | null;
  position: number;
  proposition: string | null;
  note: string | null;
  verified: boolean;
  metadata_json: Record<string, unknown>;
}

export interface ResearchCollectionRead {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  practice_area: string | null;
  issue_key: string | null;
  status: ResearchCollectionStatus;
  approved_at: string | null;
  created_at: string;
}

export type ResearchCollectionStatus = "draft" | "approved" | "retired";

// NOTE: app__schemas__research__SourceRead shares a class name with app__schemas__intelligence__SourceRead; emitted as ResearchSourceRead.

export interface ResearchSourceRead {
  id: string;
  code: string;
  name: string;
  kind: string;
  base_url: string | null;
  jurisdiction: string;
  official: boolean;
  access_mode: string;
  enabled: boolean;
  notes: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface RestoreDrillRead {
  id: string;
  organization_id: string;
  backup_run_id: string;
  status: string;
  scope: string;
  started_at: string | null;
  finished_at: string | null;
  reviewed_at: string | null;
  database_verified: boolean;
  documents_verified: boolean;
  artifact_hashes_verified: boolean;
  document_count_verified: number;
  result_hash: string | null;
  notes: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface RestoreDrillReview {
  notes?: string | null;
}

export interface RetentionPolicyCreate {
  resource_type: RetentionResourceType;
  retention_days: number;
  enabled: boolean;
  auto_delete_enabled: boolean;
  notes?: string | null;
}

export interface RetentionPolicyRead {
  id: string;
  organization_id: string;
  resource_type: RetentionResourceType;
  retention_days: number;
  enabled: boolean;
  auto_delete_enabled: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export type RetentionResourceType = "matter" | "document" | "ai_run" | "draft" | "contract" | "audit";

export interface ReviewClauseRead {
  id: string;
  clause_type: string;
  heading: string | null;
  source_text: string;
  position: number;
  classification_confidence: number;
  matched_template_id: string | null;
  similarity: number;
  deviation_status: ClauseDeviationStatus;
  suggested_title_en: string | null;
  suggested_title_hi: string | null;
  suggested_body_en: string | null;
  suggested_body_hi: string | null;
  decision: string | null;
  metadata_json: Record<string, unknown>;
}

export interface ReviewFindingRead {
  id: string;
  review_clause_id: string | null;
  rule_code: string;
  clause_type: string | null;
  title: string;
  explanation: string;
  recommended_action: string;
  level: ContractRiskLevel;
  status: ReviewFindingStatus;
  metadata_json: Record<string, unknown>;
}

export type ReviewFindingStatus = "open" | "resolved" | "accepted" | "ignored";

export interface ReviewItemRead {
  id: string;
  matter_id: string;
  item_type: ReviewItemType;
  target_id: string;
  title: string;
  reason: string;
  priority: ReviewPriority;
  status: ReviewStatus;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type ReviewItemType = "fact" | "contradiction" | "statement";

export interface ReviewItemUpdate {
  status: ReviewStatus;
}

export type ReviewPriority = "low" | "medium" | "high";

export interface ReviewRequestCreate {
  document_version_id?: string | null;
  assigned_to_membership_id: string;
  due_at?: string | null;
  note?: string | null;
}

export interface ReviewRequestRead {
  id: string;
  document_id: string;
  document_version_id: string | null;
  matter_id: string;
  requested_by_user_id: string;
  assigned_to_membership_id: string;
  status: ReviewRequestStatus;
  due_at: string | null;
  note: string | null;
  completed_at: string | null;
  created_at: string;
}

export type ReviewRequestStatus = "open" | "in_review" | "approved" | "changes_requested" | "cancelled";

export interface ReviewStats {
  reviews: number;
  clauses: number;
  open_high_risks: number;
  redlines: number;
}

export type ReviewStatus = "open" | "confirmed" | "rejected" | "dismissed";

export interface RiskRead {
  id: string;
  rule_code: string;
  clause_type: string | null;
  title: string;
  explanation: string;
  level: ContractRiskLevel;
  status: ContractRiskStatus;
  metadata_json: Record<string, unknown>;
}

export interface RiskRebuildSummary {
  created: number;
  updated: number;
  resolved: number;
  active: number;
  message?: string | null;
}

export interface RiskSignalRead {
  id: string;
  matter_id: string | null;
  client_id: string | null;
  membership_id: string | null;
  signal_type: string;
  severity: AnalyticsRiskSeverity;
  status: AnalyticsRiskStatus;
  title: string;
  explanation: string;
  metric_key: string | null;
  observed_value: number | null;
  threshold_value: number | null;
  detected_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  metadata_json: Record<string, unknown>;
}

export interface RiskSignalUpdate {
  status: AnalyticsRiskStatus;
}

export interface RiskUpdate {
  status: ContractRiskStatus;
}

export interface RollbackPointCreate {
  database_revision?: string | null;
  release_artifact_id?: string | null;
  backup_run_id?: string | null;
  notes?: string | null;
  verified: boolean;
}

export interface RollbackPointRead {
  id: string;
  app_version: string;
  database_revision: string | null;
  status: string;
  verified_at: string | null;
  notes: string | null;
}

export interface RuleDeadlineCreate {
  deadline_rule_id: string;
  trigger_date: string;
  matter_procedure_id?: string | null;
  trigger_type: string;
  trigger_id?: string | null;
  holidays?: string[];
  notes?: string | null;
}

export interface RuntimeReadiness {
  ready: boolean;
  checks: ReadinessCheck[];
  app_version: string;
  build_ref: string | null;
  commit_ref: string | null;
}

export type SanitizationStatus = "not_reviewed" | "reviewed" | "not_required";

export interface SavedCaseChange {
  id: string;
  field: string;
  change_type: string;
  old?: unknown;
  new?: unknown;
  summary: string;
  detected_at: string;
}

export interface SavedCaseDetailRead {
  id: string;
  matter_id: string | null;
  record: CaseRecordData;
  changes?: SavedCaseChange[];
  stale: boolean;
}

export interface SavedCaseSummaryRead {
  id: string;
  matter_id: string | null;
  cnr: string | null;
  case_type: string | null;
  case_number: string;
  year: number | null;
  case_title: string | null;
  court_name: string;
  district: string | null;
  state: string | null;
  case_status: string | null;
  case_stage: string | null;
  next_hearing_date: string | null;
  source_name: string;
  fetched_at: string;
  stale_after: string | null;
}

export interface SavedSearchCreate {
  name: string;
  query: string;
  scopes?: SearchEntityType[];
  filters?: Record<string, unknown>;
  pinned: boolean;
}

export interface SavedSearchRead {
  id: string;
  name: string;
  query: string;
  scopes_json: SearchEntityType[];
  filters_json: Record<string, unknown>;
  pinned: boolean;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SearchDuplicateItem {
  id: string;
  kind: string;
  similarity: number;
  hamming_distance: number;
  shingle_jaccard: number;
  left: SearchDuplicateSide;
  right: SearchDuplicateSide;
}

export interface SearchDuplicateSide {
  title: string;
  href: string;
  matter_id?: string | null;
}

export type SearchEntityType = "matter" | "client" | "document" | "fact" | "evidence" | "witness" | "contract" | "draft" | "deadline" | "hearing" | "task" | "invoice" | "statute" | "judgment" | "precedent" | "communication";

export interface SearchGroup {
  entity_type: SearchEntityType;
  count: number;
  results: SearchResult[];
}

export interface SearchIndexHealth {
  entry_count: number;
  chunk_count: number;
  exact_duplicate_pairs: number;
  near_duplicate_pairs: number;
  by_entity: Record<string, number>;
  last_completed_job_at?: string | null;
  snapshot_hash: string;
}

export interface SearchIndexJobRead {
  id: string;
  kind: string;
  status: string;
  entries_seen: number;
  entries_created: number;
  entries_updated: number;
  entries_deleted: number;
  duplicates_detected: number;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}

export interface SearchPreferenceRead {
  id: string;
  default_scopes_json: SearchEntityType[];
  default_language: string;
  max_results: number;
  include_legal_corpus: boolean;
  show_recent_items: boolean;
  command_palette_enabled: boolean;
}

export interface SearchPreferenceUpdate {
  default_scopes_json?: SearchEntityType[] | null;
  default_language?: string | null;
  max_results?: number | null;
  include_legal_corpus?: boolean | null;
  show_recent_items?: boolean | null;
  command_palette_enabled?: boolean | null;
}

export interface SearchResult {
  entity_type: SearchEntityType;
  entity_id: string;
  title: string;
  subtitle?: string | null;
  snippet: string;
  href: string;
  score: number;
  badges?: string[];
  matter_id?: string | null;
  client_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface SearchResultRead {
  id: string;
  result_type: string;
  title: string;
  subtitle: string | null;
  snippet: string;
  score: number;
  authority_score: number;
  lexical_score: number;
  language_score: number;
  source_name: string;
  source_url: string | null;
  court_level?: CourtLevel | null;
  court_name?: string | null;
  decision_date?: string | null;
  act_title?: string | null;
  section_number?: string | null;
  paragraph_number?: string | null;
  metadata?: Record<string, unknown>;
}

export type SearchScope = "all" | "statutes" | "judgments";

export interface SecretReferenceInput {
  secret_key: string;
  reference: string;
  required: boolean;
}

export type SecretReferenceProvider = "environment" | "docker_secret" | "vault" | "cloud_secret_manager" | "kubernetes_secret" | "other";

export interface SecurityCaseRead {
  id: string;
  case_key: string;
  title: string;
  kind: string;
  enabled: boolean;
  critical: boolean;
  description: string | null;
  request_json: Record<string, unknown>;
  expected_json: Record<string, unknown>;
}

export interface SecurityOverviewRead {
  actor: ActorRead;
  organization: OrganizationRead;
  policy: SecurityPolicyRead;
  members: number;
  active_sessions: number;
  restricted_matters: number;
  ethical_wall_matters: number;
  active_legal_holds: number;
  pending_deletions: number;
  audit_entries: number;
}

export interface SecurityPolicyRead {
  id: string;
  organization_id: string;
  session_idle_timeout_minutes: number;
  session_absolute_lifetime_hours: number;
  max_concurrent_sessions: number;
  password_min_length: number;
  max_failed_login_attempts: number;
  lockout_minutes: number;
  allow_remote_ai_default: boolean;
  allow_exports_default: boolean;
  require_mfa_for_remote_ai: boolean;
  require_mfa_for_highly_confidential: boolean;
  audit_log_retention_days: number;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SecurityPolicyUpdate {
  session_idle_timeout_minutes?: number | null;
  session_absolute_lifetime_hours?: number | null;
  max_concurrent_sessions?: number | null;
  password_min_length?: number | null;
  max_failed_login_attempts?: number | null;
  lockout_minutes?: number | null;
  allow_remote_ai_default?: boolean | null;
  allow_exports_default?: boolean | null;
  require_mfa_for_remote_ai?: boolean | null;
  require_mfa_for_highly_confidential?: boolean | null;
  audit_log_retention_days?: number | null;
}

export interface SecurityResultCreate {
  case_id: string;
  actual_json?: Record<string, unknown>;
  error?: string | null;
}

export interface SecurityRunRead {
  id: string;
  case_id: string;
  status: string;
  actual_json: Record<string, unknown>;
  details_json: Record<string, unknown>;
  error: string | null;
  snapshot_hash: string | null;
  created_at: string;
}

export interface SecurityUserRead {
  id: string;
  email: string;
  display_name: string;
  status: UserStatus;
  locale: string;
  mfa_enrolled: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SignerCreate {
  name: string;
  email: string;
  role?: string | null;
  signing_order: number;
}

export interface SignerRead {
  id: string;
  envelope_id: string;
  name: string;
  email: string;
  role: string | null;
  signing_order: number;
  status: ESignatureSignerStatus;
  signed_at: string | null;
}

export interface SnapshotCreate {
  kind: SnapshotKind;
  notes?: string | null;
}

export type SnapshotKind = "manual" | "daily" | "weekly" | "monthly";

export interface SnapshotRead {
  id: string;
  organization_id: string;
  kind: SnapshotKind;
  period_start: string;
  period_end: string;
  generated_by_membership_id: string | null;
  payload_hash: string;
  summary_json: Record<string, unknown>;
  notes: string | null;
  created_at: string;
}

export interface SourceRead {
  id: string;
  document_id: string;
  filename?: string | null;
  page_id: string | null;
  page_number: number | null;
  relation: SourceRelation;
  quote: string;
  start_char: number | null;
  end_char: number | null;
  confidence: number;
}

export type SourceRelation = "supports" | "contradicts" | "context";

export interface StageResultCreate {
  status: string;
  duration_ms: number;
  details_json?: Record<string, unknown>;
  error?: string | null;
}

export interface StampDutyCalculationRequest {
  rule_pack_id: string;
  instrument_date: string;
  consideration_value?: number | string | null;
  market_value?: number | string | null;
  assessable_value?: number | string | null;
  include_optional_charge_codes?: string[];
}

export interface StampDutyCalculationResponse {
  rule_pack_id: string;
  rule_pack_version: string;
  jurisdiction: string;
  instrument_type: string;
  currency: string;
  instrument_date: string;
  valuation_basis: ValuationBasis;
  duty_base_value: string | null;
  base_duty: string;
  mandatory_charge_total: string;
  optional_charge_total: string;
  subtotal_before_limits: string;
  subtotal_after_limits: string;
  final_duty: string;
  breakdown: DutyBreakdownLine[];
  adjustments: string[];
  source_note: string;
  disclaimer: string;
}

export interface StampDutyRulePackSummary {
  id: string;
  version: string;
  jurisdiction: string;
  instrument_type: string;
  currency: string;
  effective_from: string;
  effective_to: string | null;
  valuation_basis: ValuationBasis;
  method: DutyMethod;
  source_note: string;
}

export type StatementKind = "claim" | "admission" | "denial";

export interface StatementRead {
  id: string;
  matter_id: string;
  document_id: string;
  filename?: string | null;
  page_id: string | null;
  page_number: number | null;
  kind: StatementKind;
  speaker_role: string | null;
  raw_text: string;
  normalized_text: string;
  confidence: number;
  start_char: number | null;
  end_char: number | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface StatuteImportRequest {
  source_code: string;
  external_id: string;
  title_en: string;
  title_hi?: string | null;
  short_title?: string | null;
  act_number?: string | null;
  act_year?: number | null;
  enactment_date?: string | null;
  ministry?: string | null;
  department?: string | null;
  jurisdiction: string;
  state?: string | null;
  source_url?: string | null;
  metadata?: Record<string, unknown>;
  sections?: StatuteImportSection[];
}

export interface StatuteImportSection {
  section_number: string;
  provision_type: string;
  heading_en?: string | null;
  heading_hi?: string | null;
  text_en?: string | null;
  text_hi?: string | null;
  effective_from?: string | null;
  effective_to?: string | null;
  version_label?: string | null;
  source_url?: string | null;
  metadata?: Record<string, unknown>;
}

export interface StatuteRead {
  id: string;
  external_id: string;
  title_en: string;
  title_hi: string | null;
  short_title: string | null;
  act_number: string | null;
  act_year: number | null;
  enactment_date: string | null;
  ministry: string | null;
  department: string | null;
  jurisdiction: string;
  state: string | null;
  is_active: boolean;
  source_url: string | null;
  metadata_json: Record<string, unknown>;
}

export interface StatuteSectionRead {
  id: string;
  statute_id: string;
  parent_id: string | null;
  section_key: string;
  section_number: string;
  provision_type: string;
  heading_en: string | null;
  heading_hi: string | null;
  text_en: string | null;
  text_hi: string | null;
  effective_from: string | null;
  effective_to: string | null;
  version_label: string | null;
  source_url: string | null;
  metadata_json: Record<string, unknown>;
}

export interface SupervisionMember {
  name: string;
  role: string;
  open: number;
  overdue: number;
  high: number;
}

export interface SupervisionSummary {
  team: Record<string, SupervisionMember>;
  total_open: number;
  generated_at: string;
}

export interface SupportedClauseType {
  clause_type: ClauseType;
  heading_terms: string[];
  body_pattern_count: number;
}

export interface SupportedPatternsResponse {
  absolute_date_formats: string[];
  relative_deadline_examples: string[];
  obligation_markers: string[];
  disclaimer: string;
}

export interface SweepRequest {
  horizon_hours: number;
  escalate_overdue_hours: number;
}

export interface SystemHealthDashboard {
  latest_run: HealthRunRead | null;
  components: HealthComponentRead[];
  open_incidents: IncidentRead[];
  recovery_objectives: RecoveryObjectiveRead;
  backup_policies: BackupPolicyRead[];
  recent_backups: BackupRunRead[];
  recent_restore_drills: RestoreDrillRead[];
  latest_metrics: MetricSnapshotRead | null;
}

export interface TaskCreate {
  title: string;
  description?: string | null;
  client_id?: string | null;
  matter_id?: string | null;
  lead_id?: string | null;
  assigned_membership_id?: string | null;
  due_at?: string | null;
  priority: CRMTaskPriority;
}

export interface TaskRead {
  id: string;
  title: string;
  description: string | null;
  client_id: string | null;
  matter_id: string | null;
  lead_id: string | null;
  assigned_membership_id: string | null;
  due_at: string | null;
  status: CRMTaskStatus;
  priority: CRMTaskPriority;
  completed_at: string | null;
  created_at: string;
}

export interface TaskUpdate {
  status?: CRMTaskStatus | null;
  priority?: CRMTaskPriority | null;
  assigned_membership_id?: string | null;
  due_at?: string | null;
}

export interface TeamPerformanceRead {
  membership_id: string;
  user_id: string;
  name: string;
  role: string;
  open_tasks: number;
  overdue_tasks: number;
  high_priority_tasks: number;
  completed_tasks_window: number;
  billable_minutes_window: number;
  submitted_minutes_window: number;
  workload_score: number;
}

export interface TemplateField {
  key: string;
  label: string;
  kind: FieldKind;
  required: boolean;
  max_length: number;
  help_text?: string | null;
}

export interface TemplateSeedResult {
  created: number;
}

export interface TimeEntryCreate {
  client_id?: string | null;
  matter_id?: string | null;
  work_date: string;
  minutes: number;
  narrative: string;
  billable: boolean;
  hourly_rate?: number | null;
  currency: string;
}

export interface TimeEntryRead {
  id: string;
  client_id: string | null;
  matter_id: string | null;
  user_id: string;
  work_date: string;
  minutes: number;
  narrative: string;
  billable: boolean;
  hourly_rate: number | null;
  currency: string;
  status: TimeEntryStatus;
  created_at: string;
}

export type TimeEntryStatus = "draft" | "submitted" | "approved" | "invoiced";

export interface TimelineEvent {
  event_date?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  title: string;
  description?: string | null;
  event_type: TimelineEventType;
  importance: TimelineImportance;
  parties?: string[];
  source_references?: TimelineSourceReference[];
  tags?: string[];
}

export interface TimelineEventRead {
  id: string;
  matter_id: string;
  event_key: string;
  event_type: string;
  event_date: string;
  title: string;
  description: string;
  confidence: number;
  metadata_json: Record<string, unknown>;
  sources?: TimelineSourceRead[];
  created_at: string;
  updated_at: string;
}

export type TimelineEventType = "fact" | "communication" | "filing" | "hearing" | "order" | "payment" | "contract" | "notice" | "evidence" | "other";

export type TimelineImportance = "low" | "normal" | "high" | "critical";

export interface TimelineSourceRead {
  id: string;
  document_id: string;
  filename?: string | null;
  page_id: string | null;
  page_number: number | null;
  quote: string;
  start_char: number | null;
  end_char: number | null;
  confidence: number;
}

export interface TimelineSourceReference {
  label: string;
  document_id?: string | null;
  page?: string | null;
  note?: string | null;
}

export interface TimelineSummary {
  event_count: number;
  first_date: string;
  last_date: string;
  span_days: number;
  critical_count: number;
  high_count: number;
  events_with_sources: number;
}

export interface TokenDiff {
  operation: DiffOperation;
  original: string;
  revised: string;
}

export interface TransferDecision {
  approve: boolean;
  note?: string | null;
}

export interface TransferRequestCreate {
  account_id: string;
  client_id: string;
  matter_id?: string | null;
  invoice_id?: string | null;
  amount: number | string;
  currency: string;
  justification: string;
}

export interface TransferRequestRead {
  id: string;
  account_id: string;
  client_id: string;
  matter_id: string | null;
  invoice_id: string | null;
  amount: string;
  currency: string;
  status: TransferRequestStatus;
  justification: string;
  requested_by_user_id: string;
  approved_by_user_id: string | null;
  approved_at: string | null;
  rejected_by_user_id: string | null;
  rejected_at: string | null;
  executed_by_user_id: string | null;
  executed_at: string | null;
  review_note: string | null;
  created_at: string;
}

export type TransferRequestStatus = "pending" | "approved" | "rejected" | "executed" | "cancelled";

export type UIContrast = "standard" | "high";

export type UIDensity = "comfortable" | "compact";

export type UIFontScale = "small" | "default" | "large" | "extra_large";

export type UILanguage = "en" | "hi" | "bilingual";

export interface UniversalSearchResponse {
  query: string;
  normalized_query: string;
  expanded_terms: string[];
  result_count: number;
  groups: SearchGroup[];
  results: SearchResult[];
}

export interface UserCreateRequest {
  email: string;
  display_name: string;
  password: string;
  locale: string;
  role: OrganizationRole;
}

export type UserStatus = "active" | "disabled";

export interface ValidationCampaignCreate {
  name: string;
  candidate_version: string;
  release_run_id?: string | null;
  environment_id?: string | null;
  build_ref?: string | null;
}

export interface ValidationCampaignDetail {
  campaign: ValidationCampaignRead;
  scenarios: ValidationScenarioRead[];
  runs: ValidationScenarioRunRead[];
  checks: PilotReadinessRead[];
  datasets: ValidationDatasetRead[];
  signoffs: ValidationSignoffRead[];
  manifest: ReleaseCandidateManifestRead | null;
  gate: Record<string, unknown>;
}

export interface ValidationCampaignRead {
  id: string;
  organization_id: string;
  release_run_id: string | null;
  environment_id: string | null;
  name: string;
  candidate_version: string;
  build_ref: string | null;
  status: ValidationCampaignStatus;
  started_at: string | null;
  finished_at: string | null;
  summary_json: Record<string, unknown>;
  snapshot_hash: string | null;
  created_at: string;
}

export type ValidationCampaignStatus = "draft" | "running" | "held" | "passed" | "approved";

export interface ValidationDashboard {
  scenarios: ValidationScenarioRead[];
  campaigns: ValidationCampaignRead[];
  summary: Record<string, unknown>;
}

export interface ValidationDatasetCreate {
  kind: ValidationDatasetKind;
  name: string;
  record_count: number;
  page_count: number;
  size_bytes: number;
  generation_seed?: number | null;
  manifest_path?: string | null;
  sha256: string;
  metadata_json?: Record<string, unknown>;
}

export type ValidationDatasetKind = "synthetic_documents" | "large_pdf" | "search_corpus" | "bilingual_corpus" | "security_fixtures";

export interface ValidationDatasetRead {
  id: string;
  organization_id: string;
  campaign_id: string | null;
  kind: ValidationDatasetKind;
  name: string;
  record_count: number;
  page_count: number;
  size_bytes: number;
  generation_seed: number | null;
  manifest_path: string | null;
  sha256: string;
  metadata_json: Record<string, unknown>;
}

export interface ValidationError {
  loc: string | number[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

export interface ValidationEvidenceCreate {
  kind: ValidationEvidenceKind;
  label: string;
  storage_path?: string | null;
  sha256?: string | null;
  size_bytes: number;
  metadata_json?: Record<string, unknown>;
}

export type ValidationEvidenceKind = "report" | "log" | "hash" | "screenshot" | "artifact" | "attestation";

export interface ValidationEvidenceRead {
  id: string;
  scenario_run_id: string;
  kind: ValidationEvidenceKind;
  label: string;
  storage_path: string | null;
  sha256: string | null;
  size_bytes: number;
  metadata_json: Record<string, unknown>;
}

export type ValidationExecutionMode = "local" | "staging" | "manual";

export type ValidationRunStatus = "pending" | "running" | "passed" | "failed" | "blocked" | "skipped";

export type ValidationScenarioKind = "e2e" | "security" | "load" | "recovery" | "accessibility" | "data_integrity" | "bilingual" | "large_document" | "workers" | "deployment";

export interface ValidationScenarioRead {
  id: string;
  scenario_key: string;
  name: string;
  description: string;
  kind: ValidationScenarioKind;
  execution_mode: ValidationExecutionMode;
  severity: ValidationSeverity;
  enabled: boolean;
  thresholds_json: Record<string, unknown>;
  instructions_json: Record<string, unknown>;
}

export interface ValidationScenarioResultCreate {
  scenario_id: string;
  status: ValidationRunStatus;
  duration_ms: number;
  metrics_json?: Record<string, unknown>;
  details_json?: Record<string, unknown>;
  error?: string | null;
}

export interface ValidationScenarioRunRead {
  id: string;
  campaign_id: string;
  scenario_id: string;
  status: ValidationRunStatus;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number;
  metrics_json: Record<string, unknown>;
  details_json: Record<string, unknown>;
  error: string | null;
  snapshot_hash: string | null;
}

export type ValidationSeverity = "advisory" | "required" | "critical";

export interface ValidationSignoffCreate {
  decision: ValidationSignoffDecision;
  role_label: string;
  note?: string | null;
}

export type ValidationSignoffDecision = "approve" | "reject";

export interface ValidationSignoffRead {
  id: string;
  campaign_id: string;
  membership_id: string;
  decision: ValidationSignoffDecision;
  role_label: string;
  note: string | null;
  decided_at: string;
}

export type ValuationBasis = "consideration" | "market_value" | "greater_of_consideration_or_market" | "assessable_value";

export type VersionSource = "upload" | "system" | "redline" | "signed";

export interface WebhookEndpointCreate {
  connection_id: string;
  endpoint_key: string;
  signing_secret_reference?: string | null;
  event_types?: string[];
}

export interface WebhookEndpointRead {
  id: string;
  organization_id: string;
  connection_id: string;
  endpoint_key: string;
  signing_secret_reference: string | null;
  enabled: boolean;
  event_types_json: unknown[];
  metadata_json: Record<string, unknown>;
}

export interface WebhookEventRead {
  id: string;
  endpoint_id: string;
  external_event_id: string;
  event_type: string;
  status: string;
  body_sha256: string;
  signature_valid: boolean;
  normalized_payload_json: Record<string, unknown>;
  received_at: string;
  processed_at: string | null;
  error_message: string | null;
}

export interface WitnessCreate {
  name: string;
  kind: WitnessKind;
  side?: string | null;
  role?: string | null;
  notes?: string | null;
}

export type WitnessKind = "fact" | "expert" | "formal" | "party" | "unknown";

export interface WitnessLinkCreate {
  evidence_item_id: string;
  relationship: string;
  rationale?: string | null;
}

export interface WitnessLinkRead {
  id: string;
  matter_id: string;
  witness_id: string;
  evidence_item_id: string;
  relationship: string;
  confidence: number;
  rationale: string | null;
}

export type WitnessPrepStatus = "draft" | "reviewed" | "used";

export interface WitnessRead {
  id: string;
  matter_id: string;
  name: string;
  normalized_name: string;
  kind: WitnessKind;
  side: string | null;
  role: string | null;
  notes: string | null;
  source: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface WorkerRead {
  id: string;
  organization_id: string;
  worker_key: string;
  hostname: string;
  pid: number;
  status: string;
  queues_json: unknown[];
  started_at: string;
  heartbeat_at: string;
  current_job_id: string | null;
  jobs_succeeded: number;
  jobs_failed: number;
}

export interface WorkflowTaskCreate {
  matter_id?: string | null;
  title: string;
  description?: string | null;
  assigned_membership_id?: string | null;
  priority: WorkflowTaskPriority;
  due_at?: string | null;
}

export type WorkflowTaskPriority = "low" | "medium" | "high" | "urgent";

export interface WorkflowTaskRead {
  id: string;
  organization_id: string;
  matter_id: string | null;
  workflow_run_id: string | null;
  source_event_id: string | null;
  assigned_membership_id: string | null;
  title: string;
  description: string | null;
  status: WorkflowTaskStatus;
  priority: WorkflowTaskPriority;
  due_at: string | null;
  completed_at: string | null;
  escalation_level: number;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type WorkflowTaskStatus = "todo" | "in_progress" | "done" | "cancelled";

export interface WorkflowTaskUpdate {
  status?: WorkflowTaskStatus | null;
  priority?: WorkflowTaskPriority | null;
  assigned_membership_id?: string | null;
  due_at?: string | null;
}

export interface WorkflowTemplateRead {
  id: string;
  organization_id: string | null;
  code: string;
  name_en: string;
  name_hi: string | null;
  description: string | null;
  version: number;
  status: WorkflowTemplateStatus;
  trigger_type: string;
  conditions_json: Record<string, unknown>;
  actions_json: unknown[];
  source_label: string | null;
  created_at: string;
  updated_at: string;
}

export type WorkflowTemplateStatus = "draft" | "active" | "disabled";

export interface documents_post {
  file: string;
}

export interface versions_post {
  file: string;
  change_note?: string | null;
}
