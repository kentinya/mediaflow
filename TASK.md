# Phase 19.7 — Bidirectional Notification and Schedule Audit Pagination

## Goal

Remove the Phase 19.6 recent-100 visibility limit by extending the existing directional keyset
cursor architecture to NotificationDelivery and per-schedule ScheduleAudit records. Preserve
deterministic bounded reads, resource/filter isolation, redaction, and the read-only operator UI.

## 1. Cursor and repository boundaries

- Add resource-scoped v2 cursors for notification deliveries and schedule audits.
- Use newest-first `(created_at, delivery_id)` and `(emitted_at, audit_id)` canonical ordering.
- Add mutually exclusive `after`/`before` repository boundaries with reverse SQL ordering,
  `limit + 1`, and canonical-order restoration for Previous pages.
- A schedule-audit cursor must only be usable within the schedule selected by its endpoint; bind the
  schedule ID into cursor scope without exposing configuration or media values.
- Notification status remains an explicit filter; bind cursor scope to that filter so a cursor from
  one status cannot be reused with another status or `all`.
- Continue accepting valid existing no-cursor clients. Never use OFFSET, totals, or full enumeration.

## 2. API and UI

- Notification and schedule-audit responses expose Previous and Next cursors.
- First/middle/last pages expose correct navigation boundaries, including page size one and empty data.
- Notification status selection resets to its first page; Previous/Next preserves the selected status.
- Schedule audit Previous/Next remains inside the selected schedule detail.
- Reselecting/refreshing a view returns to its first page; no automatic polling.

## 3. Safety and compatibility

- Preserve strict query validation, RBAC, normalized security audit, CSP, text-node rendering, and
  all Phase 19.6 redaction rules.
- Cursors contain no webhook URL/body/signature, response body, raw error, media path, credential,
  provider/policy data, or secret derivative.
- Construct no Storage, Provider, workflow service, Scheduler tick, Notification worker, or Executor.
- Add no delivery/requeue, schedule edit/tick, Task/Job, execute, overwrite, or delete controls.

## Required tests

- Notification first→middle→last→middle→first traversal with identical timestamps and page size one.
- Independent pagination for `all` and each notification status; cross-filter cursors fail safely.
- Per-schedule audit traversal; cross-schedule cursor use fails safely.
- SQL-level reverse keyset and `limit + 1` verification for both repositories.
- Empty datasets, insertion/deletion boundaries, canonical order, and no duplicates.
- Malformed/cross-kind/direction/version/time/ID/oversize/duplicate/injected query rejection.
- UI Previous/Next state preservation, status reset, schedule isolation, explicit refresh, and no writes.
- Existing Scheduler, Notification, pagination, RBAC/audit, Dashboard/reviews, Worker, and full regressions.
- Formatter, lint, compile, dependency/build/configuration, FFprobe/FFmpeg, and diff checks.

## Documentation

Update README, requirements status, configuration, architecture, progress, and roadmap with cursor
scope, ordering, consistency, and remaining no-jump/no-total/no-live-update limits.

## Out of scope

Persistent application logs, arbitrary jumps/page numbers/totals, notification payload viewing or
requeue, schedule editing/ticking, live polling/SSE/WebSocket, workflow controls, OIDC, Secret Store,
and TLS termination.

## Final report

## Phase 19.7 Result

PASS / FAIL

## Scoped Cursors

## Reverse Keyset Queries

## Operator UI

## Safety and Compatibility

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
