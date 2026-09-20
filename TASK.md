# Task 37.7 — Formal Classification Library-Prefix Destination Parity

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.7
Parent Slice: 37
Status: PLANNED
Task Base: 1eb43931219b58d84216fe6d6a7b359c815b6503
Difficulty: High
Test Level: T4
Planner / Reviewer: B (delegated to A for this turn)
```

## Goal

Make the formal media-organization destination semantics identical to the local `strategy-test`
CLI: `ClassificationRule.result.library` is the first relative destination prefix, followed by
the rule's relative `path`, naming directory segments and naming filename.

For this rule:

```json
{
  "mediaLibraryId": "Test_Target",
  "library": "Movies",
  "path": ["其他电影"]
}
```

the formal Plan, Preview, precheck and execution target must contain:

```text
Movies/其他电影/<naming directory>/<naming filename>
```

`mediaLibraryId` remains the sole authority for resolving the configured MediaLibrary, Storage and
MediaLibrary root. `library` changes only the relative path composed beneath that root.

This advances Slice 37 outcomes RO-8 and RO-8C and closes the P1 mismatch recorded in the
reactivated Slice Contract.

## Why This Task Exists

The CLI currently constructs its plan with a temporary MediaLibrary whose root path is
`classification.library`, so it previews `Movies/其他电影/...`. The formal Organizer and
destination-preview paths currently compose only `classification.relative_path`, so the same
configuration produces `其他电影/...` beneath the configured MediaLibrary root. This violates the
operator's expectation that Preview and execution describe and perform the same target.

The defect crosses the shared destination-composition boundary and its callers. It must be fixed
as one coherent task so Organize Plan, configuration Destination Preview/precheck, manual and
automation projections, execution result evidence and local CLI behavior cannot drift again.

## Implementation Scope

Implement the correction across the shared formal target-path boundary:

- validate `ClassificationRule.library` as a bounded safe relative path prefix, with no absolute
  path, traversal component, backslash, empty component or NUL;
- compose `library/path/naming-directory/naming-filename` through one shared safe destination
  calculation;
- update Organizer planning and every formal destination Preview/precheck caller to pass the
  classification library prefix;
- keep `mediaLibraryId`-based MediaLibrary and Storage resolution unchanged;
- update bounded destination/result evidence where the composed path is surfaced so the operator
  can see the exact target and its contributing prefix;
- preserve the CLI's existing `Movies/...` behavior while making formal and CLI target results
  equal;
- add focused regression coverage for movie and TV-style paths, safe multi-segment prefixes,
  invalid prefixes, unresolved MediaLibrary behavior, DryRun zero mutation and execution target
  parity.

Production code, tests and only the directly necessary configuration/architecture guidance are in
scope. Files UI layout, direct file-management commands, metadata/provider behavior, RecognitionType
identity, Storage adapters, persistence schema and conflict/destructive-operation semantics are
frozen.

## Acceptance Criteria

- [ ] A configured `library = "Movies"` and `path = ["其他电影"]` produces
      `Movies/其他电影/...` in formal OrganizePlan output.
- [ ] Formal destination Preview, read-only destination precheck, manual/automation preview
      projections, execution and persisted/result evidence use the same composed target.
- [ ] The CLI and formal target calculations agree for the same resolved strategy input.
- [ ] `mediaLibraryId` still resolves the actual configured MediaLibrary and Storage root; changing
      `library` cannot select a different MediaLibrary or Storage.
- [ ] `library` is rejected fail-closed for absolute paths, traversal, backslashes, empty path
      components, NULs and other unsafe destination contributions before Storage mutation.
- [ ] DryRun/Preview and all analysis stages remain zero-mutation, and OrganizerExecutor remains
      the only Storage mutation boundary.
- [ ] Existing classification, naming, conflict, attachment, source-cleanup and recovery semantics
      remain unchanged apart from the intended destination-prefix correction.
- [ ] Focused tests cover success, invalid input, unresolved destination, path safety and parity;
      assigned T4 validation passes with actual evidence.
- [ ] The checkpoint contains only this Task and required evidence, preserving the pre-existing
      dirty reference image.

## Required Tests

Run and record:

```bash
python3 scripts/check_governance.py
.venv/bin/pytest -q tests/test_organizer.py tests/test_configuration_destination.py tests/test_strategy_cli.py
.venv/bin/pytest -q tests/test_classification.py tests/test_runtime_strategy_configuration.py tests/test_configuration_destination_activation.py
.venv/bin/ruff check mediaflow tests
.venv/bin/python -m compileall -q mediaflow
git diff --check
```

Before Task review, run the Slice-level relevant regression and safety gates:

```bash
.venv/bin/pytest -q
```

No production TMDB, SMB, OpenList, S3 or R2 service is required. Use fakes, temporary directories
and existing read-only Storage guards.

## Non-goals

- Reopening or redesigning the Files workspace, V2 shell or direct file-management journey.
- Changing `mediaLibraryId` resolution, MediaLibrary roots, Storage adapters or path authority.
- Adding classification conditions, providers, metadata fields or new policy types.
- Changing NamingPolicy output, conflict handling, attachment handling, cleanup or mutation policy.
- Replacing the local CLI or making CLI-only behavior a new operator journey.
- Broad documentation reconciliation, unrelated P2 cleanup or redesigning closed Slice outcomes.

## Developer Completion Report

### Changed Files

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [full SHA]
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING | PASS | FIX REQUIRED
Slice Required Outcomes all satisfied: PENDING | YES | NO
Next: PENDING | SAME TASK FIX LOOP | NEXT TASK | SLICE READY FOR A REVIEW
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
