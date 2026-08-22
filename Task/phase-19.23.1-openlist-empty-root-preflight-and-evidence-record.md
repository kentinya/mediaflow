# Phase 19.23.1 — OpenList Empty-Root Preflight and Evidence Record

## Goal

Close the remaining safety and evidence gaps in the Phase 19.23 real OpenList
acceptance harness without advancing to Phase 19.24. Prove the explicitly
approved remote test root is empty before any mutation and produce one
non-secret, machine-readable acceptance record after an attempted real run.

## Scope

### 1. Fail-closed empty-root preflight

- Keep every Phase 19.23 URL/token/root/confirmation prerequisite.
- Before creating a run child, use production `OpenListStorage` read operations
  to prove the configured root exists, is a directory, and contains zero items.
- Any listed item, permission failure, or unreadable root blocks mutation and
  fails acceptance.
- Do not delete, rename, move, or otherwise prepare a non-empty root.

### 2. Explicit evidence destination

- Require `TEST_OPENLIST_REPORT` for an enabled real run.
- It must be an absolute, non-existing local `.json` file whose parent exists.
- Never overwrite a report and never derive its path from runtime/user config.
- Publish the completed report without exposing a partial target.

### 3. Safe acceptance record

Record only bounded, non-secret evidence:

- schema/version and UTC start/end time
- suite/result (`PASS` or `FAIL`)
- production adapter and package version
- approved test-root identifier, never URL/token/header
- planned operation names and completed operation names
- empty-root preflight result
- cleanup attempted/result
- normalized error category without raw remote response or secrets

The report is evidence of an attempted run, not an automatic claim that all of
Phase 19 is accepted.

### 4. Unit coverage

- Test report-path prerequisite rejection without network.
- Test empty, non-empty, unreadable, and non-directory root preflight.
- Test report redaction, no-overwrite publication, PASS and FAIL records.
- Confirm every rejected preflight performs zero Storage mutations.

### 5. Status

- Execute the real matrix only when all five prerequisites exist.
- If they are absent, retain `BLOCKED / NOT RUN`; do not use `config/alist.json`.
- Do not begin SMB/S3/R2 acceptance or alter production adapters in this task.

## Boundaries

Do not modify Parser, Scanner, Recognition, Metadata, Naming, Classification,
Planner, OrganizerExecutor, production Storage semantics, UI, API, or user
configuration. Generated report writing is limited to the operator-selected
new local evidence file.

## Validation

Run focused OpenList acceptance/gate tests, all Storage and Organizer
regressions, the full offline suite, formatter, lint, compile, dependency and
configuration checks, FFmpeg/FFprobe audit, and isolated wheel smoke. Run real
OpenList only when every prerequisite is explicitly supplied.

## Completion Report

Finish with:

## Phase 19.23.1 Result

PASS / BLOCKED / FAIL

## Empty-Root Preflight

## Evidence Record

## Safety

## Regression

## Changed Files

## Remaining Work

## Risks

## Final Recommendation
