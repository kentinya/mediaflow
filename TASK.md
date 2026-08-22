# Phase 19.18 — Explicit DryRun Automation Job Submission UI

## Goal

Expose the existing `scan` and `preview` AutomationJob submission boundary through the authenticated
operator UI with review-before-submit. Preserve DryRun and do not expose organize, execute authority,
Scheduler changes, Task control, or Storage mutation.

## 1. Existing submission boundary

- Reuse `POST /api/v1/jobs`, `AutomationJobService.submit`, `SUBMIT_DRY_RUN`, durable queueing, Worker,
  security audit, and existing Job list/detail/cancellation UI.
- Do not duplicate command/limit validation or workflow behavior in the UI.
- Only `scan` and `preview` are valid; both remain non-executing workflows.

## 2. Strict DryRun transport

- For scan/preview, accept exactly `command` and optional `limit`; reject queries, unknown fields,
  booleans/non-integers, zero/negative/out-of-range limits, execute/organize/overwrite/delete/path/task/
  actor/schedule fields, and malformed JSON before queue creation.
- Define and enforce a conservative maximum UI/API limit consistent with batch safety.
- Preserve the separately gated remote-organize branch without exposing it in this UI.
- A failed security-audit write or repository insert must create no partial Job.

## 3. Operator UI

- Add `Queue DryRun job` to the Jobs view for authenticated users; API RBAC remains authoritative.
- Provide only command choices `scan` and `preview`, plus an optional bounded positive integer limit.
- Require three explicit steps: open form, review an immutable summary, confirm queueing; Back/Keep
  performs no request.
- Display `DRY_RUN`, no media mutation, no execution authorization, and that scan/preview may read
  configured Storage/provider resources.
- After a successful 202 response, reload the first Jobs page and open the created Job detail.
- Use DOM text nodes and event listeners only; no inline handlers, native implicit confirm, polling,
  token persistence, optimistic Job IDs/status, or arbitrary request fields.

## 4. Authorization and safety

- Viewer/Auditor may view the form but receive 403 if they attempt submission; Operator/Executor/Admin
  retain existing `SUBMIT_DRY_RUN` authority.
- UI must never send `execute`, an execution token/header, `organize`, overwrite/delete, path, Task,
  actor, policy, Storage, or Scheduler fields.
- Submission itself constructs no Storage/provider/workflow/Executor; only a later Worker processes the
  durable Job under existing boundaries.
- Preserve RecognitionType C, conflict rules, one-time remote execution authorization, and zero mutation
  for DryRun.

## Required tests

- Scan and preview submission with omitted and bounded limit.
- Three-step UI flow; Back/Keep performs no request; success refreshes first page and opens Job detail.
- Viewer 403 and Operator success; audit route contains no body/query/command/limit.
- Unknown fields/query, malformed JSON, invalid limits, organize, execute, path, Task, actor, policy,
  Storage, Scheduler, overwrite, and delete inputs create zero Jobs.
- Remote organize API behavior remains separately gated and unchanged.
- UI contains only scan/preview choices and never emits execute authority/header or organization controls.
- Submission API constructs no Storage/provider/Scanner/workflow/Planner/Executor and performs zero
  media mutations before Worker processing.
- Existing cancellation, API/UI, automation/worker/security/runtime/media regressions and quality gates pass.

## Documentation

Update README, requirements, architecture, progress, roadmap, and operator/API documentation.

## Out of scope

Organize/execute UI, Task submission/control/resume/retry, Scheduler/Notification controls,
configuration editing, live progress/polling, forced cancellation, rollback, OIDC, and TLS.

## Final report

## Phase 19.18 Result

PASS / FAIL

## Submission Flow

## Authorization and Validation

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
