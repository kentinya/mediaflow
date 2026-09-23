# Task 38.3 — 完成 MediaLibrary 有界直接文件维护

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 38.3
Parent Slice: 38
Status: PLANNED
Task Base: fabdb35373038ef36dd8b558688b2bce53ddcc89
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An authorized operator can perform the bounded, ordinary maintenance actions supported by the
MediaLibrary Files page: create a folder, create a supported text file, rename one entry, open and
save supported text, and delete selected entries. Every action is scoped to the exact enabled
MediaLibrary in the current Active configuration, uses the existing safe direct-file execution
boundary, reports durable per-item outcomes, and provides a Web recovery path. This advances Slice
38 RO-5 and the MediaLibrary mutation portion of RO-7 while preserving the completed browse and
configuration journeys from Tasks 38.1 and 38.2.

## Why This Task Exists

Task 38.1 delivered a live, read-only MediaLibrary browser and Task 38.2 delivered page-local
MediaLibrary configuration. The page still cannot maintain the files that an operator sees, so the
main ordinary MediaLibrary journey stops after inspection. The repository already has bounded
ResourceLibrary direct-file admission, evidence, OrganizerExecutor mutation, task/result and Web
dialog patterns; the next coherent unit is to extend those mechanisms with an independent
MediaLibrary authority rather than duplicate or relabel ResourceLibrary IDs.

This Task is intentionally limited to the non-transfer direct commands. Copy/Move between
MediaLibraries needs its own cross-endpoint resolution, verification, durable transfer and Worker
recovery review; it is not required to make this Task independently useful and remains a later
Task.

## Implementation Scope

```text
Domain / direct-command application
  → MediaLibrary-scoped persistence and exact-Active admission
  → API
  → Web client, dialogs and page actions
  → focused, integration and browser tests
```

- Extend the existing direct-file command boundary so Create Folder, Create supported Text File,
  single-item Rename, bounded supported-text Open/Edit/Save and Delete resolve an enabled
  MediaLibrary from the exact immutable Active snapshot. Client-supplied Storage IDs, host roots
  and arbitrary paths are never runtime authority.
- Add MediaLibrary-scoped API surfaces matching the existing direct-command behavior for:
  command admission/execution, text read/save, delete impact and rename evidence. Use the
  `/api/v1/media-libraries/{id}/files/...` namespace and preserve ResourceLibrary route and
  response compatibility. Enforce the same authenticated permissions, path confinement, provider
  capability checks, entry type/size limits, current-version evidence and conflict rules in API and
  Web.
- Route every Storage mutation through `OrganizerExecutor`. Reads, impact/evidence calculation,
  text opening and configuration lookup remain zero-mutation and do not invoke Scanner, Parser,
  Recognition, Metadata, Naming, Classification or media Organize.
- Preserve direct-command safety semantics: no silent overwrite/delete, explicit Delete
  confirmation, no batch Rename, supported text extensions only, bounded text size, no arbitrary
  binary/image/video editing, no implicit capability fallback, and no automatic replay after an
  uncertain transport or mutation result.
- Record and expose bounded per-item outcomes and known effects using the existing direct-command
  task/result model. Completed, failed, partial and uncertain outcomes remain independently
  inspectable; refresh reconciles the live MediaLibrary listing without treating FileIndex or
  Result history as physical-file authority.
- Add MediaLibrary action controls to the existing Files page and reuse the established dialog
  interaction patterns. The normal page remains read-only until an explicit command is chosen;
  inputs stay available after correctable failures, pending controls prevent duplicate submission,
  Escape/Cancel do not imply rollback, and focus/usable narrow-screen behavior remain intact.
- Keep the selected MediaLibrary and exact library-relative path bound through command admission,
  evidence, execution and refresh. Same-ID ResourceLibrary requests, stale Active/configuration
  revisions, escaped/aliased paths, unavailable or disabled Storage and unsupported capabilities
  must fail closed with secret-free, action-oriented recovery.
- Preserve Task 38.1/38.2 behavior, the complete ResourceLibrary Files command journey and
  Organize routes. Do not modify the user's dirty `docs/pics/文件页.png`, the canonical
  `docs/pics/媒体库页.png`, `config/alist.json` or credentials.

## Acceptance Criteria

- [ ] An authorized operator can complete Create Folder, Create supported Text File, single-item
      Rename, supported text Open/Edit/Save and Delete from `/ui-v2/medialib/files`; the page shows
      the affected MediaLibrary-relative location, closes or reconciles only after a known result,
      and retains correctable input after a recoverable failure.
- [ ] MediaLibrary API and Web use the same application behavior and permissions for command
      admission, text access, delete impact and rename evidence. ResourceLibrary endpoints and
      behavior remain compatible, and equal IDs cannot exchange authority.
- [ ] Every mutation is executed only by `OrganizerExecutor`; analysis, browse, text read, impact,
      evidence, denied requests, invalid paths and failed admission perform zero Storage mutation
      and start no media pipeline work.
- [ ] The backend resolves the exact enabled MediaLibrary and its enabled Storage from the current
      Active snapshot, confines every source/target to the configured MediaLibrary root, rejects
      traversal, symlink/alias escapes, wrong entry types, stale version evidence, conflicts,
      unsupported capabilities and disabled/unavailable bindings without silently falling back.
- [ ] Delete is explicit and bounded; text Save is an explicit replacement intent; Rename is
      single-item and evidence-bound; supported text type/size and provider limits are enforced
      honestly in both API and Web. No arbitrary binary/media/image editing or silent overwrite is
      introduced.
- [ ] Durable command/task/result projections preserve independent success, failure, partial and
      uncertain per-item outcomes, known effects and safe next actions. Uncertain mutation is never
      replayed automatically, and a fresh live listing can reconcile a known successful result.
- [ ] Focused, affected regression, T4 quality gates and MediaLibrary desktop/narrow browser
      journeys pass with actual totals, skips and unavailable gates reported. The checkpoint is
      limited to this Task, contains no credentials or forbidden files, and does not weaken or
      delete existing tests.

## Required Tests

Run from the repository root unless a `web/` prefix is shown. Use local fakes and temporary
Storage only; never use production services, credentials or user media.

- `python3 scripts/check_governance.py`
- Add and run focused Python tests for MediaLibrary direct command resolution, exact Active/library
  and path authority, all command success/failure/conflict/capability cases, zero-mutation
  analysis, stale evidence, uncertain outcomes and ResourceLibrary compatibility.
- `.venv/bin/python -m unittest discover -s tests -p 'test_direct_file_operations.py'`
- `.venv/bin/python -m unittest discover -s tests -p 'test_direct_file_transfers.py'`
- `.venv/bin/python -m unittest discover -s tests -p 'test_api_security.py'`
- `.venv/bin/python -m unittest discover -s tests`
- Add and run focused frontend model/API/dialog/page tests for MediaLibrary commands, malformed
  responses, permissions, retained input, explicit confirmation, no automatic replay and per-item
  result reconciliation.
- `npm --prefix web run test -- --run`
- `npm --prefix web run test:e2e -- tests/e2e/medialib-files.spec.ts tests/e2e/medialib-commands.spec.ts`
  including desktop and supported narrow viewport success, denied, conflict and recovery journeys.
- `npm --prefix web run typecheck`
- `npm --prefix web run lint`
- `npm --prefix web run format:check`
- `npm --prefix web run build`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/python -m compileall -q mediaflow tests scripts`
- `.venv/bin/python -m pip check`
- `.venv/bin/mediaflow --config config/strategy.example.json config validate`
- `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`
- Confirm the FFmpeg/FFprobe exclusion with the repository-available grep command.
- `TMPDIR=/root/mediaflow/.smoke-tmp .venv/bin/python scripts/docker_release_security_smoke_test.py`
- Inspect `git diff --check`, the complete Task Base..Head manifest, private files and both
  reference images. Preserve the pre-existing dirty Files image.

## Non-goals

- MediaLibrary Copy/Move or cross-MediaLibrary transfer admission, cross-Storage
  Copy→verify→Delete-source semantics, durable transfer Worker reconstruction, Operations revisit
  or transfer-specific recovery. These require the next transfer/recovery Task.
- MediaLibrary Organize, Scan, Preview, recognition, metadata lookup, naming, classification,
  thumbnails, stream inspection, full-library statistics, Upload/Download or arbitrary binary,
  image or video editing.
- Batch Rename, unbounded recursion/global search, automatic directory-creation policy changes,
  silent overwrite/delete, implicit operation fallback or automatic replay of uncertain mutation.
- New Storage providers, broad configuration migration, identity-system changes, V1 cutover,
  shared shell redesign, changes to ResourceLibrary semantics, or changes to the A-owned Slice
  Contract/Roadmap.
- Controlled Slice screenshots, remaining RO-6/RO-7/RO-8 integration closure and Slice Final.

## Developer Completion Report

### Changed Files

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: IN PROGRESS
Head SHA: NOT SET
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
