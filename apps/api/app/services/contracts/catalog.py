from __future__ import annotations

from typing import Any

from app.models.contract import ContractType


ALL_TYPES = [item.value for item in ContractType]
PAID_TYPES = {
    ContractType.EMPLOYMENT.value,
    ContractType.CONSULTING.value,
    ContractType.FREELANCE.value,
    ContractType.VENDOR.value,
    ContractType.SERVICES.value,
    ContractType.SAAS.value,
    ContractType.SOFTWARE_DEVELOPMENT.value,
}


def question(
    key: str,
    label_en: str,
    label_hi: str,
    *,
    kind: str = "text",
    required: bool = False,
    placeholder: str | None = None,
    options: list[dict[str, str]] | None = None,
    default: Any = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label_en": label_en,
        "label_hi": label_hi,
        "kind": kind,
        "required": required,
        "placeholder": placeholder,
        "options": options or [],
        "default": default,
    }


COMMON_QUESTIONS = [
    question("party_a_address", "Party A address", "पक्ष A का पता", required=True),
    question("party_b_address", "Party B address", "पक्ष B का पता", required=True),
    question("effective_date", "Effective date", "प्रभावी तिथि", kind="date", required=True),
    question("governing_state", "Governing State / UT", "लागू राज्य / केंद्र शासित प्रदेश", required=True),
    question(
        "dispute_mode",
        "Dispute resolution",
        "विवाद समाधान",
        kind="select",
        required=True,
        default="arbitration",
        options=[
            {"value": "arbitration", "label_en": "Arbitration", "label_hi": "मध्यस्थता"},
            {"value": "courts", "label_en": "Courts", "label_hi": "न्यायालय"},
        ],
    ),
    question("arbitration_city", "Arbitration / jurisdiction city", "मध्यस्थता / क्षेत्राधिकार शहर"),
    question("notice_days", "Termination notice (days)", "समाप्ति सूचना (दिन)", kind="number", default=30),
]


CONTRACT_DEFINITIONS: dict[str, dict[str, Any]] = {
    ContractType.NDA.value: {
        "name_en": "Non-Disclosure Agreement",
        "name_hi": "गोपनीयता समझौता",
        "description": "Mutual or one-way confidentiality arrangement.",
        "required_fields": ["purpose", "confidentiality_term_months"],
        "questions": [
            question("purpose", "Purpose of disclosure", "जानकारी साझा करने का उद्देश्य", required=True),
            question("confidentiality_term_months", "Confidentiality period (months)", "गोपनीयता अवधि (महीने)", kind="number", required=True, default=36),
            question("mutual", "Mutual NDA", "पारस्परिक NDA", kind="boolean", default=True),
        ],
        "clauses": ["purpose", "confidentiality", "confidentiality_exclusions", "permitted_disclosure", "return_destroy", "term_termination", "remedies", "governing_law", "dispute_resolution", "notices", "entire_agreement"],
    },
    ContractType.EMPLOYMENT.value: {
        "name_en": "Employment Agreement",
        "name_hi": "रोज़गार समझौता",
        "description": "Employment terms with compensation, confidentiality and IP provisions.",
        "required_fields": ["role_title", "start_date", "monthly_salary", "work_location"],
        "questions": [
            question("role_title", "Role / designation", "पद / भूमिका", required=True),
            question("start_date", "Start date", "कार्य प्रारंभ तिथि", kind="date", required=True),
            question("monthly_salary", "Monthly gross compensation (INR)", "मासिक सकल वेतन (INR)", kind="number", required=True),
            question("work_location", "Primary work location", "मुख्य कार्य स्थान", required=True),
            question("probation_months", "Probation (months)", "परिवीक्षा (महीने)", kind="number", default=3),
            question("benefits_summary", "Benefits summary", "लाभों का सार"),
        ],
        "clauses": ["appointment_scope", "fees_payment", "confidentiality", "ip", "data_protection", "non_solicit", "term_termination", "governing_law", "dispute_resolution", "notices", "force_majeure", "entire_agreement"],
    },
    ContractType.CONSULTING.value: {
        "name_en": "Consulting Agreement",
        "name_hi": "परामर्श समझौता",
        "description": "Independent consultant engagement and deliverables.",
        "required_fields": ["scope_description", "fee_amount", "payment_schedule"],
        "questions": [
            question("scope_description", "Services / deliverables", "सेवाएँ / डिलिवरेबल्स", kind="textarea", required=True),
            question("fee_amount", "Fees (INR)", "शुल्क (INR)", kind="number", required=True),
            question("payment_schedule", "Payment schedule", "भुगतान अनुसूची", required=True, placeholder="Monthly / milestone / 50-50"),
            question("term_months", "Term (months)", "अवधि (महीने)", kind="number", default=6),
        ],
        "clauses": ["appointment_scope", "fees_payment", "confidentiality", "ip", "data_protection", "non_solicit", "term_termination", "warranty", "liability", "indemnity", "governing_law", "dispute_resolution", "notices", "force_majeure", "assignment", "entire_agreement"],
    },
    ContractType.FREELANCE.value: {
        "name_en": "Freelance Services Agreement",
        "name_hi": "फ्रीलांस सेवा समझौता",
        "description": "Project-based freelance services and IP transfer.",
        "required_fields": ["scope_description", "fee_amount", "payment_schedule"],
        "questions": [
            question("scope_description", "Project scope", "प्रोजेक्ट का दायरा", kind="textarea", required=True),
            question("fee_amount", "Project fee (INR)", "प्रोजेक्ट शुल्क (INR)", kind="number", required=True),
            question("payment_schedule", "Payment schedule", "भुगतान अनुसूची", required=True, default="50% advance, 50% on completion"),
            question("revision_rounds", "Included revision rounds", "शामिल संशोधन राउंड", kind="number", default=2),
            question("delivery_date", "Target delivery date", "लक्षित डिलीवरी तिथि", kind="date"),
        ],
        "clauses": ["appointment_scope", "fees_payment", "confidentiality", "ip", "term_termination", "warranty", "liability", "indemnity", "governing_law", "dispute_resolution", "notices", "force_majeure", "assignment", "entire_agreement"],
    },
    ContractType.VENDOR.value: {
        "name_en": "Vendor / Supplier Agreement",
        "name_hi": "विक्रेता / आपूर्तिकर्ता समझौता",
        "description": "Supply of goods or recurring vendor services.",
        "required_fields": ["scope_description", "fee_amount", "payment_schedule", "delivery_terms"],
        "questions": [
            question("scope_description", "Goods / services", "वस्तुएँ / सेवाएँ", kind="textarea", required=True),
            question("fee_amount", "Contract value (INR)", "अनुबंध मूल्य (INR)", kind="number", required=True),
            question("payment_schedule", "Payment terms", "भुगतान शर्तें", required=True, default="Within 30 days of valid invoice"),
            question("delivery_terms", "Delivery / acceptance terms", "डिलीवरी / स्वीकृति शर्तें", required=True),
            question("warranty_days", "Warranty period (days)", "वारंटी अवधि (दिन)", kind="number", default=90),
        ],
        "clauses": ["appointment_scope", "fees_payment", "confidentiality", "data_protection", "term_termination", "warranty", "liability", "indemnity", "governing_law", "dispute_resolution", "notices", "force_majeure", "assignment", "entire_agreement"],
    },
    ContractType.SERVICES.value: {
        "name_en": "Services Agreement",
        "name_hi": "सेवा समझौता",
        "description": "General business-to-business services engagement.",
        "required_fields": ["scope_description", "fee_amount", "payment_schedule"],
        "questions": [
            question("scope_description", "Services", "सेवाएँ", kind="textarea", required=True),
            question("fee_amount", "Fees (INR)", "शुल्क (INR)", kind="number", required=True),
            question("payment_schedule", "Payment terms", "भुगतान शर्तें", required=True),
            question("service_level", "Service levels / turnaround", "सेवा स्तर / समय सीमा"),
        ],
        "clauses": ["appointment_scope", "fees_payment", "confidentiality", "ip", "data_protection", "term_termination", "warranty", "liability", "indemnity", "governing_law", "dispute_resolution", "notices", "force_majeure", "assignment", "entire_agreement"],
    },
    ContractType.SAAS.value: {
        "name_en": "SaaS Subscription Agreement",
        "name_hi": "SaaS सदस्यता समझौता",
        "description": "Cloud software subscription, support and data handling.",
        "required_fields": ["service_name", "fee_amount", "payment_schedule"],
        "questions": [
            question("service_name", "Service / product name", "सेवा / उत्पाद का नाम", required=True),
            question("scope_description", "Subscription scope", "सदस्यता का दायरा", kind="textarea", required=True),
            question("fee_amount", "Subscription fees (INR)", "सदस्यता शुल्क (INR)", kind="number", required=True),
            question("payment_schedule", "Billing frequency", "बिलिंग आवृत्ति", required=True, default="Annual in advance"),
            question("service_level", "Support / uptime commitment", "सहायता / अपटाइम प्रतिबद्धता"),
            question("data_processing", "Will customer personal data be processed?", "क्या ग्राहक का व्यक्तिगत डेटा प्रोसेस होगा?", kind="boolean", default=True),
        ],
        "clauses": ["appointment_scope", "fees_payment", "acceptable_use", "confidentiality", "ip", "data_protection", "term_termination", "warranty", "liability", "indemnity", "governing_law", "dispute_resolution", "notices", "force_majeure", "assignment", "entire_agreement"],
    },
    ContractType.SOFTWARE_DEVELOPMENT.value: {
        "name_en": "Software Development Agreement",
        "name_hi": "सॉफ्टवेयर विकास समझौता",
        "description": "Custom software build with milestones, acceptance and IP terms.",
        "required_fields": ["scope_description", "fee_amount", "payment_schedule", "delivery_date"],
        "questions": [
            question("scope_description", "Project scope / specifications", "प्रोजेक्ट दायरा / विनिर्देश", kind="textarea", required=True),
            question("fee_amount", "Project fee (INR)", "प्रोजेक्ट शुल्क (INR)", kind="number", required=True),
            question("payment_schedule", "Milestone payment schedule", "माइलस्टोन भुगतान अनुसूची", required=True),
            question("delivery_date", "Target delivery date", "लक्षित डिलीवरी तिथि", kind="date", required=True),
            question("acceptance_days", "Acceptance testing period (days)", "स्वीकृति परीक्षण अवधि (दिन)", kind="number", default=10),
            question("warranty_days", "Defect warranty (days)", "दोष वारंटी (दिन)", kind="number", default=60),
        ],
        "clauses": ["appointment_scope", "fees_payment", "acceptance", "confidentiality", "ip", "data_protection", "term_termination", "warranty", "liability", "indemnity", "governing_law", "dispute_resolution", "notices", "force_majeure", "assignment", "entire_agreement"],
    },
}


for definition in CONTRACT_DEFINITIONS.values():
    definition["questions"] = COMMON_QUESTIONS + definition["questions"]


def _clause(
    clause_type: str,
    title_en: str,
    title_hi: str,
    body_en: str,
    body_hi: str,
    *,
    variant: str = "balanced",
    contract_types: list[str] | None = None,
    variables: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "code": f"{clause_type}.{variant}",
        "clause_type": clause_type,
        "variant_key": variant,
        "title_en": title_en,
        "title_hi": title_hi,
        "body_en": body_en.strip(),
        "body_hi": body_hi.strip(),
        "contract_types_json": contract_types or ALL_TYPES,
        "variables_json": variables or [],
        "version": 1,
        "active": True,
        "metadata_json": {"jurisdiction_pack": "india", "lawyer_review_required": True},
    }


BUILTIN_CLAUSES: list[dict[str, Any]] = [
    _clause(
        "purpose", "Purpose", "उद्देश्य",
        "The Parties may disclose Confidential Information solely for {{purpose}} (the “Purpose”). No licence or other right is granted except as expressly stated in this Agreement.",
        "पक्ष केवल {{purpose}} (\"उद्देश्य\") के लिए गोपनीय जानकारी साझा कर सकते हैं। इस समझौते में स्पष्ट रूप से दिए गए अधिकारों के अतिरिक्त कोई लाइसेंस या अन्य अधिकार प्रदान नहीं किया जाता।",
        contract_types=[ContractType.NDA.value], variables=["purpose"],
    ),
    _clause(
        "appointment_scope", "Scope and Responsibilities", "कार्य-क्षेत्र और दायित्व",
        "{{party_a_name}} engages {{party_b_name}} for the following scope: {{scope_description}}. Each Party shall perform its stated responsibilities in a professional and timely manner and shall cooperate reasonably to enable performance.",
        "{{party_a_name}}, {{party_b_name}} को निम्न कार्य-क्षेत्र के लिए नियुक्त करता/करती है: {{scope_description}}। प्रत्येक पक्ष अपने निर्धारित दायित्वों का पेशेवर और समयबद्ध तरीके से पालन करेगा और कार्य-निष्पादन हेतु उचित सहयोग देगा।",
        contract_types=[t for t in ALL_TYPES if t != ContractType.NDA.value], variables=["scope_description"],
    ),
    _clause(
        "fees_payment", "Fees and Payment", "शुल्क और भुगतान",
        "The commercial consideration is INR {{fee_amount}}. Payment shall be made as follows: {{payment_schedule}}. Valid, undisputed invoices shall be paid according to the agreed schedule. Taxes shall be dealt with as applicable to the transaction.",
        "वाणिज्यिक प्रतिफल INR {{fee_amount}} है। भुगतान इस प्रकार किया जाएगा: {{payment_schedule}}। वैध और निर्विवाद चालानों का भुगतान सहमत अनुसूची के अनुसार किया जाएगा। करों का निपटान लेन-देन पर लागू नियमों के अनुसार किया जाएगा।",
        contract_types=list(PAID_TYPES), variables=["fee_amount", "payment_schedule"],
    ),
    _clause(
        "confidentiality", "Confidentiality", "गोपनीयता",
        "Each receiving Party shall use the other Party’s Confidential Information only for this Agreement, protect it using at least reasonable care, and disclose it only to personnel or advisers who need to know it and are bound by confidentiality obligations. The confidentiality period is {{confidentiality_term_months}} months unless a longer period is required for information that remains legally protectable.",
        "प्रत्येक प्राप्तकर्ता पक्ष दूसरे पक्ष की गोपनीय जानकारी का उपयोग केवल इस समझौते के लिए करेगा, कम-से-कम उचित सावधानी से उसकी सुरक्षा करेगा और उसे केवल ऐसे कर्मचारियों या सलाहकारों को बताएगा जिन्हें इसकी आवश्यकता हो तथा जो गोपनीयता दायित्वों से बंधे हों। गोपनीयता अवधि {{confidentiality_term_months}} महीने होगी, जब तक कि विधिक रूप से संरक्षित जानकारी के लिए अधिक अवधि आवश्यक न हो।",
        variables=["confidentiality_term_months"],
    ),
    _clause(
        "confidentiality_exclusions", "Exclusions from Confidential Information", "गोपनीय जानकारी से अपवाद",
        "Confidential Information does not include information that the receiving Party can demonstrate was lawfully known without restriction, becomes public without breach, is independently developed without use of the disclosed information, or is lawfully received from a third party without a duty of confidence.",
        "गोपनीय जानकारी में वह जानकारी शामिल नहीं होगी जिसे प्राप्तकर्ता पक्ष यह सिद्ध कर सके कि वह बिना प्रतिबंध के पहले से विधिसम्मत रूप से ज्ञात थी, उल्लंघन के बिना सार्वजनिक हो गई, साझा जानकारी का उपयोग किए बिना स्वतंत्र रूप से विकसित की गई, या किसी तृतीय पक्ष से गोपनीयता दायित्व के बिना विधिसम्मत रूप से प्राप्त हुई।",
        contract_types=[ContractType.NDA.value],
    ),
    _clause(
        "permitted_disclosure", "Required Disclosure", "आवश्यक प्रकटीकरण",
        "A Party may disclose Confidential Information to the extent required by law or a binding order, provided it gives prompt notice where legally permitted and reasonably assists the other Party in seeking protective treatment.",
        "कोई पक्ष कानून या बाध्यकारी आदेश द्वारा आवश्यक सीमा तक गोपनीय जानकारी प्रकट कर सकता है, बशर्ते जहाँ विधिक रूप से अनुमति हो वहाँ शीघ्र सूचना दे और संरक्षणात्मक उपाय प्राप्त करने में दूसरे पक्ष को उचित सहयोग प्रदान करे।",
        contract_types=[ContractType.NDA.value],
    ),
    _clause(
        "return_destroy", "Return or Destruction", "वापसी या नष्ट करना",
        "Upon written request or termination, the receiving Party shall return or securely destroy Confidential Information, except for archival copies required for law, compliance or automated backup, which remain subject to confidentiality obligations.",
        "लिखित अनुरोध या समाप्ति पर प्राप्तकर्ता पक्ष गोपनीय जानकारी वापस करेगा या सुरक्षित रूप से नष्ट करेगा, सिवाय उन अभिलेखीय प्रतियों के जो कानून, अनुपालन या स्वचालित बैकअप के लिए आवश्यक हों; ऐसी प्रतियाँ गोपनीयता दायित्वों के अधीन रहेंगी।",
        contract_types=[ContractType.NDA.value],
    ),
    _clause(
        "acceptable_use", "Acceptable Use", "स्वीकार्य उपयोग",
        "The customer shall use {{service_name}} only for lawful business purposes, shall not interfere with the service or attempt unauthorized access, and is responsible for use by its authorized users.",
        "ग्राहक {{service_name}} का उपयोग केवल वैध व्यावसायिक उद्देश्यों के लिए करेगा, सेवा में बाधा नहीं डालेगा या अनधिकृत पहुँच का प्रयास नहीं करेगा, और अपने अधिकृत उपयोगकर्ताओं के उपयोग के लिए उत्तरदायी होगा।",
        contract_types=[ContractType.SAAS.value], variables=["service_name"],
    ),
    _clause(
        "acceptance", "Delivery and Acceptance", "डिलीवरी और स्वीकृति",
        "The target delivery date is {{delivery_date}}. The customer shall have {{acceptance_days}} days after delivery of a milestone to test it against the agreed specifications and identify material non-conformities. The developer shall use reasonable efforts to correct validated non-conformities.",
        "लक्षित डिलीवरी तिथि {{delivery_date}} है। ग्राहक को किसी माइलस्टोन की डिलीवरी के बाद सहमत विनिर्देशों के अनुसार परीक्षण करने और महत्वपूर्ण असंगतियों की पहचान करने के लिए {{acceptance_days}} दिन मिलेंगे। डेवलपर सत्यापित असंगतियों को ठीक करने के लिए उचित प्रयास करेगा।",
        contract_types=[ContractType.SOFTWARE_DEVELOPMENT.value], variables=["delivery_date", "acceptance_days"],
    ),
    _clause(
        "ip", "Intellectual Property", "बौद्धिक संपदा",
        "Each Party retains ownership of intellectual property owned or developed independently before this engagement. Subject to full payment, project-specific deliverables created specifically for {{party_a_name}} shall be assigned or licensed as stated in the commercial schedule, while reusable tools, know-how, libraries and pre-existing materials remain with their original owner unless expressly agreed otherwise.",
        "प्रत्येक पक्ष इस कार्य से पहले स्वतंत्र रूप से स्वामित्व या विकसित की गई बौद्धिक संपदा का स्वामित्व बनाए रखेगा। पूर्ण भुगतान के अधीन, {{party_a_name}} के लिए विशेष रूप से बनाए गए प्रोजेक्ट डिलिवरेबल्स को वाणिज्यिक अनुसूची के अनुसार हस्तांतरित या लाइसेंस किया जाएगा, जबकि पुन: उपयोग योग्य उपकरण, ज्ञान, लाइब्रेरी और पूर्व-मौजूदा सामग्री मूल स्वामी के पास रहेगी, जब तक कि स्पष्ट रूप से अन्यथा सहमति न हो।",
        contract_types=[ContractType.EMPLOYMENT.value, ContractType.CONSULTING.value, ContractType.FREELANCE.value, ContractType.SERVICES.value, ContractType.SAAS.value, ContractType.SOFTWARE_DEVELOPMENT.value],
    ),
    _clause(
        "data_protection", "Data Protection and Security", "डेटा संरक्षण और सुरक्षा",
        "Each Party shall handle personal data received under this Agreement only for agreed purposes, implement reasonable technical and organisational safeguards, restrict access to authorised persons, and comply with applicable data-protection obligations relevant to its role and processing activities.",
        "प्रत्येक पक्ष इस समझौते के अंतर्गत प्राप्त व्यक्तिगत डेटा को केवल सहमत उद्देश्यों के लिए संभालेगा, उचित तकनीकी और संगठनात्मक सुरक्षा उपाय लागू करेगा, पहुँच को अधिकृत व्यक्तियों तक सीमित रखेगा और अपनी भूमिका तथा प्रोसेसिंग गतिविधियों से संबंधित लागू डेटा-संरक्षण दायित्वों का पालन करेगा।",
        contract_types=[ContractType.EMPLOYMENT.value, ContractType.CONSULTING.value, ContractType.VENDOR.value, ContractType.SERVICES.value, ContractType.SAAS.value, ContractType.SOFTWARE_DEVELOPMENT.value],
    ),
    _clause(
        "non_solicit", "Non-Solicitation", "गैर-प्रलोभन",
        "During the engagement and for a reasonable period thereafter, neither Party shall knowingly solicit for employment personnel of the other Party who were materially involved in the engagement, except through general recruitment not targeted at such personnel. This clause shall apply only to the extent enforceable under applicable law.",
        "कार्यकाल के दौरान और उसके बाद उचित अवधि तक कोई भी पक्ष जानबूझकर दूसरे पक्ष के उन कर्मचारियों को रोजगार हेतु लक्षित रूप से आकर्षित नहीं करेगा जो इस कार्य में महत्वपूर्ण रूप से शामिल थे; सामान्य, गैर-लक्षित भर्ती पर यह प्रतिबंध लागू नहीं होगा। यह खंड केवल लागू कानून के तहत प्रवर्तनीय सीमा तक लागू होगा।",
        contract_types=[ContractType.EMPLOYMENT.value, ContractType.CONSULTING.value],
    ),
    _clause(
        "term_termination", "Term and Termination", "अवधि और समाप्ति",
        "This Agreement starts on {{effective_date}} and continues until completed or terminated. Either Party may terminate for material breach not cured within a reasonable cure period after written notice, and either Party may terminate without cause by giving {{notice_days}} days’ written notice unless the commercial schedule states otherwise.",
        "यह समझौता {{effective_date}} से प्रारंभ होगा और पूर्ण होने या समाप्त किए जाने तक जारी रहेगा। कोई भी पक्ष लिखित सूचना के बाद उचित सुधार अवधि में ठीक न किए गए महत्वपूर्ण उल्लंघन पर इसे समाप्त कर सकता है, तथा वाणिज्यिक अनुसूची में अन्यथा न होने पर कोई भी पक्ष {{notice_days}} दिन की लिखित सूचना देकर बिना कारण समाप्त कर सकता है।",
        variables=["effective_date", "notice_days"],
    ),
    _clause(
        "term_termination", "Term and Termination", "अवधि और समाप्ति",
        "This Agreement starts on {{effective_date}}. {{party_a_name}} may terminate without cause on {{notice_days}} days’ written notice. {{party_b_name}} may terminate without cause on 30 days’ written notice. Either Party may terminate for a material uncured breach. Accrued payment and confidentiality obligations survive termination.",
        "यह समझौता {{effective_date}} से प्रारंभ होगा। {{party_a_name}} {{notice_days}} दिन की लिखित सूचना देकर बिना कारण समाप्त कर सकता/सकती है। {{party_b_name}} 30 दिन की लिखित सूचना देकर बिना कारण समाप्त कर सकता/सकती है। कोई भी पक्ष महत्वपूर्ण और असुधारित उल्लंघन पर समाप्त कर सकता है। अर्जित भुगतान और गोपनीयता दायित्व समाप्ति के बाद भी प्रभावी रहेंगे।",
        variant="pro_party_a", variables=["effective_date", "notice_days"],
    ),
    _clause(
        "term_termination", "Term and Termination", "अवधि और समाप्ति",
        "This Agreement starts on {{effective_date}}. {{party_b_name}} may terminate without cause on {{notice_days}} days’ written notice. {{party_a_name}} may terminate without cause on 30 days’ written notice. Either Party may terminate for a material uncured breach. Accrued payment and confidentiality obligations survive termination.",
        "यह समझौता {{effective_date}} से प्रारंभ होगा। {{party_b_name}} {{notice_days}} दिन की लिखित सूचना देकर बिना कारण समाप्त कर सकता/सकती है। {{party_a_name}} 30 दिन की लिखित सूचना देकर बिना कारण समाप्त कर सकता/सकती है। कोई भी पक्ष महत्वपूर्ण और असुधारित उल्लंघन पर समाप्त कर सकता है। अर्जित भुगतान और गोपनीयता दायित्व समाप्ति के बाद भी प्रभावी रहेंगे।",
        variant="pro_party_b", variables=["effective_date", "notice_days"],
    ),
    _clause(
        "warranty", "Representations and Warranty", "प्रतिनिधित्व और वारंटी",
        "Each Party represents that it has authority to enter into this Agreement. The service provider shall perform the services with reasonable skill and care. Any specific warranty period agreed by the Parties is {{warranty_days}} days where that field is applicable.",
        "प्रत्येक पक्ष यह घोषित करता है कि उसे यह समझौता करने का अधिकार है। सेवा प्रदाता सेवाएँ उचित कौशल और सावधानी के साथ प्रदान करेगा। जहाँ लागू हो, पक्षों द्वारा सहमत विशिष्ट वारंटी अवधि {{warranty_days}} दिन है।",
        contract_types=[ContractType.CONSULTING.value, ContractType.FREELANCE.value, ContractType.VENDOR.value, ContractType.SERVICES.value, ContractType.SAAS.value, ContractType.SOFTWARE_DEVELOPMENT.value], variables=["warranty_days"],
    ),
    _clause(
        "liability", "Limitation of Liability", "दायित्व की सीमा",
        "Subject to liabilities that cannot lawfully be limited, each Party’s aggregate contractual liability arising from this Agreement shall not exceed the fees paid or payable under this Agreement during the preceding twelve months. Neither Party shall be liable for indirect or consequential loss except where expressly agreed.",
        "उन दायित्वों के अधीन जिन्हें विधिसम्मत रूप से सीमित नहीं किया जा सकता, इस समझौते से उत्पन्न प्रत्येक पक्ष का कुल संविदात्मक दायित्व पिछले बारह महीनों में इस समझौते के अंतर्गत भुगतान किए गए या देय शुल्क से अधिक नहीं होगा। स्पष्ट सहमति के अतिरिक्त कोई पक्ष अप्रत्यक्ष या परिणामी हानि के लिए उत्तरदायी नहीं होगा।",
        contract_types=list(PAID_TYPES),
    ),
    _clause(
        "liability", "Limitation of Liability", "दायित्व की सीमा",
        "Subject to liabilities that cannot lawfully be limited, {{party_a_name}}’s aggregate contractual liability shall not exceed the fees paid in the preceding six months, while {{party_b_name}}’s aggregate liability shall not exceed the fees paid or payable in the preceding twelve months. Indirect and consequential loss is excluded to the extent permitted by law.",
        "उन दायित्वों के अधीन जिन्हें विधिसम्मत रूप से सीमित नहीं किया जा सकता, {{party_a_name}} का कुल संविदात्मक दायित्व पिछले छह महीनों में भुगतान किए गए शुल्क से अधिक नहीं होगा, जबकि {{party_b_name}} का कुल दायित्व पिछले बारह महीनों में भुगतान किए गए या देय शुल्क से अधिक नहीं होगा। कानून द्वारा अनुमत सीमा तक अप्रत्यक्ष और परिणामी हानि को बाहर रखा जाता है।",
        variant="pro_party_a", contract_types=list(PAID_TYPES),
    ),
    _clause(
        "liability", "Limitation of Liability", "दायित्व की सीमा",
        "Subject to liabilities that cannot lawfully be limited, {{party_b_name}}’s aggregate contractual liability shall not exceed the fees paid in the preceding six months, while {{party_a_name}}’s aggregate liability shall not exceed the fees paid or payable in the preceding twelve months. Indirect and consequential loss is excluded to the extent permitted by law.",
        "उन दायित्वों के अधीन जिन्हें विधिसम्मत रूप से सीमित नहीं किया जा सकता, {{party_b_name}} का कुल संविदात्मक दायित्व पिछले छह महीनों में भुगतान किए गए शुल्क से अधिक नहीं होगा, जबकि {{party_a_name}} का कुल दायित्व पिछले बारह महीनों में भुगतान किए गए या देय शुल्क से अधिक नहीं होगा। कानून द्वारा अनुमत सीमा तक अप्रत्यक्ष और परिणामी हानि को बाहर रखा जाता है।",
        variant="pro_party_b", contract_types=list(PAID_TYPES),
    ),
    _clause(
        "indemnity", "Indemnity", "क्षतिपूर्ति",
        "Each Party shall indemnify the other against direct third-party claims to the extent caused by its material breach, wilful misconduct, or infringement arising from materials supplied by that Party, subject to prompt notice, reasonable control of defence and cooperation.",
        "प्रत्येक पक्ष दूसरे पक्ष को उन प्रत्यक्ष तृतीय-पक्ष दावों से क्षतिपूर्ति देगा जो उसके महत्वपूर्ण उल्लंघन, जानबूझकर कदाचार या उस पक्ष द्वारा प्रदान की गई सामग्री से उत्पन्न उल्लंघन के कारण हों, बशर्ते शीघ्र सूचना, बचाव पर उचित नियंत्रण और सहयोग प्रदान किया जाए।",
        contract_types=[ContractType.CONSULTING.value, ContractType.FREELANCE.value, ContractType.VENDOR.value, ContractType.SERVICES.value, ContractType.SAAS.value, ContractType.SOFTWARE_DEVELOPMENT.value],
    ),
    _clause(
        "indemnity", "Indemnity", "क्षतिपूर्ति",
        "{{party_b_name}} shall indemnify {{party_a_name}} against direct third-party claims arising from {{party_b_name}}’s material breach, wilful misconduct or infringement by deliverables supplied by {{party_b_name}}. Any indemnity by {{party_a_name}} is limited to third-party claims caused by materials expressly supplied by {{party_a_name}}.",
        "{{party_b_name}}, {{party_a_name}} को {{party_b_name}} के महत्वपूर्ण उल्लंघन, जानबूझकर कदाचार या {{party_b_name}} द्वारा दिए गए डिलिवरेबल्स से उत्पन्न उल्लंघन संबंधी प्रत्यक्ष तृतीय-पक्ष दावों से क्षतिपूर्ति देगा। {{party_a_name}} की कोई भी क्षतिपूर्ति केवल {{party_a_name}} द्वारा स्पष्ट रूप से प्रदान की गई सामग्री से उत्पन्न तृतीय-पक्ष दावों तक सीमित होगी।",
        variant="pro_party_a", contract_types=[ContractType.CONSULTING.value, ContractType.FREELANCE.value, ContractType.VENDOR.value, ContractType.SERVICES.value, ContractType.SAAS.value, ContractType.SOFTWARE_DEVELOPMENT.value],
    ),
    _clause(
        "indemnity", "Indemnity", "क्षतिपूर्ति",
        "{{party_a_name}} shall indemnify {{party_b_name}} against direct third-party claims arising from {{party_a_name}}’s material breach, wilful misconduct or infringement by materials supplied by {{party_a_name}}. Any indemnity by {{party_b_name}} is limited to third-party claims caused by materials expressly supplied by {{party_b_name}}.",
        "{{party_a_name}}, {{party_b_name}} को {{party_a_name}} के महत्वपूर्ण उल्लंघन, जानबूझकर कदाचार या {{party_a_name}} द्वारा दी गई सामग्री से उत्पन्न उल्लंघन संबंधी प्रत्यक्ष तृतीय-पक्ष दावों से क्षतिपूर्ति देगा। {{party_b_name}} की कोई भी क्षतिपूर्ति केवल {{party_b_name}} द्वारा स्पष्ट रूप से प्रदान की गई सामग्री से उत्पन्न तृतीय-पक्ष दावों तक सीमित होगी।",
        variant="pro_party_b", contract_types=[ContractType.CONSULTING.value, ContractType.FREELANCE.value, ContractType.VENDOR.value, ContractType.SERVICES.value, ContractType.SAAS.value, ContractType.SOFTWARE_DEVELOPMENT.value],
    ),
    _clause(
        "remedies", "Remedies", "उपचार",
        "The Parties acknowledge that unauthorised disclosure may cause harm that is difficult to quantify. A Party may seek appropriate interim or equitable relief in addition to other remedies available under applicable law, subject to the competent forum’s discretion.",
        "पक्ष स्वीकार करते हैं कि अनधिकृत प्रकटीकरण से ऐसी हानि हो सकती है जिसका परिमाण निर्धारित करना कठिन हो। सक्षम मंच के विवेक के अधीन, कोई पक्ष लागू कानून के तहत उपलब्ध अन्य उपचारों के अतिरिक्त उपयुक्त अंतरिम या न्यायसंगत राहत मांग सकता है।",
        contract_types=[ContractType.NDA.value],
    ),
    _clause(
        "governing_law", "Governing Law", "लागू कानून",
        "This Agreement shall be governed by the laws applicable in India. Subject to the dispute-resolution clause, courts at {{arbitration_city}} in {{governing_state}} shall have jurisdiction to the extent agreed and legally permissible.",
        "यह समझौता भारत में लागू कानूनों द्वारा शासित होगा। विवाद-समाधान खंड के अधीन, {{governing_state}} के {{arbitration_city}} स्थित न्यायालयों को सहमत और विधिसम्मत सीमा तक क्षेत्राधिकार होगा।",
        variables=["arbitration_city", "governing_state"],
    ),
    _clause(
        "dispute_resolution", "Dispute Resolution", "विवाद समाधान",
        "The Parties shall first attempt good-faith resolution. Where arbitration is selected, unresolved disputes shall be referred to arbitration at {{arbitration_city}} under a mutually agreed procedure consistent with applicable law. If courts are selected, disputes shall be submitted to the agreed competent courts.",
        "पक्ष पहले सद्भावपूर्वक समाधान का प्रयास करेंगे। जहाँ मध्यस्थता चुनी गई है, वहाँ अनसुलझे विवादों को {{arbitration_city}} में लागू कानून के अनुरूप पारस्परिक रूप से सहमत प्रक्रिया के तहत मध्यस्थता के लिए भेजा जाएगा। यदि न्यायालय चुने गए हैं, तो विवाद सहमत सक्षम न्यायालयों में प्रस्तुत किए जाएंगे।",
        variables=["dispute_mode", "arbitration_city"],
    ),
    _clause(
        "notices", "Notices", "सूचनाएँ",
        "Formal notices under this Agreement shall be in writing and delivered to the addresses or designated electronic contacts notified by the Parties. A Party shall promptly notify changes to its notice details.",
        "इस समझौते के अंतर्गत औपचारिक सूचनाएँ लिखित रूप में होंगी और पक्षों द्वारा सूचित पतों या निर्दिष्ट इलेक्ट्रॉनिक संपर्कों पर भेजी जाएंगी। कोई पक्ष अपनी सूचना संबंधी जानकारी में बदलाव की शीघ्र सूचना देगा।",
    ),
    _clause(
        "force_majeure", "Force Majeure", "अप्रत्याशित / नियंत्रण से बाहर घटनाएँ",
        "A Party is not liable for delay caused by events beyond its reasonable control if it promptly notifies the other Party and uses reasonable efforts to mitigate the impact. Payment obligations already due are not excused solely by this clause.",
        "यदि देरी किसी पक्ष के उचित नियंत्रण से बाहर की घटना के कारण हो और वह दूसरे पक्ष को शीघ्र सूचना दे तथा प्रभाव कम करने के उचित प्रयास करे, तो वह उस देरी के लिए उत्तरदायी नहीं होगा। पहले से देय भुगतान दायित्व केवल इस खंड के कारण समाप्त नहीं होंगे।",
        contract_types=[t for t in ALL_TYPES if t != ContractType.NDA.value],
    ),
    _clause(
        "assignment", "Assignment", "हस्तांतरण",
        "Neither Party may assign this Agreement without the other Party’s prior written consent, except to an affiliate or as part of a bona fide merger, reorganisation or transfer of substantially all relevant business assets, subject to the assignee assuming the obligations of this Agreement.",
        "कोई भी पक्ष दूसरे पक्ष की पूर्व लिखित सहमति के बिना इस समझौते का हस्तांतरण नहीं करेगा, सिवाय किसी संबद्ध इकाई को या वास्तविक विलय, पुनर्गठन अथवा संबंधित व्यवसायिक संपत्तियों के लगभग पूर्ण हस्तांतरण के हिस्से के रूप में, बशर्ते हस्तांतरण प्राप्तकर्ता इस समझौते के दायित्व स्वीकार करे।",
        contract_types=[ContractType.CONSULTING.value, ContractType.FREELANCE.value, ContractType.VENDOR.value, ContractType.SERVICES.value, ContractType.SAAS.value, ContractType.SOFTWARE_DEVELOPMENT.value],
    ),
    _clause(
        "entire_agreement", "Entire Agreement and Amendments", "पूर्ण समझौता और संशोधन",
        "This Agreement and its schedules constitute the entire agreement on their subject matter and supersede prior discussions on that subject. Amendments must be recorded in writing and agreed by authorised representatives of both Parties. If any provision is unenforceable, the remaining provisions continue to the extent permitted by law.",
        "यह समझौता और इसकी अनुसूचियाँ अपने विषय पर पक्षों के बीच पूर्ण समझौता हैं और उस विषय पर पूर्व चर्चाओं का स्थान लेते हैं। संशोधन लिखित रूप में दर्ज होंगे और दोनों पक्षों के अधिकृत प्रतिनिधियों द्वारा सहमत किए जाएंगे। यदि कोई प्रावधान अप्रवर्तनीय हो, तो शेष प्रावधान कानून द्वारा अनुमत सीमा तक प्रभावी रहेंगे।",
    ),
]


def get_contract_catalog() -> list[dict[str, Any]]:
    return [
        {"contract_type": key, **{k: v for k, v in value.items() if k != "questions" and k != "clauses"}}
        for key, value in CONTRACT_DEFINITIONS.items()
    ]


def get_contract_definition(contract_type: str) -> dict[str, Any]:
    return CONTRACT_DEFINITIONS[contract_type]
