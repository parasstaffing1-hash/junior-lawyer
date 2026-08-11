from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.jobs import JobPriority, JobStatus

PRIORITY_VALUE = {
    JobPriority.LOW: 20,
    JobPriority.NORMAL: 50,
    JobPriority.HIGH: 80,
    JobPriority.URGENT: 100,
}

TERMINAL_STATUSES = {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.DEAD_LETTER}
RUNNABLE_STATUSES = {JobStatus.QUEUED, JobStatus.RETRY_WAIT}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def retry_delay_seconds(attempt_number: int, base_seconds: int, cap_seconds: int = 3600) -> int:
    attempt = max(1, attempt_number)
    return min(cap_seconds, max(1, base_seconds) * (2 ** (attempt - 1)))


def retry_at(now: datetime, attempt_number: int, base_seconds: int) -> datetime:
    return now + timedelta(seconds=retry_delay_seconds(attempt_number, base_seconds))


def progress_percent(current: int, total: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(100, round(current * 100 / total)))


def can_retry(attempt_count: int, max_attempts: int) -> bool:
    return attempt_count < max(1, max_attempts)
