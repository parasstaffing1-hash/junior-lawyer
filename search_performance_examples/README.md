# Batch 19 search performance notes

## First production rebuild

After migrating to Batch 19, an owner/admin/partner can call:

```http
POST /api/v1/search/index/rebuild?include_corpus=true
```

The rebuild is idempotent: stable `source_key` values update existing chunks rather than duplicating them.

## Incremental documents

Normal document processing now calls the incremental reindex hook automatically. Maintenance endpoint:

```http
POST /api/v1/search/index/documents/{document_id}
```

Document deletion creates search-index tombstones before the source record is removed.

## PostgreSQL acceleration

Migration `20260808_0018` enables `pg_trgm` and creates:

- GIN full-text index over `to_tsvector('simple', normalized_text)`
- GIN trigram index over `normalized_text`
- GIN trigram index over `title`

SQLite remains a development/test fallback and uses portable indexes plus bounded candidate scans.

## Local vectors

Default: deterministic 128-dimensional feature-hash vector (zero model/API cost).

Optional: point `SEARCH_LOCAL_EMBEDDING_MODEL_PATH` at an **already-downloaded local** sentence-transformers model. No remote model download or embedding API is performed by Junior Lawyer. Install `sentence-transformers` yourself only if you want this optional mode.

## Duplicate detection

Exact duplicates use normalized SHA-256 grouping. Near duplicates use:

1. 64-bit SimHash
2. 4 LSH bands to generate candidate pairs
3. Hamming-distance threshold
4. token-shingle Jaccard confirmation

This avoids a naive O(n²) comparison across the full document index.

## Security invariant

Search-index rows carry organization, matter and client scope. Search applies those permission predicates **inside the database query before result ranking**. Public legal corpus rows have `organization_id = NULL` and are handled separately from confidential firm content.
