from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class DutyMethod(str, Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    PROGRESSIVE = "progressive"


class ValuationBasis(str, Enum):
    CONSIDERATION = "consideration"
    MARKET_VALUE = "market_value"
    GREATER_OF_CONSIDERATION_OR_MARKET = "greater_of_consideration_or_market"
    ASSESSABLE_VALUE = "assessable_value"


class RoundingMethod(str, Enum):
    NONE = "none"
    UP = "up"
    DOWN = "down"
    NEAREST = "nearest"


class DutySlab(BaseModel):
    up_to: Decimal | None = Field(default=None, gt=0)
    rate_percent: Decimal = Field(ge=0, le=100)


class DutyCharge(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=200)
    amount: Decimal | None = Field(default=None, ge=0)
    percent_of_duty: Decimal | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def validate_charge(self) -> "DutyCharge":
        supplied = sum(value is not None for value in (self.amount, self.percent_of_duty))
        if supplied != 1:
            raise ValueError("a duty charge must define exactly one of amount or percent_of_duty")
        return self


class StampDutyRulePack(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    jurisdiction: str = Field(min_length=1, max_length=160)
    instrument_type: str = Field(min_length=1, max_length=160)
    currency: str = Field(min_length=3, max_length=3)
    effective_from: date
    effective_to: date | None = None
    valuation_basis: ValuationBasis
    method: DutyMethod
    fixed_duty: Decimal | None = Field(default=None, ge=0)
    rate_percent: Decimal | None = Field(default=None, ge=0, le=100)
    slabs: list[DutySlab] = Field(default_factory=list)
    minimum_duty: Decimal | None = Field(default=None, ge=0)
    maximum_duty: Decimal | None = Field(default=None, ge=0)
    mandatory_charges: list[DutyCharge] = Field(default_factory=list)
    optional_charges: list[DutyCharge] = Field(default_factory=list)
    rounding_method: RoundingMethod = RoundingMethod.NONE
    rounding_unit: Decimal = Field(default=Decimal("1"), gt=0)
    source_note: str = Field(min_length=1, max_length=800)

    @model_validator(mode="after")
    def validate_rule_pack(self) -> "StampDutyRulePack":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be earlier than effective_from")

        if self.method == DutyMethod.FIXED:
            if self.fixed_duty is None:
                raise ValueError("fixed_duty is required for fixed rule packs")
            if self.rate_percent is not None or self.slabs:
                raise ValueError("percentage/slab fields must be omitted for fixed rule packs")

        elif self.method == DutyMethod.PERCENTAGE:
            if self.rate_percent is None:
                raise ValueError("rate_percent is required for percentage rule packs")
            if self.fixed_duty is not None or self.slabs:
                raise ValueError("fixed_duty/slabs must be omitted for percentage rule packs")

        elif self.method == DutyMethod.PROGRESSIVE:
            if self.fixed_duty is not None or self.rate_percent is not None:
                raise ValueError("fixed_duty/rate_percent must be omitted for progressive rule packs")
            if not self.slabs:
                raise ValueError("at least one slab is required for progressive rule packs")
            if self.slabs[-1].up_to is not None:
                raise ValueError("the final progressive slab must be open-ended (up_to=null)")

            previous_limit = Decimal("0")
            for slab in self.slabs:
                if slab.up_to is not None:
                    if slab.up_to <= previous_limit:
                        raise ValueError("progressive slab limits must be strictly increasing")
                    previous_limit = slab.up_to

        if (
            self.minimum_duty is not None
            and self.maximum_duty is not None
            and self.minimum_duty > self.maximum_duty
        ):
            raise ValueError("minimum_duty cannot exceed maximum_duty")

        mandatory_codes = [item.code for item in self.mandatory_charges]
        optional_codes = [item.code for item in self.optional_charges]
        all_codes = mandatory_codes + optional_codes
        if len(all_codes) != len(set(all_codes)):
            raise ValueError("duty charge codes must be unique within a rule pack")

        return self


class StampDutyCalculationRequest(BaseModel):
    rule_pack_id: str = Field(min_length=1, max_length=120)
    instrument_date: date
    consideration_value: Decimal | None = Field(default=None, ge=0)
    market_value: Decimal | None = Field(default=None, ge=0)
    assessable_value: Decimal | None = Field(default=None, ge=0)
    include_optional_charge_codes: list[str] = Field(default_factory=list)


class DutyBreakdownLine(BaseModel):
    label: str
    basis: str
    amount: Decimal


class StampDutyCalculationResponse(BaseModel):
    rule_pack_id: str
    rule_pack_version: str
    jurisdiction: str
    instrument_type: str
    currency: str
    instrument_date: date
    valuation_basis: ValuationBasis
    duty_base_value: Decimal | None
    base_duty: Decimal
    mandatory_charge_total: Decimal
    optional_charge_total: Decimal
    subtotal_before_limits: Decimal
    subtotal_after_limits: Decimal
    final_duty: Decimal
    breakdown: list[DutyBreakdownLine]
    adjustments: list[str]
    source_note: str
    disclaimer: str


class StampDutyRulePackSummary(BaseModel):
    id: str
    version: str
    jurisdiction: str
    instrument_type: str
    currency: str
    effective_from: date
    effective_to: date | None
    valuation_basis: ValuationBasis
    method: DutyMethod
    source_note: str
