# Court Operations examples

Batch 14 treats court websites and imported records as external evidence sources, not as executable instructions.

Recommended production flow:

1. Register a tracker for the matter/CNR/case number.
2. Obtain the case status from a permitted official source, approved connector, or user-assisted official lookup.
3. Record/import a normalized snapshot.
4. Junior Lawyer compares it with the previous snapshot.
5. Material changes become `court_case_changes`.
6. Deterministic workflow templates create tasks/notifications.
7. A lawyer reviews the underlying official source and marks the change reviewed.

The built-in `ecourts_manual` source deliberately does not automate CAPTCHA solving or access-control circumvention.

For actual unattended production polling, implement an approved source connector or data arrangement and invoke the same snapshot service; do not replace the provenance/review layer with scraping assumptions.
