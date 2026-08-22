# Phase 18.11 — Classification Review Queue and Explicit Rule Selection

## Goal

Capture production `unclassified` outcomes as durable review records and let an authorized operator
select one configured ClassificationRule. The decision must be persistence-only and a later
explicit Task resume must revalidate the policy/rule before continuing to planning.

## 1. Review domain and persistence

- Add immutable ClassificationReview, bounded ClassificationReviewChoice, and decision-audit models
  plus a repository port.
- Persist Task/TaskItem/source identity, RecognitionType, ClassificationPolicy, normalized media
  identity summary, status/timestamps, and enabled configured rule choices.
- Choices contain only rule ID/name, MediaLibrary ID, safe relative path, priority, and description.
- Add `waiting_classification` TaskItem status and treat it as partial/waiting, not blind retry.
- Atomically create review/choices and transition processing item to waiting; release its source lock.
- Add compatible SQLite v12 schema, one review per TaskItem, bounded deterministic ordering.

## 2. Explicit resolution and recovery

- Resolve only a persisted choice rank; arbitrary MediaLibrary/path/rule injection is forbidden.
- Atomically mark one pending review resolved, append immutable audit, and change its TaskItem to
  `pending`. Concurrent or repeated resolution commits once; failures roll back all state.
- Selection itself creates no Task/Job and never resumes automatically.
- On later explicit `tasks resume TASK_ID`, re-run Parser/Recognition/Metadata/Naming normally.
- Verify RecognitionType and ClassificationPolicy still match, and verify the selected configured
  rule is still enabled with the same MediaLibrary and safe relative path.
- Apply that configured rule as an explicit manual ClassificationResult without changing
  ClassificationEngine matching semantics, then continue unchanged Planner/DryRun/Executor flow.
- RecognitionType C must remain C and execution authority cannot be widened.

## 3. CLI and API

- Add `mediaflow classification-reviews list [--limit N]`, `show REVIEW_ID`, and
  `resolve REVIEW_ID --choice-rank N [--actor ID] [--note TEXT]`.
- Add authenticated GET collection/detail and POST
  `/api/v1/classification-reviews/{id}/resolve` accepting exactly `choiceRank`.
- Add `resolve_classification_review` permission for operator/executor/admin; viewer/auditor are
  read-only. API actor always comes from the authenticated principal.
- Include pending classification-review count in Dashboard.
- Outputs are bounded, deterministic, redacted, and use normalized security-audit routes.

## 4. Safety and privacy

- Review creation/reads/resolution perform zero Storage mutation and resolution constructs no
  Storage/provider/network adapter.
- Resolution does not accept custom paths, library IDs, policy IDs, RecognitionTypes, execute
  flags, or actor identity from API clients.
- A configured rule is a destination classification choice only; Naming and Organizer remain
  unchanged and OrganizerExecutor remains the only mutation boundary.
- Preserve conflict confirmation, metadata review, one-time execute authorization, Scheduler,
  no-overwrite/delete, and DryRun boundaries.

## Required tests

- Unclassified creates a bounded review and waiting item; classified/error outcomes do not.
- Choices are enabled configured rules in deterministic priority/ID order and preserve safe paths.
- C review and resumed selection retain RecognitionType C while using ClassificationPolicy A.
- Valid resolution, invalid rank, missing/already-resolved review, and non-waiting item.
- Atomic creation/resolution rollback, concurrency, restart persistence, and SQLite v11-to-v12.
- Explicit resume uses only the still-compatible configured rule; stale type/policy/rule/path fails.
- CLI/API list/show/resolve, limits, RBAC, injected-field rejection, actor protection, redaction,
  normalized security audit, and Dashboard count.
- Resolution has zero Storage/provider/network calls and creates no Task/Job/execution.
- Resumed DryRun has zero Storage mutation and execute authority rules remain unchanged.
- All Classification, Metadata, strategy, Naming, Planner/Executor, Task, API/RBAC, Dashboard,
  conflict, notification, Scanner/FileIndex, Storage, and DryRun regressions.

## Documentation and validation

Update README, architecture, configuration where relevant, progress, roadmap, and product status.
Run all tests plus formatter, lint, compile, dependency, build, configuration, FFprobe/FFmpeg, and
diff checks.

## Out of scope

- Arbitrary destination/path editing, creating rules from the review UI/API, automatic resume/Job,
  changing ClassificationEngine matching behavior, metadata candidate editing, Web UI, remote
  Overwrite, database users/OIDC, scheduled execute, and Rollback.

## Final report

## Phase 18.11 Result

PASS / FAIL

## Classification Review Queue

## Explicit Rule Selection

## CLI and API

## Privacy and Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
