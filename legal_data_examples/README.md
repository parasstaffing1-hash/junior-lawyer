# Batch-26 legal-data examples

These files demonstrate normalized *input* to Junior Lawyer. They are not web-scraper configurations.

1. Seed/read the official legal-source rows and copy the appropriate `source_id`.
2. Create a feed using `feed.request.json` (replace the placeholder UUID).
3. Submit `statute-update.manifest.json` to `/api/v1/legal-data/feeds/{feed_id}/ingest`, or place it beneath the configured filesystem-drop directory.
4. Review any detected amendment event before activating a dependent jurisdiction-pack release.

The example statute text is intentionally short/synthetic and should not be treated as authoritative legal content.
