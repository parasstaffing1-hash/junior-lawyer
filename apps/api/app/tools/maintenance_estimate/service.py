"""A range for maintenance, not a number.

There is no statutory formula for maintenance in India. Courts decide on the
means of the respondent, the reasonable needs of the applicant, the standard of
living the parties enjoyed, and the respondent's own obligations. Different
benches land in different places on identical facts.

So this returns a band with the arithmetic shown, and refuses to present one
figure as the answer. Anchors used, and their limits:

  * one quarter of net income is a commonly cited starting point for a wife
    alone, but it is a convention drawn from reported decisions, not a rule;
  * awards rise where minor children are involved and fall where the respondent
    supports other dependants;
  * only statutory deductions are taken off gross income. Courts routinely
    decline to deduct loan EMIs or discretionary spending, and a tool that did
    so would understate every claim.

The output exists to frame a conversation with the client, and says so.
"""

from __future__ import annotations

from app.tools.maintenance_estimate.models import (
    MaintenanceBand,
    MaintenanceEstimateRequest,
    MaintenanceEstimateResponse,
)

DISCLAIMER_EN = (
    "Indicative range only. Indian law prescribes no formula for maintenance; "
    "the amount is discretionary and depends on means, needs, standard of living "
    "and the respondent's other obligations. Not a prediction of any court's order."
)
DISCLAIMER_HI = (
    "केवल सांकेतिक अनुमान। भरण-पोषण की कोई निश्चित गणना विधि नहीं है; राशि "
    "न्यायालय के विवेक पर निर्भर करती है।"
)


class MaintenanceInputError(ValueError):
    """The figures given cannot describe a real claim."""


def estimate_maintenance(request: MaintenanceEstimateRequest) -> MaintenanceEstimateResponse:
    if request.statutory_deductions > request.respondent_monthly_income:
        raise MaintenanceInputError("Deductions cannot exceed gross income.")

    net = round(request.respondent_monthly_income - request.statutory_deductions, 2)
    if net <= 0:
        raise MaintenanceInputError(
            "Net income after statutory deductions is zero; maintenance cannot be "
            "estimated from these figures."
        )

    # Start from the conventional one-quarter anchor, then move within a band.
    low, mid, high = 0.20, 0.25, 0.33
    factors: list[str] = ["Starting point of about one quarter of net monthly income."]

    if request.minor_children:
        step = min(0.03 * request.minor_children, 0.09)
        low, mid, high = low + step, mid + step, min(high + step, 0.50)
        factors.append(
            f"Raised for {request.minor_children} minor "
            f"child{'ren' if request.minor_children > 1 else ''} in the applicant's care."
        )
    if request.respondent_has_other_dependants:
        low, mid, high = max(low - 0.04, 0.10), max(mid - 0.04, 0.12), max(high - 0.05, 0.15)
        factors.append("Reduced because the respondent supports other dependants.")
    if request.applicant_monthly_income > 0:
        ratio = request.applicant_monthly_income / max(net, 1)
        if ratio >= 0.5:
            low, mid, high = max(low - 0.08, 0.05), max(mid - 0.08, 0.07), max(high - 0.10, 0.10)
            factors.append("Reduced sharply: the applicant's own income approaches the respondent's.")
        elif ratio >= 0.2:
            low, mid, high = max(low - 0.04, 0.08), max(mid - 0.04, 0.10), max(high - 0.05, 0.12)
            factors.append("Reduced: the applicant has independent income.")
    if request.dependants > 1:
        factors.append(
            f"{request.dependants} dependants claimed — courts often award a combined "
            "figure rather than a multiple of the single-claimant rate."
        )

    bands = [
        MaintenanceBand(
            label_en="Conservative",
            label_hi="न्यूनतम",
            monthly_amount=round(net * low, 2),
            share_of_net_income=round(low, 3),
            reasoning_en="Lower end, where the respondent's obligations weigh heavily.",
        ),
        MaintenanceBand(
            label_en="Typical",
            label_hi="सामान्य",
            monthly_amount=round(net * mid, 2),
            share_of_net_income=round(mid, 3),
            reasoning_en="Around the conventional anchor, adjusted for the facts given.",
        ),
        MaintenanceBand(
            label_en="Higher",
            label_hi="अधिकतम",
            monthly_amount=round(net * high, 2),
            share_of_net_income=round(high, 3),
            reasoning_en="Upper end, where needs are high and the respondent's means are clear.",
        ),
    ]

    return MaintenanceEstimateResponse(
        net_monthly_income=net,
        bands=bands,
        factors_en=factors,
        disclaimer_en=DISCLAIMER_EN,
        disclaimer_hi=DISCLAIMER_HI,
    )
