import json
import os
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path

from app.tools.stamp_duty.models import (
    DutyBreakdownLine,
    DutyCharge,
    DutyMethod,
    RoundingMethod,
    StampDutyCalculationRequest,
    StampDutyCalculationResponse,
    StampDutyRulePack,
    StampDutyRulePackSummary,
    ValuationBasis,
)

RULES_DIR = Path(__file__).with_name("rules")
DISCLAIMER = (
    "This calculator performs deterministic arithmetic using the selected stamp-duty "
    "rule pack. It does not determine legal classification, exemptions, concessions, "
    "market valuation, registration fees, penalties, or whether a particular law applies. "
    "Verify the current official stamp law/schedule and instrument facts before relying on it."
)


class StampDutyRulePackNotFoundError(ValueError):
    pass


class StampDutyRulePackDateError(ValueError):
    pass


class StampDutyInputError(ValueError):
    pass


def _production_rule_pack_allowed(rule_pack_id: str) -> bool:
    if not rule_pack_id.lower().startswith("demo-"):
        return True
    return os.getenv("LAWYER_TOOLS_ENV", "development").strip().lower() != "production" and os.getenv("LAWYER_TOOLS_ALLOW_DEMO_RULES", "true").lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def load_rule_packs() -> dict[str, StampDutyRulePack]:
    packs: dict[str, StampDutyRulePack] = {}
    for path in sorted(RULES_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not _production_rule_pack_allowed(str(payload.get("id", ""))):
            continue
        pack = StampDutyRulePack.model_validate(payload)
        if pack.id in packs:
            raise ValueError(f"duplicate stamp-duty rule pack id: {pack.id}")
        packs[pack.id] = pack
    return packs


def list_rule_packs() -> list[StampDutyRulePackSummary]:
    return [
        StampDutyRulePackSummary(
            id=pack.id,
            version=pack.version,
            jurisdiction=pack.jurisdiction,
            instrument_type=pack.instrument_type,
            currency=pack.currency,
            effective_from=pack.effective_from,
            effective_to=pack.effective_to,
            valuation_basis=pack.valuation_basis,
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


def _resolve_duty_base(
    request: StampDutyCalculationRequest,
    basis: ValuationBasis,
) -> Decimal | None:
    if basis == ValuationBasis.CONSIDERATION:
        if request.consideration_value is None:
            raise StampDutyInputError("consideration_value is required by this rule pack")
        return request.consideration_value

    if basis == ValuationBasis.MARKET_VALUE:
        if request.market_value is None:
            raise StampDutyInputError("market_value is required by this rule pack")
        return request.market_value

    if basis == ValuationBasis.ASSESSABLE_VALUE:
        if request.assessable_value is None:
            raise StampDutyInputError("assessable_value is required by this rule pack")
        return request.assessable_value

    if request.consideration_value is None or request.market_value is None:
        raise StampDutyInputError(
            "consideration_value and market_value are required by this rule pack"
        )
    return max(request.consideration_value, request.market_value)


def _calculate_progressive_duty(
    base_value: Decimal,
    pack: StampDutyRulePack,
) -> tuple[Decimal, list[DutyBreakdownLine]]:
    remaining = base_value
    previous_limit = Decimal("0")
    total = Decimal("0")
    breakdown: list[DutyBreakdownLine] = []

    for index, slab in enumerate(pack.slabs, start=1):
        if remaining <= 0:
            break

        if slab.up_to is None:
            taxable = remaining
            range_label = f"above {previous_limit}"
        else:
            slab_width = slab.up_to - previous_limit
            taxable = min(remaining, slab_width)
            range_label = f"{previous_limit} to {slab.up_to}"

        amount = taxable * slab.rate_percent / Decimal("100")
        total += amount
        breakdown.append(
            DutyBreakdownLine(
                label=f"Duty slab {index}",
                basis=f"{taxable} at {slab.rate_percent}% ({range_label})",
                amount=_money(amount),
            )
        )
        remaining -= taxable
        if slab.up_to is not None:
            previous_limit = slab.up_to

    return total, breakdown


def _calculate_charge(
    charge: DutyCharge,
    base_duty: Decimal,
) -> tuple[Decimal, str]:
    if charge.amount is not None:
        return charge.amount, f"Fixed charge: {charge.code}"

    assert charge.percent_of_duty is not None
    amount = base_duty * charge.percent_of_duty / Decimal("100")
    return amount, f"{charge.percent_of_duty}% of base duty: {charge.code}"


def calculate_stamp_duty(
    request: StampDutyCalculationRequest,
) -> StampDutyCalculationResponse:
    packs = load_rule_packs()
    pack = packs.get(request.rule_pack_id)
    if pack is None:
        raise StampDutyRulePackNotFoundError(
            f"unknown stamp-duty rule pack: {request.rule_pack_id}"
        )

    if request.instrument_date < pack.effective_from or (
        pack.effective_to is not None and request.instrument_date > pack.effective_to
    ):
        raise StampDutyRulePackDateError(
            "selected rule pack is not effective on the requested instrument_date"
        )

    breakdown: list[DutyBreakdownLine] = []
    adjustments: list[str] = []

    duty_base_value: Decimal | None = None
    if pack.method == DutyMethod.FIXED:
        assert pack.fixed_duty is not None
        base_duty = pack.fixed_duty
        breakdown.append(
            DutyBreakdownLine(
                label="Fixed stamp duty",
                basis="Fixed amount from rule pack",
                amount=_money(base_duty),
            )
        )
    else:
        duty_base_value = _resolve_duty_base(request, pack.valuation_basis)
        assert duty_base_value is not None

        if pack.method == DutyMethod.PERCENTAGE:
            assert pack.rate_percent is not None
            base_duty = duty_base_value * pack.rate_percent / Decimal("100")
            breakdown.append(
                DutyBreakdownLine(
                    label="Percentage stamp duty",
                    basis=f"{duty_base_value} at {pack.rate_percent}%",
                    amount=_money(base_duty),
                )
            )
        else:
            base_duty, slab_breakdown = _calculate_progressive_duty(duty_base_value, pack)
            breakdown.extend(slab_breakdown)

    mandatory_total = Decimal("0")
    for charge in pack.mandatory_charges:
        amount, basis = _calculate_charge(charge, base_duty)
        mandatory_total += amount
        breakdown.append(
            DutyBreakdownLine(label=charge.label, basis=basis, amount=_money(amount))
        )

    optional_by_code = {item.code: item for item in pack.optional_charges}
    unknown_codes = sorted(
        set(request.include_optional_charge_codes) - set(optional_by_code)
    )
    if unknown_codes:
        raise StampDutyInputError(
            "unknown optional charge code(s): " + ", ".join(unknown_codes)
        )

    optional_total = Decimal("0")
    for code in dict.fromkeys(request.include_optional_charge_codes):
        charge = optional_by_code[code]
        amount, basis = _calculate_charge(charge, base_duty)
        optional_total += amount
        breakdown.append(
            DutyBreakdownLine(label=charge.label, basis=basis, amount=_money(amount))
        )

    subtotal_before_limits = base_duty + mandatory_total + optional_total
    subtotal_after_limits = subtotal_before_limits

    if pack.minimum_duty is not None and subtotal_after_limits < pack.minimum_duty:
        adjustments.append(
            f"Minimum total duty applied: {subtotal_after_limits} -> {pack.minimum_duty}"
        )
        subtotal_after_limits = pack.minimum_duty

    if pack.maximum_duty is not None and subtotal_after_limits > pack.maximum_duty:
        adjustments.append(
            f"Maximum total duty applied: {subtotal_after_limits} -> {pack.maximum_duty}"
        )
        subtotal_after_limits = pack.maximum_duty

    final_duty = _round_to_unit(
        subtotal_after_limits,
        pack.rounding_unit,
        pack.rounding_method,
    )
    if final_duty != subtotal_after_limits:
        adjustments.append(
            f"Rounding applied ({pack.rounding_method.value} to {pack.rounding_unit}): "
            f"{subtotal_after_limits} -> {final_duty}"
        )

    return StampDutyCalculationResponse(
        rule_pack_id=pack.id,
        rule_pack_version=pack.version,
        jurisdiction=pack.jurisdiction,
        instrument_type=pack.instrument_type,
        currency=pack.currency,
        instrument_date=request.instrument_date,
        valuation_basis=pack.valuation_basis,
        duty_base_value=_money(duty_base_value) if duty_base_value is not None else None,
        base_duty=_money(base_duty),
        mandatory_charge_total=_money(mandatory_total),
        optional_charge_total=_money(optional_total),
        subtotal_before_limits=_money(subtotal_before_limits),
        subtotal_after_limits=_money(subtotal_after_limits),
        final_duty=_money(final_duty),
        breakdown=breakdown,
        adjustments=adjustments,
        source_note=pack.source_note,
        disclaimer=DISCLAIMER,
    )
