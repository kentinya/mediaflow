# Phase 19.17 — Explicit Automation Job Cancellation UI

## Goal

Expose the already-implemented cooperative AutomationJob cancellation through the authenticated
operator UI with an explicit two-step confirmation. Do not add job submission, Task control,
resume/retry, remote execution, or media mutation behavior.

## 1. Existing cancellation boundary

- Reuse `POST /api/v1/jobs/{id}/cancel`, `AutomationJobService.cancel`, existing
  `CANCEL_JOB` permission, persistence transitions, worker cancellation observation, and security audit.
- Do not duplicate cancellation semantics in JavaScript or add a second endpoint.
- Pending jobs become cancelled; running jobs record a cooperative cancellation request; terminal jobs
  remain rejected by the existing application service.

## 2. Operator UI control

- Show cancellation only in AutomationJob detail for `pending` or `running` jobs.
- Use two distinct user actions: `Request cancellation`, then `Confirm cancellation` or `Keep job`.
- Explain that running cancellation is cooperative, an in-flight operation may finish, completed work is
  not rolled back, and no new media execution authority is granted.
- After success, reload the job detail and Jobs list; render errors through existing text-node-only UI.
- Do not use browser-native implicit confirmation, automatic requests, polling, or optimistic status.

## 3. Authorization and transport safety

- Viewer/Auditor READ-only credentials may inspect jobs but cancellation remains forbidden by API RBAC.
- Operator/Executor/Admin permissions retain existing cancellation authority.
- Send an empty POST body with no actor, status, command, task, path, execute flag, or arbitrary fields.
- Normalize audit routes as already implemented and never expose tokens, source paths, errors, or secrets.

## 4. Safety boundaries

- Construct no Storage, MetadataProvider, Scanner, strategy pipeline, Planner, OrganizerExecutor,
  Scheduler, Notification worker, backup/restore, preflight, or migration service for UI/API cancellation.
- Cancellation never grants execute authority, never resumes/retries a Task, and never rolls back or deletes
  completed media operations.
- Preserve default DryRun, explicit execution authorization, conflict protection, and RecognitionType C.

## Required tests

- Pending Job two-step UI control and successful cancellation refresh.
- Running Job cooperative cancellation request and explanatory warning.
- Completed/failed/cancelled jobs expose no cancellation control.
- `Keep job` performs no request and restores the detail state.
- Viewer gets 403; Operator succeeds; malformed method/path/query/body cannot bypass the existing endpoint.
- One click cannot cancel; rendering remains text-node-only with no inline handlers or token persistence.
- No submit/resume/retry/execute/overwrite controls are introduced.
- API/UI cancellation constructs no media services and performs zero Storage mutations.
- Existing API/UI/automation/worker/security/runtime/media regressions and all quality gates pass.

## Documentation

Update README, requirements, architecture, progress, roadmap, and operator/API documentation.

## Out of scope

Job submission UI, Task pause/resume/retry/cancel, forced interruption, rollback, Scheduler controls,
notification controls, remote execute UI, configuration editing, OIDC, TLS, and media organization changes.

## Final report

## Phase 19.17 Result

PASS / FAIL

## Cancellation Flow

## Authorization and Audit

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
