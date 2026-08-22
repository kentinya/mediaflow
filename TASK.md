# Phase 18.9 — Persistent Metadata Review Queue

## Goal

Capture Metadata NeedConfirm/Ambiguous outcomes as durable, bounded, provider-neutral review records
for CLI/API and a future UI. This phase is review-queue creation and visibility only: it must not
select a candidate, fetch more metadata, resume a Task, or execute media operations.

## 1. Review domain and persistence

- Add immutable MetadataReview and MetadataReviewCandidate snapshot models plus a repository port.
- Persist review ID, Task/TaskItem identity, source Storage/path, RecognitionType, MetadataPolicy,
  query, reason/status, timestamps, and bounded candidate snapshots.
- Candidate snapshots may contain provider/provider ID, media type, title/original title, canonical
  and regional year, total score, matched provider title/source, and bounded score components.
- Do not persist provider DTOs, overview/images, alternative-title collections, HTTP data, cache
  internals, credentials, headers, cookies, tokens, or raw exceptions.
- Add a compatible SQLite v10 migration, deterministic ordering, bounded list methods, and a unique
  review per TaskItem.

## 2. Workflow integration

- When production Metadata returns NeedConfirm or Ambiguous with candidates, atomically persist the
  review/candidates and transition the TaskItem to `waiting_metadata`.
- Release the source lock after durable waiting state.
- Treat waiting metadata like waiting conflict for Task partial-success accounting and exclude it
  from blind retry.
- NotFound, provider errors, and malformed outcomes keep their current failure behavior.
- Do not change CandidateMatcher thresholds, ordering, score semantics, MetadataProvider behavior,
  RecognitionType, Naming, Classification, Planner, or Executor.

## 3. Read-only CLI and API

- Add `mediaflow metadata-reviews list [--limit N]` and `show REVIEW_ID`.
- Add authenticated read-only `GET /api/v1/metadata-reviews?limit=N` and
  `GET /api/v1/metadata-reviews/{id}`.
- Viewer/operator/executor/auditor/admin may read through the existing read permission.
- API routes use normalized Phase 18.6 security audit records.
- CLI/API output is bounded, deterministic, secret-free, and constructs no Storage/provider/network
  adapter.

## 4. Dashboard and safety

- Add pending metadata-review count to the existing Dashboard snapshot.
- A review does not authorize a candidate, change RecognitionType, create a Job, resume/retry a
  Task, or perform Storage mutation.
- Preserve conflict confirmation, one-time execute authorization, no-overwrite/delete, Scheduler,
  DryRun, and OrganizerExecutor boundaries.

## Required tests

- NeedConfirm and Ambiguous create durable reviews with correct bounded candidate/evidence snapshots.
- Matched/NotFound/provider-error outcomes do not create a review.
- Review creation, candidates, and TaskItem waiting transition are atomic; injected failure rolls
  back all state.
- One review per TaskItem and deterministic bounded candidate/list ordering.
- Restart persistence and SQLite v9-to-v10 migration.
- Task finish/retry semantics for waiting metadata and source-lock release.
- CLI/API list/show, limit validation, RBAC read matrix, 404, redaction, normalized security audit.
- Dashboard pending-review count.
- Zero Storage mutation/construction, zero provider/network calls during review reads, and no Job or
  execution creation.
- RecognitionType C remains C in stored review context.
- All Metadata/CandidateMatcher, API/RBAC, Dashboard, conflict, Task, DryRun, strategy,
  notification, Scanner/FileIndex, and Storage regressions.

## Documentation and validation

Update README, architecture, configuration where relevant, progress, roadmap, and product status.
Run all tests plus formatter, lint, compile, dependency, build, configuration, FFprobe/FFmpeg, and
diff checks.

## Out of scope

- Candidate selection/resolution, provider details fetch on selection, automatic resume/retry,
  classification correction, Web UI, remote Overwrite, database users/OIDC, scheduled execute,
  Rollback, and changes to CandidateMatcher thresholds or TMDB behavior.

## Final report

## Phase 18.9 Result

PASS / FAIL

## Metadata Review Queue

## Workflow Integration

## CLI and API

## Privacy and Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
