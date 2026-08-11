from sqlalchemy import create_engine

from app.db.base import Base
import app.models  # noqa: F401
from app.models.search_index import SearchIndexEntry, SearchIndexJob, SearchPerformancePreference


def test_batch19_search_index_tables_registered():
    expected = {
        "search_index_entries", "search_index_jobs", "search_index_cursors",
        "search_duplicate_relations", "search_index_health_snapshots", "search_performance_preferences",
    }
    assert expected <= set(Base.metadata.tables)
    assert len(Base.metadata.tables) == 250


def test_batch19_schema_creates_on_sqlite():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    names = set(engine.dialect.get_table_names(engine.connect()))
    assert SearchIndexEntry.__tablename__ in names
    assert SearchIndexJob.__tablename__ in names
    assert SearchPerformancePreference.__tablename__ in names
    assert len(names) == 250
