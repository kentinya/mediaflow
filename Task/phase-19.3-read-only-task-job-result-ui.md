# Phase 19.3 — Read-only Task, Job, and Result Observability UI

## Goal

Extend the existing operator UI with bounded, read-only visibility into persistent Tasks,
Automation Jobs, TaskItems, and ResultRecords. Reuse existing persistence and API models; do not add
workflow control or execution authority.

## 1. Bounded observability API

- Add validated `limit` queries to Task and Job collections, bounded from 1 to 100.
- Add independently bounded `itemLimit` and `resultLimit` queries to Task detail.
- Execute limits in SQLite, fetching at most limit+1 to report deterministic truncation without
  loading an entire large Task into memory.
- Return explicit `limit`/truncation metadata while preserving existing item documents.
- Reject unknown, duplicate, non-integer, zero, negative, or excessive query fields.
- Keep viewer-readable RBAC and normalized security audit routes unchanged.

## 2. Operator UI

- Add read-only Tasks and Jobs navigation to the existing dependency-free UI.
- Show compact status, command, counters, authority mode, timestamps, and linked identifiers.
- Task detail shows bounded TaskItems and ResultRecords, including stage/status and destination
  outcome needed for diagnosis.
- Job detail shows its linked Task ID where available and permits navigation to that Task only.
- Display truncation clearly and let the operator refresh; do not implement polling/live push.
- Render all persisted values using safe text nodes and keep the bearer token memory-only.

## 3. Safety and privacy

- Do not add submit, cancel, retry, resume, execute, overwrite, delete, authorization, or scheduler
  controls to the UI.
- Reads perform no Storage/Provider/network operations and no persistence mutation other than the
  existing redacted API security audit.
- UI/API must not expose credentials, notification bodies, raw provider payloads, or new secret
  fields. Do not add arbitrary search/path queries.
- Preserve all strategy engines, Task execution semantics, review workflows, RBAC, one-time execute
  authorization, and OrganizerExecutor boundaries.

## Required tests

- Task/Job list default/custom limits, truncation, invalid and injected queries.
- Task detail independent item/result limits, SQL-level bounded reads, missing records, and stable
  ordering.
- UI Task/Job tabs, list/detail fields, Task link, truncation visibility, safe text rendering, and
  absence of workflow-control payloads.
- Viewer access and 401/403/security-audit compatibility.
- Read paths construct no Storage/MetadataProvider and execute zero media mutations.
- Existing API, credential, Dashboard, review UI, Task persistence, Worker, and full regressions.
- Full formatter, lint, compile, dependency/build/configuration and FFprobe audits.

## Documentation

Update README, requirements status, configuration, architecture, progress, and roadmap with the
read-only observability scope and limits.

## Out of scope

Task resume/retry/cancel, Job submit/cancel, real execution, execution authorization, Scheduler UI,
log streaming, WebSocket/SSE, arbitrary filtering/search, history export, Storage/policy editors,
OIDC, and TLS termination.

## Final report

## Phase 19.3 Result

PASS / FAIL

## Task and Job Visibility

## Bounded Reads

## Operator UI

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
