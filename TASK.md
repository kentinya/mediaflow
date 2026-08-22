# Phase 19.9 — Read-only Operational Log API and UI

## Goal

Expose Phase 19.8's already-redacted structured operational records through the existing authenticated
API and operator UI using stable bidirectional keyset pagination. Keep retrieval bounded and strictly
read-only; do not expand the persisted log schema or expose discarded context.

## 1. Repository and cursor reads

- Extend operational log reads with newest-first `(occurred_at, log_id)` after/before boundaries.
- Add a scoped v2 cursor kind bound to the selected minimum level (`all` included).
- Apply `limit + 1` in SQLite, reverse keyset queries for Previous, and restore canonical ordering.
- Never use OFFSET, total counts, full enumeration, full-text search, or arbitrary context matching.

## 2. API

- Add authenticated `GET /api/v1/logs?limit=100&level=all&cursor=...`.
- Accept only 1–100 limit, existing level names, and one cursor; reject malformed/duplicate fields.
- Return only Phase 19.8 safe fields plus Previous/Next cursors.
- Use existing READ permission and normalized audit; query/cursor/records must not enter audit/errors.

## 3. Operator UI

- Add a read-only Logs tab with level selector, explicit refresh, and Previous/Next.
- Level changes reset to first page; cursor navigation preserves the selected level.
- Render via text nodes and preserve CSP, no-store, same-origin, and in-memory credentials.
- Add no prune, live tail, Task/Job controls, workflow actions, or execution controls.

## Required tests

- First→middle→last→middle→first traversal, same timestamps, page size one, empty dataset.
- Minimum-level filters, filter-bound cursors, cross-filter/cross-kind rejection.
- SQL reverse keyset/limit verification, insertion/deletion boundaries, canonical order/no duplicates.
- Malformed version/direction/scope/time/ID/oversize and duplicate/injected query rejection.
- API field allowlist and absence of paths/errors/titles/provider/HTTP/context/secrets.
- Viewer/operator/executor/auditor/admin read behavior and normalized audit without query data.
- UI level reset, Previous/Next preservation, explicit refresh, text rendering, and no write controls.
- Existing logs CLI/prune, pagination, API/UI, Scheduler/Notification, workflow, Storage, and full regressions.
- Formatter, lint, compile, dependency/build/configuration, FFprobe/FFmpeg, and diff checks.

## Documentation

Update README, requirements, configuration, architecture, progress, and roadmap with endpoint,
ordering, cursor scope, redaction, and no-search/no-live-tail limitations.

## Out of scope

Log writes through API, prune through API/UI, full-text search, arbitrary fields/context, media paths,
raw errors, remote shipping/OpenTelemetry, live tail/SSE/WebSocket, OIDC, Secret Store, and TLS.

## Final report

## Phase 19.9 Result

PASS / FAIL

## Log Pagination

## API and UI

## Redaction and Authorization

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
