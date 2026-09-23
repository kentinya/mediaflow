# Task 38.2 — 完成 MediaLibrary 添加、激活与安全移除

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 38.2
Parent Slice: 38
Status: PLANNED
Task Base: 6419ae1bb2e505c6128029bfddd32d90130f81ee
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An authorized operator can add a MediaLibrary from the MediaLibrary page, publish it only through
the exact checked Active-configuration boundary, and remove an unreferenced MediaLibrary
configuration without touching its files. This completes Slice 38 RO-4 and the Add drawer portion
of RO-2 while preserving the read journey delivered by Task 38.1.

## Why This Task Exists

Task 38.1 made enabled MediaLibraries browseable but deliberately exposed no Add or removal control.
The ordinary journey still falls back to general configuration knowledge, and the current
ResourceLibrary-focused save/removal APIs cannot be reused by relabelling IDs: MediaLibrary has its
own configuration section, destination-root checks and ClassificationPolicy references.

The largest coherent next unit is the complete page-local configuration lifecycle:

```text
Managed configuration/Application → API → typed Web client → Add/removal UI → tests
```

It gives the operator a real success, failure and recovery path before file commands are added, and
keeps configuration authority separate from later OrganizerExecutor mutation work.

## Implementation Scope

- Add MediaLibrary-specific application behavior for page-local Save, removal preview and removal.
  Reuse or safely generalize the existing managed successor, validation, read-only Storage check,
  destination precheck, checked activation, runtime-binding preparation, optimistic concurrency,
  references and audit mechanisms. Do not call ResourceLibrary methods with MediaLibrary IDs.
- Save accepts exactly a bounded name, lowercase-letter/digit/hyphen ID, enabled state, an existing
  enabled Storage ID and a safe Storage-relative `rootPath`. The ID is creation-only. Duplicate IDs,
  missing/disabled Storage, unsafe/missing roots, invalid references, stale Active, persistence,
  validation, precheck, activation and runtime-load failures must leave the previous Active runtime
  usable and return bounded secret-free recovery evidence.
- One successful enabled Save must publish the immutable successor, refresh the process runtime,
  make the new library immediately selectable and browse its root. A successful disabled Save must
  publish truthfully, remain absent from normal browsing, preserve its files and show the existing
  Web configuration handoff for re-enabling it. Do not label a Draft or failed candidate Active.
- Add MediaLibrary-scoped authenticated API under `/api/v1/media-libraries`: page-local Save,
  exact-Active removal preview and confirmed removal. Require both configuration-management and
  activation permissions. Responses and errors must distinguish candidate/durable state, actual
  Active identity and safe next action without exposing secrets or accepting client Storage roots
  as runtime authority.
- Removal must bind the exact previewed Active revision/version/digest and selected MediaLibrary.
  Show bounded ClassificationPolicy or other reference evidence and block referenced removal.
  Reject stale/mismatched/disabled/unknown confirmations before successor creation. Successful
  removal changes configuration only, never deletes the MediaLibrary root or any Storage entry, and
  leaves the page on another valid enabled library or the truthful empty state.
- Add strict frontend-owned MediaLibrary save/removal models and API normalization. Malformed or
  split-identity success documents must never render as success. Transport-unknown mutation results
  are not retried automatically; refresh Active state and explain what the operator must verify.
- Complete the MediaLibrary header and right-side three-step drawer from the visual specification:
  `基本信息 → 存储位置 → 确认`, explicit Add intent, enabled toggle, close/cancel/Escape, Back/Next/Save,
  pending state, inline validation and retained correctable input. Normal entry, reload and auth
  reconnect keep the drawer closed; focus returns to the invoking Add control where practical.
- Add a selected-card configuration menu and confirmed removal dialog. Explain that removal keeps
  physical files. Reference/stale failures keep the dialog or recovery context available for a
  safe re-review rather than silently closing or retrying.
- Keep Task 38.1 browsing, route state, bounded search/paging, exact path identity and read-only
  behavior intact. Preserve the ResourceLibrary Files body and its existing save/removal journey.
  Preserve the user's dirty `docs/pics/文件页.png` and the canonical
  `docs/pics/媒体库页.png`; do not include `config/alist.json` or credentials.

## Acceptance Criteria

- [ ] An authorized operator opens `+ 添加媒体库`, completes the three steps and submits exactly one
      bounded candidate without handling revision IDs or activation internals.
- [ ] Enabled Save success is the exact immutable Active runtime consumed by list/browse, is selected
      immediately and is browseable at its configured root. Disabled Save success is truthful,
      hidden from browse and offers the existing Web configuration handoff for re-enabling.
- [ ] Invalid name/ID/path, duplicate ID, missing or disabled Storage/root, denied permissions,
      stale/concurrent Active changes, reference/validation/precheck failures and runtime/persistence
      failures preserve the prior Active and retain actionable, correctable UI state.
- [ ] Removal preview identifies the selected MediaLibrary and exact Active evidence. Referenced,
      stale, mismatched, disabled or unknown removal is blocked with a safe next action; successful
      removal never invokes Storage mutation and never deletes files or the library root.
- [ ] Save/removal APIs and Web use the same MediaLibrary application behavior, permissions,
      validation, Active authority and failure semantics. Malformed or identity-inconsistent success
      payloads do not produce a success state, and uncertain mutation is never replayed automatically.
- [ ] Normal entry/reload/reconnect keeps the drawer closed. Close, Cancel and Escape preserve the
      page and restore focus where practical; failed Save keeps input. Desktop and narrow layouts,
      keyboard order, card overflow and removal controls remain usable without statistics,
      thumbnails or dead file-command controls.
- [ ] Existing MediaLibrary browse/deep-link tests and the complete ResourceLibrary Files
      add/remove/browse/Organize journey remain passing and behaviorally unchanged.
- [ ] T4 regression and quality gates pass with actual totals/skips/unavailable gates reported. The
      checkpoint is coherent, contains no unrelated/private files, and does not weaken or delete
      tests, assertions, permission checks, activation checks or Storage-mutation guards.

## Required Tests

Run from the repository root unless a `web/` prefix is shown. Use temporary/local fake Storage and
configuration repositories only; never use production services, credentials or user media.

- `python3 scripts/check_governance.py`
- Add focused Python tests for MediaLibrary Save/removal success, disabled Save, duplicate/invalid
  candidates, missing/disabled Storage and root, exact destination precheck, permissions,
  persistence/validation/activation/runtime failures, concurrent Active changes, reference-blocked
  and stale removal, exact audit evidence and zero Storage mutation.
- `.venv/bin/python -m unittest discover -s tests -p 'test_media_library_activation.py'`
- `.venv/bin/python -m unittest discover -s tests -p 'test_resource_library_activation.py'`
- `.venv/bin/python -m unittest discover -s tests -p 'test_configuration_destination_precheck.py'`
- `.venv/bin/python -m unittest discover -s tests -p 'test_media_library_browser.py'`
- `.venv/bin/python -m unittest discover -s tests -p 'test_api_security.py'`
- `.venv/bin/python -m unittest discover -s tests`
- Add/run focused frontend model/API/component tests for the drawer, validation, checked success,
  disabled handoff, retained-input failures, malformed/split-identity responses, removal preview,
  references, stale re-review, uncertain transport and focus/keyboard behavior.
- `npm --prefix web run test -- --run`
- From `web/`: `npm run test:e2e -- tests/e2e/medialib-files.spec.ts
  tests/e2e/library-files.spec.ts tests/e2e/deep-link.spec.ts` with new MediaLibrary Add/removal
  success/failure/recovery coverage at desktop and narrow viewports.
- From `web/`: `npx playwright test`
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
- Confirm `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` has no matches.
- `TMPDIR=/root/mediaflow/.smoke-tmp .venv/bin/python scripts/docker_release_security_smoke_test.py`
- Inspect `git diff --check`, Task Base..Head name/status/stat, audit/error redaction, private files,
  reference images and the preserved dirty image. Report unavailable gates honestly.

## Non-goals

- MediaLibrary Create Folder/Text, Rename, Edit, Delete, Copy or Move; selection command controls,
  durable file-operation Tasks/Workers and per-item command recovery remain later Slice work.
- MediaLibrary Organize/Scan/Preview, FileIndex membership, metadata/status columns, thumbnails,
  card statistics/capacity/placeholders, Upload/Download or full configuration editing/migration.
- Automatic root creation, forced removal, policy rewrites, disabling referenced libraries,
  arbitrary host paths, new Storage providers or new directory-creation policy semantics.
- ResourceLibrary Files presentation or behavior changes beyond regression fixes strictly required
  by a shared mechanism and proven against its existing contract.
- Slice-final screenshots, CURRENT documentation reconciliation, Closure Packet or A Final Review.

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
