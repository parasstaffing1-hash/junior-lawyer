from datetime import datetime, timezone

from app.models.jobs import JobPriority
from app.services.jobs.engine import PRIORITY_VALUE, can_retry, progress_percent, retry_delay_seconds, retry_at


def test_priority_values_are_ordered():
    assert PRIORITY_VALUE[JobPriority.URGENT] > PRIORITY_VALUE[JobPriority.HIGH] > PRIORITY_VALUE[JobPriority.NORMAL] > PRIORITY_VALUE[JobPriority.LOW]


def test_exponential_backoff_is_deterministic_and_capped():
    assert retry_delay_seconds(1,10)==10
    assert retry_delay_seconds(2,10)==20
    assert retry_delay_seconds(3,10)==40
    assert retry_delay_seconds(20,10)==3600


def test_retry_at_uses_backoff():
    now=datetime(2026,8,8,tzinfo=timezone.utc)
    assert (retry_at(now,3,10)-now).total_seconds()==40


def test_progress_percent_is_safe():
    assert progress_percent(0,0)==0
    assert progress_percent(50,100)==50
    assert progress_percent(500,100)==100


def test_retry_limit():
    assert can_retry(1,3)
    assert can_retry(2,3)
    assert not can_retry(3,3)
