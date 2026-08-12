# Batch 25 integrations

Junior Lawyer keeps provider **credentials outside the application database**. Connection rows store public configuration and secret references such as `env://JL_GOOGLE_REFRESH_TOKEN`; the built-in resolver reads environment variables at runtime. Vault/cloud secret managers should be added as explicit resolver adapters rather than storing plaintext tokens in database JSON.

## Google Workspace

The connector uses the OAuth 2.0 web-server pattern, refreshes an access token from a pre-provisioned refresh token, sends mail with Gmail `users.messages.send`, and creates events with Calendar `events.insert`. The OAuth-start endpoint generates an authorization URL and CSRF state record, but intentionally does not persist the returned refresh token; persist that token in the firm's secret store and reference it from the connection.

Required secret references: `client_secret`, `refresh_token`. Common scopes: `https://www.googleapis.com/auth/gmail.send` and `https://www.googleapis.com/auth/calendar.events`.

## Razorpay

The connector creates standard Payment Links at `/v1/payment_links` using Basic authentication and validates inbound webhook signatures against the **raw request body** with HMAC-SHA256. `x-razorpay-event-id` is used for webhook idempotency when present. Mapping a Payment Link to an internal `payment_intent` allows verified paid/partially-paid/expired/cancelled events to update that intent.

## DocuSign

The connector creates eSignature envelopes from a document version the acting lawyer is allowed to download. The file is loaded through the existing local/S3 storage adapter, sent as an envelope document, and represented in the existing `esignature_envelopes` workflow. Connect HMAC callbacks can update the local envelope status.

Access tokens in the starter adapter are resolved from a secret reference. Production firms should implement a proper OAuth token lifecycle/rotation adapter rather than manually rotating long-lived access tokens.

## Generic webhooks

Outbound JSON is canonicalized and may be signed with `X-Junior-Lawyer-Signature: sha256=...`. Inbound webhooks can require the same HMAC check. Webhook event rows retain the raw-body SHA-256 and a minimized normalized payload, not the raw request body.

## Official legal-data boundary

`official_legal_import` never performs CAPTCHA bypassing or arbitrary URL fetching. An authenticated manager supplies an already obtained normalized statute/judgment payload plus its official source URL; the hostname must match the connection's allowlist before the existing corpus importer accepts it.

## Webhook endpoint security

Inbound provider paths under `/api/v1/integrations/webhooks/<endpoint-key>` are authentication-exempt because providers cannot possess a Junior Lawyer browser session. They are therefore protected by an unguessable endpoint key plus provider HMAC verification. Configure a signing-secret reference for production endpoints and restrict the accepted event types.

## Provider references used while implementing Batch 25

- Google Workspace Gmail API: OAuth web-server authorization and `users.messages.send`
- Google Calendar API: `events.insert`
- Razorpay Payment Links API and webhook HMAC validation
- DocuSign eSignature `createEnvelope` and Connect HMAC validation

Always re-check provider documentation and scopes during deployment because provider APIs, quotas and authentication policies can change.

## Batch 26 legal-data bridge

The normalized official-legal-data integration request now accepts an optional `feed_id`. When present, the validated connector payload is routed through Batch 26's feed/integrity/amendment/checkpoint pipeline rather than imported directly. A bound feed must match the integration connection. See `LEGAL_DATA.md` for legal-data lifecycle controls.

## Google Drive → Aiven legal-data catalog

The repository includes `apps/api/scripts/sync_google_drive_to_aiven.py` plus the scheduled/manual `Google Drive to Aiven sync` GitHub Actions workflow. It recursively catalogs the `junior-lawyer-data` Drive folder into Aiven PostgreSQL, extracts searchable text for supported files, skips unchanged content, retains oversized/unsupported items as metadata-only records, and soft-marks files that disappear after a complete traversal.

Credentials remain outside source control. The workflow requires the GitHub Actions secrets `AIVEN_DATABASE_URL` and `GOOGLE_SERVICE_ACCOUNT_JSON`; the Drive folder only needs to be shared with the service-account email as Viewer. See `docs/GOOGLE_DRIVE_AIVEN_SYNC.md` for setup and operating details.
