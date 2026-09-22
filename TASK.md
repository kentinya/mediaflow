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

The repository's active-Task release-quality policy also requires this exact command inventory to
remain documented in this file:

```text
python3 scripts/check_governance.py
scripts/docker_release_security_smoke_test.py
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall -q mediaflow tests scripts
```

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

Implementation and tests (commit `b085e90`):

- `web/src/entities/shared/normalize.ts` — added `normalizeIdentityText`, the identity-preserving
  bounded-string guard.
- `web/src/entities/library/storage-files.ts` — Files identity fields now use it: entry `name` and
  `path`, breadcrumb `name` and `path`, and the current model `path`.
- `web/src/features/library/StorageFilesPage.tsx` — edge-whitespace presentation helpers
  (`readEdgeWhitespace`, `identityAccessibleName`, `IdentityLabel`) applied to the directory tree,
  breadcrumb, table name cell, grid cell, selection checkbox and row-menu accessible labels.
- `web/src/shared/ui/styles.css` — `.mf-identity-label`, `.mf-ws-marker`, `.mf-ws-value` and the
  `.mf-visually-hidden` utility.
- `web/src/entities/library/storage-files.test.ts` — exact-identity normalization tests.
- `web/src/features/library/StorageFilesPage.test.tsx` — exact-path navigation test plus the
  not-found counterpart.
- `web/tests/fake-server.mjs` — opt-in `whitespace=1` session fixture.
- `web/tests/e2e/library-files.spec.ts` — focused browser regression and its counterpart.
- `TASK.md` — restored the release-quality command inventory required by the committed
  active-Task policy test.

Not changed: Python `Storage`/API/`FileIndex`/`OrganizerExecutor` code, Dockerfile, Compose,
deployment configuration, `ResourceLibrary` configuration or Active snapshot. No user media was
touched.

### Implemented

1. **Identity-preserving normalization boundary.** `normalizeIdentityText` keeps a required bounded
   server value byte for byte instead of trimming its end. `normalizeStorageFiles` uses it for every
   Files field that identifies or addresses a live Storage entry, so the real `name = "SSH "` stays
   `"SSH "` and `path = "电影/SSH "` stays `"电影/SSH "` through the model boundary. Empty and
   over-limit values remain malformed, and display-only normalization
   (`normalizeBoundedText`/`normalizeOptionalText`) is unchanged for unrelated projections.
2. **Unambiguous presentation of invisible boundary whitespace.** A name whose real characters begin
   or end with whitespace renders its server value verbatim plus one visible `␣` boundary marker per
   edge, with an explicit assistive description (`名称结尾包含空格`) that survives accessible-name
   computation — which itself trims raw whitespace and therefore cannot express the distinction on
   its own. Ordinary names render exactly as before, and the six-column composition is unchanged.
3. **Navigation keeps the exact path.** The tree, breadcrumb, grid, row-name and `打开` callbacks all
   pass the preserved model path, so opening the entry requests the exact encoded
   ResourceLibrary-relative path. No trimmed path, fallback, reconstructed label or alternate-path
   retry exists.

### Tests and Results

All commands run from `/root/mediaflow` (Web commands from `/root/mediaflow/web`).

| # | Task Required Test | Result |
|---|---|---|
| 1 | `python3 scripts/check_governance.py` | PASS — `governance check: PASS` |
| 2 | `npm run test -- --run src/entities/library/storage-files.test.ts src/features/library/StorageFilesPage.test.tsx` | PASS — 2 files, 56/56 (16 + 40) |
| 3 | `npm run test:e2e -- tests/e2e/library-files.spec.ts` | PASS — 34/34 passed (32 pre-existing + 2 new) |
| 4 | `npm run typecheck` | PASS |
| 5 | `npm run lint` | PASS — no output |
| 6 | `npm run format:check` | PASS — "All matched files use Prettier code style!" |
| 7 | `npm run test -- --run` | PASS — 33 files, 464/464 (was 460; +4 new) |
| 8 | `npm run build` | PASS — built in 526ms; pre-existing >500 kB chunk-size warning only |
| 9 | `git diff --check` | PASS — exit 0 |

Full browser regression and the release-quality inventory (the latter also mandated by committed
`TASK.md` policy and by `tests/test_release_security.py`):

| Command | Result |
|---|---|
| `npm run test:e2e` (full Playwright suite) | PASS — 122/122 passed (1.5m) |
| `scripts/docker_release_security_smoke_test.py` | PASS — "Release-security smoke acceptance passed." |
| `.venv/bin/ruff format --check .` | PASS — 309 files already formatted |
| `.venv/bin/ruff check .` | PASS — All checks passed! |
| `.venv/bin/python -m unittest discover -s tests` | PASS — Ran 1718 tests, OK (skipped=7) |
| `.venv/bin/python -m compileall -q mediaflow tests scripts` | PASS |
| `.venv/bin/python -m pytest -q` (full Python regression) | PASS — 1711 passed, 7 skipped, 1392 subtests passed |
| `mediaflow --config … config validate` (both CI example configs) | PASS |
| `pip check` | PASS — No broken requirements found |
| `test -z "$(grep -rn -i 'ffprobe\|ffmpeg' mediaflow pyproject.toml)"` | PASS — none found |
| `pip wheel . && scripts/wheel_smoke_test.py` | PASS — Status: PASS, schema 38 |

New regression coverage was verified to actually detect the defect rather than merely pass:
temporarily reverting `normalizeIdentityText` back to the trimming helper made the entity tests fail
(2 failed) and the Files interaction test fail (`Unable to find role="button" and name
"SSH（名称结尾包含空格）"`); the implementation was then restored and re-verified at 56/56.

Task 5 (full Web suite) and 7 baselines: the pre-Task full Web suite was 460/460 and the focused
Files suite was 32 tests; this Task adds 4 Vitest tests and 2 Playwright tests with no removals,
skips or weakened assertions.

### Decisions

- **Split the normalizer instead of weakening it.** The Task allowed either behaviour change at the
  shared helper or a focused split, conditional on a focused test proving the split is needed. The
  Files interaction test proves it: trimming is correct for display-only strings but wrong for a
  value that later addresses Storage, so `normalizeIdentityText` was added next to
  `normalizeBoundedText` and unrelated projections were left untouched.
- **Keep the server value verbatim in the DOM.** The visible `␣` markers are separate elements, so
  `textContent` of the value node is still exactly `SSH `. The label the operator reads therefore
  always corresponds to the path that will be requested.
- **Describe the whitespace explicitly for assistive technology.** Accessible-name computation trims
  and collapses raw whitespace, so a trailing space inside the label or `aria-label` is not
  observable on its own; the added description is what makes `SSH ` distinguishable from `SSH` for a
  screen-reader user. Ordinary labels are returned unchanged, keeping existing selectors working.
- **Make the fake server's trimmed path genuinely absent.** The fixture session is opt-in
  (`whitespace=1`) and returns a real `storage_browser_not_found` for `电影/SSH`, so the regression
  cannot pass merely because the fake answers every path with an empty listing.
- **Restore the release-quality inventory in `TASK.md`.** `SLICE.md` requires that inventory to remain
  present in the active `TASK.md`, and `tests/test_release_security.py` enforces it; A's Task-definition
  commit had dropped it, leaving the full Python suite red for a documentation reason unrelated to
  this Task's code. The inventory was restored verbatim and the suite is now green.

### Remaining In-Slice Work

- None known that belongs to this Task. Any further Files-scope correction is B's planning decision.

### Risks / Deviations

- **No pre-existing or unrelated failures remain.** The full Python suite is green (1718 tests, OK,
  skipped=7). Before restoring the `TASK.md` inventory it reported `1 failed` —
  `tests/test_release_security.py::…test_release_quality_gate_commands_are_documented_for_task_execution`
  — which was a Task-documentation gap introduced at HEAD (`351b4f8`), not caused by any
  implementation change and not a product defect; it is fixed rather than reclassified.
- **Docker gate available this time.** The earlier Closure Packet recorded the Docker release-security
  smoke as unavailable. In this session Docker was available and the harness passed end to end,
  including the V2 manual-Organize probe that previously blocked it. This is stronger evidence than
  before and no claim rests on the older unavailable status.
- **The Docker smoke harness needs a workspace-local `TMPDIR` in this sandbox** (the daemon does not
  share this container's `/tmp`); it was run as `TMPDIR=/root/mediaflow`, and the two temporary
  workspace directories it created were removed afterwards, leaving the worktree clean.
- **Scope note (not a deviation):** the presentation change is confined to the Files surface and
  makes boundary whitespace visible only when it exists, so ordinary rows, columns and existing
  assertions are behaviourally unchanged; the six-column composition is intact.
- `docs/pics/文件页.png` was already modified in the worktree before this Task began. It is
  pre-existing user work, is excluded from this checkpoint, and was left untouched and unstaged.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: b085e90ac9b3204c84e6f9b16a39cabbcec896bd
(the report itself is committed as the direct child of this implementation checkpoint)
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
