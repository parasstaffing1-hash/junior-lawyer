/**
 * Client for the deterministic legal tools mounted at /api/v1/tools.
 *
 * These engines are pure calculators on the server: same input, same output,
 * no model call. Types here mirror the Pydantic models in app/tools/<tool>/models.py.
 */
import { apiFetch, apiFetchBlob, jsonBody } from "@/lib/client";

export type CountMode = "calendar_days" | "business_days";
export type PeriodUnit = "days" | "weeks" | "months" | "years";
export type ExpiryAdjustment = "none" | "next_business_day";

export interface ToolDescriptor {
  key: string;
  href: string;
  name: string;
  nameHi: string;
  summary: string;
  group: "Dates & limitation" | "Money" | "Drafting" | "Documents & evidence" | "Review";
  interactive: boolean;
}

/** Drives the Tools index and the command palette. `interactive` marks the
 *  tools that currently have a built UI; the rest are API-only for now. */
export const TOOL_CATALOG: ToolDescriptor[] = [
  { key: "legal-deadlines", href: "/tools/legal-deadlines", name: "Deadline calculator", nameHi: "समय-सीमा गणक", summary: "Count calendar or business days from a trigger date, skipping weekends, court holidays and excluded dates.", group: "Dates & limitation", interactive: true },
  { key: "limitation-periods", href: "/tools/limitation-periods", name: "Limitation period", nameHi: "परिसीमा अवधि", summary: "Compute an expiry date from a trigger, with extensions and next-business-day adjustment.", group: "Dates & limitation", interactive: true },
  { key: "key-dates-obligations", href: "/tools/key-dates-obligations", name: "Key dates & obligations", nameHi: "मुख्य तिथियाँ", summary: "Extract dated obligations and deadlines from contract text.", group: "Dates & limitation", interactive: true },
  { key: "case-timelines", href: "/tools/case-timelines", name: "Case timeline", nameHi: "मामला समयरेखा", summary: "Build an ordered chronology from dated events.", group: "Dates & limitation", interactive: true },
  { key: "court-fees", href: "/tools/court-fees", name: "Court fee", nameHi: "न्यायालय शुल्क", summary: "Apply a verified fee rule pack to a claim value.", group: "Money", interactive: true },
  { key: "stamp-duty", href: "/tools/stamp-duty", name: "Stamp duty", nameHi: "स्टाम्प शुल्क", summary: "Apply a verified stamp-duty rule pack to an instrument value.", group: "Money", interactive: true },
  { key: "claim-interest", href: "/tools/claim-interest", name: "Claim interest", nameHi: "दावा ब्याज", summary: "Simple or compound interest across day-count conventions.", group: "Money", interactive: true },
  { key: "legal-notices", href: "/tools/legal-notices", name: "Legal notice", nameHi: "कानूनी नोटिस", summary: "Generate a notice from a reviewed template.", group: "Drafting", interactive: true },
  { key: "affidavits", href: "/tools/affidavits", name: "Affidavit", nameHi: "शपथपत्र", summary: "Generate an affidavit from a reviewed template.", group: "Drafting", interactive: true },
  { key: "client-intakes", href: "/tools/client-intakes", name: "Client intake", nameHi: "मुवक्किल इनटेक", summary: "Produce a structured intake record from a questionnaire.", group: "Drafting", interactive: true },
  { key: "legal-checklists", href: "/tools/legal-checklists", name: "Legal checklist", nameHi: "जाँच सूची", summary: "Evaluate a matter against a procedural checklist template.", group: "Review", interactive: true },
  { key: "contract-compare", href: "/tools/contract-compare", name: "Contract compare", nameHi: "अनुबंध तुलना", summary: "Clause-level diff between two contract versions.", group: "Review", interactive: true },
  { key: "contract-clauses", href: "/tools/contract-clauses", name: "Clause extractor", nameHi: "क्लॉज़ निष्कर्षण", summary: "Identify and classify clauses in a contract.", group: "Review", interactive: true },
  { key: "legal-citations", href: "/tools/legal-citations", name: "Citation tools", nameHi: "उद्धरण उपकरण", summary: "Extract and normalise legal citations from text.", group: "Review", interactive: true },
  { key: "evidence-indexes", href: "/tools/evidence-indexes", name: "Evidence index", nameHi: "साक्ष्य सूची", summary: "Build a paginated evidence index for filing.", group: "Documents & evidence", interactive: true },
  { key: "bates-numbering", href: "/tools/bates-numbering", name: "Bates numbering", nameHi: "बेट्स नंबरिंग", summary: "Stamp sequential Bates numbers onto a PDF.", group: "Documents & evidence", interactive: true },
  { key: "legal-ocr", href: "/tools/legal-ocr", name: "OCR", nameHi: "ओसीआर", summary: "Make a scanned PDF searchable, locally.", group: "Documents & evidence", interactive: true },
  { key: "legal-documents", href: "/tools/legal-documents", name: "Document parser", nameHi: "दस्तावेज़ पार्सर", summary: "Extract structure and text from PDF/DOCX.", group: "Documents & evidence", interactive: true },
  { key: "document-exports", href: "/tools/document-exports", name: "Document export", nameHi: "दस्तावेज़ निर्यात", summary: "Render a prepared document to PDF or DOCX.", group: "Documents & evidence", interactive: true },
];

export interface DeadlineAdjustment {
  original_date: string;
  adjusted_date: string;
  reason: string;
}

export interface LegalDeadlineRequest {
  start_date: string;
  days: number;
  count_mode?: CountMode;
  include_start_date?: boolean;
  roll_if_non_business?: boolean;
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
  adjustment: DeadlineAdjustment | null;
  disclaimer: string;
}

export function calculateDeadline(payload: LegalDeadlineRequest) {
  return apiFetch<LegalDeadlineResponse>("/tools/legal-deadlines/calculate", jsonBody(payload));
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
  expiry_adjustment?: ExpiryAdjustment;
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
  expiry_adjustment: DeadlineAdjustment | null;
  excluded_dates_used: string[];
  calculation_notes: string[];
  disclaimer: string;
}

export function calculateLimitationPeriod(payload: LimitationPeriodRequest) {
  return apiFetch<LimitationPeriodResponse>("/tools/limitation-periods/calculate", jsonBody(payload));
}

/** Rule packs are operational legal data. The engine refuses to calculate
 *  against a pack that has not been verified, so the picker shows their state. */
export interface RulePackSummary {
  pack_id: string;
  name: string;
  jurisdiction?: string | null;
  version?: number | string | null;
  verified?: boolean;
  [key: string]: unknown;
}

export function getCourtFeeRulePacks() {
  return apiFetch<RulePackSummary[]>("/tools/court-fees/rule-packs");
}

export function getStampDutyRulePacks() {
  return apiFetch<RulePackSummary[]>("/tools/stamp-duty/rule-packs");
}

export interface FeeCalculationResponse {
  [key: string]: unknown;
}

export function calculateCourtFee(payload: Record<string, unknown>) {
  return apiFetch<FeeCalculationResponse>("/tools/court-fees/calculate", jsonBody(payload));
}

export function calculateStampDuty(payload: Record<string, unknown>) {
  return apiFetch<FeeCalculationResponse>("/tools/stamp-duty/calculate", jsonBody(payload));
}

export function calculateClaimInterest(payload: Record<string, unknown>) {
  return apiFetch<Record<string, unknown>>("/tools/claim-interest/calculate", jsonBody(payload));
}

export function extractCitations(payload: Record<string, unknown>) {
  return apiFetch<Record<string, unknown>>("/tools/legal-citations/extract", jsonBody(payload));
}

export function getAffidavitTemplates() {
  return apiFetch<ToolTemplate[]>("/tools/affidavits/templates");
}

export function getLegalNoticeTemplates() {
  return apiFetch<ToolTemplate[]>("/tools/legal-notices/templates");
}

export function getChecklistTemplates() {
  return apiFetch<ToolTemplate[]>("/tools/legal-checklists/templates");
}

export function getOcrCapabilities() {
  return apiFetch<Record<string, unknown>>("/tools/legal-ocr/capabilities");
}

export function getParserFormats() {
  return apiFetch<Record<string, unknown>[]>("/tools/legal-documents/formats");
}

/** Upload endpoints take multipart with a JSON options blob alongside the file. */
function uploadForm(file: File, options: Record<string, unknown>): RequestInit {
  const form = new FormData();
  form.append("file", file);
  form.append("options_json", JSON.stringify(options));
  return { method: "POST", body: form };
}

export function analyzeOcr(file: File, options: Record<string, unknown> = {}) {
  return apiFetch<Record<string, unknown>>("/tools/legal-ocr/analyze", uploadForm(file, options));
}

export function processOcr(file: File, options: Record<string, unknown> = {}) {
  return apiFetchBlob("/tools/legal-ocr/process", uploadForm(file, options));
}

export function previewBates(file: File, options: Record<string, unknown> = {}) {
  return apiFetch<Record<string, unknown>>("/tools/bates-numbering/preview", uploadForm(file, options));
}

export function stampBates(file: File, options: Record<string, unknown> = {}) {
  return apiFetchBlob("/tools/bates-numbering/stamp", uploadForm(file, options));
}

export function parseLegalDocument(file: File, options: Record<string, unknown> = {}) {
  return apiFetch<Record<string, unknown>>("/tools/legal-documents/parse", uploadForm(file, options));
}

/* ---------------------------------------------------------------- */
/* Remaining tool endpoints                                          */
/* ---------------------------------------------------------------- */

export interface TemplateField {
  key: string;
  label?: string;
  title?: string;
  kind?: string;
  field_type?: string;
  required?: boolean;
  max_length?: number;
  section?: string;
  category?: string;
  requirement?: string;
  evidence_hint?: string;
  [key: string]: unknown;
}

export interface ToolTemplate {
  id: string;
  title: string;
  version?: string;
  jurisdiction?: string;
  source_note?: string;
  fields?: TemplateField[];
  context_fields?: TemplateField[];
  items?: TemplateField[];
  sections?: { key?: string; id?: string; title?: string; heading?: string | null; description?: string }[];
  [key: string]: unknown;
}

type Json = Record<string, unknown>;

export function formatCitation(payload: Json) {
  return apiFetch<Json>("/tools/legal-citations/format", jsonBody(payload));
}

export function extractKeyDates(payload: Json) {
  return apiFetch<Json>("/tools/key-dates-obligations/extract", jsonBody(payload));
}

export function getKeyDatePatterns() {
  return apiFetch<Json>("/tools/key-dates-obligations/patterns");
}

export function extractContractClauses(payload: Json) {
  return apiFetch<Json>("/tools/contract-clauses/extract", jsonBody(payload));
}

export function getClauseTypes() {
  return apiFetch<Json>("/tools/contract-clauses/types");
}

export function compareContracts(payload: Json) {
  return apiFetch<Json>("/tools/contract-compare/compare", jsonBody(payload));
}

export function generateCaseTimeline(payload: Json) {
  return apiFetch<Json>("/tools/case-timelines/generate", jsonBody(payload));
}

export function generateEvidenceIndex(payload: Json) {
  return apiFetch<Json>("/tools/evidence-indexes/generate", jsonBody(payload));
}

export function generateLegalNotice(payload: Json) {
  return apiFetch<Json>("/tools/legal-notices/generate", jsonBody(payload));
}

export function generateAffidavit(payload: Json) {
  return apiFetch<Json>("/tools/affidavits/generate", jsonBody(payload));
}

export function generateIntake(payload: Json) {
  return apiFetch<Json>("/tools/client-intakes/generate", jsonBody(payload));
}

export function evaluateChecklist(payload: Json) {
  return apiFetch<Json>("/tools/legal-checklists/evaluate", jsonBody(payload));
}

export function getIntakeTemplates() {
  return apiFetch<ToolTemplate[]>("/tools/client-intakes/templates");
}

export function getExportFormats() {
  return apiFetch<Json>("/tools/document-exports/formats");
}

export function previewExport(payload: Json) {
  return apiFetch<Json>("/tools/document-exports/preview", jsonBody(payload));
}

export function generateExport(payload: Json) {
  return apiFetchBlob("/tools/document-exports/generate", jsonBody(payload));
}
