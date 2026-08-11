from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.jobs import JobKind, JobPriority, JobStatus


class JobCreate(BaseModel):
    kind: JobKind
    payload: dict = Field(default_factory=dict)
    priority: JobPriority = JobPriority.NORMAL
    queue_name: str | None = Field(default=None, max_length=80)
    matter_id: UUID | None = None
    resource_type: str | None = Field(default=None, max_length=80)
    resource_id: UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=240)
    max_attempts: int | None = Field(default=None, ge=1, le=20)
    scheduled_at: datetime | None = None
    depends_on: list[UUID] = Field(default_factory=list)


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    queue_name: str
    kind: str
    status: str
    priority: str
    priority_value: int
    matter_id: UUID | None
    resource_type: str | None
    resource_id: UUID | None
    payload_json: dict
    result_json: dict
    attempt_count: int
    max_attempts: int
    scheduled_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    cancellation_requested_at: datetime | None
    progress_current: int
    progress_total: int
    progress_message: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class AttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_id: UUID
    worker_id: UUID | None
    attempt_number: int
    status: str
    leased_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_type: str | None
    error_message: str | None


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_id: UUID
    event_type: str
    level: str
    message: str
    progress_current: int | None
    progress_total: int | None
    metadata_json: dict
    created_at: datetime


class WorkerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    worker_key: str
    hostname: str
    pid: int
    status: str
    queues_json: list
    started_at: datetime
    heartbeat_at: datetime
    current_job_id: UUID | None
    jobs_succeeded: int
    jobs_failed: int


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_id: UUID
    kind: str
    storage_key: str | None
    filename: str | None
    mime_type: str | None
    size_bytes: int | None
    sha256: str | None
    metadata_json: dict
    created_at: datetime


class JobDetail(BaseModel):
    job: JobRead
    attempts: list[AttemptRead]
    events: list[EventRead]
    artifacts: list[ArtifactRead]


class JobsDashboard(BaseModel):
    total: int
    by_status: dict[str, int]
    by_queue: dict[str, int]
    online_workers: int
    dead_letter: int
    workers: list[WorkerRead]


class QueueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    enabled: bool
    max_concurrency: int
    max_per_minute: int
    default_max_attempts: int
    lease_seconds: int
    metadata_json: dict


class QueueUpdate(BaseModel):
    enabled: bool | None = None
    max_concurrency: int | None = Field(default=None, ge=1, le=128)
    max_per_minute: int | None = Field(default=None, ge=1, le=100000)
    default_max_attempts: int | None = Field(default=None, ge=1, le=20)
    lease_seconds: int | None = Field(default=None, ge=30, le=86400)
