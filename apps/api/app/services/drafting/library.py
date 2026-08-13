"""Draft template library for Indian district, tehsil and revenue practice.

The twelve entries in `catalog.py` are draft *categories* — notice, application,
petition. This is the instrument-level library beneath them: the specific things
a lawyer actually files, each with its own sections and its own intake
questions, in English and Hindi.

Every template maps to one of the existing LegalDraftType categories, so the
deterministic builder and renderer need no changes and the enum does not grow.
The stable identifier is `code`.

VERIFICATION STATUS — read before shipping any of this to a real filing.

Each template is a structural scaffold: the headings, the order of sections and
the questions a lawyer must answer. They are drawn from ordinary Indian
practice, but none has been reviewed by a practitioner, and local courts differ
on format, court-fee endorsement and annexure marking. Every entry is therefore
seeded `verified: False`, and the drafting service marks output accordingly.
A template becomes verified only when a qualified advocate signs it off for a
named jurisdiction — the same discipline the remedy rule packs already enforce.

Statutory references use the BNSS/BNS numbering that replaced the CrPC/IPC,
with the older section noted where practitioners still refer to it.
"""

from __future__ import annotations

from app.models.drafting import LegalDraftType

# --- building blocks ---------------------------------------------------------


def q(key: str, label_en: str, label_hi: str, required: bool = False, kind: str = "text") -> dict:
    return {"key": key, "label_en": label_en, "label_hi": label_hi, "required": required, "kind": kind}


def s(key: str, title_en: str, title_hi: str) -> dict:
    return {"key": key, "title_en": title_en, "title_hi": title_hi}


# Section bundles that repeat across whole families of drafts. Defined once so a
# correction to the prayer format reaches every pleading that uses it.
HEADING = [
    s("court", "Court & Cause Title", "न्यायालय एवं वाद शीर्षक"),
    s("parties", "Parties", "पक्षकार"),
]
FACTS = [s("facts", "Facts", "तथ्य")]
GROUNDS = [s("grounds", "Grounds", "आधार")]
PRAYER = [s("prayer", "Prayer", "प्रार्थना")]
VERIFICATION = [
    s("verification", "Verification", "सत्यापन"),
    s("affidavit", "Supporting Affidavit", "समर्थन शपथपत्र"),
]
PLEADING = HEADING + FACTS + GROUNDS + PRAYER + VERIFICATION
APPLICATION_SECTIONS = HEADING + FACTS + GROUNDS + PRAYER + [s("verification", "Verification", "सत्यापन")]
NOTICE_SECTIONS = [
    s("address", "Address & Subject", "पता एवं विषय"),
    s("instructions", "Under Instructions", "निर्देशानुसार"),
    s("facts", "Material Facts", "महत्वपूर्ण तथ्य"),
    s("legal_position", "Legal Position", "कानूनी स्थिति"),
    s("demand", "Demand", "मांग"),
    s("consequence", "Consequence of Non-compliance", "अनुपालन न करने का परिणाम"),
]
DEED_SECTIONS = [
    s("parties", "Parties", "पक्षकार"),
    s("recitals", "Recitals", "प्रस्तावना"),
    s("operative", "Operative Terms", "प्रमुख शर्तें"),
    s("consideration", "Consideration", "प्रतिफल"),
    s("covenants", "Covenants & Warranties", "वचन एवं आश्वासन"),
    s("schedule", "Schedule of Property", "संपत्ति का विवरण"),
    s("execution", "Execution & Witnesses", "निष्पादन एवं गवाह"),
]

# Question bundles.
PARTY_QUESTIONS = [
    q("applicant_name", "Applicant / plaintiff name", "आवेदक / वादी का नाम", True),
    q("applicant_address", "Applicant address", "आवेदक का पता", False, "textarea"),
    q("respondent_name", "Opposite party name", "विपक्षी का नाम", True),
    q("respondent_address", "Opposite party address", "विपक्षी का पता", False, "textarea"),
]
COURT_QUESTIONS = [
    q("court_name", "Court / authority", "न्यायालय / प्राधिकारी", True),
    q("case_number", "Case number (if allotted)", "वाद संख्या (यदि आवंटित)", False),
]
FACT_QUESTION = [q("facts", "Facts in brief", "संक्षिप्त तथ्य", True, "textarea")]
GROUND_QUESTION = [q("grounds", "Grounds relied on", "आधार", False, "textarea")]
PRAYER_QUESTION = [q("relief", "Relief sought", "वांछित अनुतोष", True, "textarea")]
PLACE_DATE = [
    q("place", "Place", "स्थान", False),
    q("draft_date", "Date", "दिनांक", False, "date"),
]

_TEMPLATES: list[dict] = []


def tpl(
    code: str,
    *,
    draft_type: LegalDraftType,
    category: str,
    forum: str,
    name_en: str,
    name_hi: str,
    description: str,
    authority: str | None = None,
    sections: list[dict] | None = None,
    questions: list[dict] | None = None,
) -> None:
    """Register one instrument.

    `authority` is the statute or rule the instrument is filed under, recorded
    so a reviewing advocate can check the basis rather than infer it.
    """
    _TEMPLATES.append(
        {
            "code": code,
            "draft_type": draft_type,
            "category": category,
            "forum": forum,
            "name_en": name_en,
            "name_hi": name_hi,
            "description": description,
            "authority": authority,
            "sections": sections or APPLICATION_SECTIONS,
            "questions": (questions or []) + PLACE_DATE,
            "verified": False,
        }
    )


# --- 1. notices and pre-litigation -------------------------------------------

NOTICE_Q = PARTY_QUESTIONS + [
    q("subject", "Subject of the notice", "नोटिस का विषय", True),
    q("demand", "What must the recipient do?", "प्राप्तकर्ता को क्या करना है?", True, "textarea"),
    q("response_days", "Compliance period (days)", "अनुपालन अवधि (दिन)", True, "number"),
] + FACT_QUESTION

tpl(
    "notice-cheque-dishonour-138",
    draft_type=LegalDraftType.LEGAL_NOTICE,
    category="notices",
    forum="pre-litigation",
    name_en="Cheque Dishonour Notice (s.138 NI Act)",
    name_hi="चेक अनादर नोटिस (धारा 138 एन.आई. अधिनियम)",
    description="Statutory demand after a cheque is returned unpaid. The 15-day period and the 30-day limit to complain both run from service, so the dates matter more than the language.",
    authority="Section 138 proviso (b), Negotiable Instruments Act, 1881",
    sections=NOTICE_SECTIONS,
    questions=NOTICE_Q + [
        q("cheque_number", "Cheque number", "चेक संख्या", True),
        q("cheque_amount", "Cheque amount", "चेक राशि", True, "number"),
        q("cheque_date", "Cheque date", "चेक की तारीख", True, "date"),
        q("bank_name", "Drawee bank", "बैंक का नाम", True),
        q("return_date", "Return memo date", "वापसी ज्ञापन दिनांक", True, "date"),
        q("return_reason", "Reason for return", "वापसी का कारण", True),
        q("debt_particulars", "Legally enforceable debt", "वैध ऋण का विवरण", True, "textarea"),
    ],
)

tpl(
    "notice-eviction-tenancy",
    draft_type=LegalDraftType.LEGAL_NOTICE,
    category="notices",
    forum="pre-litigation",
    name_en="Notice to Quit / Determine Tenancy",
    name_hi="किरायेदारी समाप्ति नोटिus",
    description="Terminates a tenancy before an eviction suit. The notice period and the expiry date must align with the tenancy month, which is where most such notices fail.",
    authority="Section 106, Transfer of Property Act, 1882",
    sections=NOTICE_SECTIONS,
    questions=NOTICE_Q + [
        q("premises", "Tenanted premises", "किरायेदारी परिसर", True, "textarea"),
        q("tenancy_start", "Tenancy commenced on", "किरायेदारी प्रारंभ", False, "date"),
        q("rent_amount", "Monthly rent", "मासिक किराया", False, "number"),
        q("arrears_amount", "Arrears claimed", "बकाया राशि", False, "number"),
        q("ground", "Ground for eviction", "बेदखली का आधार", True, "textarea"),
    ],
)

tpl(
    "notice-rent-arrears",
    draft_type=LegalDraftType.LEGAL_NOTICE,
    category="notices",
    forum="pre-litigation",
    name_en="Demand Notice for Rent Arrears",
    name_hi="किराया बकाया मांग नोटिस",
    description="Demands arrears and puts the tenant in default before eviction proceedings.",
    sections=NOTICE_SECTIONS,
    questions=NOTICE_Q + [
        q("premises", "Premises", "परिसर", True, "textarea"),
        q("arrears_period", "Period of arrears", "बकाया अवधि", True),
        q("arrears_amount", "Amount due", "देय राशि", True, "number"),
    ],
)

tpl(
    "notice-recovery-money",
    draft_type=LegalDraftType.LEGAL_NOTICE,
    category="notices",
    forum="pre-litigation",
    name_en="Money Recovery Notice",
    name_hi="धन वसूली नोटिस",
    description="Demand before a recovery suit, recording the debt, its acknowledgement and the running of interest.",
    sections=NOTICE_SECTIONS,
    questions=NOTICE_Q + [
        q("principal_amount", "Principal due", "मूल राशि", True, "number"),
        q("interest_rate", "Interest claimed (% p.a.)", "ब्याज दर (% वार्षिक)", False, "number"),
        q("due_since", "Amount due since", "कब से देय", False, "date"),
        q("acknowledgement", "Last acknowledgement of debt", "ऋण की अंतिम स्वीकृति", False, "date"),
    ],
)

tpl(
    "notice-consumer-deficiency",
    draft_type=LegalDraftType.LEGAL_NOTICE,
    category="notices",
    forum="pre-litigation",
    name_en="Consumer Deficiency Notice",
    name_hi="उपभोक्ता सेवा दोष नोटिस",
    description="Pre-complaint notice to a trader or service provider setting out the defect or deficiency.",
    authority="Consumer Protection Act, 2019",
    sections=NOTICE_SECTIONS,
    questions=NOTICE_Q + [
        q("purchase_date", "Date of purchase / service", "खरीद / सेवा की तारीख", False, "date"),
        q("amount_paid", "Amount paid", "भुगतान राशि", False, "number"),
        q("defect", "Defect or deficiency", "दोष अथवा कमी", True, "textarea"),
    ],
)

tpl(
    "notice-government-80cpc",
    draft_type=LegalDraftType.LEGAL_NOTICE,
    category="notices",
    forum="pre-litigation",
    name_en="Notice to Government (s.80 CPC)",
    name_hi="सरकार को नोटिस (धारा 80 सी.पी.सी.)",
    description="Mandatory two-month notice before suing the government or a public officer. A suit filed without it is liable to be returned.",
    authority="Section 80, Code of Civil Procedure, 1908",
    sections=NOTICE_SECTIONS,
    questions=NOTICE_Q + [
        q("department", "Department / office", "विभाग / कार्यालय", True),
        q("cause_of_action", "Cause of action", "वाद कारण", True, "textarea"),
    ],
)

tpl(
    "notice-employment-dues",
    draft_type=LegalDraftType.LEGAL_NOTICE,
    category="notices",
    forum="pre-litigation",
    name_en="Notice for Unpaid Wages or Dues",
    name_hi="अवैतनिक वेतन / देय नोटिस",
    description="Demand for wages, gratuity or terminal dues before a labour claim.",
    sections=NOTICE_SECTIONS,
    questions=NOTICE_Q + [
        q("employer_name", "Employer", "नियोक्ता", True),
        q("employment_period", "Period of employment", "सेवा अवधि", False),
        q("dues_breakup", "Break-up of dues", "देय राशि का विवरण", True, "textarea"),
    ],
)

tpl(
    "notice-reply-general",
    draft_type=LegalDraftType.NOTICE_REPLY,
    category="notices",
    forum="pre-litigation",
    name_en="Reply to Legal Notice",
    name_hi="कानूनी नोटिस का उत्तर",
    description="Para-wise reply denying or answering each allegation, and setting up the recipient's own case.",
    sections=[
        s("address", "Address & Reference", "पता एवं संदर्भ"),
        s("preliminary", "Preliminary Objections", "प्रारंभिक आपत्तियाँ"),
        s("para_wise_reply", "Para-wise Reply", "पैरा-वार उत्तर"),
        s("facts", "True Facts", "वास्तविक तथ्य"),
        s("legal_position", "Legal Position", "कानूनी स्थिति"),
        s("closing", "Conclusion", "निष्कर्ष"),
    ],
    questions=PARTY_QUESTIONS + [
        q("notice_date", "Date of notice replied to", "नोटिस की तारीख", True, "date"),
        q("preliminary", "Preliminary objections", "प्रारंभिक आपत्तियाँ", False, "textarea"),
        q("para_wise_reply", "Para-wise reply", "पैरा-वार उत्तर", True, "textarea"),
    ],
)

# --- 2. civil pleadings -------------------------------------------------------

PLAINT_Q = COURT_QUESTIONS + PARTY_QUESTIONS + FACT_QUESTION + PRAYER_QUESTION + [
    q("cause_of_action_date", "Date cause of action arose", "वाद कारण की तिथि", True, "date"),
    q("suit_valuation", "Valuation for court fee", "न्यायशुल्क हेतु मूल्यांकन", True, "number"),
    q("jurisdiction_ground", "Basis of territorial jurisdiction", "क्षेत्राधिकार का आधार", False, "textarea"),
]

for code, name_en, name_hi, description, extra in [
    (
        "plaint-recovery-money",
        "Plaint — Recovery of Money",
        "वाद पत्र — धन वसूली",
        "Suit for a liquidated sum with interest, the commonest civil filing in a district court.",
        [q("principal_amount", "Principal claimed", "मूल राशि", True, "number"),
         q("interest_rate", "Interest (% p.a.)", "ब्याज (% वार्षिक)", False, "number")],
    ),
    (
        "plaint-possession-immovable",
        "Plaint — Possession of Immovable Property",
        "वाद पत्र — अचल संपत्ति का कब्जा",
        "Suit for possession based on title, with mesne profits where occupation continued after demand.",
        [q("property_description", "Property description", "संपत्ति का विवरण", True, "textarea"),
         q("title_basis", "Basis of title", "स्वामित्व का आधार", True, "textarea"),
         q("mesne_profits", "Mesne profits claimed", "मध्यवर्ती लाभ", False, "number")],
    ),
    (
        "plaint-permanent-injunction",
        "Plaint — Permanent Injunction",
        "वाद पत्र — स्थायी निषेधाज्ञा",
        "Suit restraining interference with possession or a legal right.",
        [q("property_description", "Property / right", "संपत्ति / अधिकार", True, "textarea"),
         q("threatened_act", "Act to be restrained", "निषेध हेतु कार्य", True, "textarea")],
    ),
    (
        "plaint-declaration",
        "Plaint — Declaration of Title",
        "वाद पत्र — स्वामित्व घोषणा",
        "Suit declaring title or status, usually with consequential relief.",
        [q("declaration_sought", "Declaration sought", "वांछित घोषणा", True, "textarea"),
         q("consequential_relief", "Consequential relief", "पारिणामिक अनुतोष", False, "textarea")],
    ),
    (
        "plaint-specific-performance",
        "Plaint — Specific Performance",
        "वाद पत्र — विशिष्ट अनुपालन",
        "Suit to enforce an agreement to sell. Readiness and willingness must be pleaded throughout, not merely asserted.",
        [q("agreement_date", "Agreement date", "अनुबंध दिनांक", True, "date"),
         q("consideration", "Consideration agreed", "तय प्रतिफल", True, "number"),
         q("amount_paid", "Amount already paid", "भुगतान की गई राशि", False, "number"),
         q("readiness", "Readiness and willingness", "तत्परता एवं इच्छा", True, "textarea")],
    ),
    (
        "plaint-partition",
        "Plaint — Partition",
        "वाद पत्र — बँटवारा",
        "Suit for partition and separate possession of a share in joint property.",
        [q("property_description", "Joint property", "संयुक्त संपत्ति", True, "textarea"),
         q("share_claimed", "Share claimed", "दावाकृत हिस्सा", True),
         q("co_sharers", "Co-sharers", "सह-हिस्सेदार", True, "textarea")],
    ),
    (
        "plaint-eviction-rent",
        "Plaint — Eviction of Tenant",
        "वाद पत्र — किरायेदार बेदखली",
        "Eviction suit on statutory grounds, following a valid notice determining the tenancy.",
        [q("premises", "Premises", "परिसर", True, "textarea"),
         q("ground", "Ground for eviction", "बेदखली का आधार", True, "textarea"),
         q("notice_date", "Date notice served", "नोटिस तामील दिनांक", False, "date")],
    ),
    (
        "plaint-damages",
        "Plaint — Damages / Compensation",
        "वाद पत्र — क्षतिपूर्ति",
        "Suit for damages for breach, negligence or tort.",
        [q("loss_particulars", "Particulars of loss", "हानि का विवरण", True, "textarea"),
         q("damages_claimed", "Damages claimed", "दावाकृत क्षतिपूर्ति", True, "number")],
    ),
]:
    tpl(
        code,
        draft_type=LegalDraftType.PETITION,
        category="civil-pleadings",
        forum="civil-court",
        name_en=name_en,
        name_hi=name_hi,
        description=description,
        authority="Order VII, Code of Civil Procedure, 1908",
        sections=PLEADING,
        questions=PLAINT_Q + extra,
    )

tpl(
    "written-statement-civil",
    draft_type=LegalDraftType.WRITTEN_STATEMENT,
    category="civil-pleadings",
    forum="civil-court",
    name_en="Written Statement",
    name_hi="लिखित कथन",
    description="Defence to a plaint. An allegation not specifically denied is taken as admitted, which is why the para-wise reply carries the case.",
    authority="Order VIII, Code of Civil Procedure, 1908",
    sections=HEADING + [
        s("preliminary", "Preliminary Objections", "प्रारंभिक आपत्तियाँ"),
        s("para_wise_reply", "Para-wise Reply", "पैरा-वार उत्तर"),
        s("facts", "Additional Pleas", "अतिरिक्त कथन"),
        s("prayer", "Prayer", "प्रार्थना"),
    ] + VERIFICATION,
    questions=COURT_QUESTIONS + PARTY_QUESTIONS + [
        q("preliminary", "Preliminary objections", "प्रारंभिक आपत्तियाँ", False, "textarea"),
        q("para_wise_reply", "Para-wise reply", "पैरा-वार उत्तर", True, "textarea"),
        q("additional_pleas", "Additional pleas", "अतिरिक्त कथन", False, "textarea"),
    ],
)

tpl(
    "counter-claim",
    draft_type=LegalDraftType.WRITTEN_STATEMENT,
    category="civil-pleadings",
    forum="civil-court",
    name_en="Counter-Claim",
    name_hi="प्रतिदावा",
    description="Defendant's own claim raised within the written statement; court fee is payable on it as on a plaint.",
    authority="Order VIII Rule 6A, Code of Civil Procedure, 1908",
    sections=PLEADING,
    questions=COURT_QUESTIONS + FACT_QUESTION + PRAYER_QUESTION + [
        q("counter_claim_value", "Value of counter-claim", "प्रतिदावा मूल्यांकन", True, "number"),
    ],
)

tpl(
    "replication-rejoinder",
    draft_type=LegalDraftType.REJOINDER,
    category="civil-pleadings",
    forum="civil-court",
    name_en="Replication / Rejoinder",
    name_hi="प्रत्युत्तर",
    description="Answer to new matter raised in the written statement, without introducing a fresh case.",
    authority="Order VIII Rule 9, Code of Civil Procedure, 1908",
    sections=HEADING + [
        s("para_wise_reply", "Para-wise Reply", "पैरा-वार उत्तर"),
        s("facts", "Reiteration", "पुनर्कथन"),
    ] + VERIFICATION,
    questions=COURT_QUESTIONS + [
        q("para_wise_reply", "Reply to new pleas", "नए कथनों का उत्तर", True, "textarea"),
    ],
)

# --- 3. civil applications ----------------------------------------------------

for code, name_en, name_hi, description, authority, extra in [
    (
        "app-temporary-injunction",
        "Application — Temporary Injunction",
        "आवेदन — अस्थायी निषेधाज्ञा",
        "Interim restraint pending suit. Prima facie case, balance of convenience and irreparable injury must each be pleaded separately.",
        "Order XXXIX Rules 1 & 2, Code of Civil Procedure, 1908",
        [q("threatened_act", "Act to be restrained", "निषेध हेतु कार्य", True, "textarea"),
         q("irreparable_injury", "Irreparable injury", "अपूरणीय क्षति", True, "textarea")],
    ),
    (
        "app-ex-parte-set-aside",
        "Application — Set Aside Ex-Parte Decree",
        "आवेदन — एकपक्षीय डिक्री अपास्त",
        "Application to set aside a decree passed ex-parte, showing sufficient cause for non-appearance.",
        "Order IX Rule 13, Code of Civil Procedure, 1908",
        [q("decree_date", "Date of ex-parte decree", "डिक्री दिनांक", True, "date"),
         q("sufficient_cause", "Sufficient cause", "पर्याप्त कारण", True, "textarea")],
    ),
    (
        "app-restoration-dismissal",
        "Application — Restoration of Dismissed Suit",
        "आवेदन — वाद पुनर्स्थापन",
        "Restores a suit dismissed for default of appearance. The lifeline after a missed date.",
        "Order IX Rule 9, Code of Civil Procedure, 1908",
        [q("dismissal_date", "Date of dismissal", "खारिजी दिनांक", True, "date"),
         q("sufficient_cause", "Reason for absence", "अनुपस्थिति का कारण", True, "textarea")],
    ),
    (
        "app-condonation-delay",
        "Application — Condonation of Delay",
        "आवेदन — विलंब क्षमा",
        "Explains day-to-day delay in filing. Courts expect the whole period accounted for, not a general excuse.",
        "Section 5, Limitation Act, 1963",
        [q("delay_days", "Days of delay", "विलंब के दिन", True, "number"),
         q("delay_explanation", "Explanation for the delay", "विलंब का कारण", True, "textarea")],
    ),
    (
        "app-amendment-pleadings",
        "Application — Amendment of Pleadings",
        "आवेदन — अभिवचन संशोधन",
        "Seeks leave to amend a plaint or written statement.",
        "Order VI Rule 17, Code of Civil Procedure, 1908",
        [q("proposed_amendment", "Proposed amendment", "प्रस्तावित संशोधन", True, "textarea"),
         q("why_necessary", "Why necessary now", "अभी क्यों आवश्यक", True, "textarea")],
    ),
    (
        "app-impleadment",
        "Application — Impleadment of Party",
        "आवेदन — पक्षकार जोड़ना",
        "Adds a necessary or proper party to the proceedings.",
        "Order I Rule 10, Code of Civil Procedure, 1908",
        [q("proposed_party", "Party to be added", "जोड़ा जाने वाला पक्ष", True),
         q("why_necessary", "Why a necessary party", "आवश्यक पक्ष क्यों", True, "textarea")],
    ),
    (
        "app-substitution-lrs",
        "Application — Substitution of Legal Representatives",
        "आवेदन — विधिक प्रतिनिधि प्रतिस्थापन",
        "Brings the legal representatives of a deceased party on record before abatement sets in.",
        "Order XXII, Code of Civil Procedure, 1908",
        [q("deceased_name", "Deceased party", "मृतक पक्षकार", True),
         q("death_date", "Date of death", "मृत्यु दिनांक", True, "date"),
         q("legal_representatives", "Legal representatives", "विधिक प्रतिनिधि", True, "textarea")],
    ),
    (
        "app-local-commissioner",
        "Application — Appointment of Local Commissioner",
        "आवेदन — स्थानीय आयुक्त नियुक्ति",
        "Seeks a commission for local inspection, measurement or recording of evidence.",
        "Order XXVI, Code of Civil Procedure, 1908",
        [q("purpose", "Purpose of the commission", "आयोग का उद्देश्य", True, "textarea")],
    ),
    (
        "app-attachment-before-judgment",
        "Application — Attachment Before Judgment",
        "आवेदन — निर्णय पूर्व कुर्की",
        "Attaches property where the defendant is about to dispose of it to defeat a decree.",
        "Order XXXVIII Rule 5, Code of Civil Procedure, 1908",
        [q("property_description", "Property to attach", "कुर्की योग्य संपत्ति", True, "textarea"),
         q("apprehension", "Grounds for apprehension", "आशंका के आधार", True, "textarea")],
    ),
    (
        "app-adjournment",
        "Application — Adjournment",
        "आवेदन — स्थगन",
        "Seeks the next date, with the reason recorded. Short, frequent, and worth having ready.",
        "Order XVII, Code of Civil Procedure, 1908",
        [q("reason", "Reason for adjournment", "स्थगन का कारण", True, "textarea")],
    ),
    (
        "app-exemption-appearance",
        "Application — Exemption from Personal Appearance",
        "आवेदन — व्यक्तिगत उपस्थिति से छूट",
        "Excuses the party's presence on a given date, counsel appearing instead.",
        None,
        [q("hearing_date", "Date to be excused", "छूट हेतु दिनांक", True, "date"),
         q("reason", "Reason", "कारण", True, "textarea")],
    ),
    (
        "app-interim-maintenance",
        "Application — Interim Maintenance",
        "आवेदन — अंतरिम भरण-पोषण",
        "Interim support pending the main matrimonial or maintenance proceeding.",
        None,
        [q("monthly_claim", "Monthly amount claimed", "मासिक दावा राशि", True, "number"),
         q("income_details", "Opposite party's income", "विपक्षी की आय", False, "textarea")],
    ),
    (
        "app-production-documents",
        "Application — Production of Documents",
        "आवेदन — दस्तावेज प्रस्तुतीकरण",
        "Seeks a direction to produce documents in the opposite party's possession.",
        "Order XI, Code of Civil Procedure, 1908",
        [q("documents_sought", "Documents sought", "वांछित दस्तावेज", True, "textarea")],
    ),
    (
        "app-caveat",
        "Caveat",
        "कैविएट",
        "Ensures the caveator is heard before any ex-parte order. Valid 90 days.",
        "Section 148A, Code of Civil Procedure, 1908",
        [q("anticipated_matter", "Anticipated proceeding", "संभावित कार्यवाही", True, "textarea")],
    ),
    (
        "app-execution-petition",
        "Execution Petition",
        "निष्पादन याचिका",
        "Enforces a decree by attachment, sale, arrest or delivery of possession.",
        "Order XXI, Code of Civil Procedure, 1908",
        [q("decree_date", "Decree date", "डिक्री दिनांक", True, "date"),
         q("decree_amount", "Amount / relief decreed", "डिक्रीत राशि / अनुतोष", True),
         q("mode_of_execution", "Mode of execution sought", "निष्पादन का प्रकार", True, "textarea")],
    ),
    (
        "app-objection-execution",
        "Objection in Execution",
        "निष्पादन में आपत्ति",
        "Third-party or judgment-debtor objection to attachment or sale.",
        "Order XXI Rule 58, Code of Civil Procedure, 1908",
        [q("objection_grounds", "Grounds of objection", "आपत्ति के आधार", True, "textarea")],
    ),
]:
    tpl(
        code,
        draft_type=LegalDraftType.APPLICATION,
        category="civil-applications",
        forum="civil-court",
        name_en=name_en,
        name_hi=name_hi,
        description=description,
        authority=authority,
        questions=COURT_QUESTIONS + PARTY_QUESTIONS + FACT_QUESTION + GROUND_QUESTION + PRAYER_QUESTION + extra,
    )

# --- 4. criminal --------------------------------------------------------------

CRIMINAL_Q = COURT_QUESTIONS + [
    q("accused_name", "Accused name", "अभियुक्त का नाम", True),
    q("complainant_name", "Complainant / State", "परिवादी / राज्य", True),
    q("police_station", "Police station", "थाना", False),
    q("fir_number", "FIR number", "प्राथमिकी संख्या", False),
    q("fir_date", "FIR date", "प्राथमिकी दिनांक", False, "date"),
    q("offences", "Sections invoked", "लगाई गई धाराएँ", False),
] + FACT_QUESTION

for code, name_en, name_hi, description, authority, extra in [
    (
        "crim-bail-regular",
        "Regular Bail Application",
        "नियमित जमानत आवेदन",
        "Bail for an accused in custody, addressing gravity, antecedents, and the risk of tampering or flight.",
        "Section 483, BNSS 2023 (formerly s.439 CrPC)",
        [q("custody_since", "In custody since", "अभिरक्षा दिनांक", True, "date"),
         q("bail_grounds", "Grounds for bail", "जमानत के आधार", True, "textarea")],
    ),
    (
        "crim-bail-anticipatory",
        "Anticipatory Bail Application",
        "अग्रिम जमानत आवेदन",
        "Pre-arrest protection where apprehension of arrest is reasonable.",
        "Section 482, BNSS 2023 (formerly s.438 CrPC)",
        [q("apprehension", "Basis of apprehension of arrest", "गिरफ्तारी की आशंका का आधार", True, "textarea")],
    ),
    (
        "crim-bail-default",
        "Default Bail Application",
        "डिफ़ॉल्ट जमानत आवेदन",
        "Bail as of right where the charge-sheet was not filed within the statutory period.",
        "Section 187(3), BNSS 2023 (formerly s.167(2) CrPC)",
        [q("custody_since", "In custody since", "अभिरक्षा दिनांक", True, "date"),
         q("period_expired", "Statutory period expired on", "अवधि समाप्ति दिनांक", True, "date")],
    ),
    (
        "crim-complaint-138",
        "Complaint — Cheque Dishonour (s.138 NI Act)",
        "परिवाद — चेक अनादर (धारा 138)",
        "Complaint filed within 30 days of the notice period expiring. Late filing needs a condonation application alongside.",
        "Section 138 read with s.142, Negotiable Instruments Act, 1881",
        [q("cheque_number", "Cheque number", "चेक संख्या", True),
         q("cheque_amount", "Cheque amount", "चेक राशि", True, "number"),
         q("notice_date", "Notice date", "नोटिस दिनांक", True, "date"),
         q("notice_served_date", "Notice served on", "तामील दिनांक", True, "date")],
    ),
    (
        "crim-private-complaint",
        "Private Complaint",
        "निजी परिवाद",
        "Complaint to a magistrate where the police have not registered or acted on the case.",
        "Section 223, BNSS 2023 (formerly s.200 CrPC)",
        [q("witnesses", "Witnesses to be examined", "परीक्षण हेतु गवाह", True, "textarea")],
    ),
    (
        "crim-app-fir-direction",
        "Application for Direction to Register FIR",
        "प्राथमिकी दर्ज कराने हेतु आवेदन",
        "Seeks a magistrate's direction to the police to register and investigate.",
        "Section 175(3), BNSS 2023 (formerly s.156(3) CrPC)",
        [q("police_approach_date", "Police approached on", "पुलिस से संपर्क दिनांक", False, "date"),
         q("inaction", "Nature of police inaction", "पुलिस निष्क्रियता", True, "textarea")],
    ),
    (
        "crim-discharge",
        "Discharge Application",
        "उन्मोचन आवेदन",
        "Seeks discharge where the material does not disclose a case even if taken at face value.",
        "Sections 250 & 262, BNSS 2023",
        [q("discharge_grounds", "Grounds for discharge", "उन्मोचन के आधार", True, "textarea")],
    ),
    (
        "crim-exemption-317",
        "Application — Exemption from Personal Appearance (Criminal)",
        "आवेदन — व्यक्तिगत उपस्थिति से छूट (आपराधिक)",
        "Excuses the accused's attendance on a specific date.",
        "Section 355, BNSS 2023 (formerly s.317 CrPC)",
        [q("hearing_date", "Date", "दिनांक", True, "date"),
         q("reason", "Reason", "कारण", True, "textarea")],
    ),
    (
        "crim-surety-bond",
        "Surety and Bail Bond",
        "जमानतनामा एवं प्रतिभू",
        "Bond and surety particulars furnished after bail is granted.",
        "Sections 478-486, BNSS 2023 (formerly ss.441-445 CrPC)",
        [q("surety_name", "Surety name", "प्रतिभू का नाम", True),
         q("surety_address", "Surety address", "प्रतिभू का पता", True, "textarea"),
         q("bond_amount", "Bond amount", "बंधपत्र राशि", True, "number")],
    ),
    (
        "crim-revision",
        "Criminal Revision",
        "आपराधिक पुनरीक्षण",
        "Challenges an interlocutory or final order of a subordinate criminal court.",
        "Section 438, BNSS 2023 (formerly s.397 CrPC)",
        [q("impugned_order_date", "Impugned order date", "आक्षेपित आदेश दिनांक", True, "date"),
         q("revision_grounds", "Grounds", "आधार", True, "textarea")],
    ),
    (
        "crim-quashing",
        "Petition for Quashing",
        "अभियोजन निरस्तीकरण याचिका",
        "High Court petition to quash an FIR or proceeding. Filed above the district level but drafted here.",
        "Section 528, BNSS 2023 (formerly s.482 CrPC)",
        [q("quashing_grounds", "Grounds for quashing", "निरस्तीकरण के आधार", True, "textarea"),
         q("settlement", "Settlement, if any", "समझौता, यदि कोई", False, "textarea")],
    ),
]:
    tpl(
        code,
        draft_type=LegalDraftType.APPLICATION if "bail" in code or "app" in code else LegalDraftType.PETITION,
        category="criminal",
        forum="criminal-court",
        name_en=name_en,
        name_hi=name_hi,
        description=description,
        authority=authority,
        questions=CRIMINAL_Q + extra,
    )

# --- 5. family ----------------------------------------------------------------

FAMILY_Q = COURT_QUESTIONS + [
    q("husband_name", "Husband's name", "पति का नाम", True),
    q("wife_name", "Wife's name", "पत्नी का नाम", True),
    q("marriage_date", "Date of marriage", "विवाह दिनांक", False, "date"),
    q("marriage_place", "Place of marriage", "विवाह स्थान", False),
    q("children", "Children, if any", "संतान, यदि कोई", False, "textarea"),
] + FACT_QUESTION

for code, name_en, name_hi, description, authority, extra in [
    (
        "family-divorce-mutual",
        "Petition — Divorce by Mutual Consent",
        "याचिका — पारस्परिक सहमति से विवाह विच्छेद",
        "Joint petition with the statutory cooling-off period and settled terms on maintenance, custody and property.",
        "Section 13B, Hindu Marriage Act, 1955",
        [q("separation_since", "Living separately since", "पृथक निवास दिनांक", True, "date"),
         q("settlement_terms", "Agreed terms", "सहमत शर्तें", True, "textarea")],
    ),
    (
        "family-divorce-contested",
        "Petition — Divorce (Contested)",
        "याचिका — विवाह विच्छेद (प्रतिवादित)",
        "Contested petition on statutory grounds such as cruelty or desertion, each of which must be particularised.",
        "Section 13, Hindu Marriage Act, 1955",
        [q("ground", "Ground relied on", "आधार", True, "textarea"),
         q("particulars", "Particulars of the ground", "आधार का विवरण", True, "textarea")],
    ),
    (
        "family-restitution",
        "Petition — Restitution of Conjugal Rights",
        "याचिका — दांपत्य अधिकारों की पुनर्स्थापना",
        "Seeks the return of a spouse who has withdrawn without reasonable excuse.",
        "Section 9, Hindu Marriage Act, 1955",
        [q("withdrawal_date", "Withdrawal since", "पृथक होने की तिथि", False, "date")],
    ),
    (
        "family-maintenance",
        "Application — Maintenance",
        "आवेदन — भरण-पोषण",
        "Maintenance for a wife, child or parent unable to maintain themselves.",
        "Section 144, BNSS 2023 (formerly s.125 CrPC)",
        [q("monthly_claim", "Monthly maintenance claimed", "मासिक भरण-पोषण दावा", True, "number"),
         q("income_details", "Opposite party's means", "विपक्षी के साधन", False, "textarea")],
    ),
    (
        "family-custody",
        "Petition — Custody of Minor",
        "याचिका — अवयस्क की अभिरक्षा",
        "Custody or guardianship, decided on the welfare of the child rather than parental right.",
        "Guardians and Wards Act, 1890",
        [q("child_name", "Child's name and age", "बच्चे का नाम एवं आयु", True),
         q("welfare_grounds", "Welfare considerations", "कल्याण संबंधी आधार", True, "textarea")],
    ),
    (
        "family-domestic-violence",
        "Application — Protection under PWDVA",
        "आवेदन — घरेलू हिंसा संरक्षण",
        "Protection, residence, monetary and custody orders for an aggrieved woman.",
        "Section 12, Protection of Women from Domestic Violence Act, 2005",
        [q("incidents", "Incidents of violence", "हिंसा की घटनाएँ", True, "textarea"),
         q("reliefs_sought", "Reliefs sought", "वांछित अनुतोष", True, "textarea")],
    ),
    (
        "family-succession-certificate",
        "Petition — Succession Certificate",
        "याचिका — उत्तराधिकार प्रमाणपत्र",
        "Authorises the holder to collect the deceased's debts and securities.",
        "Part X, Indian Succession Act, 1925",
        [q("deceased_name", "Deceased", "मृतक", True),
         q("death_date", "Date of death", "मृत्यु दिनांक", True, "date"),
         q("assets", "Debts and securities", "ऋण एवं प्रतिभूतियाँ", True, "textarea"),
         q("heirs", "Legal heirs", "विधिक उत्तराधिकारी", True, "textarea")],
    ),
    (
        "family-legal-heir",
        "Application — Legal Heir Certificate",
        "आवेदन — विधिक उत्तराधिकारी प्रमाणपत्र",
        "Establishes the heirs of a deceased person for service and pension claims.",
        "State revenue/registration rules — no central statute; verify the local provision",
        [q("deceased_name", "Deceased", "मृतक", True),
         q("death_date", "Date of death", "मृत्यु दिनांक", True, "date"),
         q("heirs", "Surviving heirs", "जीवित उत्तराधिकारी", True, "textarea")],
    ),
    (
        "family-guardianship",
        "Petition — Guardianship",
        "याचिका — संरक्षकता",
        "Appointment of a guardian for a minor's person or property.",
        "Guardians and Wards Act, 1890",
        [q("minor_name", "Minor's name and age", "अवयस्क का नाम एवं आयु", True),
         q("property_description", "Minor's property", "अवयस्क की संपत्ति", False, "textarea")],
    ),
]:
    tpl(
        code,
        draft_type=LegalDraftType.PETITION,
        category="family",
        forum="family-court",
        name_en=name_en,
        name_hi=name_hi,
        description=description,
        authority=authority,
        sections=PLEADING,
        questions=FAMILY_Q + extra,
    )

# --- 6. revenue and tehsil ----------------------------------------------------

REVENUE_Q = [
    q("authority_name", "Revenue authority", "राजस्व प्राधिकारी", True),
    q("applicant_name", "Applicant", "आवेदक", True),
    q("village", "Village", "ग्राम", True),
    q("tehsil", "Tehsil", "तहसील", True),
    q("district", "District", "जिला", True),
    q("khasra_number", "Khasra / survey number", "खसरा / सर्वे संख्या", True),
    q("khata_number", "Khata number", "खाता संख्या", False),
    q("area", "Area", "क्षेत्रफल", False),
] + FACT_QUESTION

for code, name_en, name_hi, description, extra in [
    (
        "revenue-mutation",
        "Application — Mutation (Namantaran)",
        "आवेदन — नामांतरण",
        "Records a change of ownership in the revenue records after sale, inheritance or gift.",
        [q("basis", "Basis of mutation", "नामांतरण का आधार", True, "textarea"),
         q("previous_holder", "Previous recorded holder", "पूर्व दर्ज धारक", True)],
    ),
    (
        "revenue-partition-agricultural",
        "Application — Partition of Agricultural Land",
        "आवेदन — कृषि भूमि बँटवारा",
        "Partition of joint holdings before the revenue court.",
        [q("co_sharers", "Co-sharers", "सह-खातेदार", True, "textarea"),
         q("share_claimed", "Share claimed", "दावाकृत हिस्सा", True)],
    ),
    (
        "revenue-record-correction",
        "Application — Correction of Revenue Records",
        "आवेदन — राजस्व अभिलेख शुद्धि",
        "Corrects a clerical or factual error in the khatauni or khasra.",
        [q("error_details", "Error to be corrected", "शुद्धि योग्य त्रुटि", True, "textarea")],
    ),
    (
        "revenue-demarcation",
        "Application — Demarcation of Boundaries",
        "आवेदन — सीमांकन",
        "Seeks measurement and fixing of boundaries by the revenue staff.",
        [q("dispute_details", "Boundary dispute", "सीमा विवाद", True, "textarea")],
    ),
    (
        "revenue-encroachment",
        "Application — Removal of Encroachment",
        "आवेदन — अतिक्रमण हटाना",
        "Removal of encroachment on private or public land.",
        [q("encroacher_name", "Encroacher", "अतिक्रमणकारी", True),
         q("encroachment_details", "Extent of encroachment", "अतिक्रमण का विवरण", True, "textarea")],
    ),
    (
        "revenue-lease-patta",
        "Application — Grant of Patta / Lease",
        "आवेदन — पट्टा आवंटन",
        "Allotment of government land or regularisation of possession.",
        [q("land_details", "Land sought", "वांछित भूमि", True, "textarea"),
         q("eligibility", "Eligibility", "पात्रता", True, "textarea")],
    ),
    (
        "revenue-succession-mutation",
        "Application — Mutation on Inheritance",
        "आवेदन — उत्तराधिकार नामांतरण",
        "Records heirs in the revenue record after a landholder's death.",
        [q("deceased_name", "Deceased holder", "मृतक धारक", True),
         q("death_date", "Date of death", "मृत्यु दिनांक", True, "date"),
         q("heirs", "Heirs", "उत्तराधिकारी", True, "textarea")],
    ),
    (
        "revenue-stay-application",
        "Application — Stay of Revenue Proceedings",
        "आवेदन — राजस्व कार्यवाही स्थगन",
        "Interim stay pending decision of the revenue appeal or revision.",
        [q("proceeding_details", "Proceeding to be stayed", "स्थगन योग्य कार्यवाही", True, "textarea")],
    ),
    (
        "revenue-appeal",
        "Revenue Appeal",
        "राजस्व अपील",
        "Appeal to the SDM, Collector or Commissioner against a revenue order.",
        [q("impugned_order_date", "Impugned order date", "आक्षेपित आदेश दिनांक", True, "date"),
         q("appeal_grounds", "Grounds of appeal", "अपील के आधार", True, "textarea")],
    ),
    (
        "revenue-caste-domicile",
        "Application — Caste / Domicile / Income Certificate",
        "आवेदन — जाति / निवास / आय प्रमाणपत्र",
        "Certificate application before the tehsildar, with the supporting documents listed.",
        [q("certificate_type", "Certificate sought", "वांछित प्रमाणपत्र", True),
         q("supporting_documents", "Supporting documents", "संलग्न दस्तावेज", False, "textarea")],
    ),
]:
    tpl(
        code,
        draft_type=LegalDraftType.APPLICATION,
        category="revenue",
        forum="revenue-court",
        name_en=name_en,
        name_hi=name_hi,
        description=description,
        authority="State land revenue code — verify the local provision",
        questions=REVENUE_Q + extra + PRAYER_QUESTION,
    )

# --- 7. motor accident, consumer, labour --------------------------------------

tpl(
    "mact-claim-petition",
    draft_type=LegalDraftType.PETITION,
    category="claims",
    forum="tribunal",
    name_en="MACT Claim Petition",
    name_hi="मोटर दुर्घटना दावा याचिका",
    description="Compensation claim before the Motor Accidents Claims Tribunal, with income, dependency and multiplier pleaded.",
    authority="Section 166, Motor Vehicles Act, 1988",
    sections=PLEADING,
    questions=COURT_QUESTIONS + PARTY_QUESTIONS + FACT_QUESTION + [
        q("accident_date", "Date of accident", "दुर्घटना दिनांक", True, "date"),
        q("accident_place", "Place of accident", "दुर्घटना स्थल", True),
        q("vehicle_number", "Offending vehicle number", "वाहन संख्या", True),
        q("insurer", "Insurer", "बीमा कंपनी", False),
        q("injury_details", "Injuries / death", "चोट / मृत्यु विवरण", True, "textarea"),
        q("deceased_income", "Income of deceased / injured", "आय", False, "number"),
        q("dependents", "Dependants", "आश्रित", False, "textarea"),
        q("compensation_claimed", "Compensation claimed", "दावाकृत क्षतिपूर्ति", True, "number"),
    ],
)

tpl(
    "consumer-complaint",
    draft_type=LegalDraftType.PETITION,
    category="claims",
    forum="consumer-commission",
    name_en="Consumer Complaint",
    name_hi="उपभोक्ता परिवाद",
    description="Complaint before the District Consumer Commission for defective goods or deficient service.",
    authority="Section 35, Consumer Protection Act, 2019",
    sections=PLEADING,
    questions=COURT_QUESTIONS + PARTY_QUESTIONS + FACT_QUESTION + [
        q("purchase_date", "Date of purchase / service", "खरीद दिनांक", True, "date"),
        q("amount_paid", "Amount paid", "भुगतान राशि", True, "number"),
        q("defect", "Defect or deficiency", "दोष / सेवा में कमी", True, "textarea"),
        q("compensation_claimed", "Compensation claimed", "दावाकृत क्षतिपूर्ति", False, "number"),
    ],
)

tpl(
    "labour-recovery-33c2",
    draft_type=LegalDraftType.APPLICATION,
    category="claims",
    forum="labour-court",
    name_en="Application — Recovery of Wages",
    name_hi="आवेदन — वेतन वसूली",
    description="Recovery of money due to a workman where the entitlement is already settled.",
    authority="Section 33C(2), Industrial Disputes Act, 1947",
    questions=COURT_QUESTIONS + PARTY_QUESTIONS + FACT_QUESTION + [
        q("employment_period", "Period of employment", "सेवा अवधि", True),
        q("amount_claimed", "Amount claimed", "दावाकृत राशि", True, "number"),
    ],
)

tpl(
    "labour-gratuity-claim",
    draft_type=LegalDraftType.APPLICATION,
    category="claims",
    forum="labour-court",
    name_en="Application — Gratuity Claim",
    name_hi="आवेदन — उपदान दावा",
    description="Claim before the Controlling Authority for unpaid gratuity.",
    authority="Payment of Gratuity Act, 1972",
    questions=COURT_QUESTIONS + PARTY_QUESTIONS + [
        q("employment_period", "Period of service", "सेवा अवधि", True),
        q("last_drawn_wages", "Last drawn wages", "अंतिम आहरित वेतन", True, "number"),
    ] + FACT_QUESTION,
)

# --- 8. supporting documents --------------------------------------------------

tpl(
    "vakalatnama",
    draft_type=LegalDraftType.APPLICATION,
    category="supporting",
    forum="all",
    name_en="Vakalatnama",
    name_hi="वकालतनामा",
    description="Authority to appear. Filed with the first pleading in every matter.",
    sections=[
        s("court", "Court & Cause Title", "न्यायालय एवं वाद शीर्षक"),
        s("authority", "Authority Granted", "प्रदत्त अधिकार"),
        s("execution", "Execution & Acceptance", "निष्पादन एवं स्वीकृति"),
    ],
    questions=COURT_QUESTIONS + [
        q("client_name", "Client name", "मुवक्किल का नाम", True),
        q("advocate_name", "Advocate name", "अधिवक्ता का नाम", True),
        q("enrolment_number", "Enrolment number", "नामांकन संख्या", False),
    ],
)

tpl(
    "memo-of-parties",
    draft_type=LegalDraftType.ANNEXURE_INDEX,
    category="supporting",
    forum="all",
    name_en="Memo of Parties",
    name_hi="पक्षकार विवरण",
    description="Full names, parentage, age and addresses of every party, as required for summons.",
    sections=[s("parties", "Parties", "पक्षकार")],
    questions=COURT_QUESTIONS + PARTY_QUESTIONS,
)

tpl(
    "affidavit-general",
    draft_type=LegalDraftType.AFFIDAVIT,
    category="supporting",
    forum="all",
    name_en="General Affidavit",
    name_hi="सामान्य शपथपत्र",
    description="Sworn statement in support of a pleading or application.",
    sections=[
        s("court", "Court & Cause Title", "न्यायालय एवं वाद शीर्षक"),
        s("deponent", "Deponent", "शपथकर्ता"),
        s("statements", "Statements", "कथन"),
        s("verification", "Verification", "सत्यापन"),
    ],
    questions=COURT_QUESTIONS + [
        q("deponent_name", "Deponent name", "शपथकर्ता का नाम", True),
        q("deponent_age", "Age", "आयु", False, "number"),
        q("deponent_address", "Address", "पता", True, "textarea"),
        q("statements", "Statements on oath", "शपथ पर कथन", True, "textarea"),
    ],
)

tpl(
    "affidavit-no-objection",
    draft_type=LegalDraftType.AFFIDAVIT,
    category="supporting",
    forum="all",
    name_en="No-Objection Affidavit",
    name_hi="अनापत्ति शपथपत्र",
    description="Consent affidavit, commonly required in mutation, succession and transfer matters.",
    sections=[
        s("deponent", "Deponent", "शपथकर्ता"),
        s("statements", "No Objection", "अनापत्ति"),
        s("verification", "Verification", "सत्यापन"),
    ],
    questions=[
        q("deponent_name", "Deponent", "शपथकर्ता", True),
        q("subject", "Subject of no-objection", "अनापत्ति का विषय", True, "textarea"),
        q("beneficiary", "In whose favour", "किसके पक्ष में", True),
    ],
)

tpl(
    "list-of-documents",
    draft_type=LegalDraftType.ANNEXURE_INDEX,
    category="supporting",
    forum="all",
    name_en="List of Documents / Annexure Index",
    name_hi="दस्तावेज सूची",
    description="Numbered index of filed documents with annexure marks and page numbers.",
    sections=[s("index", "Index", "अनुक्रमणिका")],
    questions=COURT_QUESTIONS + [
        q("documents", "Documents filed", "दाखिल दस्तावेज", True, "textarea"),
    ],
)

tpl(
    "synopsis-list-of-dates",
    draft_type=LegalDraftType.CASE_SYNOPSIS,
    category="supporting",
    forum="all",
    name_en="Synopsis and List of Dates",
    name_hi="सारांश एवं तिथि सूची",
    description="Opening pages of an appeal or petition: the case in brief, then every material date in order.",
    sections=[
        s("synopsis", "Synopsis", "सारांश"),
        s("dates", "List of Dates", "तिथि सूची"),
    ],
    questions=COURT_QUESTIONS + [
        q("synopsis", "Synopsis", "सारांश", True, "textarea"),
    ],
)

tpl(
    "cross-examination-questions",
    draft_type=LegalDraftType.HEARING_NOTE,
    category="supporting",
    forum="all",
    name_en="Cross-Examination Question Set",
    name_hi="प्रति-परीक्षण प्रश्न सूची",
    description="Question plan for a witness, grouped by the contradiction or omission each line is aimed at.",
    sections=[
        s("witness", "Witness", "साक्षी"),
        s("objectives", "Objectives", "उद्देश्य"),
        s("questions", "Questions", "प्रश्न"),
        s("documents", "Documents to Confront", "प्रस्तुत दस्तावेज"),
    ],
    questions=[
        q("witness_name", "Witness", "साक्षी", True),
        q("objectives", "What to establish", "क्या स्थापित करना है", True, "textarea"),
    ],
)

# --- 9. deeds and conveyancing ------------------------------------------------

DEED_Q = [
    q("first_party", "First party (transferor)", "प्रथम पक्ष (अंतरणकर्ता)", True),
    q("second_party", "Second party (transferee)", "द्वितीय पक्ष (अंतरिती)", True),
    q("property_description", "Property description", "संपत्ति का विवरण", True, "textarea"),
    q("consideration", "Consideration", "प्रतिफल", False, "number"),
    q("stamp_value", "Value for stamp duty", "स्टांप शुल्क हेतु मूल्य", False, "number"),
    q("witnesses", "Witnesses", "गवाह", False, "textarea"),
]

for code, name_en, name_hi, description, extra in [
    ("deed-sale", "Sale Deed", "विक्रय पत्र", "Conveys ownership on payment of consideration; requires registration.", []),
    ("deed-agreement-to-sell", "Agreement to Sell", "बयाना / विक्रय अनुबंध", "Records the bargain and the time for performance before the sale deed.", [q("completion_date", "Date for completion", "पूर्णता तिथि", False, "date")]),
    ("deed-gift", "Gift Deed", "दान पत्र", "Voluntary transfer without consideration; acceptance during the donor's lifetime is essential.", [q("relationship", "Relationship to donee", "संबंध", False)]),
    ("deed-relinquishment", "Relinquishment Deed", "अधिकार त्याग पत्र", "Co-heir releases their share in favour of the other heirs.", [q("share_released", "Share released", "त्यक्त हिस्सा", True)]),
    ("deed-partition", "Partition Deed", "बँटवारा पत्र", "Records an agreed division of joint property by metes and bounds.", [q("shares", "Shares allotted", "आवंटित हिस्से", True, "textarea")]),
    ("deed-lease", "Lease Deed", "पट्टा विलेख", "Grants possession for a term at a rent.", [q("term_months", "Term (months)", "अवधि (माह)", True, "number"), q("rent_amount", "Rent", "किराया", True, "number")]),
    ("deed-rent-agreement", "Rent Agreement", "किरायानामा", "Eleven-month tenancy agreement, the standard residential form.", [q("rent_amount", "Monthly rent", "मासिक किराया", True, "number"), q("security_deposit", "Security deposit", "प्रतिभूति राशि", False, "number")]),
    ("deed-mortgage", "Mortgage Deed", "बंधक पत्र", "Security over immovable property for a loan.", [q("loan_amount", "Loan amount", "ऋण राशि", True, "number")]),
    ("deed-will", "Will", "वसीयत", "Testamentary disposition. Two attesting witnesses are essential; registration is optional but prudent.", [q("beneficiaries", "Beneficiaries and bequests", "उत्तराधिकारी एवं वसीयत", True, "textarea"), q("executor", "Executor", "निष्पादक", False)]),
    ("deed-gpa", "General Power of Attorney", "आम मुख्तारनामा", "Broad authority to act; scope should be stated narrowly in practice.", [q("powers", "Powers granted", "प्रदत्त अधिकार", True, "textarea")]),
    ("deed-spa", "Special Power of Attorney", "विशेष मुख्तारनामा", "Authority limited to one transaction or proceeding.", [q("specific_purpose", "Specific purpose", "विशिष्ट प्रयोजन", True, "textarea")]),
    ("deed-partnership", "Partnership Deed", "साझेदारी विलेख", "Constitutes a firm, with capital, profit sharing and retirement terms.", [q("partners", "Partners and capital", "साझेदार एवं पूंजी", True, "textarea"), q("profit_ratio", "Profit sharing ratio", "लाभ अनुपात", True)]),
    ("deed-adoption", "Adoption Deed", "दत्तक ग्रहण पत्र", "Records an adoption and the giving and taking ceremony.", [q("child_name", "Child adopted", "दत्तक बालक", True)]),
    ("deed-exchange", "Exchange Deed", "विनिमय पत्र", "Mutual transfer of one property for another.", [q("other_property", "Property received", "प्राप्त संपत्ति", True, "textarea")]),
]:
    tpl(
        code,
        draft_type=LegalDraftType.APPLICATION,
        category="deeds",
        forum="registration",
        name_en=name_en,
        name_hi=name_hi,
        description=description,
        authority="Transfer of Property Act, 1882 and Registration Act, 1908 — verify state stamp duty",
        sections=DEED_SECTIONS,
        questions=DEED_Q + extra,
    )

# --- 10. appeals and writs ----------------------------------------------------

tpl(
    "civil-appeal",
    draft_type=LegalDraftType.PETITION,
    category="appeals",
    forum="appellate",
    name_en="Civil Appeal (Memorandum)",
    name_hi="सिविल अपील ज्ञापन",
    description="Memorandum of appeal against a decree, with grounds stated separately and numbered.",
    authority="Order XLI, Code of Civil Procedure, 1908",
    sections=HEADING + [
        s("impugned", "Impugned Decree", "आक्षेपित डिक्री"),
        s("facts", "Facts", "तथ्य"),
        s("grounds", "Grounds of Appeal", "अपील के आधार"),
        s("prayer", "Prayer", "प्रार्थना"),
    ] + VERIFICATION,
    questions=COURT_QUESTIONS + PARTY_QUESTIONS + [
        q("impugned_order_date", "Date of decree", "डिक्री दिनांक", True, "date"),
        q("lower_court", "Court below", "अधीनस्थ न्यायालय", True),
        q("appeal_grounds", "Grounds of appeal", "अपील के आधार", True, "textarea"),
    ] + PRAYER_QUESTION,
)

tpl(
    "civil-revision",
    draft_type=LegalDraftType.PETITION,
    category="appeals",
    forum="appellate",
    name_en="Civil Revision",
    name_hi="सिविल पुनरीक्षण",
    description="Revision where no appeal lies, confined to jurisdictional error.",
    authority="Section 115, Code of Civil Procedure, 1908",
    sections=PLEADING,
    questions=COURT_QUESTIONS + PARTY_QUESTIONS + [
        q("impugned_order_date", "Impugned order date", "आक्षेपित आदेश दिनांक", True, "date"),
        q("jurisdictional_error", "Jurisdictional error", "क्षेत्राधिकार संबंधी त्रुटि", True, "textarea"),
    ],
)

tpl(
    "writ-petition-226",
    draft_type=LegalDraftType.PETITION,
    category="appeals",
    forum="high-court",
    name_en="Writ Petition (Article 226)",
    name_hi="रिट याचिका (अनुच्छेद 226)",
    description="High Court petition against state action, where no equally efficacious alternative remedy exists.",
    authority="Article 226, Constitution of India",
    sections=HEADING + [
        s("synopsis", "Synopsis & List of Dates", "सारांश एवं तिथि सूची"),
        s("facts", "Facts", "तथ्य"),
        s("grounds", "Grounds", "आधार"),
        s("alternative_remedy", "Alternative Remedy", "वैकल्पिक उपचार"),
        s("prayer", "Prayer", "प्रार्थना"),
    ] + VERIFICATION,
    questions=COURT_QUESTIONS + PARTY_QUESTIONS + FACT_QUESTION + GROUND_QUESTION + PRAYER_QUESTION + [
        q("impugned_action", "Impugned action or order", "आक्षेपित कार्रवाई", True, "textarea"),
        q("alternative_remedy", "Why no alternative remedy", "वैकल्पिक उपचार क्यों नहीं", False, "textarea"),
    ],
)

# --- registry access ----------------------------------------------------------

TEMPLATES: dict[str, dict] = {entry["code"]: entry for entry in _TEMPLATES}

CATEGORIES: dict[str, dict[str, str]] = {
    "notices": {"name_en": "Notices & Pre-litigation", "name_hi": "नोटिस एवं पूर्व-वाद"},
    "civil-pleadings": {"name_en": "Civil Pleadings", "name_hi": "सिविल अभिवचन"},
    "civil-applications": {"name_en": "Civil Applications", "name_hi": "सिविल आवेदन"},
    "criminal": {"name_en": "Criminal", "name_hi": "आपराधिक"},
    "family": {"name_en": "Family & Matrimonial", "name_hi": "पारिवारिक एवं वैवाहिक"},
    "revenue": {"name_en": "Revenue & Tehsil", "name_hi": "राजस्व एवं तहसील"},
    "claims": {"name_en": "Claims & Tribunals", "name_hi": "दावे एवं अधिकरण"},
    "supporting": {"name_en": "Supporting Documents", "name_hi": "सहायक दस्तावेज"},
    "deeds": {"name_en": "Deeds & Conveyancing", "name_hi": "विलेख एवं संपत्ति अंतरण"},
    "appeals": {"name_en": "Appeals, Revisions & Writs", "name_hi": "अपील, पुनरीक्षण एवं रिट"},
}


def list_templates(
    *, category: str | None = None, forum: str | None = None, search: str | None = None
) -> list[dict]:
    """Catalogue entries, optionally filtered. Search matches name, code or description."""
    needle = (search or "").strip().casefold()
    results = []
    for entry in _TEMPLATES:
        if category and entry["category"] != category:
            continue
        if forum and entry["forum"] != forum:
            continue
        if needle and needle not in " ".join(
            [entry["code"], entry["name_en"], entry["name_hi"], entry["description"]]
        ).casefold():
            continue
        results.append(
            {
                "code": entry["code"],
                "draft_type": entry["draft_type"].value,
                "category": entry["category"],
                "category_name_en": CATEGORIES[entry["category"]]["name_en"],
                "category_name_hi": CATEGORIES[entry["category"]]["name_hi"],
                "forum": entry["forum"],
                "name_en": entry["name_en"],
                "name_hi": entry["name_hi"],
                "description": entry["description"],
                "authority": entry["authority"],
                "section_count": len(entry["sections"]),
                "question_count": len(entry["questions"]),
                "verified": entry["verified"],
            }
        )
    return results


def get_template(code: str) -> dict | None:
    return TEMPLATES.get(code)
