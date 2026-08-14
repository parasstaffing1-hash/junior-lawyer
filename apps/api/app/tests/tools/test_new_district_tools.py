"""The four tools added for district and tehsil practice."""

from datetime import date, timedelta

import pytest

from app.tools.cause_list_match.models import CauseListCase, CauseListMatchRequest
from app.tools.cause_list_match.service import match_cause_list, normalise_case_number
from app.tools.cheque_timeline.models import ChequeTimelineRequest
from app.tools.cheque_timeline.service import (
    ChequeTimelineInputError,
    calculate_cheque_timeline,
)
from app.tools.maintenance_estimate.models import MaintenanceEstimateRequest
from app.tools.maintenance_estimate.service import MaintenanceInputError, estimate_maintenance
from app.tools.order_sheet.models import OrderSheetRequest
from app.tools.order_sheet.service import parse_order_sheet


# --- cheque timeline ----------------------------------------------------------


def test_the_three_windows_are_computed_from_the_return_memo():
    result = calculate_cheque_timeline(
        ChequeTimelineRequest(
            cheque_date=date(2026, 1, 10),
            return_memo_date=date(2026, 1, 20),
            notice_sent_date=date(2026, 1, 25),
            notice_served_date=date(2026, 1, 28),
        )
    )
    assert result.notice_deadline == date(2026, 2, 19)      # 30 days from return
    assert result.complaint_window_opens == date(2026, 2, 13)  # day after 15 days
    assert result.complaint_deadline == date(2026, 3, 12)   # one month after


def test_a_complaint_before_the_payment_window_closes_is_premature():
    # The drawer still has time to pay, so there is no cause of action yet.
    today = date.today()
    result = calculate_cheque_timeline(
        ChequeTimelineRequest(
            cheque_date=today - timedelta(days=20),
            return_memo_date=today - timedelta(days=10),
            notice_sent_date=today - timedelta(days=5),
            notice_served_date=today - timedelta(days=4),
        )
    )
    assert result.maintainable is False
    assert "Premature" in result.blocking_reason_en


def test_a_notice_sent_after_thirty_days_kills_the_cause_of_action():
    result = calculate_cheque_timeline(
        ChequeTimelineRequest(
            cheque_date=date(2026, 1, 1),
            return_memo_date=date(2026, 1, 5),
            notice_sent_date=date(2026, 2, 20),
        )
    )
    assert result.maintainable is False
    assert "30-day" in result.blocking_reason_en
    assert any("30-day window" in w for w in result.warnings)


def test_presentation_after_three_months_is_flagged():
    result = calculate_cheque_timeline(
        ChequeTimelineRequest(
            cheque_date=date(2026, 1, 1),
            return_memo_date=date(2026, 5, 1),
        )
    )
    assert result.maintainable is False
    assert "validity" in result.blocking_reason_en


def test_service_date_missing_is_warned_not_guessed():
    result = calculate_cheque_timeline(
        ChequeTimelineRequest(
            cheque_date=date(2026, 1, 1),
            return_memo_date=date(2026, 1, 5),
            notice_sent_date=date(2026, 1, 10),
        )
    )
    assert any("Service date not recorded" in w for w in result.warnings)


def test_impossible_dates_are_refused():
    with pytest.raises(ChequeTimelineInputError):
        calculate_cheque_timeline(
            ChequeTimelineRequest(
                cheque_date=date(2026, 5, 1), return_memo_date=date(2026, 1, 1)
            )
        )


def test_every_step_names_its_provision():
    result = calculate_cheque_timeline(
        ChequeTimelineRequest(cheque_date=date(2026, 1, 1), return_memo_date=date(2026, 1, 5))
    )
    assert all(step.authority for step in result.steps)


# --- cause list ---------------------------------------------------------------


def test_the_same_case_number_matches_however_the_list_writes_it():
    for spelling in ("CS 234/2026", "C.S. No. 234 of 2026", "cs/234/2026"):
        assert normalise_case_number(spelling) == "cs2342026"


def test_a_case_is_found_in_a_pasted_list():
    listing = """
    IN THE COURT OF CIVIL JUDGE, SITAPUR
    1. C.S. No. 121 of 2025   Sharma v. Verma
    2. C.S. No. 234 of 2026   Ram Singh v. State
    3. Misc. 87/2026          Gupta v. Municipal Board
    """
    result = match_cause_list(
        CauseListMatchRequest(
            cause_list_text=listing,
            cases=[CauseListCase(reference="CS 234/2026", title="Ram Singh v. State")],
        )
    )
    assert len(result.matches) == 1
    match = result.matches[0]
    assert match.item_number == "2"
    assert match.matched_on == "case_number"
    assert match.confident is True


def test_a_party_name_match_is_reported_but_not_treated_as_certain():
    # Shared names are common; the lawyer must look rather than trust.
    result = match_cause_list(
        CauseListMatchRequest(
            cause_list_text="5. Misc 90/2026   Ram Singh v. Anil Kumar",
            cases=[CauseListCase(reference="CS 999/2026", party_names=["Ram Singh"])],
        )
    )
    assert len(result.matches) == 1
    assert result.matches[0].confident is False
    assert result.matches[0].matched_on.startswith("party_name")


def test_cases_that_are_not_listed_are_named(db=None):
    result = match_cause_list(
        CauseListMatchRequest(
            cause_list_text="1. CS 111/2026  A v. B",
            cases=[
                CauseListCase(reference="CS 111/2026"),
                CauseListCase(reference="CS 222/2026"),
            ],
        )
    )
    assert result.unmatched_references == ["CS 222/2026"]


def test_unmatched_listing_lines_are_returned_for_review():
    # A case can be listed under a number the lawyer does not have on file, and
    # silently dropping it is the failure that costs a date.
    result = match_cause_list(
        CauseListMatchRequest(
            cause_list_text="1. CS 111/2026  A v. B\n2. CS 777/2026  Unknown matter",
            cases=[CauseListCase(reference="CS 111/2026")],
        )
    )
    assert any("777" in line for line in result.review_lines)


def test_headings_are_not_offered_as_review_lines():
    result = match_cause_list(
        CauseListMatchRequest(
            cause_list_text="IN THE COURT OF CIVIL JUDGE\nDAILY CAUSE LIST",
            cases=[CauseListCase(reference="CS 111/2026")],
        )
    )
    assert result.review_lines == []


# --- order sheet --------------------------------------------------------------


def test_an_explicit_next_date_is_read_confidently():
    result = parse_order_sheet(
        OrderSheetRequest(
            text="Heard counsel. List on 12.09.2026 for final arguments.",
            order_date=date(2026, 8, 14),
        )
    )
    assert result.next_hearing_date == date(2026, 9, 12)
    assert result.next_hearing_confident is True
    assert result.purpose and "arguments" in result.purpose


def test_a_relative_date_is_resolved_but_never_called_confident():
    result = parse_order_sheet(
        OrderSheetRequest(
            text="Adjourned. Put up after four weeks.", order_date=date(2026, 8, 14)
        )
    )
    assert result.next_hearing_date == date(2026, 9, 11)
    assert result.next_hearing_confident is False
    assert result.adjourned is True


def test_a_textual_date_is_parsed():
    result = parse_order_sheet(
        OrderSheetRequest(text="Renotify on 3rd September, 2026 for evidence.")
    )
    assert result.next_hearing_date == date(2026, 9, 3)


def test_directions_are_extracted_with_the_party_they_bind():
    result = parse_order_sheet(
        OrderSheetRequest(
            text="The defendant shall file the written statement within four weeks. "
            "Last opportunity is granted to the plaintiff to produce documents."
        )
    )
    assert len(result.directions) == 2
    assert result.directions[0].party_hint == "defendant"


def test_a_disposal_is_recognised():
    assert parse_order_sheet(OrderSheetRequest(text="Suit is decreed.")).disposed is True


def test_output_always_requires_review():
    # Handwriting plus OCR plus a diary is exactly where a wrong date lands.
    result = parse_order_sheet(OrderSheetRequest(text="List on 01.01.2027."))
    assert result.requires_review is True


def test_text_with_no_date_yields_none_rather_than_a_guess():
    result = parse_order_sheet(OrderSheetRequest(text="Heard. Order reserved."))
    assert result.next_hearing_date is None


# --- maintenance --------------------------------------------------------------


def test_a_band_is_returned_rather_than_a_single_figure():
    result = estimate_maintenance(
        MaintenanceEstimateRequest(respondent_monthly_income=60000, statutory_deductions=6000)
    )
    assert len(result.bands) == 3
    amounts = [band.monthly_amount for band in result.bands]
    assert amounts == sorted(amounts)
    assert result.net_monthly_income == 54000


def test_minor_children_raise_the_band_and_the_reason_is_stated():
    base = estimate_maintenance(MaintenanceEstimateRequest(respondent_monthly_income=50000))
    withkids = estimate_maintenance(
        MaintenanceEstimateRequest(respondent_monthly_income=50000, minor_children=2)
    )
    assert withkids.bands[1].monthly_amount > base.bands[1].monthly_amount
    assert any("minor" in factor for factor in withkids.factors_en)


def test_an_applicant_earning_comparably_lowers_the_band():
    modest = estimate_maintenance(
        MaintenanceEstimateRequest(respondent_monthly_income=50000, applicant_monthly_income=30000)
    )
    none = estimate_maintenance(MaintenanceEstimateRequest(respondent_monthly_income=50000))
    assert modest.bands[1].monthly_amount < none.bands[1].monthly_amount


def test_deductions_exceeding_income_are_refused():
    with pytest.raises(MaintenanceInputError):
        estimate_maintenance(
            MaintenanceEstimateRequest(
                respondent_monthly_income=20000, statutory_deductions=25000
            )
        )


def test_the_disclaimer_says_there_is_no_formula():
    result = estimate_maintenance(MaintenanceEstimateRequest(respondent_monthly_income=40000))
    assert "no formula" in result.disclaimer_en
    assert result.disclaimer_hi
