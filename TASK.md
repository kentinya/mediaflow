# Task 38.2 — 完成 MediaLibrary 添加、激活与安全移除

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 38.2
Parent Slice: 38
Status: READY FOR B REVIEW
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

Committed in `75aa8670c346c0396cdc36bb54e3210d850ae914` (Task Base `6419ae1`):

```text
mediaflow/application/configuration_objects.py       | 490 +-   Save/removal evidence + successor publish
mediaflow/interfaces/service_api.py                  | 234 +-   /api/v1/media-libraries Save/preview/DELETE
tests/test_media_library_activation.py               | 888 +    focused Python proof (new)
web/src/entities/library/media-library.ts            | 339 +    strict frontend configuration models (new)
web/src/entities/library/media-library.test.ts       | 315 +    model regression incl. split identity (new)
web/src/features/library/MediaLibraryFilesPage.tsx   | 1015 +-  Add drawer, card menu, removal dialog
web/src/features/library/MediaLibraryFilesPage.test.tsx | 19 +-  RO-4 regression corrections
web/src/features/library/MediaLibraryConfigDialogs.test.tsx | 563 + drawer/dialog component proof (new)
web/src/shared/api/api-client.ts                     | 151 +    typed MediaLibrary mutation client
web/src/shared/api/media-library-config-api.test.ts  | 407 +    client contract proof (new)
web/tests/fake-server.mjs                            | 555 +-   local MediaLibrary mutation endpoints
web/tests/e2e/medialib-config.spec.ts                | 476 +    browser Add/removal journeys (new)
web/tests/e2e/medialib-files.spec.ts                 |   8 +-   Add control regression correction
```

The pre-existing dirty `docs/pics/文件页.png` (modified 2026-09-22, before this Task existed) is
deliberately **not** in the checkpoint and is preserved byte-identical in the worktree.

### Implemented

- **Application boundary.** `ConfigurationObjectService.save_media_library` and
  `remove_media_library` compose the candidate into the save-time Active document, run the shared
  read-only Storage/destination admission gates, validate the complete successor and publish only
  through the checked activation and runtime-binding boundary. Removal binds the exact previewed
  Active revision/version/digest plus the selected library, rejects stale/mismatched/disabled/unknown
  confirmations before successor creation, blocks referenced libraries, and changes configuration
  only — no mutating Storage call and no root/file deletion is reachable.
  `media_library_removal_evidence` returns bounded, secret-free preview evidence with blocking
  references.
- **API.** MediaLibrary-scoped `/api/v1/media-libraries`: page-local Save (POST), exact-Active
  removal preview (GET `/{id}/removal-preview`) and confirmed removal (DELETE `/{id}`), requiring
  both `MANAGE_CONFIGURATION` and `ACTIVATE_CONFIGURATION`; evidence reuse was generalized
  (`is_resource_library_save` → `is_library_save`) without changing ResourceLibrary behavior.
- **Web.** Strict frontend-owned Save/preview/removal models where a malformed or split-identity
  success document fails closed; typed client with pre-request validation; three-step Add drawer
  (`基本信息 → 存储位置 → 确认`) with explicit Add intent, enabled toggle, close/cancel/Escape,
  pending state, inline validation and retained correctable input; disabled Save is truthful, hidden
  from browse and offers the existing configuration handoff; selected-card configuration menu and a
  confirmed removal dialog naming the library and stating that physical files are preserved.
  Uncertain transport outcomes are never replayed automatically.
- **Preserved.** Task 38.1 browsing, route state, bounded search/paging, exact path identity and
  read-only behavior, and the complete ResourceLibrary Files journey.

### Tests and Results

All commands from the repository root unless a `web/` prefix is shown.

| Command | Result |
|---|---|
| `python3 scripts/check_governance.py` | PASS |
| `.venv/bin/python -m unittest discover -s tests -p 'test_media_library_activation.py'` | PASS — 19 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_resource_library_activation.py'` | PASS — 14 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_configuration_destination_precheck.py'` | PASS — 26 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_media_library_browser.py'` | PASS — 5 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_api_security.py'` | PASS — 13 tests |
| `.venv/bin/python -m unittest discover -s tests` | PASS — 1745 tests, 7 skipped |
| `npm --prefix web run test -- --run` | PASS — 551 tests / 40 files |
| `npm --prefix web run test:e2e -- tests/e2e/medialib-files.spec.ts tests/e2e/medialib-config.spec.ts` | PASS — 24 tests (12 new) |
| From `web/`: `npx playwright test` | PASS — 148 tests |
| `npm --prefix web run typecheck` | PASS |
| `npm --prefix web run lint` | PASS |
| `npm --prefix web run format:check` | PASS |
| `npm --prefix web run build` | PASS |
| `.venv/bin/ruff format --check .` | PASS — 312 files formatted |
| `.venv/bin/ruff check .` | PASS |
| `.venv/bin/python -m compileall -q mediaflow tests scripts` | PASS |
| `.venv/bin/python -m pip check` | PASS — no broken requirements |
| `.venv/bin/mediaflow --config config/strategy.example.json config validate` | PASS |
| `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` | PASS |
| FFmpeg/FFprobe exclusion (`rg -n -i 'ffprobe\|ffmpeg' mediaflow pyproject.toml`) | PASS — no matches (`rg` unavailable; verified with the grep tool and `grep -rniE`) |
| `TMPDIR=/root/mediaflow/.smoke-tmp .venv/bin/python scripts/docker_release_security_smoke_test.py` | PASS — release-security smoke acceptance passed |

`git diff --check` clean. Commit manifest contains no image, no `config/alist.json` (absent; still
ignored/untracked), no credentials and no unrelated files. Skips are the pre-existing suite skips
(7), not new hidden skips; no external service gate was required — all Storage, configuration and
browser evidence uses local fakes, temporary directories and throwaway tokens.

### Decisions

- **Mirror, don't relabel.** MediaLibrary Save/removal reuse the ResourceLibrary managed-successor,
  validation, precheck, checked activation, runtime-binding, concurrency and audit mechanisms, but
  through MediaLibrary-specific application methods. No ResourceLibrary method is called with a
  MediaLibrary ID, and the shared `is_library_save` evidence generalization is behavior-preserving
  for the ResourceLibrary path (proven by its unchanged tests).
- **Removal is a configuration successor, not a file operation.** Removal deletes one object from a
  successor of the immutable Active document and publishes through checked activation; Storage is
  only ever read. This is why removal can never touch the library root or files.
- **Exact-Active confirmation binding.** The preview returns the Active revision/version/digest and
  the confirmation must echo all four fields plus the library ID, so a preview computed against a
  superseded Active cannot authorize a removal.
- **Fail closed on identity inconsistency.** Both `normalizeMediaLibrarySave` and
  `normalizeMediaLibraryRemoval` require the durable `configuration` block to agree exactly with the
  published `active` revision; a divergent pair raises instead of rendering success.
- **Add prerequisites come from system status** (`configurationActive` + an enabled Storage), so a
  status hiccup only disables Add and never fabricates a candidate or bypasses the backend.
- **Two Task-38.1 assertions were corrected rather than deleted.** The unit and browser tests that
  forbade any Add control contradicted RO-4; they now assert the Add control exists *and* that
  normal entry keeps its drawer closed, which is a strictly stronger statement. The 401 test now
  asserts the exact two read URLs are each fetched once, instead of a bare call count that the new
  status read made stale.

### Remaining In-Slice Work

Knowing only from this Task's scope, still outstanding in Slice 38:

- RO-5 bounded common file maintenance on the MediaLibrary surface (Create Folder/Text, Rename,
  Copy, Move, Delete, bounded text edit) with MediaLibrary-scoped API and durable Task/Worker
  execution.
- RO-6 durable MediaLibrary results/progress, Operations revisit and per-item recovery for media
  work, including cross-Storage verification semantics.
- RO-7 remaining media-scoped surfaces and kind-aware cursor/evidence/manifest/worker
  reconstruction.
- RO-8 remaining MediaLibrary integration/regression coverage and the controlled Slice screenshots.

### Risks / Deviations

- **Recovered uncommitted prior-session work.** At session start the working tree already contained
  this Task's implementation (application, API, page, client, models and the Python test) uncommitted
  from an earlier session, with `TASK.md` still `PLANNED` and an empty report. I verified it against
  scope and acceptance, found and fixed the real defects, added the missing frontend coverage, and
  committed it as a new coherent checkpoint. No commit was amended or rewritten, and the Task Base
  was not moved.
- **Frontend/browser coverage was the genuine gap.** The recovered work had no frontend unit or e2e
  coverage for the drawer/removal journey, and the fake API had no MediaLibrary mutation endpoints.
  Both are now implemented and passing. Two pre-existing frontend assertions that contradicted RO-4
  were corrected as described above.
- **`rg` is unavailable** in this environment, so the FFmpeg/FFprobe exclusion gate was verified with
  the grep tool and `grep -rniE` instead of the literal `rg` command; the result (no matches) is the
  same evidence.
- **No pre-existing/unrelated failures remain.** The full Python regression, web unit suite and full
  browser suite all pass on the committed revision; nothing is reported as
  `FAIL / PRE-EXISTING / UNRELATED`, and no gate is `UNAVAILABLE`.
- **Inherited residual risk unchanged.** The narrow Local directory replacement/inode-reuse race
  documented in `SLICE.md` is untouched by this Task, and no new Storage-mutation, overwrite or
  deletion path was introduced.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 75aa8670c346c0396cdc36bb54e3210d850ae914
```


## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```
