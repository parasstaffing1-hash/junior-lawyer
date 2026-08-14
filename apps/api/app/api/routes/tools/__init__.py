"""Deterministic legal utility tools.

The engines under `app.tools` are pure functions with no database, auth or
FastAPI coupling, so these routers stay thin. Authentication and CSRF are
enforced for the whole `/api/v1` tree by SecurityMiddleware; the tools do not
add their own auth dependencies.

Sub-prefixes match the original CounselDesk API shape so tool clients written
against that surface keep working under the `/tools` namespace.
"""
from fastapi import APIRouter

from app.api.routes.tools import (
    affidavit,
    bates_numbering,
    case_timeline,
    cause_list_match,
    cheque_timeline,
    claim_interest,
    client_matter_intake,
    contract_clause_extractor,
    contract_compare,
    court_fee,
    document_export,
    evidence_index,
    key_dates_obligations,
    legal_checklist,
    legal_citation,
    legal_deadline,
    legal_document_parser,
    legal_notice,
    legal_ocr,
    limitation_period,
    maintenance_estimate,
    order_sheet,
    stamp_duty,
)

router = APIRouter(prefix="/tools")

_TOOL_ROUTERS = (
    (legal_deadline, "/legal-deadlines", "tools-legal-deadlines"),
    (cause_list_match, "/cause-list", "tools-cause-list"),
    (cheque_timeline, "/cheque-timeline", "tools-cheque-timeline"),
    (maintenance_estimate, "/maintenance-estimate", "tools-maintenance-estimate"),
    (order_sheet, "/order-sheet", "tools-order-sheet"),
    (limitation_period, "/limitation-periods", "tools-limitation-periods"),
    (court_fee, "/court-fees", "tools-court-fees"),
    (claim_interest, "/claim-interest", "tools-claim-interest"),
    (stamp_duty, "/stamp-duty", "tools-stamp-duty"),
    (legal_notice, "/legal-notices", "tools-legal-notices"),
    (affidavit, "/affidavits", "tools-affidavits"),
    (case_timeline, "/case-timelines", "tools-case-timelines"),
    (evidence_index, "/evidence-indexes", "tools-evidence-indexes"),
    (bates_numbering, "/bates-numbering", "tools-bates-numbering"),
    (legal_citation, "/legal-citations", "tools-legal-citations"),
    (contract_compare, "/contract-compare", "tools-contract-compare"),
    (contract_clause_extractor, "/contract-clauses", "tools-contract-clauses"),
    (key_dates_obligations, "/key-dates-obligations", "tools-key-dates-obligations"),
    (legal_document_parser, "/legal-documents", "tools-legal-documents"),
    (legal_ocr, "/legal-ocr", "tools-legal-ocr"),
    (legal_checklist, "/legal-checklists", "tools-legal-checklists"),
    (client_matter_intake, "/client-intakes", "tools-client-intakes"),
    (document_export, "/document-exports", "tools-document-exports"),
)

for module, prefix, tag in _TOOL_ROUTERS:
    router.include_router(module.router, prefix=prefix, tags=[tag])
