from uuid import uuid4

import pytest

pytest.importorskip("aiosqlite")
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import *  # noqa: F401,F403 - register every ORM model for metadata
from app.models.matter import Matter, PartyKind, PartyRole
from app.schemas.matter import MatterPartyCreate, MatterPartyUpdate
from app.services.parties import (
    add_party,
    list_parties,
    normalize_name,
    remove_party,
    screen_name,
    update_party,
)


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def make_matter(db: AsyncSession, title: str = "ABC v. XYZ") -> Matter:
    matter = Matter(title=title)
    db.add(matter)
    await db.commit()
    await db.refresh(matter)
    return matter


# --- name normalization ------------------------------------------------------


def test_entity_noise_and_punctuation_are_dropped():
    assert normalize_name("M/s ABC Pvt. Ltd.") == "abc"
    assert normalize_name("ABC Limited") == "abc"
    assert normalize_name("Mr. Rajesh  Kumar") == "rajesh kumar"
    assert normalize_name("Rajesh Kumar") == "rajesh kumar"


def test_normalization_is_stable_for_empty_and_noise_only_input():
    assert normalize_name("") == ""
    assert normalize_name("   ") == ""
    assert normalize_name("M/s Pvt Ltd") == ""


# --- parties -----------------------------------------------------------------


async def test_a_party_is_stored_with_its_normalized_name(db):
    matter = await make_matter(db)
    party = await add_party(
        db,
        matter.id,
        MatterPartyCreate(
            role=PartyRole.OPPOSING,
            kind=PartyKind.COMPANY,
            name="M/s XYZ Pvt. Ltd.",
            advocate_name="A. Advocate",
        ),
    )
    assert party.normalized_name == "xyz"
    assert party.role == PartyRole.OPPOSING
    assert [p.id for p in await list_parties(db, matter.id)] == [party.id]


async def test_renaming_a_party_renormalizes(db):
    matter = await make_matter(db)
    party = await add_party(
        db, matter.id, MatterPartyCreate(role=PartyRole.OPPOSING, name="ABC Ltd")
    )
    updated = await update_party(
        db, matter.id, party.id, MatterPartyUpdate(name="Delta Industries Limited")
    )
    assert updated.normalized_name == "delta industries"


async def test_a_partial_update_leaves_other_fields_alone(db):
    matter = await make_matter(db)
    party = await add_party(
        db,
        matter.id,
        MatterPartyCreate(role=PartyRole.OPPOSING, name="ABC Ltd", advocate_name="A. Advocate"),
    )
    updated = await update_party(db, matter.id, party.id, MatterPartyUpdate(is_active=False))
    assert updated.is_active is False
    assert updated.advocate_name == "A. Advocate"
    assert updated.normalized_name == "abc"


async def test_a_party_from_another_matter_is_not_reachable(db):
    first = await make_matter(db, "First")
    second = await make_matter(db, "Second")
    party = await add_party(
        db, first.id, MatterPartyCreate(role=PartyRole.OPPOSING, name="ABC Ltd")
    )
    for call in (
        update_party(db, second.id, party.id, MatterPartyUpdate(name="Nope")),
        remove_party(db, second.id, party.id),
    ):
        with pytest.raises(HTTPException) as exc:
            await call
        assert exc.value.status_code == 404


async def test_adding_a_party_to_a_missing_matter_is_a_404(db):
    with pytest.raises(HTTPException) as exc:
        await add_party(db, uuid4(), MatterPartyCreate(role=PartyRole.OPPOSING, name="ABC"))
    assert exc.value.status_code == 404


async def test_removing_a_party_leaves_the_rest(db):
    matter = await make_matter(db)
    keep = await add_party(db, matter.id, MatterPartyCreate(role=PartyRole.CLIENT, name="Client"))
    drop = await add_party(db, matter.id, MatterPartyCreate(role=PartyRole.OPPOSING, name="Other"))
    await remove_party(db, matter.id, drop.id)
    assert [p.id for p in await list_parties(db, matter.id)] == [keep.id]


# --- conflict screening ------------------------------------------------------


async def test_screening_matches_across_matters_despite_entity_suffixes(db):
    first = await make_matter(db, "ABC v. XYZ")
    second = await make_matter(db, "Delta v. XYZ Group")
    await add_party(db, first.id, MatterPartyCreate(role=PartyRole.OPPOSING, name="M/s XYZ Pvt Ltd"))
    await add_party(db, second.id, MatterPartyCreate(role=PartyRole.CLIENT, name="XYZ Limited"))

    report = await screen_name(db, "XYZ")
    assert report.normalized_query == "xyz"
    assert len(report.hits) == 2
    assert {hit.matter_title for hit in report.hits} == {"ABC v. XYZ", "Delta v. XYZ Group"}
    # The name is on the other side of one matter, which is the case that
    # actually blocks an engagement.
    assert report.opposing_hit is True


async def test_screening_a_name_that_only_appears_as_a_client_is_not_an_opposing_hit(db):
    matter = await make_matter(db)
    await add_party(db, matter.id, MatterPartyCreate(role=PartyRole.CLIENT, name="Rajesh Kumar"))
    report = await screen_name(db, "Mr Rajesh Kumar")
    assert len(report.hits) == 1
    assert report.opposing_hit is False


async def test_screening_an_unknown_name_returns_nothing(db):
    await make_matter(db)
    report = await screen_name(db, "Nobody At All")
    assert report.hits == []
    assert report.opposing_hit is False


async def test_screening_noise_only_input_short_circuits(db):
    report = await screen_name(db, "M/s Pvt Ltd")
    assert report.normalized_query == ""
    assert report.hits == []
