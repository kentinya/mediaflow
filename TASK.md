# Phase 19.6 — Read-only Scheduler and Notification Operations UI

## Goal

Close the highest-priority Phase 19 operations-visibility gap by exposing configured schedules,
bounded schedule occurrence audit, and bounded notification delivery state in the existing secure
operator UI. Reuse existing repositories and API models; preserve strict read-only behavior.

## 1. Bounded API reads

- Keep schedule definitions configuration-owned and combine them only with existing persisted state.
- Add strict optional `limit` validation (1–100) to notification and schedule-audit reads.
- Add an optional notification status filter using only existing delivery statuses.
- Reject unknown, duplicate, blank, malformed, or injected query fields.
- Preserve deterministic repository ordering and apply limits in SQLite; do not enumerate full
  delivery/audit history and do not add OFFSET or total-count scans.
- Do not expose webhook URLs, signatures, request bodies, secrets, response bodies, headers, media
  paths, raw exception text, or credentials.

## 2. Operator UI

- Add read-only Schedules and Notifications navigation views to the existing same-origin UI.
- Schedule rows show safe definition/state fields and open a bounded occurrence-audit detail view.
- Notification rows show safe delivery ID, webhook ID, event type, status, attempts, timestamps,
  failure category, and numeric response status.
- Provide a local notification status selector and explicit refresh; no automatic polling.
- Render exclusively with DOM text nodes; retain CSP, no-store, same-origin, and in-memory token rules.

## 3. Authorization and safety

- Viewer/operator/executor/admin read permissions continue through existing RBAC; auditor behavior
  remains consistent with current route policy.
- Access remains covered by normalized security audit without query strings or response data.
- Construct no Storage, MetadataProvider, Scanner, workflow service, or OrganizerExecutor.
- Add no notification requeue/deliver, schedule tick/edit, Job submit/cancel/resume/retry, execution
  authorization, Overwrite, Delete, or arbitrary endpoint controls.

## Required tests

- Schedule list renders interval and Cron definitions with persisted state safely.
- Known schedule audit is bounded at repository/SQL level; unknown schedule is 404.
- Notification list is bounded and filters every supported status deterministically.
- Invalid limits/statuses and unknown/duplicate/injected query fields return safe 400 responses.
- UI contains Schedules/Notifications views, status filter, refresh, and bounded audit navigation.
- UI does not contain mutation endpoints or workflow/executor controls; values use `textContent`.
- Secrets, webhook URLs/bodies/signatures, raw errors, and query strings do not enter API/UI/audit.
- Empty datasets, viewer/RBAC/audit, Dashboard, pagination, review queues, Worker, Scheduler,
  Notification, and complete regressions pass.
- Formatter, lint, compile, dependency/build/configuration, FFprobe/FFmpeg, and diff checks pass.

## Documentation

Update README, requirements status, configuration, architecture, progress, and roadmap with the new
read-only views, bounded fields, refresh behavior, and remaining log/live-control limitations.

## Out of scope

Persistent application-log ingestion/search, notification payload/body viewing, delivery requeue or
manual send, schedule editing/ticking, arbitrary pagination/jumps/totals, live polling/SSE/WebSocket,
Task/Job controls, OIDC, Secret Store, and TLS termination.

## Final report

## Phase 19.6 Result

PASS / FAIL

## Scheduler Visibility

## Notification Visibility

## Operator UI

## Safety and Authorization

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
