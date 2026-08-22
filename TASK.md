# Phase 19.23 — Isolated Real OpenList Acceptance Matrix

## Goal

Create a fail-closed, explicitly destructive opt-in acceptance suite for the
production OpenList adapter and Local↔OpenList/OpenList↔OpenList transfers.
Execute it only when a dedicated empty test root and explicit operator consent
are present. Missing prerequisites produce BLOCKED/NOT RUN, never PASS.

## Scope

### 1. Destructive acceptance gate

Require all of:

- `TEST_OPENLIST_URL`
- `TEST_OPENLIST_TOKEN`
- `TEST_OPENLIST_ROOT`
- `TEST_OPENLIST_DESTRUCTIVE_CONFIRM=DELETE_ONLY_GENERATED_MEDIAFLOW_ACCEPTANCE_DATA`

The root must be absolute, non-root, traversal-free, and have a final component
starting with `mediaflow-acceptance-`. There is no default root. Reject known
configured ResourceLibrary/MediaLibrary paths and never inspect user config to
infer consent.

### 2. Generated-run isolation and cleanup

- Create one cryptographically unique child under the approved test root.
- Mutate/delete only objects created under that child.
- Verify the child did not pre-exist.
- Always attempt bounded cleanup in `finally`.
- Cleanup failure fails acceptance and reports safe logical paths only.
- Never recursively delete unknown/pre-existing content.

### 3. Real OpenList matrix

Using production `OpenListStorage` and `OrganizerExecutor`, cover:

- health/list/stat/read/write
- no-overwrite conflict
- same-OpenList copy and move
- Local → OpenList COPY and MOVE
- OpenList → Local COPY and MOVE
- OpenList → OpenList Organizer COPY and MOVE
- source/destination size and content checks where readable
- MOVE source absence only after verified destination
- generated-object cleanup

Use small deterministic generated payloads; never media-library files.

### 4. Unit safety and fault coverage

- Unit-test every prerequisite rejection without network access.
- Existing fake OpenList timeout/rate-limit/connection/rename rollback tests
  remain UNIT PASS only.
- Add Organizer fake fault tests for the new real matrix directions if a
  direction lacks failure/source-preservation coverage.
- Do not change production OpenList behavior when acceptance discovers a defect;
  record it as FAIL for a separate repair phase.

### 5. Evidence and status

- Update `docs/storage-acceptance.md` with exact command, environment contract,
  date, and status.
- If prerequisites are absent, mark all real OpenList rows BLOCKED/NOT RUN.
- Do not claim Phase 19.23 PASS without actual isolated execution.
- Phase 19 overall remains BLOCKED until later SMB/S3 and duration gates finish.

## Boundaries

Do not modify Parser, Scanner, Recognition, Metadata, Naming, Classification,
Planner semantics, production OpenList adapter semantics, or UI/API. Do not use
`config/alist.json`. Do not add secrets to logs, reports, tests, or Git.

## Validation

Run OpenList/Organizer/Local focused unit tests, full tests, formatter, lint,
compile, dependency/configuration/FFmpeg audits, and isolated wheel validation.
Run the real suite only if every destructive prerequisite is present.

## Completion Report

Finish with:

## Phase 19.23 Result

PASS / BLOCKED / FAIL

## Destructive Gate

## Real OpenList Matrix

## Fault Injection

## Safety

## Regression

## Changed Files

## Remaining Work

## Risks

## Final Recommendation
