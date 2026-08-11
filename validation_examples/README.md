# Batch 28 validation examples

These files are templates for a controlled Junior Lawyer staging deployment. Replace placeholder IDs with synthetic/de-identified fixtures only. Never commit session cookies, CSRF tokens, passwords, API keys or privileged client content.

`authenticated-security-cases.json` is intentionally explicit and bounded; the runner never discovers or scans additional endpoints.

`staging-scenario-result.json` demonstrates the shape submitted to `/api/v1/validation/campaigns/{campaign_id}/scenario-runs` after the evidence has actually been collected.
