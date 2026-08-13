"""Populate a local database with demo data for a walkthrough.

Everything created here is fictional and labelled DEMO. Run against a local
development database only — it signs in as the bootstrap owner and writes
client, matter and document records.

    python scripts/seed_demo.py
"""

from __future__ import annotations

import io
import sys

import requests

BASE = "http://127.0.0.1:8000/api/v1"
FIRM = {
    "organization_name": "Example Chambers (DEMO)",
    "organization_slug": "example-chambers",
    "admin_email": "lawyer@example.com",
    "admin_name": "Example Lawyer",
    "password": "local-dev-password-2026",
}

# A fictional agreement, written so the clauses a lawyer would actually ask
# about — termination, payment, liability, notice — are all present.
AGREEMENT = """SERVICES AGREEMENT (DEMO DOCUMENT - FICTIONAL)

This Services Agreement is made on 12 March 2026 between Northstar Services
Private Limited, a company incorporated under the Companies Act, 2013, having
its registered office at 4th Floor, Cyber Heights, Bengaluru 560103 ("Service
Provider"), and ABC Manufacturing Private Limited, having its registered office
at Plot 22, Industrial Area, Pune 411057 ("Client").

1. SCOPE OF SERVICES
1.1 The Service Provider shall provide software maintenance and support
services as described in Schedule A.
1.2 Any change to the scope shall be agreed in writing and signed by both
parties before work commences.

2. TERM AND RENEWAL
2.1 This Agreement commences on 1 April 2026 and continues for an initial term
of twenty-four (24) months.
2.2 The Agreement renews automatically for successive twelve (12) month terms
unless either party gives written notice of non-renewal at least ninety (90)
days before the end of the then-current term.

3. PAYMENT
3.1 The Client shall pay INR 8,50,000 per quarter, invoiced in advance.
3.2 Invoices are payable within thirty (30) days of receipt.
3.3 Overdue amounts carry interest at 18% per annum calculated on a daily basis
from the due date until payment.

4. TERMINATION
4.1 Either party may terminate this Agreement for material breach if the breach
remains uncured thirty (30) days after written notice specifying the breach.
4.2 The Client may terminate for convenience on one hundred and eighty (180)
days written notice, subject to payment of an early termination charge equal to
two quarters of fees.
4.3 The Service Provider may suspend services immediately if any invoice
remains unpaid for more than sixty (60) days.

5. LIMITATION OF LIABILITY
5.1 Neither party shall be liable for indirect, incidental or consequential
loss, including loss of profit or loss of business opportunity.
5.2 The aggregate liability of the Service Provider under this Agreement shall
not exceed the total fees paid in the twelve (12) months preceding the claim.
5.3 Nothing in this clause limits liability for fraud, wilful misconduct, or
any liability that cannot be limited under applicable law.

6. CONFIDENTIALITY
6.1 Each party shall keep the other's confidential information secret and use
it only for the purposes of this Agreement.
6.2 This obligation survives termination for a period of five (5) years.

7. GOVERNING LAW AND DISPUTE RESOLUTION
7.1 This Agreement is governed by the laws of India.
7.2 Any dispute shall be referred to arbitration seated at Bengaluru under the
Arbitration and Conciliation Act, 1996, before a sole arbitrator.
7.3 The courts at Bengaluru shall have exclusive jurisdiction over any
application arising out of the arbitration.

8. NOTICES
8.1 Notices shall be in writing and delivered by hand, registered post, or
email to the addresses stated above.
8.2 A notice sent by registered post is deemed received five (5) business days
after posting.
"""


def main() -> int:
    session = requests.Session()

    print("bootstrap")
    response = session.post(f"{BASE}/security/bootstrap", json=FIRM, timeout=60)
    print(f"  {response.status_code} {response.json().get('message', response.text[:80])}")

    print("sign in")
    response = session.post(
        f"{BASE}/security/auth/login",
        json={
            "email": FIRM["admin_email"],
            "password": FIRM["password"],
            "organization_slug": FIRM["organization_slug"],
        },
        timeout=60,
    )
    response.raise_for_status()
    session.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    print(f"  signed in as {response.json()['actor']['display_name']}")

    print("client")
    response = session.post(
        f"{BASE}/crm/clients",
        json={
            "display_name": "ABC Manufacturing Private Limited",
            "client_type": "organization",
            "email": "legal@abcmanufacturing.example",
            "phone": "+91 20 5550 1234",
            "city": "Pune",
            "state": "Maharashtra",
        },
        timeout=60,
    )
    if response.status_code >= 400:
        print(f"  {response.status_code}: {response.text[:200]}")
        return 1
    client = response.json()
    print(f"  {client['display_name']}")

    # The API refuses to open a matter until a conflict check has been run and
    # decided — the same gate a real firm applies before taking on work.
    print("conflict check")
    response = session.post(
        f"{BASE}/crm/conflicts",
        json={
            "subject_name": client["display_name"],
            "related_parties": ["Northstar Services Private Limited"],
            "client_id": client["id"],
        },
        timeout=60,
    )
    if response.status_code >= 400:
        print(f"  {response.status_code}: {response.text[:300]}")
        return 1
    check = response.json()
    print(f"  raised {check['id']} status={check['status']}")

    response = session.patch(
        f"{BASE}/crm/conflicts/{check['id']}",
        json={"status": "cleared", "review_note": "DEMO: no adverse relationship found."},
        timeout=60,
    )
    if response.status_code >= 400:
        print(f"  {response.status_code}: {response.text[:300]}")
        return 1
    print(f"  cleared")

    print("matter")
    response = session.post(
        f"{BASE}/crm/clients/{client['id']}/matters",
        json={
            "title": "Northstar Services Agreement — review",
            "description": "Review the services agreement before renewal.",
            "practice_area": "Commercial contracts",
            "primary_language": "en",
        },
        timeout=60,
    )
    if response.status_code >= 400:
        print(f"  {response.status_code}: {response.text[:300]}")
        return 1
    matter = response.json()
    print(f"  {matter['title']} ({matter.get('reference_number')})")

    print("document")
    response = session.post(
        f"{BASE}/matters/{matter['id']}/documents",
        files={
            "file": (
                "northstar-services-agreement.txt",
                io.BytesIO(AGREEMENT.encode("utf-8")),
                "text/plain",
            )
        },
        params={"background": "false"},
        timeout=300,
    )
    if response.status_code >= 400:
        print(f"  {response.status_code}: {response.text[:300]}")
        return 1
    document = response.json()
    print(f"  {document.get('display_name')} — status {document.get('processing_status')}")

    print("\nseeded. sign in at http://localhost:3000/login")
    print(f"  email    {FIRM['admin_email']}")
    print(f"  password {FIRM['password']}")
    print(f"  firm     {FIRM['organization_slug']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
