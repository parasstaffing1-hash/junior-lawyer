# Batch 25 integration examples

These examples contain **references/placeholders only**. Do not commit real provider credentials.

- `google-workspace.request.json` — Google Workspace connection profile.
- `razorpay.request.json` — Razorpay Payment Links + webhook profile.
- `docusign.request.json` — DocuSign eSignature + Connect profile.
- `official-legal-import.request.json` — normalized official-source import profile.

Generic webhooks should configure an explicit HTTPS `allowed_hosts` list and HMAC secret references. Live provider operations require externally provisioned credentials.
