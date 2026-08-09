# Changelog

## 1.3.0-remediation - 2026-08-09

- Added tenant-scoped persistent idempotency and atomic confirmation claims.
- Added durable announcement-index Outbox processing with retry leases.
- Made RAG version updates rollback-safe and upload validation fail closed.
- Replaced ORM-driven migrations with explicit reversible Alembic operations.
- Replaced hard-coded evaluation/security/E2E claims with executable evidence.
- Hardened non-root containers, dependency scanning, SBOM generation and CI.
- Pinned Chroma 0.6.3 outside Critical CVE-2026-45829's affected range.

## 0.5.0-stage5-demo - 2026-08-05

- Added a repeatable Stage 5 integration, evaluation, performance, security and release workflow.
- Added browser E2E/screenshot/recording runners which use a locally installed Chrome when available.
- Added Docker web health checks and API-health dependency ordering.
- Added the release manifest, checksums and release package builders.

## 0.4.0

- Delivered the MCP, Harness and observability baseline.
