from __future__ import annotations

from app.models.drafting import LegalDraftType


def q(key: str, label_en: str, label_hi: str, required: bool = False, kind: str = "text") -> dict:
    return {
        "key": key,
        "label_en": label_en,
        "label_hi": label_hi,
        "required": required,
        "kind": kind,
    }


def s(key: str, title_en: str, title_hi: str) -> dict:
    return {"key": key, "title_en": title_en, "title_hi": title_hi}


DRAFT_DEFINITIONS: dict[str, dict] = {
    LegalDraftType.LEGAL_NOTICE.value: {
        "name_en": "Legal Notice",
        "name_hi": "कानूनी नोटिस",
        "description": "Structured demand or breach notice generated from verified matter facts.",
        "sections": [
            s("address", "Address & Subject", "पता एवं विषय"),
            s("instructions", "Under Instructions", "निर्देशानुसार"),
            s("material_facts", "Material Facts", "महत्वपूर्ण तथ्य"),
            s("legal_position", "Legal Position", "कानूनी स्थिति"),
            s("demand", "Demand", "मांग"),
            s("consequence", "Failure to Comply", "अनुपालन न करने का परिणाम"),
            s("closing", "Closing", "समापन"),
        ],
        "questions": [
            q("sender_name", "Sender / client name", "प्रेषक / मुवक्किल का नाम", True),
            q("recipient_name", "Recipient name", "प्राप्तकर्ता का नाम", True),
            q("recipient_address", "Recipient address", "प्राप्तकर्ता का पता", True, "textarea"),
            q("subject", "Notice subject", "नोटिस का विषय", True),
            q("demand", "What must the recipient do?", "प्राप्तकर्ता को क्या करना है?", True, "textarea"),
            q("response_days", "Compliance period (days)", "अनुपालन अवधि (दिन)", True, "number"),
            q("legal_position", "Legal basis / position", "कानूनी आधार / स्थिति", False, "textarea"),
        ],
    },
    LegalDraftType.NOTICE_REPLY.value: {
        "name_en": "Reply to Legal Notice",
        "name_hi": "कानूनी नोटिस का उत्तर",
        "description": "Structured reply with preliminary response, facts and para-wise position.",
        "sections": [
            s("address", "Address & Reference", "पता एवं संदर्भ"),
            s("preliminary_response", "Preliminary Response", "प्रारंभिक उत्तर"),
            s("material_facts", "Material Facts", "महत्वपूर्ण तथ्य"),
            s("para_wise_reply", "Para-wise Reply", "पैरा-वार उत्तर"),
            s("legal_position", "Legal Position", "कानूनी स्थिति"),
            s("closing", "Conclusion", "निष्कर्ष"),
        ],
        "questions": [
            q("sender_name", "Replying party", "उत्तर देने वाला पक्ष", True),
            q("recipient_name", "Notice sender", "नोटिस भेजने वाला", True),
            q("notice_date", "Notice date", "नोटिस की तारीख", False, "date"),
            q("preliminary_response", "Preliminary response", "प्रारंभिक उत्तर", False, "textarea"),
            q("para_wise_reply", "Para-wise reply", "पैरा-वार उत्तर", False, "textarea"),
            q("legal_position", "Legal position", "कानूनी स्थिति", False, "textarea"),
        ],
    },
    LegalDraftType.AFFIDAVIT.value: {
        "name_en": "Affidavit",
        "name_hi": "शपथपत्र",
        "description": "Matter-backed affidavit skeleton with source-backed facts and verification.",
        "sections": [
            s("caption", "Court Caption", "न्यायालय शीर्षक"),
            s("deponent", "Deponent", "शपथकर्ता"),
            s("material_facts", "Statements on Oath", "शपथ पर कथन"),
            s("verification", "Verification", "सत्यापन"),
        ],
        "questions": [
            q("deponent_name", "Deponent name", "शपथकर्ता का नाम", True),
            q("deponent_details", "Deponent description/address", "शपथकर्ता का विवरण/पता", False, "textarea"),
            q("verification_place", "Verification place", "सत्यापन का स्थान", False),
        ],
    },
    LegalDraftType.APPLICATION.value: {
        "name_en": "Court Application",
        "name_hi": "न्यायालय आवेदन",
        "description": "Structured interlocutory application with facts, grounds and prayer.",
        "sections": [
            s("caption", "Court Caption", "न्यायालय शीर्षक"),
            s("application_heading", "Application", "आवेदन"),
            s("material_facts", "Facts", "तथ्य"),
            s("grounds", "Grounds", "आधार"),
            s("prayer", "Prayer", "प्रार्थना"),
            s("verification", "Verification", "सत्यापन"),
        ],
        "questions": [
            q("application_heading", "Application heading / provision", "आवेदन शीर्षक / प्रावधान", True),
            q("grounds", "Grounds", "आधार", False, "textarea"),
            q("relief_requested", "Relief requested", "मांगी गई राहत", True, "textarea"),
        ],
    },
    LegalDraftType.PETITION.value: {
        "name_en": "Petition",
        "name_hi": "याचिका",
        "description": "Petition skeleton assembled from matter facts, chronology and selected authorities.",
        "sections": [
            s("caption", "Court Caption", "न्यायालय शीर्षक"),
            s("synopsis", "Synopsis", "संक्षिप्त विवरण"),
            s("chronology", "List of Dates", "तिथियों की सूची"),
            s("material_facts", "Facts", "तथ्य"),
            s("grounds", "Grounds", "आधार"),
            s("authorities", "Authorities", "प्राधिकार"),
            s("prayer", "Prayer", "प्रार्थना"),
            s("verification", "Verification", "सत्यापन"),
        ],
        "questions": [
            q("petition_heading", "Petition heading / jurisdiction", "याचिका शीर्षक / अधिकारिता", True),
            q("grounds", "Grounds", "आधार", False, "textarea"),
            q("relief_requested", "Relief requested", "मांगी गई राहत", True, "textarea"),
            q("verification_place", "Verification place", "सत्यापन का स्थान", False),
        ],
    },
    LegalDraftType.WRITTEN_STATEMENT.value: {
        "name_en": "Written Statement",
        "name_hi": "लिखित बयान",
        "description": "Defence-side pleading skeleton with preliminary objections and para-wise reply.",
        "sections": [
            s("caption", "Court Caption", "न्यायालय शीर्षक"),
            s("preliminary_objections", "Preliminary Objections", "प्रारंभिक आपत्तियाँ"),
            s("material_facts", "Defendant's Facts", "प्रतिवादी के तथ्य"),
            s("para_wise_reply", "Para-wise Reply", "पैरा-वार उत्तर"),
            s("additional_pleas", "Additional Pleas", "अतिरिक्त अभिवचन"),
            s("prayer", "Prayer", "प्रार्थना"),
            s("verification", "Verification", "सत्यापन"),
        ],
        "questions": [
            q("preliminary_objections", "Preliminary objections", "प्रारंभिक आपत्तियाँ", False, "textarea"),
            q("para_wise_reply", "Para-wise reply", "पैरा-वार उत्तर", False, "textarea"),
            q("additional_pleas", "Additional pleas", "अतिरिक्त अभिवचन", False, "textarea"),
            q("relief_requested", "Prayer / relief", "प्रार्थना / राहत", False, "textarea"),
        ],
    },
    LegalDraftType.REJOINDER.value: {
        "name_en": "Rejoinder",
        "name_hi": "प्रत्युत्तर",
        "description": "Rejoinder skeleton preserving the matter's source-backed factual record.",
        "sections": [
            s("caption", "Court Caption", "न्यायालय शीर्षक"),
            s("preliminary_response", "Preliminary Submissions", "प्रारंभिक निवेदन"),
            s("material_facts", "Material Facts", "महत्वपूर्ण तथ्य"),
            s("para_wise_reply", "Reply to Written Statement", "लिखित बयान का उत्तर"),
            s("reaffirmation", "Reaffirmation", "पुनः पुष्टि"),
            s("prayer", "Prayer", "प्रार्थना"),
            s("verification", "Verification", "सत्यापन"),
        ],
        "questions": [
            q("preliminary_response", "Preliminary submissions", "प्रारंभिक निवेदन", False, "textarea"),
            q("para_wise_reply", "Para-wise rejoinder", "पैरा-वार प्रत्युत्तर", False, "textarea"),
            q("relief_requested", "Prayer / relief", "प्रार्थना / राहत", False, "textarea"),
        ],
    },
    LegalDraftType.WRITTEN_SUBMISSIONS.value: {
        "name_en": "Written Submissions",
        "name_hi": "लिखित तर्क",
        "description": "Issue-oriented submissions with verified authorities and matter provenance.",
        "sections": [
            s("caption", "Court Caption", "न्यायालय शीर्षक"),
            s("issues", "Issues", "विवादित प्रश्न"),
            s("synopsis", "Brief Facts", "संक्षिप्त तथ्य"),
            s("authorities", "Authorities", "प्राधिकार"),
            s("submissions", "Submissions", "तर्क"),
            s("prayer", "Conclusion / Prayer", "निष्कर्ष / प्रार्थना"),
        ],
        "questions": [
            q("issues", "Issues for determination", "निर्धारण हेतु प्रश्न", True, "textarea"),
            q("submissions", "Core submissions", "मुख्य तर्क", False, "textarea"),
            q("relief_requested", "Conclusion / relief", "निष्कर्ष / राहत", False, "textarea"),
        ],
    },
    LegalDraftType.CHRONOLOGY.value: {
        "name_en": "Chronology / List of Dates",
        "name_hi": "कालक्रम / तिथियों की सूची",
        "description": "Deterministic chronology generated from source-backed timeline events.",
        "sections": [s("chronology", "Chronology / List of Dates", "कालक्रम / तिथियों की सूची")],
        "questions": [],
    },
    LegalDraftType.ANNEXURE_INDEX.value: {
        "name_en": "Annexure Index",
        "name_hi": "अनुलग्नक सूची",
        "description": "Document index with deterministic annexure numbering and page metadata.",
        "sections": [s("annexure_index", "Annexure Index", "अनुलग्नक सूची")],
        "questions": [q("annexure_prefix", "Annexure prefix", "अनुलग्नक उपसर्ग", False)],
    },
    LegalDraftType.CASE_SYNOPSIS.value: {
        "name_en": "Case Synopsis",
        "name_hi": "मामले का संक्षिप्त विवरण",
        "description": "Matter briefing note assembled from facts, chronology, evidence and authorities.",
        "sections": [
            s("case_overview", "Case Overview", "मामले का अवलोकन"),
            s("material_facts", "Material Facts", "महत्वपूर्ण तथ्य"),
            s("chronology", "Key Dates", "मुख्य तिथियाँ"),
            s("issues", "Issues", "विवादित प्रश्न"),
            s("evidence", "Evidence", "साक्ष्य"),
            s("authorities", "Authorities", "प्राधिकार"),
            s("prayer", "Relief / Objective", "राहत / उद्देश्य"),
        ],
        "questions": [
            q("issues", "Issues", "विवादित प्रश्न", False, "textarea"),
            q("relief_requested", "Relief / objective", "राहत / उद्देश्य", False, "textarea"),
        ],
    },
    LegalDraftType.HEARING_NOTE.value: {
        "name_en": "Hearing Note",
        "name_hi": "सुनवाई नोट",
        "description": "Compact source-backed hearing preparation note for the next appearance.",
        "sections": [
            s("hearing_snapshot", "Hearing Snapshot", "सुनवाई सारांश"),
            s("chronology", "Recent Procedural History", "हाल का प्रक्रियात्मक इतिहास"),
            s("material_facts", "Key Facts", "मुख्य तथ्य"),
            s("contradictions", "Conflicts to Watch", "ध्यान देने योग्य विरोधाभास"),
            s("statements", "Admissions & Denials", "स्वीकारोक्ति एवं इंकार"),
            s("authorities", "Authorities", "प्राधिकार"),
            s("action_items", "Counsel Checklist", "अधिवक्ता चेकलिस्ट"),
        ],
        "questions": [
            q("hearing_date", "Hearing date", "सुनवाई की तारीख", False, "date"),
            q("hearing_purpose", "Purpose / stage", "उद्देश्य / चरण", False),
            q("action_items", "Additional action items", "अतिरिक्त कार्य", False, "textarea"),
        ],
    },
}


def get_draft_catalog() -> list[dict]:
    return [
        {
            "draft_type": key,
            "name_en": value["name_en"],
            "name_hi": value["name_hi"],
            "description": value["description"],
            "section_count": len(value["sections"]),
            "questions": value["questions"],
        }
        for key, value in DRAFT_DEFINITIONS.items()
    ]
