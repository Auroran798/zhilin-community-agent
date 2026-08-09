# Public-real data boundary

This directory contains a reproducible, privacy-minimised Stage 6 cache of official public regulatory data. It is not a property-company production database and does not describe a Chinese community.

- `manifests/` and `source_registry.csv` are tracked evidence: publisher, license/terms, URLs, checksum and retrieval method.
- `raw/` preserves only the exact fields requested from the official API. The selection intentionally excludes street address, unit, coordinates and contact fields.
- `processed/` contains safe text/location projections.
- `normalized/` is imported into the isolated `public_datasets` / `public_cases` schema, never into resident work orders, properties, bills or payments.
- `samples/` may hold tiny, sanitized review samples only.

The complete raw/processed/normalized files are ignored by Git. Recreate them with `python scripts/stage6_pipeline.py all` after reviewing the current terms and local environment configuration.
