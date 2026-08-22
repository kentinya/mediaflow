# Phase 19.5 — Bidirectional Stable Cursor Pagination

## Goal

Close the Phase 19.4 forward-only navigation risk by adding stable Previous cursors for Tasks, Jobs,
TaskItems, and ResultRecords. Preserve keyset memory safety, deterministic ordering, v1 cursor
compatibility, and the strictly read-only operator UI.

## 1. Versioned directional cursors

- Add a v2 opaque cursor with strict `next` or `previous` direction plus existing resource kind,
  UTC timestamp, and stable ID fields.
- Continue accepting valid Phase 19.4 v1 cursors as `next` cursors; emit only v2 cursors.
- Preserve length, Base64, schema, kind, UTC, ID, and query-duplication validation.
- Direction tampering, unknown versions/fields, and cross-resource use must fail clearly.
- Cursors contain no media values, errors, credentials, provider/policy data, or secret derivatives.

## 2. Reverse keyset queries

- Add mutually exclusive forward/previous repository boundaries for all four record types.
- Query the nearest previous page by reversing SQL ordering at the boundary, applying limit+1, then
  restore canonical display order before returning.
- Never use OFFSET, total-count queries, or full/prior-row enumeration.
- Task/Job canonical order remains newest-first; TaskItem/Result remains oldest-first.
- Concurrent inserts must not create duplicates inside an established forward/back navigation path.

## 3. API and UI

- Existing cursor parameters accept either direction without adding a separate direction field.
- Responses add `previous_cursor`, `previous_item_cursor`, and `previous_result_cursor` alongside
  existing Next fields.
- First pages expose no Previous; middle pages expose both; terminal pages expose no Next.
- UI adds Previous controls for Task/Job lists and independently for TaskItems/Results.
- First-page refresh remains available by reselecting a navigation tab; no automatic polling.

## 4. Safety and compatibility

- Keep existing no-cursor and v1-next clients working.
- Pagination constructs no Storage, MetadataProvider, workflow service, or executor and performs no
  media/persistent business mutation beyond existing redacted API security audit.
- Do not add Task/Job submit, cancel, resume, retry, authorize, execute, overwrite, or delete controls.
- Query strings/cursors remain absent from audit records and error responses.

## Required tests

- v1 forward compatibility and strict v2 direction validation.
- Task/Job first→middle→last→middle→first traversal with same-timestamp rows, no duplicates, and
  canonical order on every page.
- Independent TaskItem/Result backward traversal and SQL-level reverse keyset/limit verification.
- First/middle/last cursor presence, empty datasets, deletion/insertion boundaries, and page size one.
- Malformed direction/version/schema/kind/time/ID/oversize/duplicate/injected queries.
- UI Previous/Next controls, independent detail state, first-page refresh, and absence of writes.
- Viewer/RBAC/audit, credentials, Dashboard/reviews, Task persistence, Worker, and full regressions.
- Formatter, lint, compile, dependency/build/configuration, FFprobe/FFmpeg, and diff checks.

## Documentation

Update README, requirements status, configuration, architecture, progress, and roadmap with v1/v2,
direction, ordering, consistency, and remaining no-jump/no-total limitations.

## Out of scope

Arbitrary page jumps, page numbers, total-count scans, search/filtering, live polling/SSE/WebSocket,
Task/Job controls, history export, log/Scheduler/notification UI, OIDC, Secret Store, and TLS.

## Final report

## Phase 19.5 Result

PASS / FAIL

## Bidirectional Cursors

## Reverse Keyset Queries

## Operator UI

## Safety and Compatibility

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
