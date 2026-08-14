"""Browsing the Acts shelf: filters, search, and an honest empty state."""

from datetime import date

import pytest

pytest.importorskip("aiosqlite")
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import *  # noqa: F401,F403 - register every ORM model for metadata
from app.models.legal_corpus import AccessMode, LegalSource, LegalSourceKind, Statute, StatuteSection
from app.services.research import service


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def make_source(db: AsyncSession) -> LegalSource:
    source = LegalSource(
        code="test-source",
        name="Test source",
        kind=LegalSourceKind.INDIA_CODE,
        access_mode=AccessMode.MANUAL_IMPORT,
        base_url="https://example.test",
    )
    db.add(source)
    await db.commit()
    return source


async def make_act(
    db: AsyncSession,
    source,
    *,
    title: str,
    hindi: str | None = None,
    short: str | None = None,
    number: str | None = None,
    year: int | None = None,
    jurisdiction: str = "India",
    state: str | None = None,
    active: bool = True,
) -> Statute:
    act = Statute(
        source_id=source.id,
        external_id=f"ext-{title}",
        title_en=title,
        title_hi=hindi,
        short_title=short,
        act_number=number,
        act_year=year,
        jurisdiction=jurisdiction,
        state=state,
        is_active=active,
        enactment_date=date(year, 1, 1) if year else None,
    )
    db.add(act)
    await db.commit()
    return act


# --- the empty shelf ----------------------------------------------------------


async def test_an_empty_corpus_reports_zero_rather_than_failing(db):
    # The corpus ships empty until bare acts are ingested. Browsing must say so
    # plainly instead of erroring, because that state is the normal one today.
    shelf = await service.statute_shelf(db)
    assert shelf == {"total_acts": 0, "jurisdictions": [], "states": []}

    acts, total = await service.list_statutes(db)
    assert acts == []
    assert total == 0


# --- browsing -----------------------------------------------------------------


async def test_acts_are_listed_newest_first(db):
    source = await make_source(db)
    await make_act(db, source, title="Old Act", year=1872)
    await make_act(db, source, title="Newer Act", year=2023)

    acts, total = await service.list_statutes(db)
    assert total == 2
    assert [a.title_en for a in acts] == ["Newer Act", "Old Act"]


async def test_repealed_acts_are_hidden_unless_asked_for(db):
    source = await make_source(db)
    await make_act(db, source, title="Live Act", year=2020)
    await make_act(db, source, title="Repealed Act", year=1898, active=False)

    _, live = await service.list_statutes(db)
    assert live == 1
    _, everything = await service.list_statutes(db, active_only=False)
    assert everything == 2


async def test_paging_reports_the_full_total(db):
    # The count must describe the shelf, not the page, or paging controls lie.
    source = await make_source(db)
    for index in range(5):
        await make_act(db, source, title=f"Act {index}", year=2000 + index)

    page, total = await service.list_statutes(db, limit=2, offset=0)
    assert len(page) == 2
    assert total == 5

    second, _ = await service.list_statutes(db, limit=2, offset=2)
    assert {a.title_en for a in page}.isdisjoint({a.title_en for a in second})


# --- searching ----------------------------------------------------------------


async def test_search_matches_the_english_title(db):
    source = await make_source(db)
    await make_act(db, source, title="Negotiable Instruments Act", year=1881)
    await make_act(db, source, title="Transfer of Property Act", year=1882)

    acts, total = await service.list_statutes(db, search="negotiable")
    assert total == 1
    assert acts[0].title_en == "Negotiable Instruments Act"


async def test_search_matches_hindi_and_the_act_number(db):
    # A lawyer looks up "138" or a Hindi title as readily as an English name.
    source = await make_source(db)
    await make_act(
        db,
        source,
        title="Negotiable Instruments Act",
        hindi="परक्राम्य लिखत अधिनियम",
        number="26",
        year=1881,
    )
    assert (await service.list_statutes(db, search="परक्राम्य"))[1] == 1
    assert (await service.list_statutes(db, search="26"))[1] == 1


async def test_search_ignores_surrounding_whitespace(db):
    source = await make_source(db)
    await make_act(db, source, title="Limitation Act", year=1963)
    assert (await service.list_statutes(db, search="  limitation  "))[1] == 1


async def test_filtering_by_state_and_year(db):
    source = await make_source(db)
    await make_act(db, source, title="UP Revenue Code", state="Uttar Pradesh", year=2006)
    await make_act(db, source, title="MP Land Code", state="Madhya Pradesh", year=1959)

    assert (await service.list_statutes(db, state="Uttar Pradesh"))[1] == 1
    assert (await service.list_statutes(db, year=1959))[1] == 1


# --- the shelf summary --------------------------------------------------------


async def test_the_shelf_counts_what_is_actually_held(db):
    source = await make_source(db)
    await make_act(db, source, title="Central Act", year=2000)
    await make_act(db, source, title="UP Act", state="Uttar Pradesh", year=2006)
    await make_act(db, source, title="Repealed", year=1900, active=False)

    shelf = await service.statute_shelf(db)
    assert shelf["total_acts"] == 2  # the repealed act is not on the shelf
    assert {row["name"] for row in shelf["states"]} == {"Uttar Pradesh"}


# --- inside one act -----------------------------------------------------------


async def test_finding_a_provision_by_number_or_wording(db):
    source = await make_source(db)
    act = await make_act(db, source, title="Negotiable Instruments Act", year=1881)
    db.add_all(
        [
            StatuteSection(
                statute_id=act.id,
                section_key="s-138",
                section_number="138",
                heading_en="Dishonour of cheque for insufficiency of funds",
                normalized_text="dishonour of cheque for insufficiency of funds",
                sort_order=138,
            ),
            StatuteSection(
                statute_id=act.id,
                section_key="s-139",
                section_number="139",
                heading_en="Presumption in favour of holder",
                normalized_text="presumption in favour of holder",
                sort_order=139,
            ),
        ]
    )
    await db.commit()

    by_number = await service.search_sections(db, act.id, query="138")
    assert [s.section_number for s in by_number] == ["138"]

    by_words = await service.search_sections(db, act.id, query="presumption")
    assert [s.section_number for s in by_words] == ["139"]


async def test_a_section_search_stays_inside_its_own_act(db):
    source = await make_source(db)
    first = await make_act(db, source, title="Act One", year=2001)
    second = await make_act(db, source, title="Act Two", year=2002)
    db.add_all(
        [
            StatuteSection(
                statute_id=first.id, section_key="a-1", section_number="1",
                heading_en="Short title", normalized_text="short title", sort_order=1,
            ),
            StatuteSection(
                statute_id=second.id, section_key="b-1", section_number="1",
                heading_en="Short title", normalized_text="short title", sort_order=1,
            ),
        ]
    )
    await db.commit()

    found = await service.search_sections(db, first.id, query="short title")
    assert len(found) == 1
    assert found[0].statute_id == first.id
