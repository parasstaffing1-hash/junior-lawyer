from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.matter import MatterLanguage, MatterStatus, PartyKind, PartyRole


class MatterBase(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    reference_number: str | None = Field(default=None, max_length=100)
    client_name: str | None = Field(default=None, max_length=250)
    court_name: str | None = Field(default=None, max_length=300)
    case_number: str | None = Field(default=None, max_length=150)
    cnr_number: str | None = Field(default=None, max_length=32)
    jurisdiction: str = Field(default="India", max_length=100)
    description: str | None = None
    status: MatterStatus = MatterStatus.ACTIVE
    primary_language: MatterLanguage = MatterLanguage.BILINGUAL


class MatterCreate(MatterBase):
    pass


class MatterUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    reference_number: str | None = Field(default=None, max_length=100)
    client_name: str | None = Field(default=None, max_length=250)
    court_name: str | None = Field(default=None, max_length=300)
    case_number: str | None = Field(default=None, max_length=150)
    cnr_number: str | None = Field(default=None, max_length=32)
    jurisdiction: str | None = Field(default=None, max_length=100)
    description: str | None = None
    status: MatterStatus | None = None
    primary_language: MatterLanguage | None = None


class MatterRead(MatterBase):
    id: UUID
    organization_id: UUID | None = None
    created_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    document_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class MatterPartyBase(BaseModel):
    role: PartyRole
    kind: PartyKind = PartyKind.INDIVIDUAL
    name: str = Field(min_length=1, max_length=300)
    client_id: UUID | None = None
    representing_firm: str | None = Field(default=None, max_length=300)
    advocate_name: str | None = Field(default=None, max_length=250)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=60)
    address: str | None = None
    notes: str | None = None
    is_active: bool = True


class MatterPartyCreate(MatterPartyBase):
    pass


class MatterPartyUpdate(BaseModel):
    role: PartyRole | None = None
    kind: PartyKind | None = None
    name: str | None = Field(default=None, min_length=1, max_length=300)
    client_id: UUID | None = None
    representing_firm: str | None = Field(default=None, max_length=300)
    advocate_name: str | None = Field(default=None, max_length=250)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=60)
    address: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class MatterPartyRead(MatterPartyBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    matter_id: UUID
    normalized_name: str
    created_at: datetime
    updated_at: datetime


class PartyConflictHit(BaseModel):
    """One prior matter where this name already appears."""

    party_id: UUID
    matter_id: UUID
    matter_title: str
    name: str
    role: PartyRole
    is_active: bool


class PartyConflictReport(BaseModel):
    query: str
    normalized_query: str
    hits: list[PartyConflictHit] = Field(default_factory=list)
    # True when the name appears on the other side of any matter — the case
    # that actually blocks an engagement.
    opposing_hit: bool = False
