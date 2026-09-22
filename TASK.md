# Task 37.10 — Files Exact Path Identity and Whitespace Presentation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.10
Parent Slice: 37
Status: PLANNED
Task Base: 3e15ab35f3ebb7e76cb278fb5004726ad5b7aebb
Difficulty: Medium
Test Level: T2
Planner / Reviewer: A (acting in B task-planning capacity at the user's request)
```

## Goal

Restore exact Storage-relative path identity in the Files Web journey. A live directory or file name
containing leading/trailing whitespace must remain the same identity after API normalization, render
and navigation; the operator must be able to distinguish such whitespace in the Files presentation
and successfully open the exact live path. This advances Slice 37 Required Outcomes RO-3, RO-5,
RO-9 and RO-11.

## Why This Task Exists

The deployed stack at `/opt/mediaflow` mounts host Storage `/mnt/HDD_2` at container `/media`.
The live ResourceLibrary Files API returns the real directory as `name = "SSH "` and
`path = "电影/SSH "`. The shared Web normalizer in
`web/src/entities/shared/normalize.ts` applies `trimEnd()` to API-derived strings. The
ResourceLibrary Files projection therefore turns the exact API path into `电影/SSH`, while the
browser also visually collapses the trailing space in the label. Clicking the apparent `SSH`
directory sends a request for a different path and receives `Storage directory was not found`.

This is a current production-reachable P1 failure in the ordinary Files browse journey, not a
stale FileIndex record and not a reason to mutate the user-owned test directory. The largest
reasonable correction is one Web projection boundary with focused normalization, interaction and
regression coverage. Backend Storage listing and API response are already truthful and must remain
unchanged.

## User Journey

```text
Goal:
  Browse and open the exact live Storage entry selected in Files.
Entry:
  V2 Files at /ui-v2/library/files with an enabled ResourceLibrary.
Visible state:
  The live entry name/path, including any leading/trailing whitespace that affects identity, is
  presented unambiguously; ordinary names retain their existing appearance.
Action:
  The operator opens the directory or selects the file from the Files listing.
Success:
  The request uses the exact encoded ResourceLibrary-relative path and the live directory/file
  opens without a false not-found result.
Failure:
  A genuinely missing or inaccessible path keeps the existing bounded Files error and recovery
  behavior; no fallback path, trim-based retry or fabricated entry is used.
Recovery:
  The operator can refresh or return to the ResourceLibrary root. No FileIndex read, scan,
  organize intent, Storage mutation or automatic replay is introduced.
```

## Implementation Scope

- Update the Web normalization boundary so Files identity fields preserve the exact server value:
  entry `name`, entry `path`, breadcrumb `name`/`path` and the current Files model path. Do not
  silently trim leading/trailing whitespace from a value used to address Storage.
- Keep unrelated display-only normalization behavior stable unless a focused test proves that the
  shared helper must be split into identity-preserving and display-normalizing variants.
- Update the Files presentation so leading/trailing whitespace is visually and/or accessibly
  unambiguous to the operator while normal names remain unchanged. The navigation callback must
  receive the exact preserved path, not a separately reconstructed or trimmed label.
- Add focused normalization/entity tests and Files interaction tests proving that `SSH ` and
  `电影/SSH ` survive the model boundary and that opening the entry requests the encoded exact
  path.
- Extend the focused Files Playwright/fake-server coverage with a directory whose exact name has
  a trailing space. Assert the visible/accessible distinction, successful navigation, and absence
  of a false not-found state.
- Keep the change limited to Web Files projection/presentation and tests. Do not edit Python
  Storage/API/FileIndex/OrganizerExecutor code, Dockerfile, Compose, deployment configuration or
  the user's test residual directory.

## Acceptance Criteria

- [ ] Files normalization preserves exact leading/trailing whitespace for all path/name fields used
      to identify or navigate a live ResourceLibrary entry; `name: "SSH "` remains `"SSH "` and
      `path: "电影/SSH "` remains `"电影/SSH "`.
- [ ] Clicking the rendered whitespace-bearing directory issues the existing bounded authenticated
      GET for the exact encoded path and successfully opens the live directory; it never retries
      a trimmed path or reports a false `not_found`.
- [ ] The Files visible/accessible presentation makes leading/trailing whitespace unambiguous to
      the operator while ordinary names and the current six-column composition remain unchanged.
- [ ] A genuinely missing, malformed, unauthorized or unavailable path retains the existing
      bounded error and recovery state without fabricated rows or automatic alternate-path retry.
- [ ] The fix does not consult FileIndex, start Scan/Preview/Organize, mutate Storage or alter
      backend/API/Storage contracts; refresh remains the existing live GET-only operation.
- [ ] Existing Files navigation, refresh reconciliation, selection, pagination, direct commands,
      Organize continuation and non-Files V2 routes remain behaviorally compatible.
- [ ] Focused normalization, Files component, browser and Web quality checks pass with actual
      evidence.
- [ ] The checkpoint contains only Task 37.10 implementation/tests and required documentation;
      `/mnt/HDD_2/Test_Source/电影/SSH ` and all other user media remain untouched.

## Required Tests

Run from the development repository `/root/mediaflow` unless noted otherwise:

1. `python3 scripts/check_governance.py`
2. `cd web && npm run test -- --run src/entities/library/storage-files.test.ts src/features/library/StorageFilesPage.test.tsx`
3. `cd web && npm run test:e2e -- tests/e2e/library-files.spec.ts`
4. `cd web && npm run typecheck`
5. `cd web && npm run lint`
6. `cd web && npm run format:check`
7. `cd web && npm run test -- --run`
8. `cd web && npm run build`
9. `git diff --check`

No production Storage, FileIndex, TMDB, SMB, OpenList, S3/R2 service or user media mutation is
required. The test fixture must represent a trailing-space entry in memory/fake server data; do not
use or rename the real `/mnt/HDD_2/Test_Source/电影/SSH ` directory.

## Non-goals

- Deleting, renaming, moving, or otherwise cleaning the user-owned test residual directory.
- Changing the Local Storage provider, Storage path validation, backend Files API serialization,
  ResourceLibrary configuration, Active snapshot or Docker/Compose mounts.
- Rewriting all shared text normalization semantics or changing unrelated API/domain projections.
- Adding a path cache, FileIndex synchronization, scan, metadata lookup, organize workflow or
  Storage mutation.
- Redesigning the Files shell, table composition, direct file commands or non-Files routes.
- The next Task, Slice closure, Roadmap change or any new product capability.

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
