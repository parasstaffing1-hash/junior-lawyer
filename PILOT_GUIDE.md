# Controlled Lawyer Pilot Guide

## Goal

Validate that Junior Lawyer reduces routine legal work without weakening lawyer review, confidentiality, source provenance or procedural discipline.

## Suggested initial pilot

Start with a small group of trained lawyers and a deliberately limited practice scope. Prefer synthetic, public, de-identified or low-risk internal matters first. Expand to real privileged matters only after the firm's security/privacy owner has reviewed the RC evidence and deployment configuration.

## Pilot rules

- A lawyer remains responsible for every filing, advice, contract, deadline and client communication.
- Generated citations must resolve to the imported legal corpus/source before reliance.
- Deterministic deadline results remain reviewable; jurisdiction packs must identify their legal authority/version.
- Remote AI remains opt-in and can be denied per organization/matter/user.
- Ethical-wall matters require explicit access and should be included in permission-leak pilot tests.
- Do not use the product to bypass court CAPTCHA/access controls.
- Do not treat client-money controls as jurisdiction-specific trust-account certification.
- Record defects and workflow friction; do not silently create local workarounds that bypass audit/security controls.

## Pilot acceptance signals

Measure task completion, factual/citation corrections required, OCR failures, search misses, drafting-review findings, permission issues, deadline corrections, user time saved and support incidents. Avoid using the analytics workload score as an employee-quality or disciplinary rating.

## Stop conditions

Pause affected workflows if there is a confidentiality leak, unresolved citation hallucination in review-ready output, destructive data-loss behavior, incorrect access control, unexplained deadline computation, corrupted backup/restore result or material audit-log failure.
