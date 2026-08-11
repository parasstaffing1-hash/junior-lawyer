# Known Limitations — RC1

- RC1 is lawyer-supervised software, not an autonomous lawyer or a substitute for professional judgment.
- The shipped build does not claim complete coverage of every Indian statute, amendment, notification, court, tribunal or local practice. Corpus quality depends on the firm's configured authoritative sources and update operations.
- Court sources that require CAPTCHA or other protected interactions are not bypassed. User-assisted/official/approved connector workflows remain required.
- Limitation/deadline calculations require verified jurisdiction rules and lawyer review, particularly for exclusions, condonation, holidays and local practice.
- Evidence authenticity/admissibility are lawyer-review states, not automatic classifier conclusions.
- Client-money functionality is a control/accounting foundation and is not a certification of compliance with every jurisdiction's trust-account rules.
- GST/tax fields are configurable and review-gated; the software does not independently determine changing tax obligations.
- External Gmail/Calendar/Razorpay/DocuSign behavior depends on provider credentials, permissions, quotas and provider availability.
- Local OCR quality varies with scan quality, handwriting, fonts, layout and language mixture. Handwriting is not claimed as reliably supported by Tesseract.
- Local/remote generative AI is optional. Complex AI answers remain evidence-bounded and lawyer-reviewable; a configured model can still produce weak reasoning or wording.
- Accessibility engineering is substantially improved but formal WCAG certification is not claimed. RC1 requires real keyboard/screen-reader testing on target browsers/devices.
- No universal throughput figure is claimed. Search/OCR/worker capacity must be benchmarked on representative staging hardware and data volumes.
- A same-host backup is not sufficient disaster recovery. Pilot/production should use access-controlled off-host/off-site storage and verified restore drills.

## Batch 29 · Case Lookup and Legal Remedy Analysis

- Saved/cache lookup and normalized official-case imports are implemented. Live District Court/High Court/Supreme Court retrieval still depends on an approved connector or a user-assisted official-source flow where the court service requires verification/CAPTCHA. The product does not bypass CAPTCHA.
- Legal Remedy Analysis does not ship made-up generic Indian limitation periods as active law. Active results require lawyer-reviewed, verified jurisdiction rule packs with verified authorities. The included remedy-pack file is deliberately a draft template.
- A deterministic deadline is only computed when a verified rule supplies an explicit trigger and period and the case record contains the trigger date. Exclusions, condonation, alternate-remedy doctrine, appealability/revisionability, court-specific practice and latest binding precedent remain lawyer-review items.
- Batch 28 RC evidence predates Batch 29. A new staging/security/recovery/load/E2E RC campaign is required before pilot-ready status can be claimed.
