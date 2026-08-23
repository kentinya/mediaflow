# Phase 19.25 — Storage Endurance, Large Object, and Interrupted Transfer Acceptance

## Goal

Close the remaining Phase 19 runtime hard gate with reproducible production-adapter
evidence for sustained batches, streaming large objects, interrupted writes/transfers,
explicit retry, and final source/destination consistency on isolated Local, Samba,
OpenList, and MinIO services.

## Scope

### 1. Fail-closed endurance acceptance harness

- Add a separately gated real acceptance suite; it must never load runtime/user
  configuration or `config/alist.json`.
- Require explicit endpoints, dedicated credentials, new empty
  `mediaflow-acceptance-*` roots, the destructive confirmation phrase, and a new
  absolute non-overwriting report path for every enabled remote provider.
- Make batch count and large-object size explicit, bounded acceptance inputs.
- A missing real environment is `BLOCKED/NOT RUN`, never PASS.

### 2. Sustained batch and large-object matrix

- Exercise production Storage adapters and OrganizerExecutor, not fake transfer
  implementations.
- Cover Local, SMB, OpenList, and generic S3-compatible MinIO with a deterministic
  multi-file batch, bounded concurrency, exact item counts, byte sizes, and content
  verification.
- Stream at least one object large enough to cross the configured S3 multipart
  threshold without reading the whole object into memory.
- Record elapsed time as evidence, but do not introduce performance pass/fail claims
  tied to a particular host.

### 3. Interrupted transfer and explicit recovery

- Inject a deterministic source-stream failure during a real destination write or
  cross-storage COPY/MOVE for each provider without killing arbitrary host services.
- Verify the operation never reports success, MOVE retains the complete source, an
  incomplete target is never mistaken for a complete target, and owned multipart or
  stage artifacts are cleaned where the adapter promises that behavior.
- Retry only through a new explicit operation after inspecting state; verify the retry
  completes and produces exact content/size. Do not add automatic retry or rollback.
- Record any exposed partial target honestly. Do not repair a newly discovered adapter
  defect in this acceptance task; fail and create a later scoped repair task.

### 4. Evidence and cleanup

- Produce bounded, secret-free JSON evidence with profile inputs, adapter/version,
  planned/completed checks, durations, normalized failures, consistency assertions,
  and cleanup outcome.
- Cleanup only generated allowlisted objects beneath the approved empty root. Unknown
  objects stop cleanup and fail acceptance; recursive broad deletion is forbidden.
- Retain reports outside Git and destroy containers, credentials, buckets/shares,
  prefixes, temporary local data, and injected payloads after inspection.

### 5. Phase status

- Phase 19.25 PASS requires all four isolated provider profiles and their cleanup to
  pass. A provider defect is FAIL, not a skipped row.
- Phase 19 overall may become PASS only if the authoritative acceptance matrix has no
  remaining release-hard-gate row. AWS S3/R2 service-specific certification and
  power-loss durability may remain explicit deployment limitations rather than claims.

## Boundaries

Do not change Parser, Scanner, Recognition, Metadata, Naming, Classification,
policy behavior, API/UI, Scheduler, automatic retry, Rollback, Hash policy, or user
configuration. Only OrganizerExecutor may perform planned transfer mutations. Do not
use FFmpeg/FFprobe and do not begin Phase 20.

## Validation

Run acceptance-gate unit tests, focused Storage/Organizer/DryRun regressions, the full
offline suite, formatter, lint, compile, dependency/configuration checks,
FFmpeg/FFprobe audit, isolated wheel smoke, and explicitly gated isolated Local,
Samba, OpenList, and MinIO profiles.

## Completion Report

Finish with:

## Phase 19.25 Result

PASS / BLOCKED / FAIL

## Acceptance Profile

## Sustained Batch

## Large Objects

## Interrupted Transfers

## Recovery and Consistency

## Evidence

## Cleanup

## Safety

## Regression

## Changed Files

## Remaining Work

## Risks

## Final Recommendation
