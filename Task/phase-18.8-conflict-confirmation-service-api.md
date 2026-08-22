# Phase 18.8 — Conflict Confirmation Service API

## Goal

Expose the existing persistent target-conflict confirmation workflow through a least-privilege,
audited service API for future UI clients. Keep resolution as a database decision only: it must
never execute media operations, and remote Overwrite remains forbidden.

## 1. Authorization

- Add an explicit `resolve_confirmation` API permission.
- operator, executor, and admin may resolve ordinary confirmations; viewer and auditor remain
  read-only.
- Existing read permission continues to protect confirmation list/show/audit routes.
- Authentication and authorization failures remain stable 401/403 and use the redacted security
  audit.

## 2. Read API

- Keep `GET /api/v1/confirmations`, but add bounded `status=pending|resolved|all` and `limit`
  query parameters with deterministic ordering.
- Add `GET /api/v1/confirmations/{id}`.
- Add `GET /api/v1/confirmations/{id}/audit`.
- Return normalized confirmation/decision records only. Never return Task error text, credentials,
  headers, cookies, execution tokens, or unrelated media state.
- Unknown query fields, invalid values, and unknown IDs fail clearly.

## 3. Resolution API and atomic state transition

- Add `POST /api/v1/confirmations/{id}/resolve`.
- Accept only `skip` and `rename` remotely. `manual` is not a decision and `overwrite` remains
  local CLI-only even for admin.
- Derive the actor from the authenticated principal. Reject client-supplied actor, overwrite flags,
  proposed destination paths, execute fields, tokens, and unsupported fields.
- Atomically persist confirmation resolution, immutable decision audit, and the related TaskItem
  transition: Skip -> skipped; Rename -> pending for explicit retry/resume.
- Concurrent resolution attempts may succeed once only.
- Resolution never automatically retries/resumes a Task, queues a Job, or executes a plan.

## 4. CLI compatibility and safety

- Preserve existing local `mediaflow confirmations` behavior, including explicit high-risk
  overwrite confirmation.
- Move the existing CLI TaskItem transition into the shared atomic application/persistence path so
  CLI and API cannot diverge.
- Do not construct Storage, MetadataProvider, Scanner, Planner, OrganizerExecutor, or network
  clients for any confirmation API operation.
- Preserve one-time remote execution authorization, no-overwrite defaults, DryRun, and all strategy
  semantics.

## Required tests

- Viewer/auditor read access; operator/executor/admin resolve access; 401/403 matrix.
- Bounded pending/resolved/all list, deterministic ordering, show, audit, invalid query and 404.
- Remote Skip and Rename update confirmation, audit, and TaskItem atomically.
- Remote Manual/Overwrite and injected actor/path/execute/token fields are rejected for every role.
- Concurrent double resolution produces exactly one decision.
- Persistence failure rolls back confirmation, audit, and TaskItem together.
- Existing local overwrite flow remains explicit and compatible.
- Confirmation API security-audit routes are normalized and contain no body/query/token values.
- Zero Storage mutation/construction and no automatic retry/Job creation.
- All API/RBAC, Dashboard, conflict, Task, DryRun, strategy, notification, and Storage regressions.

## Documentation and validation

Update README, architecture, configuration where relevant, progress, roadmap, and product status.
Run all tests plus formatter, lint, compile, dependency, build, configuration, FFprobe/FFmpeg, and
diff checks.

## Out of scope

- Remote Overwrite/Delete approval, automatic retry/resume, metadata candidate confirmation,
  classification correction, arbitrary destination editing, Web UI, database users/OIDC, scheduled
  execute, Rollback, and OrganizerExecutor changes.

## Final report

## Phase 18.8 Result

PASS / FAIL

## Confirmation API

## Atomic Decisions

## Authorization and Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
