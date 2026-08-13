"""The diary: capturing dates from court records, and the message that goes out."""

from datetime import date, datetime, time, timedelta, timezone

import pytest

pytest.importorskip("aiosqlite")
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import *  # noqa: F401,F403 - register every ORM model for metadata
from app.models.case_lookup import CaseRecordStatus, CaseSourceKind, SavedCase
from app.models.matter import Matter
from app.models.procedure import Hearing, HearingStatus
from app.models.security import Organization
from app.services.procedure import diary


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def make_org(db: AsyncSession, slug: str = "chambers") -> Organization:
    organization = Organization(name=f"Firm {slug}", slug=slug)
    db.add(organization)
    await db.commit()
    return organization


async def make_matter(db: AsyncSession, organization, title: str) -> Matter:
    matter = Matter(title=title, organization_id=organization.id)
    db.add(matter)
    await db.commit()
    return matter


async def make_saved_case(
    db: AsyncSession,
    organization,
    matter,
    *,
    next_date,
    court: str = "Civil Court, Sitapur",
    stale: bool = False,
) -> SavedCase:
    saved = SavedCase(
        organization_id=organization.id,
        matter_id=matter.id if matter else None,
        source_case_key=f"key-{next_date}-{court}",
        case_number="CS 234/2026",
        cnr="UPSI010012342026",
        court_name=court,
        case_stage="Evidence",
        next_hearing_date=next_date,
        source_kind=CaseSourceKind.USER_ASSISTED,
        source_name="User-assisted import",
        fetched_at=datetime.now(timezone.utc),
        record_status=CaseRecordStatus.ACTIVE,
        stale_after=(
            datetime.now(timezone.utc) - timedelta(days=1) if stale else None
        ),
    )
    db.add(saved)
    await db.commit()
    return saved


# --- capturing dates ----------------------------------------------------------


async def test_a_saved_case_date_becomes_a_diary_entry(db):
    organization = await make_org(db)
    matter = await make_matter(db, organization, "Ram Singh v. State")
    listed = date.today() + timedelta(days=3)
    await make_saved_case(db, organization, matter, next_date=listed)

    result = await diary.sync_saved_case_dates(db, organization.id)
    assert result["created"] == 1

    hearing = await db.scalar(select(Hearing).where(Hearing.matter_id == matter.id))
    assert hearing.scheduled_for.date() == listed
    assert hearing.court_name == "Civil Court, Sitapur"
    assert hearing.metadata_json["source"] == diary.DIARY_SOURCE
    assert hearing.metadata_json["case_number"] == "CS 234/2026"


async def test_syncing_twice_updates_rather_than_duplicates(db):
    organization = await make_org(db)
    matter = await make_matter(db, organization, "Ram Singh v. State")
    await make_saved_case(db, organization, matter, next_date=date.today() + timedelta(days=3))

    await diary.sync_saved_case_dates(db, organization.id)
    second = await diary.sync_saved_case_dates(db, organization.id)

    assert second["created"] == 0
    assert second["updated"] == 1
    rows = (await db.scalars(select(Hearing).where(Hearing.matter_id == matter.id))).all()
    assert len(rows) == 1


async def test_a_hand_entered_hearing_is_never_overwritten(db):
    # The lawyer's own entry outranks anything captured from a court record.
    organization = await make_org(db)
    matter = await make_matter(db, organization, "Ram Singh v. State")
    listed = date.today() + timedelta(days=3)
    manual = Hearing(
        matter_id=matter.id,
        scheduled_for=datetime.combine(listed, time(10, 30), tzinfo=timezone.utc),
        court_name="Court as noted by counsel",
        purpose="Final arguments",
        status=HearingStatus.SCHEDULED,
        metadata_json={},
    )
    db.add(manual)
    await db.commit()
    await make_saved_case(db, organization, matter, next_date=listed)

    result = await diary.sync_saved_case_dates(db, organization.id)
    assert result["skipped"] == 1
    await db.refresh(manual)
    assert manual.court_name == "Court as noted by counsel"
    assert manual.purpose == "Final arguments"


async def test_past_dates_are_not_carried_into_the_diary(db):
    organization = await make_org(db)
    matter = await make_matter(db, organization, "Old matter")
    await make_saved_case(db, organization, matter, next_date=date.today() - timedelta(days=5))
    result = await diary.sync_saved_case_dates(db, organization.id)
    assert result["created"] == 0
    assert result["skipped"] == 1


async def test_a_case_with_no_matter_is_research_not_a_listing(db):
    organization = await make_org(db)
    await make_saved_case(db, organization, None, next_date=date.today() + timedelta(days=2))
    result = await diary.sync_saved_case_dates(db, organization.id)
    assert result["saved_cases_considered"] == 0


async def test_a_stale_source_is_counted_and_marked(db):
    # The date may be out of date at the court. Say so rather than imply a
    # freshness that was never checked.
    organization = await make_org(db)
    matter = await make_matter(db, organization, "Stale source")
    await make_saved_case(
        db, organization, matter, next_date=date.today() + timedelta(days=4), stale=True
    )
    result = await diary.sync_saved_case_dates(db, organization.id)
    assert result["stale_sources"] == 1
    hearing = await db.scalar(select(Hearing).where(Hearing.matter_id == matter.id))
    assert hearing.metadata_json["source_stale"] is True


async def test_another_firms_cases_are_not_synced(db):
    ours = await make_org(db, "ours")
    theirs = await make_org(db, "theirs")
    their_matter = await make_matter(db, theirs, "Their matter")
    await make_saved_case(db, theirs, their_matter, next_date=date.today() + timedelta(days=2))
    result = await diary.sync_saved_case_dates(db, ours.id)
    assert result["saved_cases_considered"] == 0


# --- the day's list -----------------------------------------------------------


async def test_the_digest_groups_by_court(db):
    organization = await make_org(db)
    listed = date.today() + timedelta(days=1)
    for court, title in [
        ("Tehsil Court, Biswan", "Mutation matter"),
        ("Tehsil Court, Biswan", "Partition matter"),
        ("Civil Court, Sitapur", "Recovery suit"),
    ]:
        matter = await make_matter(db, organization, title)
        db.add(
            Hearing(
                matter_id=matter.id,
                scheduled_for=datetime.combine(listed, time(11, 0), tzinfo=timezone.utc),
                court_name=court,
                status=HearingStatus.SCHEDULED,
                metadata_json={},
            )
        )
    await db.commit()

    digest = await diary.daily_digest(db, organization.id, on_date=listed)
    assert digest["hearing_count"] == 3
    counts = {court["court_name"]: len(court["items"]) for court in digest["courts"]}
    assert counts == {"Tehsil Court, Biswan": 2, "Civil Court, Sitapur": 1}


async def test_the_digest_covers_only_the_requested_day(db):
    organization = await make_org(db)
    matter = await make_matter(db, organization, "Tomorrow only")
    tomorrow = date.today() + timedelta(days=1)
    for when in (tomorrow, tomorrow + timedelta(days=1)):
        db.add(
            Hearing(
                matter_id=matter.id,
                scheduled_for=datetime.combine(when, time(11, 0), tzinfo=timezone.utc),
                court_name="Civil Court",
                status=HearingStatus.SCHEDULED,
                metadata_json={},
            )
        )
    await db.commit()
    assert (await diary.daily_digest(db, organization.id, on_date=tomorrow))["hearing_count"] == 1


async def test_cancelled_hearings_are_left_out(db):
    organization = await make_org(db)
    matter = await make_matter(db, organization, "Cancelled")
    listed = date.today() + timedelta(days=1)
    db.add(
        Hearing(
            matter_id=matter.id,
            scheduled_for=datetime.combine(listed, time(11, 0), tzinfo=timezone.utc),
            court_name="Civil Court",
            status=HearingStatus.CANCELLED,
            metadata_json={},
        )
    )
    await db.commit()
    assert (await diary.daily_digest(db, organization.id, on_date=listed))["hearing_count"] == 0


# --- the message --------------------------------------------------------------


async def test_the_english_message_leads_with_the_count(db):
    organization = await make_org(db)
    listed = date.today() + timedelta(days=1)
    matter = await make_matter(db, organization, "Recovery suit")
    db.add(
        Hearing(
            matter_id=matter.id,
            scheduled_for=datetime.combine(listed, time(11, 0), tzinfo=timezone.utc),
            court_name="Civil Court, Sitapur",
            courtroom="Room 4",
            status=HearingStatus.SCHEDULED,
            metadata_json={},
        )
    )
    await db.commit()
    digest = await diary.daily_digest(db, organization.id, on_date=listed)
    message = diary.render_digest(digest, language="en")

    assert "1 hearing" in message
    assert "Civil Court, Sitapur: 1" in message
    assert "Room 4" in message
    assert "Recovery suit" in message


async def test_the_hindi_message_is_actually_hindi(db):
    organization = await make_org(db)
    listed = date.today() + timedelta(days=1)
    matter = await make_matter(db, organization, "नामांतरण")
    db.add(
        Hearing(
            matter_id=matter.id,
            scheduled_for=datetime.combine(listed, time(11, 0), tzinfo=timezone.utc),
            court_name="तहसील न्यायालय",
            status=HearingStatus.SCHEDULED,
            metadata_json={},
        )
    )
    await db.commit()
    digest = await diary.daily_digest(db, organization.id, on_date=listed)
    message = diary.render_digest(digest, language="hi")

    assert "पेशी" in message
    assert "तहसील न्यायालय: 1" in message
    # The date is written in Hindi too, not left in English.
    assert diary.HINDI_MONTHS[listed.month] in message


async def test_an_empty_day_says_so_in_both_languages(db):
    organization = await make_org(db)
    listed = date.today() + timedelta(days=1)
    digest = await diary.daily_digest(db, organization.id, on_date=listed)
    assert "no hearings or deadlines" in diary.render_digest(digest, language="en")
    assert "कोई पेशी" in diary.render_digest(digest, language="hi")


async def test_a_stale_date_is_flagged_in_the_message(db):
    organization = await make_org(db)
    matter = await make_matter(db, organization, "Stale listing")
    listed = date.today() + timedelta(days=1)
    db.add(
        Hearing(
            matter_id=matter.id,
            scheduled_for=datetime.combine(listed, time(11, 0), tzinfo=timezone.utc),
            court_name="Civil Court",
            status=HearingStatus.SCHEDULED,
            metadata_json={"source": diary.DIARY_SOURCE, "source_stale": True},
        )
    )
    await db.commit()
    digest = await diary.daily_digest(db, organization.id, on_date=listed)
    assert "source not re-checked" in diary.render_digest(digest, language="en")
    assert "⚠" in diary.render_digest(digest, language="hi")
