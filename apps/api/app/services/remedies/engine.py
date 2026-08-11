from __future__ import annotations

from datetime import date
from typing import Any

from app.models.procedure import DayBasis, DeadlineAdjustment
from app.services.procedure.calculator import calculate_deadline


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(f"{key} {_text(item)}" for key, item in value.items())
    return str(value)


def _matches(patterns: list[str], text: str) -> bool:
    if not patterns:
        return True
    haystack = text.casefold()
    return any(pattern.casefold() in haystack for pattern in patterns if pattern.strip())



_MATCH_LABEL_HI = {
    "case stage": "मामले का चरण",
    "case status": "मामले की स्थिति",
    "court level": "न्यायालय स्तर",
    "latest/order type": "आदेश का प्रकार",
    "applicable Act": "लागू अधिनियम",
    "applicable section": "लागू धारा",
}

def _localized(english: str, hindi: str, language: str) -> str:
    if language == "hi":
        return hindi
    if language == "bilingual":
        return f"{english} / {hindi}"
    return english

def _match_reason(label: str, value: str, language: str) -> str:
    english = f"Matched {label}: {value or 'available record'}"
    hindi_label = _MATCH_LABEL_HI.get(label, label)
    hindi = f"{hindi_label} मेल खाता है: {value or 'उपलब्ध रिकॉर्ड'}"
    return _localized(english, hindi, language)

def latest_order_date(context: dict) -> date | None:
    values: list[date] = []
    for item in context.get("orders", []):
        raw = item.get("order_date")
        if isinstance(raw, date):
            values.append(raw)
        elif raw:
            try:
                values.append(date.fromisoformat(str(raw)[:10]))
            except ValueError:
                pass
    for item in context.get("judgments", []):
        raw = item.get("decision_date")
        if isinstance(raw, date):
            values.append(raw)
        elif raw:
            try:
                values.append(date.fromisoformat(str(raw)[:10]))
            except ValueError:
                pass
    return max(values) if values else None


def is_final_order_context(context: dict) -> bool:
    status = _text(context.get("status")).casefold()
    stage = _text(context.get("case_stage")).casefold()
    if context.get("judgments"):
        return True
    return any(token in f"{status} {stage}" for token in ("disposed", "decided", "final", "judgment", "decree", "convicted", "acquitted"))


def evaluate_rule(rule, context: dict, *, as_of_date: date | None = None, language: str = "en") -> dict | None:
    stages = _text(context.get("case_stage"))
    status = _text(context.get("status"))
    court_level = _text(context.get("court_level"))
    order_types = " ".join(_text(item.get("order_type")) for item in context.get("orders", []))
    acts = " ".join(_text(item.get("act_name")) for item in context.get("acts", []))
    sections = " ".join(_text(item.get("sections")) for item in context.get("acts", []))

    required_checks = [
        (rule.case_stage_patterns_json, stages, "case stage"),
        (rule.status_patterns_json, status, "case status"),
        (rule.court_level_patterns_json, court_level, "court level"),
        (rule.order_type_patterns_json, order_types, "latest/order type"),
        (rule.act_patterns_json, acts, "applicable Act"),
        (rule.section_patterns_json, sections, "applicable section"),
    ]
    reasons: list[str] = []
    score = 40
    for patterns, value, label in required_checks:
        if patterns and not _matches(patterns, value):
            return None
        if patterns:
            reasons.append(_match_reason(label, value, language))
            score += 8

    if rule.requires_final_order:
        if not is_final_order_context(context):
            return None
        reasons.append(_localized("A final/dispositive order or judgment is present in the case record.", "मामले के रिकॉर्ड में अंतिम/निर्णायक आदेश या निर्णय उपलब्ध है।", language))
        score += 10
    if rule.requires_latest_order:
        if not (context.get("orders") or context.get("judgments")):
            return None
        reasons.append(_localized("The case record contains an order/judgment relevant to the remedy trigger.", "मामले के रिकॉर्ड में उपचार के ट्रिगर से संबंधित आदेश/निर्णय उपलब्ध है।", language))
        score += 8

    maintainability = evaluate_maintainability(rule.maintainability_json, context)
    if maintainability["failed"]:
        candidate_status = "not_maintainable"
    elif maintainability["unknown"]:
        candidate_status = "conditional"
    else:
        candidate_status = "possible"
        score += 6

    deadline = evaluate_limitation(rule.limitation_json, context, as_of_date=as_of_date)
    if deadline.get("status") == "expired_or_due":
        candidate_status = "conditional"
    if deadline.get("calculated"):
        score += 5

    return {
        "status": candidate_status,
        "score": min(score + int(rule.priority / 10), 100),
        "reasons": reasons,
        "maintainability": maintainability,
        "deadline": deadline,
    }


def evaluate_maintainability(spec: dict, context: dict) -> dict:
    requirements = list(spec.get("requirements") or [])
    checks: list[dict] = []
    failed = False
    unknown = False
    for requirement in requirements:
        if isinstance(requirement, str):
            requirement = {"field": requirement, "operator": "exists", "label": requirement.replace("_", " ").title()}
        field = str(requirement.get("field") or "")
        operator = str(requirement.get("operator") or "exists")
        expected = requirement.get("value")
        label = requirement.get("label") or field.replace("_", " ").title()
        if field == "latest_order":
            actual = bool(context.get("orders") or context.get("judgments"))
        elif field == "final_order":
            actual = is_final_order_context(context)
        else:
            actual = context.get(field)
        if operator == "exists":
            passed = actual not in (None, "", [], {})
        elif operator == "equals":
            passed = _text(actual).casefold() == _text(expected).casefold()
        elif operator == "contains":
            passed = _text(expected).casefold() in _text(actual).casefold()
        elif operator == "in":
            expected_values = expected if isinstance(expected, list) else [expected]
            passed = any(_text(value).casefold() == _text(actual).casefold() for value in expected_values)
        else:
            passed = None
        if passed is False:
            failed = True
        if passed is None:
            unknown = True
        checks.append({"field": field, "label": label, "operator": operator, "expected": expected, "actual": actual, "passed": passed})
    return {
        "checks": checks,
        "failed": failed,
        "unknown": unknown,
        "note": spec.get("note"),
        "requires_lawyer_review": bool(spec.get("requires_lawyer_review", True)),
    }


def _trigger_date(trigger: str, context: dict) -> date | None:
    if trigger in {"latest_order", "latest_order_date"}:
        return latest_order_date(context)
    if trigger == "registration_date":
        raw = context.get("registration_date")
    elif trigger == "filing_date":
        raw = context.get("filing_date")
    elif trigger == "previous_hearing_date":
        raw = context.get("previous_hearing_date")
    else:
        raw = context.get(trigger)
    if isinstance(raw, date):
        return raw
    if raw:
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            return None
    return None


def evaluate_limitation(spec: dict, context: dict, *, as_of_date: date | None = None) -> dict:
    if not spec:
        return {"calculated": False, "status": "not_configured", "requires_lawyer_review": True}
    days = spec.get("days")
    trigger_name = str(spec.get("trigger") or "latest_order_date")
    trigger = _trigger_date(trigger_name, context)
    output = {
        "calculated": False,
        "trigger": trigger_name,
        "trigger_date": trigger.isoformat() if trigger else None,
        "days": days,
        "source_citation": spec.get("source_citation"),
        "source_url": spec.get("source_url"),
        "exceptions": spec.get("exceptions", []),
        "requires_lawyer_review": bool(spec.get("requires_lawyer_review", True)),
    }
    if not isinstance(days, int) or days < 0 or trigger is None:
        output["status"] = "needs_review"
        return output
    try:
        day_basis = DayBasis(str(spec.get("day_basis") or "calendar"))
    except ValueError:
        day_basis = DayBasis.CALENDAR
    try:
        adjustment = DeadlineAdjustment(str(spec.get("adjustment") or "none"))
    except ValueError:
        adjustment = DeadlineAdjustment.NONE
    result = calculate_deadline(
        trigger,
        offset_days=days,
        day_basis=day_basis,
        count_from_next_day=bool(spec.get("count_from_next_day", True)),
        adjustment=adjustment,
        holidays=set(),
    )
    output.update(result.as_dict())
    output["calculated"] = True
    today = as_of_date or date.today()
    output["status"] = "expired_or_due" if result.due_date <= today else "upcoming"
    return output


RESEARCH_HINTS = [
    {
        "code": "appeal_review_revision",
        "name_en": "Appeal / review / revision route",
        "name_hi": "अपील / पुनर्विचार / पुनरीक्षण मार्ग",
        "when": lambda c: bool(c.get("orders") or c.get("judgments")),
        "reason": "An order or judgment is present, but no verified remedy rule currently establishes which supervisory/appellate route is maintainable.",
    },
    {
        "code": "restoration_recall",
        "name_en": "Restoration / recall route",
        "name_hi": "बहाली / आदेश वापस लेने का मार्ग",
        "when": lambda c: any(token in _text(c.get("status") or c.get("case_stage")).casefold() for token in ("dismiss", "default", "ex parte", "non prosecution", "non-prosecution")),
        "reason": "The recorded posture suggests dismissal/default/ex-parte circumstances; the enabling provision and forum must be verified.",
    },
    {
        "code": "execution_enforcement",
        "name_en": "Execution / enforcement route",
        "name_hi": "निष्पादन / प्रवर्तन मार्ग",
        "when": is_final_order_context,
        "reason": "A final/dispositive outcome may create an enforcement question; verify whether an executable decree/order/award exists.",
    },
]


def research_hints(context: dict) -> list[dict]:
    return [
        {"code": item["code"], "name_en": item["name_en"], "name_hi": item["name_hi"], "reason": item["reason"]}
        for item in RESEARCH_HINTS
        if item["when"](context)
    ]
