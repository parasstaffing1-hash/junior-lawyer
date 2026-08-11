BUILTIN_PACKS = {
    "india_litigation_case_management": {
        "name_en": "India Litigation Case Management",
        "name_hi": "भारत वाद प्रबंधन",
        "jurisdiction": "India",
        "proceeding_type": "general_litigation",
        "court_level": None,
        "description": "A non-substantive workflow pack for matter operations. It intentionally contains no statutory limitation period.",
        "verified": False,
        "source_name": "Internal workflow template",
        "source_citation": "Not a statement of law",
        "steps": [
            {"code": "matter_opening", "sequence": 10, "name_en": "Matter opening", "name_hi": "मामला प्रारंभ", "required": True, "checklist": ["Conflict check", "Client/matter identifiers", "Authority to act"]},
            {"code": "source_documents", "sequence": 20, "name_en": "Source documents", "name_hi": "स्रोत दस्तावेज़", "required": True, "checklist": ["Collect pleadings/orders", "OCR/index", "Verify dates and parties"]},
            {"code": "issues_and_evidence", "sequence": 30, "name_en": "Issues and evidence", "name_hi": "मुद्दे और साक्ष्य", "required": True, "checklist": ["Review facts", "Resolve contradictions", "Build evidence matrix"]},
            {"code": "research_and_drafting", "sequence": 40, "name_en": "Research and drafting", "name_hi": "शोध और मसौदा", "required": True, "checklist": ["Verify authorities", "Prepare draft", "Lawyer review"]},
            {"code": "hearing_preparation", "sequence": 50, "name_en": "Hearing preparation", "name_hi": "सुनवाई तैयारी", "required": True, "checklist": ["Read last order", "Check directions", "Prepare hearing note"]},
            {"code": "post_hearing_compliance", "sequence": 60, "name_en": "Post-hearing compliance", "name_hi": "सुनवाई पश्चात अनुपालन", "required": True, "checklist": ["Record directions", "Create reviewed deadlines", "Assign compliance"]},
        ],
        "deadline_rules": [],
    }
}


def get_catalog() -> list[dict]:
    return [{"code": code, **{k: v for k, v in data.items() if k not in {"steps", "deadline_rules"}}, "step_count": len(data["steps"]), "deadline_rule_count": len(data["deadline_rules"])} for code, data in BUILTIN_PACKS.items()]
