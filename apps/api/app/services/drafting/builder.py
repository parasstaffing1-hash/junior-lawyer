from __future__ import annotations

from datetime import date
from typing import Any

from app.models.drafting import DraftFindingLevel, DraftSourceType, LegalDraftType


COURT_DRAFTS = {
    LegalDraftType.AFFIDAVIT.value,
    LegalDraftType.APPLICATION.value,
    LegalDraftType.PETITION.value,
    LegalDraftType.WRITTEN_STATEMENT.value,
    LegalDraftType.REJOINDER.value,
    LegalDraftType.WRITTEN_SUBMISSIONS.value,
}

GROUNDS_DRAFTS = {
    LegalDraftType.APPLICATION.value,
    LegalDraftType.PETITION.value,
}

PARA_REPLY_DRAFTS = {
    LegalDraftType.NOTICE_REPLY.value,
    LegalDraftType.WRITTEN_STATEMENT.value,
    LegalDraftType.REJOINDER.value,
}

RELIEF_DRAFTS = {
    LegalDraftType.APPLICATION.value,
    LegalDraftType.PETITION.value,
    LegalDraftType.WRITTEN_SUBMISSIONS.value,
}


def format_date(value: Any) -> str:
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    return str(value or "")


def safe_facts(facts: list[dict], contradictions: list[dict]) -> tuple[list[dict], list[dict]]:
    conflicted_ids = {
        str(fact_id)
        for contradiction in contradictions
        if contradiction.get("status", "open") == "open"
        for fact_id in contradiction.get("fact_ids", [])
    }
    safe, excluded = [], []
    for fact in facts:
        if str(fact.get("id")) in conflicted_ids:
            excluded.append(fact)
        elif fact.get("status") != "rejected":
            safe.append(fact)
    return safe, excluded


def health_score(findings: list[dict]) -> int:
    penalties = {
        DraftFindingLevel.HIGH.value: 20,
        DraftFindingLevel.MEDIUM.value: 10,
        DraftFindingLevel.LOW.value: 4,
    }
    score = 100
    for finding in findings:
        if finding.get("status", "open") == "open":
            score -= penalties.get(str(finding.get("level")), 0)
    return max(0, score)


def source_spec(source_type: str, source_id: Any, label: str, locator: str | None = None, excerpt: str | None = None, verified: bool = True, metadata: dict | None = None) -> dict:
    return {
        "source_type": source_type,
        "source_id": source_id,
        "label": label,
        "locator": locator,
        "excerpt": excerpt,
        "verified": verified,
        "metadata": metadata or {},
    }


def _fact_block(facts: list[dict], *, hindi: bool = False) -> tuple[str, list[dict]]:
    if not facts:
        return (
            "सत्यापित सामग्री तथ्यों की समीक्षा एवं प्रविष्टि आवश्यक है।" if hindi
            else "Verified material facts require lawyer review and/or entry.",
            [],
        )
    lines, sources = [], []
    for index, fact in enumerate(facts, start=1):
        lines.append(f"{index}. {fact.get('label')}: {fact.get('value')}")
        src = fact.get("source") or {}
        if src:
            sources.append(source_spec(
                DraftSourceType.FACT.value,
                fact.get("id"),
                str(fact.get("label") or "Matter fact"),
                src.get("locator"),
                src.get("excerpt"),
                True,
            ))
    return "\n".join(lines), sources


def _timeline_block(events: list[dict], *, hindi: bool = False, limit: int = 40) -> tuple[str, list[dict]]:
    if not events:
        return ("कोई सत्यापित कालक्रम घटना उपलब्ध नहीं है।" if hindi else "No verified timeline events are available.", [])
    lines, sources = [], []
    for event in events[:limit]:
        lines.append(f"{format_date(event.get('date'))} — {event.get('title')}: {event.get('description')}")
        src = event.get("source") or {}
        sources.append(source_spec(
            DraftSourceType.TIMELINE.value,
            event.get("id"),
            str(event.get("title") or "Timeline event"),
            src.get("locator"),
            src.get("excerpt"),
            True,
        ))
    return "\n".join(lines), sources


def _annexure_block(documents: list[dict], prefix: str = "A", *, hindi: bool = False) -> tuple[str, list[dict]]:
    if not documents:
        return ("कोई दस्तावेज उपलब्ध नहीं है।" if hindi else "No matter documents are available.", [])
    lines, sources = [], []
    for index, document in enumerate(documents, start=1):
        page_text = f"{document.get('pages')} pages" if document.get("pages") else "page count pending"
        annexure = f"{prefix}-{index}"
        lines.append(f"Annexure {annexure} — {document.get('name')} — {page_text}")
        sources.append(source_spec(
            DraftSourceType.DOCUMENT.value,
            document.get("id"),
            str(document.get("name") or "Document"),
            f"Annexure {annexure}",
            None,
            True,
        ))
    return "\n".join(lines), sources


def _authority_block(authorities: list[dict], *, hindi: bool = False) -> tuple[str, list[dict]]:
    if not authorities:
        return (
            "कोई सत्यापित प्राधिकार चयनित नहीं है। दाखिल करने से पहले प्राधिकार जोड़ें और सत्यापित करें।" if hindi
            else "No verified authorities are selected. Add and verify authorities before filing.",
            [],
        )
    lines, sources = [], []
    for index, authority in enumerate(authorities, start=1):
        lines.append(f"{index}. {authority['label']}{' — ' + authority['locator'] if authority.get('locator') else ''}")
        sources.append(source_spec(
            authority["source_type"],
            authority.get("source_id"),
            authority["label"],
            authority.get("locator"),
            authority.get("excerpt"),
            authority.get("verified", True),
            authority.get("metadata"),
        ))
    return "\n".join(lines), sources


def _statement_block(statements: list[dict], *, hindi: bool = False) -> tuple[str, list[dict]]:
    relevant = [item for item in statements if item.get("kind") in {"admission", "denial"}]
    if not relevant:
        return ("कोई स्वचालित स्वीकारोक्ति या इंकार उपलब्ध नहीं है।" if hindi else "No classified admissions or denials are available.", [])
    lines, sources = [], []
    for item in relevant[:20]:
        label = "स्वीकारोक्ति" if hindi and item.get("kind") == "admission" else "इंकार" if hindi else str(item.get("kind", "statement")).title()
        lines.append(f"{label}: {item.get('text')}")
        sources.append(source_spec(
            DraftSourceType.STATEMENT.value,
            item.get("id"),
            str(item.get("kind") or "statement"),
            item.get("locator"),
            item.get("text"),
            True,
        ))
    return "\n".join(lines), sources


def _contradiction_block(contradictions: list[dict], *, hindi: bool = False) -> tuple[str, list[dict]]:
    open_items = [item for item in contradictions if item.get("status", "open") == "open"]
    if not open_items:
        return ("कोई खुला संरचित विरोधाभास नहीं मिला।" if hindi else "No open structured contradictions were detected.", [])
    lines, sources = [], []
    for item in open_items[:15]:
        values = " vs ".join(str(v) for v in item.get("values", []))
        lines.append(f"{item.get('severity', 'medium').upper()}: {item.get('label')} — {values}")
        sources.append(source_spec(
            DraftSourceType.CONTRADICTION.value,
            item.get("id"),
            str(item.get("label") or "Contradiction"),
            None,
            values,
            True,
        ))
    return "\n".join(lines), sources


def build_findings(draft_type: str, context: dict, questionnaire: dict, authorities: list[dict], section_keys: list[str]) -> list[dict]:
    findings: list[dict] = []

    def add(code: str, title: str, explanation: str, level: str, section_key: str | None = None, metadata: dict | None = None) -> None:
        findings.append({
            "rule_code": code,
            "title": title,
            "explanation": explanation,
            "level": level,
            "status": "open",
            "section_key": section_key,
            "metadata": metadata or {},
        })

    if draft_type in COURT_DRAFTS and not context.get("court_name"):
        add("missing_court", "Court not confirmed", "Confirm the court/forum before filing.", "high", "caption")
    if draft_type in COURT_DRAFTS and not context.get("case_number"):
        add("missing_case_number", "Case number not confirmed", "Confirm the case/proceeding number where applicable.", "medium", "caption")
    if not context.get("safe_facts") and draft_type not in {LegalDraftType.ANNEXURE_INDEX.value, LegalDraftType.CHRONOLOGY.value}:
        add("no_safe_facts", "No conflict-free facts available", "The matter does not currently contain safe structured facts for this draft.", "high", "material_facts")
    if context.get("excluded_facts"):
        add(
            "conflicting_facts_excluded",
            "Conflicting facts were excluded",
            f"{len(context['excluded_facts'])} fact value(s) involved in open contradictions were not inserted. Resolve them before filing.",
            "high",
            "material_facts",
            {"excluded_fact_ids": [str(item.get("id")) for item in context["excluded_facts"]]},
        )
    if draft_type == LegalDraftType.LEGAL_NOTICE.value:
        if not questionnaire.get("recipient_name") or not questionnaire.get("recipient_address"):
            add("notice_recipient_missing", "Recipient details incomplete", "Recipient name and address should be confirmed.", "high", "address")
        if not questionnaire.get("demand"):
            add("notice_demand_missing", "Demand is missing", "A legal notice should state the action/remedy demanded.", "high", "demand")
    if draft_type in GROUNDS_DRAFTS and not str(questionnaire.get("grounds") or "").strip():
        add("grounds_need_lawyer", "Grounds require lawyer drafting", "No custom grounds were supplied. The generated placeholder must be replaced or confirmed by counsel.", "high", "grounds")
    if draft_type in PARA_REPLY_DRAFTS and not str(questionnaire.get("para_wise_reply") or "").strip():
        add("para_reply_needed", "Para-wise response requires input", "The system cannot safely invent a paragraph-by-paragraph response without the pleading/notice position being confirmed.", "high", "para_wise_reply")
    if draft_type in RELIEF_DRAFTS and not str(questionnaire.get("relief_requested") or "").strip():
        add("relief_missing", "Relief / prayer requires confirmation", "Confirm the exact relief before the document is approved.", "high", "prayer")
    if "authorities" in section_keys and not authorities:
        add("authorities_missing", "No verified authorities selected", "Add statute provisions and/or judgment paragraphs from the local legal corpus before relying on authorities.", "medium", "authorities")
    unverified = [a for a in authorities if not a.get("verified", True)]
    if unverified:
        add("unverified_authorities", "Authority verification required", "One or more selected authorities could not be verified against the local corpus.", "high", "authorities")
    return findings


def build_sections(definition: dict, draft_type: str, context: dict, questionnaire: dict, authorities: list[dict]) -> tuple[list[dict], list[dict]]:
    safe = context.get("safe_facts", [])
    timeline = context.get("timeline", [])
    documents = context.get("documents", [])
    statements = context.get("statements", [])
    contradictions = context.get("contradictions", [])
    matter_title = context.get("matter_title") or "Matter"
    court_name = context.get("court_name") or "[Court / Forum to be confirmed]"
    case_number = context.get("case_number") or "[Case number to be confirmed]"

    fact_en, fact_sources = _fact_block(safe)
    fact_hi, _ = _fact_block(safe, hindi=True)
    chrono_en, chrono_sources = _timeline_block(timeline)
    chrono_hi, _ = _timeline_block(timeline, hindi=True)
    annexure_en, annexure_sources = _annexure_block(documents, str(questionnaire.get("annexure_prefix") or "A"))
    annexure_hi, _ = _annexure_block(documents, str(questionnaire.get("annexure_prefix") or "A"), hindi=True)
    authority_en, authority_sources = _authority_block(authorities)
    authority_hi, _ = _authority_block(authorities, hindi=True)
    statements_en, statement_sources = _statement_block(statements)
    statements_hi, _ = _statement_block(statements, hindi=True)
    contradiction_en, contradiction_sources = _contradiction_block(contradictions)
    contradiction_hi, _ = _contradiction_block(contradictions, hindi=True)

    custom = lambda key: str(questionnaire.get(key) or "").strip()
    body: dict[str, tuple[str, str, list[dict]]] = {
        "caption": (
            f"IN THE {court_name.upper()}\n{case_number}\n{matter_title}",
            f"{court_name}\n{case_number}\n{matter_title}",
            [],
        ),
        "address": (
            "\n".join(filter(None, [f"To: {custom('recipient_name') or '[Recipient]'}", custom("recipient_address"), f"Subject: {custom('subject') or matter_title}"])),
            "\n".join(filter(None, [f"प्रति: {custom('recipient_name') or '[प्राप्तकर्ता]'}", custom("recipient_address"), f"विषय: {custom('subject') or matter_title}"])),
            [],
        ),
        "instructions": (
            f"Under instructions from and on behalf of {custom('sender_name') or context.get('client_name') or '[Client]'}, the following notice is issued on the basis of the reviewed matter record.",
            f"{custom('sender_name') or context.get('client_name') or '[मुवक्किल]'} के निर्देशानुसार एवं उनकी ओर से, समीक्षा किए गए मामले के अभिलेख के आधार पर यह नोटिस जारी किया जाता है।",
            [],
        ),
        "material_facts": (fact_en, fact_hi, fact_sources),
        "chronology": (chrono_en, chrono_hi, chrono_sources),
        "annexure_index": (annexure_en, annexure_hi, annexure_sources),
        "authorities": (authority_en, authority_hi, authority_sources),
        "statements": (statements_en, statements_hi, statement_sources),
        "contradictions": (contradiction_en, contradiction_hi, contradiction_sources),
        "legal_position": (
            custom("legal_position") or "Legal position requires counsel review. No legal conclusion is inferred solely from extracted facts.",
            custom("legal_position") or "कानूनी स्थिति की अधिवक्ता द्वारा समीक्षा आवश्यक है। केवल निकाले गए तथ्यों के आधार पर कोई कानूनी निष्कर्ष स्वतः नहीं निकाला गया है।",
            [],
        ),
        "demand": (
            custom("demand") or "[Counsel to specify the exact demand.]",
            custom("demand") or "[अधिवक्ता सटीक मांग निर्दिष्ट करें।]",
            [],
        ),
        "consequence": (
            f"If the above demand is not complied with within {custom('response_days') or '[●]'} days of receipt, the client reserves the right to take such lawful steps as counsel may advise, without prejudice to other rights and remedies.",
            f"यदि प्राप्ति से {custom('response_days') or '[●]'} दिनों के भीतर उपरोक्त मांग का अनुपालन नहीं किया जाता है, तो मुवक्किल अन्य अधिकारों एवं उपचारों को प्रभावित किए बिना अधिवक्ता की सलाह के अनुसार विधिसम्मत कदम उठाने का अधिकार सुरक्षित रखता है।",
            [],
        ),
        "closing": (
            "This draft is generated from structured matter data and must be reviewed, settled and signed by the responsible lawyer before use.",
            "यह मसौदा संरचित मामले के डेटा से तैयार किया गया है और उपयोग से पहले जिम्मेदार अधिवक्ता द्वारा समीक्षा, अंतिम रूप एवं हस्ताक्षर आवश्यक हैं।",
            [],
        ),
        "preliminary_response": (
            custom("preliminary_response") or "The preliminary response requires counsel confirmation.",
            custom("preliminary_response") or "प्रारंभिक उत्तर की अधिवक्ता द्वारा पुष्टि आवश्यक है।",
            [],
        ),
        "para_wise_reply": (
            custom("para_wise_reply") or "[Para-wise response must be prepared against the source pleading/notice and reviewed by counsel.]",
            custom("para_wise_reply") or "[स्रोत अभिवचन/नोटिस के अनुसार पैरा-वार उत्तर तैयार कर अधिवक्ता द्वारा समीक्षा की जानी है।]",
            [],
        ),
        "deponent": (
            f"I, {custom('deponent_name') or '[Deponent]'}, {custom('deponent_details')}, do hereby state that the following contents are based on the reviewed matter record and my instructions/knowledge as applicable.",
            f"मैं, {custom('deponent_name') or '[शपथकर्ता]'}, {custom('deponent_details')}, यह कथन करता/करती हूँ कि निम्न सामग्री समीक्षा किए गए मामले के अभिलेख तथा लागू होने पर मेरे निर्देश/ज्ञान पर आधारित है।",
            [],
        ),
        "verification": (
            f"Verified at {custom('verification_place') or '[Place]'} that the contents above have been reviewed for accuracy. Counsel must adapt the verification to the applicable procedural requirements before filing.",
            f"{custom('verification_place') or '[स्थान]'} पर सत्यापित कि उपरोक्त सामग्री की शुद्धता हेतु समीक्षा की गई है। दाखिल करने से पूर्व अधिवक्ता लागू प्रक्रियात्मक आवश्यकताओं के अनुसार सत्यापन को अनुकूलित करें।",
            [],
        ),
        "application_heading": (
            custom("application_heading") or "[Application heading / statutory provision to be confirmed]",
            custom("application_heading") or "[आवेदन शीर्षक / वैधानिक प्रावधान की पुष्टि आवश्यक]",
            [],
        ),
        "grounds": (
            custom("grounds") or "[Grounds require lawyer drafting. Deterministic extraction is not used to invent legal grounds.]",
            custom("grounds") or "[आधारों का अधिवक्ता द्वारा मसौदा आवश्यक है। निर्धारक निष्कर्षण का उपयोग कानूनी आधार गढ़ने के लिए नहीं किया जाता।]",
            [],
        ),
        "prayer": (
            custom("relief_requested") or "[Exact relief / prayer to be confirmed by counsel.]",
            custom("relief_requested") or "[सटीक राहत / प्रार्थना की अधिवक्ता द्वारा पुष्टि आवश्यक है।]",
            [],
        ),
        "synopsis": (
            f"{matter_title}.\n\n{fact_en}",
            f"{matter_title}.\n\n{fact_hi}",
            fact_sources,
        ),
        "preliminary_objections": (
            custom("preliminary_objections") or "[Preliminary objections require defendant-side lawyer instructions.]",
            custom("preliminary_objections") or "[प्रारंभिक आपत्तियों हेतु प्रतिवादी-पक्ष के अधिवक्ता के निर्देश आवश्यक हैं।]",
            [],
        ),
        "additional_pleas": (
            custom("additional_pleas") or "[Additional pleas, if any, require counsel review.]",
            custom("additional_pleas") or "[अतिरिक्त अभिवचन, यदि कोई हों, अधिवक्ता की समीक्षा आवश्यक है।]",
            [],
        ),
        "reaffirmation": (
            "Except to the extent expressly modified in the reviewed instructions, the party's previously confirmed position is reiterated, subject to counsel settlement.",
            "समीक्षित निर्देशों में स्पष्ट रूप से संशोधित सीमा को छोड़कर, पक्ष की पूर्व पुष्टि की गई स्थिति को अधिवक्ता द्वारा अंतिम रूप दिए जाने के अधीन पुनः दोहराया जाता है।",
            [],
        ),
        "issues": (
            custom("issues") or "[Issues for determination require counsel confirmation.]",
            custom("issues") or "[निर्धारण हेतु प्रश्नों की अधिवक्ता द्वारा पुष्टि आवश्यक है।]",
            [],
        ),
        "submissions": (
            custom("submissions") or "[Submissions require counsel drafting. Use selected verified authorities and source-backed facts only.]",
            custom("submissions") or "[तर्कों का अधिवक्ता द्वारा मसौदा आवश्यक है। केवल चयनित सत्यापित प्राधिकार और स्रोत-समर्थित तथ्यों का उपयोग करें।]",
            [],
        ),
        "case_overview": (
            f"Matter: {matter_title}\nCourt: {court_name}\nCase: {case_number}\nClient: {context.get('client_name') or '[not recorded]'}",
            f"मामला: {matter_title}\nन्यायालय: {court_name}\nवाद: {case_number}\nमुवक्किल: {context.get('client_name') or '[दर्ज नहीं]'}",
            [],
        ),
        "evidence": (
            "\n".join(f"{index}. {fact.get('label')} — {len(fact.get('all_sources', [])) or 1} source(s)" for index, fact in enumerate(safe, 1)) or "No structured evidence facts available.",
            "\n".join(f"{index}. {fact.get('label')} — {len(fact.get('all_sources', [])) or 1} स्रोत" for index, fact in enumerate(safe, 1)) or "कोई संरचित साक्ष्य तथ्य उपलब्ध नहीं है।",
            fact_sources,
        ),
        "hearing_snapshot": (
            f"Matter: {matter_title}\nCourt: {court_name}\nCase: {case_number}\nHearing date: {custom('hearing_date') or '[not entered]'}\nPurpose/stage: {custom('hearing_purpose') or '[not entered]'}",
            f"मामला: {matter_title}\nन्यायालय: {court_name}\nवाद: {case_number}\nसुनवाई: {custom('hearing_date') or '[दर्ज नहीं]'}\nउद्देश्य/चरण: {custom('hearing_purpose') or '[दर्ज नहीं]'}",
            [],
        ),
        "action_items": (
            custom("action_items") or "1. Confirm open factual conflicts.\n2. Verify filing/hearing instructions.\n3. Confirm authorities and exact propositions relied upon.\n4. Confirm any court directions from the latest order.",
            custom("action_items") or "1. खुले तथ्यात्मक विरोधाभासों की पुष्टि करें।\n2. दाखिल/सुनवाई निर्देश सत्यापित करें।\n3. प्राधिकार और उन पर निर्भर सटीक प्रतिपाद्य की पुष्टि करें।\n4. नवीनतम आदेश के न्यायालय निर्देशों की पुष्टि करें।",
            [],
        ),
    }

    sections: list[dict] = []
    for position, section_definition in enumerate(definition["sections"], start=1):
        key = section_definition["key"]
        body_en, body_hi, sources = body.get(key, ("[Lawyer input required]", "[अधिवक्ता इनपुट आवश्यक]", []))
        sections.append({
            "section_key": key,
            "title_en": section_definition["title_en"],
            "title_hi": section_definition["title_hi"],
            "body_en": body_en,
            "body_hi": body_hi,
            "position": position,
            "sources": sources,
            "metadata": {"generated_by": "deterministic_builder_v1"},
        })

    findings = build_findings(draft_type, context, questionnaire, authorities, [section["section_key"] for section in sections])
    return sections, findings
