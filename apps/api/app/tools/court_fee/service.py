import json
import os
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path

from app.tools.court_fee.models import (
    CourtFeeCalculationRequest,
    CourtFeeCalculationResponse,
    CourtFeeRulePack,
    CourtFeeRulePackSummary,
    FeeBreakdownLine,
    FeeMethod,
    RoundingMethod,
)

RULES_DIR = Path(__file__).with_name("rules")
DISCLAIMER = (
    "This calculator performs deterministic arithmetic using the selected rule pack. "
    "It does not determine whether a filing, valuation, exemption, surcharge, or legal "
    "provision applies. Verify the applicable court-fee law and current official schedule."
)


class CourtFeeRulePackNotFoundError(ValueError):
    pass


class CourtFeeRulePackDateError(ValueError):
    pass


class CourtFeeInputError(ValueError):
    pass


def _production_rule_pack_allowed(rule_pack_id: str) -> bool:
    if not rule_pack_id.lower().startswith("demo-"):
        return True
    return os.getenv("LAWYER_TOOLS_ENV", "development").strip().lower() != "production" and os.getenv("LAWYER_TOOLS_ALLOW_DEMO_RULES", "true").lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def load_rule_packs() -> dict[str, CourtFeeRulePack]:
    packs: dict[str, CourtFeeRulePack] = {}
    for path in sorted(RULES_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not _production_rule_pack_allowed(str(payload.get("id", ""))):
            continue
        pack = CourtFeeRulePack.model_validate(payload)
        if pack.id in packs:
            raise ValueError(f"duplicate court-fee rule pack id: {pack.id}")
        packs[pack.id] = pack
    return packs


def list_rule_packs() -> list[CourtFeeRulePackSummary]:
    return [
        CourtFeeRulePackSummary(
            id=pack.id,
            version=pack.version,
            jurisdiction=pack.jurisdiction,
            court=pack.court,
            case_type=pack.case_type,
            currency=pack.currency,
            effective_from=pack.effective_from,
            effective_to=pack.effective_to,
            method=pack.method,
            source_note=pack.source_note,
        )
        for pack in load_rule_packs().values()
    ]


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_to_unit(value: Decimal, unit: Decimal, method: RoundingMethod) -> Decimal:
    if method == RoundingMethod.NONE:
        return value

    quotient = value / unit
    if method == RoundingMethod.UP:
        rounded = quotient.quantize(Decimal("1"), rounding=ROUND_CEILING)
    elif method == RoundingMethod.DOWN:
        rounded = quotient.quantize(Decimal("1"), rounding=ROUND_FLOOR)
    else:
        rounded = quotient.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return rounded * unit


def _calculate_progressive_fee(
    claim_value: Decimal,
    pack: CourtFeeRulePack,
) -> tuple[Decimal, list[FeeBreakdownLine]]:
    remaining = claim_value
    previous_limit = Decimal("0")
    total = Decimal("0")
    breakdown: list[FeeBreakdownLine] = []

    for index, slab in enumerate(pack.slabs, start=1):
        if remaining <= 0:
            break

        if slab.up_to is None:
            taxable = remaining
            upper_label = "above"
        else:
            slab_width = slab.up_to - previous_limit
            taxable = min(remaining, slab_width)
            upper_label = f"up to {slab.up_to}"

        amount = taxable * slab.rate_percent / Decimal("100")
        total += amount
        breakdown.append(
            FeeBreakdownLine(
                label=f"Progressive slab {index}",
                basis=f"{taxable} at {slab.rate_percent}% ({upper_label})",
                amount=_money(amount),
            )
        )
        remaining -= taxable

        if slab.up_to is not None:
            previous_limit = slab.up_to

    return total, breakdown


def calculate_court_fee(request: CourtFeeCalculationRequest) -> CourtFeeCalculationResponse:
    packs = load_rule_packs()
    pack = packs.get(request.rule_pack_id)
    if pack is None:
        raise CourtFeeRulePackNotFoundError(
            f"unknown court-fee rule pack: {request.rule_pack_id}"
        )

    if request.filing_date < pack.effective_from or (
        pack.effective_to is not None and request.filing_date > pack.effective_to
    ):
        raise CourtFeeRulePackDateError(
            "selected rule pack is not effective on the requested filing_date"
        )

    breakdown: list[FeeBreakdownLine] = []
    adjustments: list[str] = []

    if pack.method == FeeMethod.FIXED:
        assert pack.fixed_fee is not None
        base_fee = pack.fixed_fee
        breakdown.append(
            FeeBreakdownLine(
                label="Fixed filing fee",
                basis="Fixed amount from rule pack",
                amount=_money(base_fee),
            )
        )
    else:
        if request.claim_value is None:
            raise CourtFeeInputError("claim_value is required for progressive rule packs")
        base_fee, progressive_breakdown = _calculate_progressive_fee(
            request.claim_value,
            pack,
        )
        breakdown.extend(progressive_breakdown)

    additional_by_code = {item.code: item for item in pack.additional_fees}
    unknown_codes = sorted(
        set(request.include_additional_fee_codes) - set(additional_by_code)
    )
    if unknown_codes:
        raise CourtFeeInputError(
            "unknown additional fee code(s): " + ", ".join(unknown_codes)
        )

    additional_total = Decimal("0")
    for code in dict.fromkeys(request.include_additional_fee_codes):
        item = additional_by_code[code]
        additional_total += item.amount
        breakdown.append(
            FeeBreakdownLine(
                label=item.label,
                basis=f"Optional additional fee: {item.code}",
                amount=_money(item.amount),
            )
        )

    subtotal_before_limits = base_fee + additional_total
    subtotal_after_limits = subtotal_before_limits

    if pack.minimum_fee is not None and subtotal_after_limits < pack.minimum_fee:
        adjustments.append(
            f"Minimum fee applied: {subtotal_after_limits} -> {pack.minimum_fee}"
        )
        subtotal_after_limits = pack.minimum_fee

    if pack.maximum_fee is not None and subtotal_after_limits > pack.maximum_fee:
        adjustments.append(
            f"Maximum fee applied: {subtotal_after_limits} -> {pack.maximum_fee}"
        )
        subtotal_after_limits = pack.maximum_fee

    final_fee = _round_to_unit(
        subtotal_after_limits,
        pack.rounding_unit,
        pack.rounding_method,
    )
    if final_fee != subtotal_after_limits:
        adjustments.append(
            f"Rounding applied ({pack.rounding_method.value} to {pack.rounding_unit}): "
            f"{subtotal_after_limits} -> {final_fee}"
        )

    return CourtFeeCalculationResponse(
        rule_pack_id=pack.id,
        rule_pack_version=pack.version,
        jurisdiction=pack.jurisdiction,
        court=pack.court,
        case_type=pack.case_type,
        currency=pack.currency,
        filing_date=request.filing_date,
        claim_value=request.claim_value,
        base_fee=_money(base_fee),
        additional_fee_total=_money(additional_total),
        subtotal_before_limits=_money(subtotal_before_limits),
        subtotal_after_limits=_money(subtotal_after_limits),
        final_fee=_money(final_fee),
        breakdown=breakdown,
        adjustments=adjustments,
        source_note=pack.source_note,
        disclaimer=DISCLAIMER,
    )
