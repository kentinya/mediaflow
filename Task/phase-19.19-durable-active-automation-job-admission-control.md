# Phase 19.19 — Durable Active Automation Job Admission Control

## Goal

Prevent authorized clients or schedules from building an unbounded Pending/Running AutomationJob
backlog. Enforce one configuration-driven active-Job capacity atomically in persistence without
starting workflows, changing media behavior, or weakening execution authorization.

## 1. Runtime policy

- Add `automation.maximumActiveJobs`, default 100, valid integer range 1–10000.
- Count only Pending and Running Jobs as active; Completed, Failed, and Cancelled release capacity.
- Apply the same capacity to manual scan/preview submission, Scheduler emission, and remote organize
  submission. Do not create separate hidden limits by command or transport.
- Configuration validation must construct no Storage/provider/workflow and must reject booleans,
  strings, zero, negatives, overflow, and unknown automation fields according to existing rules.

## 2. Atomic persistence admission

- Add an AutomationJobRepository admission operation that counts active rows and inserts the Job in one
  SQLite write transaction. Concurrent processes must never admit more than the configured capacity.
- Keep direct `create_job` only for migrations/tests/internal fixtures; every production submission path
  must use admission control.
- Queue-full failure creates no Job and returns a stable domain/application error without exposing Job
  IDs, commands, paths, credentials, database details, or counts beyond the configured capacity.
- Repository/audit failure creates no partial admitted Job beyond the existing audit-before-action rule.

## 3. Scheduler and remote execution

- Scheduler capacity failure must not advance occurrence state or append emission audit; a later tick may
  retry after capacity is released, preserving existing no-backfill semantics.
- Remote organize capacity failure must not consume/revoke the one-time execution authorization and must
  not create an execute-authorized Job.
- Preserve atomic one-time ticket consumption once capacity is available.

## 4. API/UI behavior

- Return HTTP 409 `queue_full` for capacity rejection; preserve 401/403/400 ordering and normalized audit.
- DryRun submission UI displays a clear bounded-queue error and does not optimistically add a Job.
- Add configured maximum active Jobs to the existing safe System snapshot as a numeric operational limit;
  do not expose current Job counts there or add polling.
- Add no queue purge, priority, force-admit, execute, retry, Scheduler, or Task controls.

## 5. Safety boundaries

- Admission performs SQLite state checks/writes only; construct no Storage, provider, Scanner, workflow,
  Planner, OrganizerExecutor, Notification worker, backup/restore, or migration service.
- Do not cancel or delete existing Jobs to make room.
- Preserve DryRun, one-time execute authorization, RecognitionType C, conflicts, and zero media mutation.

## Required tests

- Configuration default/custom/boundaries/invalid values and no Storage construction.
- Pending and Running consume capacity; Completed/Failed/Cancelled release it.
- Concurrent repository/service submissions never exceed capacity.
- Manual scan/preview queue-full returns 409 and creates no Job.
- Scheduler full leaves state/audit unchanged, then emits once after capacity release.
- Remote organize full preserves active ticket; later admission consumes it exactly once.
- Audit failure and repository failure preserve existing atomic behavior.
- System snapshot exposes only the configured numeric maximum and no Job records/counts/secrets.
- UI retains three-step DryRun flow, displays API error, and adds no bypass/force/purge controls.
- Existing submission/cancellation/API/UI/automation/scheduler/execution authorization/runtime/media
  regressions and all quality gates pass.

## Documentation

Update example configurations, README, requirements, architecture, progress, roadmap, and configuration/API
documentation.

## Out of scope

Per-principal quotas, rate limiting, Job priority, queue purge, automatic cancellation, Scheduler UI,
Task controls, distributed databases, organize UI, rollback, OIDC, TLS, and media workflow changes.

## Final report

## Phase 19.19 Result

PASS / FAIL

## Admission Policy

## Atomicity and Authorization

## API and UI

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
