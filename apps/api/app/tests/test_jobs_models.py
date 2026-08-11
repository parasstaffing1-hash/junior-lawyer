from app import models  # noqa: F401
from app.db.base import Base


def test_batch20_tables_are_registered():
    names=set(Base.metadata.tables)
    expected={"background_queues","background_jobs","background_job_attempts","background_job_events","background_workers","background_job_dependencies","background_job_artifacts"}
    assert expected <= names
    assert len(names)==250
