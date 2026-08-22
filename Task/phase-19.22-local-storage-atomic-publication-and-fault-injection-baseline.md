# Phase 19.22 — Local Storage Atomic Publication and Fault-Injection Baseline

## Goal

Correct the Phase 19 acceptance drift by implementing and validating the first
real Storage safety gate: atomic target visibility for LocalStorage write/copy,
failure cleanup, overwrite preservation, and Organizer cross-storage failure
semantics. Record remote real-storage matrix items as blocking and unverified
unless an isolated destructive test root is explicitly supplied.

## Scope

### 1. Production-readiness status correction

- Remove or qualify claims that Phase 19 or the project is production accepted.
- Publish one authoritative Storage acceptance matrix covering Local, SMB,
  OpenList, and S3/R2 plus same/cross-storage transfer directions.
- Distinguish unit/fake coverage, isolated real coverage, blocked, and failed.
- Never count fake transports or mock servers as real-storage acceptance.

### 2. LocalStorage atomic target visibility

- `write` and `copy` stage data in a unique same-directory temporary file.
- Publish only after the complete stage succeeds.
- Default no-overwrite publication must atomically fail if target exists.
- Explicit overwrite must atomically replace the target.
- Any source/read/copy/publish failure must preserve an existing target and
  remove only the operation-owned temporary file.
- Temporary names must not expose source media names unnecessarily and must not
  escape the configured Storage root.
- Do not claim power-loss durability or transactional source+target atomicity.

### 3. Fault injection

Add deterministic tests for:

- stream failure before publication
- copy failure after partial stage data
- target race during no-overwrite publication
- overwrite failure preserving original target
- publication failure cleanup
- no orphan operation-owned stage files
- source remains unchanged on write/copy failure
- Organizer cross-storage copy/write failure does not delete source
- cross-storage MOVE delete failure remains explicit PARTIAL with both copies
- size verification failure remains visible and never reported SUCCESS

### 4. Real acceptance evidence boundary

- Execute Local adapter tests against real temporary filesystem directories.
- Document exact isolated prerequisites for SMB, OpenList, and S3/R2 destructive
  acceptance: dedicated credentials, dedicated empty test root/bucket prefix,
  explicit operator confirmation, and permission to create/delete test data.
- Do not read or mutate configured media-library roots.
- Do not run against `config/alist.json` or any user Storage automatically.
- Remote matrices remain BLOCKED/NOT RUN in this phase unless those explicit
  prerequisites are provided.

### 5. Architecture boundaries

- Keep filesystem APIs inside LocalStorage infrastructure.
- Do not change Parser, Recognition, Metadata, Naming, Classification, Scanner,
  Task, Planner policy semantics, or remote Storage adapter behavior.
- OrganizerExecutor remains the only business-layer Storage mutation boundary.
- Preserve DryRun zero mutation and RecognitionType C behavior.

## Tests and quality gates

Run:

- focused LocalStorage atomic/fault tests
- Organizer execution/fault regressions
- all Local/SMB/OpenList/S3-R2 unit regressions
- DryRun and full project tests
- formatter, lint, compile, dependency check
- both canonical configuration validations
- FFmpeg/FFprobe audit
- isolated wheel build/smoke validation

## Documentation

Update README, requirements, architecture, progress, roadmap, release checklist,
and add an authoritative Storage acceptance matrix document.

## Out of Scope

- claiming SMB/OpenList/S3-R2 real acceptance without isolated endpoints
- automatic destructive acceptance against configured libraries
- remote adapter redesign
- distributed transactions or rollback
- power-loss/fsync durability certification
- UI, OIDC, scheduling, or recovery features

## Completion Report

Finish with:

## Phase 19.22 Result

PASS / FAIL

## Atomic Publication

## Fault Injection

## Storage Acceptance Matrix

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
