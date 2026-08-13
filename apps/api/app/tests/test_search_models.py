from sqlalchemy import create_engine

from app.db.base import Base
from app.models.search import RecentItem, SavedSearch, SearchPreference


def test_batch18_search_tables_registered():
    expected = {"search_preferences", "saved_searches", "recent_items"}
    assert expected <= set(Base.metadata.tables)
    assert len(Base.metadata.tables) == 252


def test_batch18_schema_creates_on_sqlite():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    names = set(engine.dialect.get_table_names(engine.connect()))
    assert {RecentItem.__tablename__, SavedSearch.__tablename__, SearchPreference.__tablename__} <= names
    assert len(names) == 252
