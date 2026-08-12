from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class FeeMethod(str, Enum):
    FIXED = "fixed"
    PROGRESSIVE = "progressive"


class RoundingMethod(str, Enum):
    NONE = "none"
    UP = "up"
    DOWN = "down"
    NEAREST = "nearest"


class FeeSlab(BaseModel):
    up_to: Decimal | None = Field(default=None, gt=0)
    rate_percent: Decimal = Field(ge=0, le=100)


class AdditionalFee(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(ge=0)


class CourtFeeRulePack(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    jurisdiction: str = Field(min_length=1, max_length=160)
    court: str = Field(min_length=1, max_length=160)
    case_type: str = Field(min_length=1, max_length=160)
    currency: str = Field(min_length=3, max_length=3)
    effective_from: date
    effective_to: date | None = None
    method: FeeMethod
    fixed_fee: Decimal | None = Field(default=None, ge=0)
    slabs: list[FeeSlab] = Field(default_factory=list)
    minimum_fee: Decimal | None = Field(default=None, ge=0)
    maximum_fee: Decimal | None = Field(default=None, ge=0)
    additional_fees: list[AdditionalFee] = Field(default_factory=list)
    rounding_method: RoundingMethod = RoundingMethod.NONE
    rounding_unit: Decimal = Field(default=Decimal("1"), gt=0)
    source_note: str = Field(min_length=1, max_length=600)

    @model_validator(mode="after")
    def validate_rule_pack(self) -> "CourtFeeRulePack":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be earlier than effective_from")

        if self.method == FeeMethod.FIXED:
            if self.fixed_fee is None:
                raise ValueError("fixed_fee is required for fixed fee rule packs")
            if self.slabs:
                raise ValueError("slabs must be empty for fixed fee rule packs")

        if self.method == FeeMethod.PROGRESSIVE:
            if self.fixed_fee is not None:
                raise ValueError("fixed_fee must be omitted for progressive rule packs")
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
            self.minimum_fee is not None
            and self.maximum_fee is not None
            and self.minimum_fee > self.maximum_fee
        ):
            raise ValueError("minimum_fee cannot exceed maximum_fee")

        return self


class CourtFeeCalculationRequest(BaseModel):
    rule_pack_id: str = Field(min_length=1, max_length=120)
    filing_date: date
    claim_value: Decimal | None = Field(default=None, ge=0)
    include_additional_fee_codes: list[str] = Field(default_factory=list)


class FeeBreakdownLine(BaseModel):
    label: str
    basis: str
    amount: Decimal


class CourtFeeCalculationResponse(BaseModel):
    rule_pack_id: str
    rule_pack_version: str
    jurisdiction: str
    court: str
    case_type: str
    currency: str
    filing_date: date
    claim_value: Decimal | None
    base_fee: Decimal
    additional_fee_total: Decimal
    subtotal_before_limits: Decimal
    subtotal_after_limits: Decimal
    final_fee: Decimal
    breakdown: list[FeeBreakdownLine]
    adjustments: list[str]
    source_note: str
    disclaimer: str


class CourtFeeRulePackSummary(BaseModel):
    id: str
    version: str
    jurisdiction: str
    court: str
    case_type: str
    currency: str
    effective_from: date
    effective_to: date | None
    method: FeeMethod
    source_note: str
