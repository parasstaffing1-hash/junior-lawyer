from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.matter import MatterLanguage, MatterStatus


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
