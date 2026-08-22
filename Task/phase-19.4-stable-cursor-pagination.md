# Phase 19.4 — Stable Cursor Pagination for Operational History

## Goal

Remove the Phase 19.3 large-history limitation by adding deterministic, bounded keyset cursor
pagination for Tasks, Jobs, TaskItems, and ResultRecords. Extend the read-only operator UI to move
through pages without adding any workflow control.

## 1. Cursor model

- Define a provider-neutral opaque URL-safe cursor containing only resource kind, ordering timestamp,
  and stable record ID.
- Strictly validate encoding, schema, kind, timestamp, ID, and total length. Reject cross-resource,
  malformed, duplicate, oversized, or injected cursors.
- Do not include paths, titles, errors, credentials, policy/provider values, or secret-derived data.
- Cursor decoding is transport/application logic, not a domain strategy concern.

## 2. Keyset persistence queries

- Use stable composite ordering `(created_at, stable_id)` for Tasks, Jobs, TaskItems, and Results.
- Task/Job history orders newest first; TaskItem/Result detail preserves oldest-first processing order.
- Add optional keyset boundaries to repository reads and execute `limit+1` in SQLite.
- Do not use OFFSET and do not enumerate preceding/all rows.
- Preserve existing no-cursor response compatibility while adding `nextCursor` when another page
  exists. End pages return no cursor and `truncated=false`.

## 3. API and operator UI

- Task/Job collections accept one optional `cursor` with existing `limit`.
- Task detail accepts independent `itemCursor` and `resultCursor` with existing limits.
- UI provides explicit Next controls for each collection and independently for TaskItems/Results.
- Navigation replaces the displayed page, clearly identifies paged data, and supports returning to
  the first page via Refresh. No automatic polling, infinite scroll, or background prefetch.
- Continue safe text rendering and memory-only bearer credentials.

## 4. Safety

- Pagination is read-only and constructs no Storage, MetadataProvider, Task/Job service, or executor.
- Do not add submit/cancel/resume/retry/authorize/execute/overwrite/delete controls.
- Preserve RBAC, normalized audit routes, review workflows, strategy engines, and execution safety.
- Cursor values must never be logged in security audit because query strings remain excluded.

## Required tests

- Multi-page Task/Job newest-first traversal with identical timestamps and no duplicate/missing rows.
- Independent TaskItem/Result oldest-first traversal and SQL-level keyset/limit verification.
- End-page semantics, empty pages, cursor kind mismatch, malformed/base64/JSON/time/ID/oversize,
  duplicate parameters, and query-field injection.
- Concurrent insertion before/after a cursor does not shift already established page boundaries.
- UI Next controls, independent detail cursors, first-page refresh, safe encoding, and no write calls.
- Viewer/RBAC/audit compatibility and zero Storage/provider/media mutation.
- Existing API, credentials, Dashboard, reviews, Task persistence, Worker, UI, and full regressions.
- Full formatter, lint, compile, dependency/build/configuration and FFprobe audits.

## Documentation

Update README, requirements status, configuration, architecture, progress, and roadmap with cursor
semantics, ordering, limits, and consistency boundaries.

## Out of scope

Backward/previous cursors, arbitrary page jumps, total-count scans, search/filtering, live polling,
SSE/WebSocket, Task/Job controls, history export, log UI, Scheduler/notification UI, OIDC, and TLS.

## Final report

## Phase 19.4 Result

PASS / FAIL

## Cursor Pagination

## Stable Ordering

## Operator UI

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
