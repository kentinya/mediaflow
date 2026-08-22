# Phase 18.7 — Operational Dashboard Read Model

## Goal

Provide a bounded, read-only operational snapshot for CLI, API, and a future Web UI by aggregating
existing persistent FileIndex, Task, Job, Confirmation, and Notification state. Do not implement a
Web UI and do not move workflow logic into the dashboard.

## 1. Dashboard model and query service

- Add provider-neutral immutable dashboard summary and recent-failure models.
- Count configured/enabled ResourceLibraries and MediaLibraries from normalized runtime
  configuration.
- Aggregate indexed media by scan status, Tasks and AutomationJobs by status, pending conflict
  confirmations, and notification dead letters from SQLite.
- Include only bounded recent failure identifiers, kind, status/category, and timestamp. Do not
  expose raw exception text, media paths, notification bodies, destination paths, or secrets.
- Generate one UTC `asOf` value and deterministic output.

## 2. Persistence read boundary

- Add an explicit dashboard read port and a SQLite implementation using aggregate SQL rather than
  loading entire large-library tables into memory.
- Treat a not-yet-created FileIndex table as an empty index without creating or mutating it during
  the query.
- Dashboard queries must not mutate database state and must not construct or call Storage,
  MetadataProvider, Scanner, strategy engines, Planner, OrganizerExecutor, notification transport,
  or network clients.
- Do not change schema version unless persistent schema actually changes.

## 3. CLI and API

- Add local `mediaflow dashboard [--recent-limit N]`.
- Add authenticated `GET /api/v1/dashboard` under existing read permission.
- Keep `GET /health` minimal and public; do not leak dashboard state through health.
- Validate recent limits with a small bound and return stable JSON through the existing API
  serialization boundary.
- All API dashboard access remains covered by the Phase 18.6 redacted security audit.

## 4. Safety and compatibility

- Preserve every Parser, Recognition, Metadata, Naming, Classification, Planner, Executor, Storage,
  Task, Scheduler, notification, RBAC, and one-time execution authorization behavior.
- Dashboard must remain useful when tables are empty and after restart.
- RecognitionType C invariants and DryRun zero-mutation guarantees remain unchanged.

## Required tests

- Empty database/config snapshot.
- Accurate indexed Ready/Missing and Task/Job/Confirmation/notification counts.
- Bounded deterministic recent failures with no raw errors, paths, bodies, credentials, or secrets.
- Large-library aggregation proves the service does not enumerate FileIndex records.
- Missing FileIndex table is read as zero without creating it.
- CLI rendering and API JSON; viewer can read, unauthenticated is 401, auditor/admin can read.
- Dashboard CLI/API construct no Storage and perform zero Storage mutations/network calls.
- API dashboard request produces a normalized redacted security audit record.
- Existing API/RBAC, Task, Scanner/FileIndex, notification, DryRun, strategy and Storage regressions.

## Documentation and validation

Update README, architecture, configuration where relevant, progress, roadmap, and product status.
Run all tests plus formatter, lint, compile, dependency, build, configuration, FFprobe/FFmpeg, and
diff checks.

## Out of scope

- HTML/JavaScript/Web UI, charts, live push/WebSocket/SSE, Storage health probing, database users,
  OIDC/OAuth, metric time-series retention, log search, policy editing, confirmation mutation,
  automatic remediation, and scheduled execute.

## Final report

## Phase 18.7 Result

PASS / FAIL

## Dashboard Model

## CLI and API

## Privacy and Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation

