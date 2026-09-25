# Task 38.8 — ResourceLibrary/MediaLibrary Page-local Edit and Atomic Activation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md). It is planned under the user-authorized A scope expansion and
is the first implementation unit after the historical Slice 38 B Closure Packet.

```text
Task ID: 38.8
Parent Slice: 38
Status: READY FOR B REVIEW
Task Base: 64d0020265f2870983cd31d07d3809e425767d0d
Difficulty: High
Test Level: T4
Planner / Reviewer: B (user-authorized delegation)
```

## Goal

Complete the operator journey from the selected ResourceLibrary or MediaLibrary card's action menu
through focused configuration editing and checked atomic activation. The operator can edit name,
enabled state, Storage and the kind-specific Storage-relative root, while the stable library ID and
all unexposed configuration remain unchanged. This advances Slice 38 RO-4, RO-9 and AC-10.

## Why This Task Exists

The current Files and MediaLibrary pages expose Add and Delete/Remove, but no Edit action. Their
page-local Save APIs are create-only: an existing ID is rejected as duplicate, and the form has no
exact-Active edit projection or stale-writer contract. The managed configuration service already
provides the successor/validation/evidence/runtime-binding/activation pipeline, so the largest
reasonable unit is one vertical behavior spanning application merge semantics, kind-specific API
authority, both Web pages and regression proof.

This is not a general configuration-editor redesign. Keeping the edit inside this Task preserves
the existing Add/Configuration page boundaries while making the requested card-level journey
complete for both library kinds.

## Implementation Scope

### Application and managed configuration

- Add an update path for existing ResourceLibrary and MediaLibrary objects that replaces only the
  focused fields in the exact Active document and preserves all unexposed fields, references and
  sibling objects.
- Keep each stable ID immutable. Reject route/body identity mismatch, missing target, wrong kind,
  invalid fields, disabled/unavailable Storage and unsafe relative roots with bounded error codes.
- Bind the edit to the exact Active revision read for the form. A stale revision/version/digest
  must fail closed before successor publication and preserve the previous Active.
- Reuse the existing complete validation, applicable read-only Storage/strategy/destination
  evidence, prepared runtime binding and atomic activation boundary. Return success only after the
  new Active runtime is consumable.
- Record bounded, secret-free Before/After audit for the focused object. Editing configuration never
  calls OrganizerExecutor, creates a directory, or moves/copies/renames/deletes Storage content.
- Preserve existing create and remove semantics and compatibility. An edit that disables a
  referenced library must fail through graph validation rather than silently orphaning dependents.

### API

- Add kind-specific bounded edit projections that return the exact editable object, enabled Storage
  projection and Active revision identity needed for optimistic concurrency. Internal revision
  fields may remain in memory in the browser; the ordinary operator does not copy or enter them.
- Add kind-specific update endpoints, recommended as `PUT /api/v1/resource-libraries/{id}` and
  `PUT /api/v1/media-libraries/{id}`, with exact field allowlists and expected Active identity.
  Keep `POST` create payloads and DELETE removal confirmation contracts backward compatible.
- Apply the same RBAC, validation, error mapping, audit and runtime-binding behavior to API and Web;
  equal IDs in the two namespaces must never share edit authority or cached evidence.

### Web and shared presentation

- Extend the selected-card `⋯` menu with `编辑资源库` / `编辑媒体库` beside the existing
  Delete/Remove action, preserving menu focus, keyboard and narrow-screen behavior.
- Reuse the existing three-step drawer as an Add/Edit form (or a minimal shared form primitive)
  without resetting unexposed fields. Edit opens only on explicit intent, pre-fills current values,
  renders ID read-only and identifies configuration-only Storage/root changes.
- Keep the drawer open with entered values and an action-oriented error after recoverable failure;
  never auto-retry an unknown result. Use a distinct edit title/accessible name and a final action
  such as `保存并激活` so activation semantics are truthful.
- On success, invalidate the relevant status/list/files queries and reconcile selection/path:
  name-only edits preserve a valid directory, Storage/root edits return to that library root, and a
  disabled result is removed from browse selection with the existing configuration handoff.
- Keep Add, existing Delete/Remove, direct file commands, Organize continuation and the other
  library kind's cache/navigation state unchanged.

## Acceptance Criteria

- [ ] ResourceLibrary and MediaLibrary selected-card menus expose accessible Edit actions without
      changing existing Delete/Remove confirmation or ordinary entry command menus.
- [ ] Edit opens a prefilled three-step form for the selected exact Active object; name, enabled
      state, Storage and kind-specific root are editable, while ID is visible and disabled/read-only.
- [ ] The backend updates the existing object by immutable ID, preserves every unexposed field and
      sibling/reference object, rejects cross-kind/equal-ID authority reuse, and keeps create/remove
      API behavior compatible.
- [ ] The edit read/save path uses exact Active optimistic concurrency. A stale writer receives a
      bounded recovery error and cannot publish a successor or overwrite a newer Active.
- [ ] Successful edit performs complete validation, applicable read-only evidence, runtime binding
      and atomic activation; the response and Web state identify the same consumed Active snapshot.
- [ ] A successful enabled edit is immediately browseable. Name-only edits preserve a valid path;
      Storage/root edits reset to the new root; disabling hides the library truthfully and does not
      delete or migrate files.
- [ ] Invalid names/IDs/roots, unavailable or disabled Storage, missing target, references,
      permission denial, validation/evidence failure, persistence failure, activation conflict and
      runtime-load failure preserve the prior Active and keep correctable form input where Web was
      involved.
- [ ] Edit reads, validation, evidence and activation perform zero Storage-content mutations and
      do not start Scan, Task, Job, Provider, Metadata or OrganizerExecutor work.
- [ ] Web and API use the same behavior, permission checks, field allowlists, error/recovery
      semantics and secret-free audit evidence for both library kinds.
- [ ] Existing Slice 38 Add, Remove, browse, file-command, transfer, Organize-return and route/auth
      regressions remain green; no card statistics, thumbnails, ID migration or general configuration
      editor is introduced.

## Required Tests

The Developer must run and record actual results for the following T4 evidence, using fakes/local
servers and temporary Storage roots only:

- Focused Python application/API tests in `tests/test_configuration_objects.py`,
  `tests/test_resource_library_activation.py` and `tests/test_media_library_activation.py` for
  both kinds, field-preserving merge, immutable IDs, exact Active stale conflicts, RBAC, all
  failure paths, audit redaction and zero Storage/Task/Provider/OrganizerExecutor side effects.
- Relevant Python configuration/API regression:
  `.venv/bin/python -m unittest discover -s tests`.
- Focused Web API/model/component tests in `web/src/shared/api/library-api.test.ts`,
  `web/src/shared/api/media-library-config-api.test.ts`, `web/src/features/library/StorageFilesPage.test.tsx`,
  `web/src/features/library/MediaLibraryConfigDialogs.test.tsx` and affected page/menu tests.
- Web unit/component and static checks:
  `npm --prefix web run test -- --run`, `npm --prefix web run typecheck`,
  `npm --prefix web run lint`, `npm --prefix web run format:check` and
  `npm --prefix web run build`.
- Browser journeys in both `web/tests/e2e/library-files.spec.ts` and
  `web/tests/e2e/medialib-config.spec.ts`: prefill/edit/save-and-activate success, name/root/
  Storage/enabled transitions, stale/failure recovery, no automatic retry, and unchanged delete.
- T4 quality/safety gates material to the changed boundary, including
  `python3 scripts/check_governance.py`, `git diff --check`, the repository's normal Python quality
  checks, `.venv/bin/python -m compileall -q mediaflow tests scripts`, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `scripts/docker_release_security_smoke_test.py`, and a controlled edit open/closed
  screenshot plus narrow-screen/focus evidence.
  Do not modify or include the pre-existing dirty `docs/pics/文件页.png`.

## Non-goals

- General Configuration-page redesign or editing arbitrary configuration-object fields.
- Changing or migrating ResourceLibrary/MediaLibrary IDs, references, routes, history or persisted
  task identities.
- Moving, copying, renaming, creating or deleting root contents when Storage/root configuration
  changes; no automatic directory creation or content migration.
- Editing disabled libraries from a new browse surface; the existing configuration handoff remains
  the re-enable path.
- MediaLibrary Scan/Preview/Organize, metadata/recognition behavior, Upload/Download, thumbnails,
  statistics, browser binary/media editing, cross-kind transfers or transfer Replace mode.
- Replacing the managed configuration authority, introducing a second Web/API permission model,
  exposing raw tokens/revision ceremony to ordinary operators, or changing existing Add/Remove
  contracts beyond the edit capability.
- Unrelated shell, route, Storage adapter, OrganizerExecutor, Worker, V1 UI or product refactors.

## Developer Completion Report

### Changed Files

- `mediaflow/application/configuration_objects.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_resource_library_activation.py`
- `tests/test_media_library_activation.py`
- `web/src/shared/api/api-client.ts`
- `web/src/features/library/LibraryCardStrip.tsx`
- `web/src/features/library/StorageFilesPage.tsx`
- `web/src/features/library/MediaLibraryFilesPage.tsx`
- `web/src/features/library/StorageFilesPage.test.tsx`
- `web/src/features/library/MediaLibraryConfigDialogs.test.tsx`
- `web/src/shared/api/library-api.test.ts`
- `web/src/shared/api/media-library-config-api.test.ts`
- `web/tests/e2e/library-files.spec.ts`
- `web/tests/e2e/medialib-config.spec.ts`
- `web/tests/fake-server.mjs`
- `TASK.md`

### Implemented

- Added exact-Active edit projections and immutable-ID PUT updates for ResourceLibrary and
  MediaLibrary, preserving unexposed fields through a merged successor document.
- Reused checked validation, read-only evidence, runtime preparation and atomic activation; stale
  revision/version/digest writers fail closed without replacing Active.
- Added Web API client helpers, selected-card edit actions and prefilled edit-capable drawers with
  read-only IDs and `保存并激活` semantics.
- Added API regression coverage for field preservation, stale writers and zero-content mutation
  through the existing activation fixtures.
- Corrected exact-Active concurrency to consume `revisionSequence`, matching the immutable identity
  returned by both edit projections even when mutable revision `version` differs.
- Added visible projection-failure recovery outside the closed drawer, retained failed Save input
  without automatic replay, focus return, narrow-screen coverage and ResourceLibrary disable
  handoff to configuration.
- Added focused API/client/component and browser edit journeys for both library kinds, including
  divergent version/sequence, prefill/read-only ID, field transitions, stale/failure recovery,
  unchanged removal regressions and controlled edit-drawer screenshots.
- Added the enabled Storage choices to each kind-specific edit projection from the same verified
  Active snapshot; edit drawers now use only that projection and fail visibly if the current
  binding cannot be represented instead of substituting cached status data.
- Restored successful-edit keyboard focus: enabled edits return to the invoking selected-card menu
  trigger, while disabling an edited library focuses the visible configuration recovery handoff.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS
- `.venv/bin/python -m unittest tests.test_resource_library_activation tests.test_media_library_activation` — PASS (37 tests)
- `npm --prefix web run test -- --run src/shared/api/library-api.test.ts src/shared/api/media-library-config-api.test.ts` — PASS (41 tests)
- `npm --prefix web run test -- --run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryConfigDialogs.test.tsx` — PASS (58 tests after path-preservation fix)
- `npm --prefix web run typecheck` — PASS
- `npm --prefix web run lint -- --max-warnings=0` — PASS
- `npm --prefix web run format:check` — PASS
- `npm --prefix web run test -- --run` — PASS (611 tests)
- `npm --prefix web run build` — PASS (existing chunk-size warning only)
- `.venv/bin/python scripts/docker_release_security_smoke_test.py` — PASS
- `npm --prefix web run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-config.spec.ts` — PASS (58 tests)
- `python3 -m unittest tests.test_release_security.ReleaseSecurityPolicyTests.test_release_quality_gate_commands_are_documented_for_task_execution` — PASS
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS
- `.venv/bin/ruff check .` — PASS
- `.venv/bin/ruff format --check .` — PASS
- `.venv/bin/python -m unittest discover -s tests` — PASS (1795 tests, 7 skipped)
- `git diff --check` — PASS

### Decisions

- Edit requests use the exact Active revision identity read by the page; the browser never edits a
  Draft or performs a separate activation step.
- The existing Save pipeline remains authoritative for both create and edit; edit merges the
  focused fields into the current object before normalization so extensions and future fields are
  not reset.
- `revisionSequence` is the edit form's immutable optimistic-concurrency version; mutable Draft
  `version` remains a separate lifecycle token and is not exposed as edit authority.
- Projection failure stays outside the drawer with explicit refresh/dismiss actions; unknown reads
  and writes are never replayed automatically.
- Edit Storage choices and the selected object are one atomic read model from the same verified
  Active revision; cached `system-status` remains Add-page state only and cannot rewrite an edit.
- Focus restoration follows the durable result: return to the still-present invoking trigger after
  enabled success, or to the explicit configuration handoff when disable removes that trigger.

### Remaining In-Slice Work

- No additional Task-local work is known; Slice completeness remains for B/A review.

### Risks / Deviations

- The browser proof writes controlled `resource-library-edit-drawer.png` and
  `media-library-edit-drawer.png` evidence under Playwright `test-results`; these generated files
  are not committed.
- The pre-existing modified `docs/pics/文件页.png` remains preserved and excluded from both
  correction commits.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 7d4503e45dc3aa79628ed0d98e887167e1e7c529
```

## B Review Result

```text
Reviewed: 64d0020265f2870983cd31d07d3809e425767d0d..1074a6b095f2eac5e407c687df38a65cd27f89dc
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The edit projection still does not return the enabled Storage projection required by this Task.
  `resource_library_edit_projection` and `media_library_edit_projection` return only the selected
  object and Active summary, while both drawers receive Storage choices from the independent cached
  `system-status` query. The production form then replaces an exact-Active `initial.storageId` that
  is absent from that cached list with `storages[0].id` (`StorageFilesPage.tsx:1548-1558` and
  `MediaLibraryFilesPage.tsx:1378-1387`). A legal sequence—page caches Active N status, Active N+1
  changes/adds the selected library's Storage, operator opens Edit and receives the N+1 object—thus
  displays and can save a different Storage while the N+1 optimistic identity still passes. This
  affects the current selected-card edit journey and violates the Task API scope, RO-9 exact bounded
  Active projection, and the Acceptance requirement that the exact Active object be prefilled.
  Return the enabled Storage choices from the same verified Active projection for each kind, make
  the edit drawer consume that projection instead of unrelated cache authority, fail visibly if the
  exact binding cannot be represented, and add a regression where cached status and edit Active
  differ without silently changing Storage.
- Successful Edit does not restore keyboard focus to the invoking selected-card action button.
  `closeDrawer()` restores `editDrawerInvokerRef`, but both successful mutation paths directly call
  `setDrawerOpen(false)` and clear edit state without using that focus recovery
  (`StorageFilesPage.tsx:2079-2105`, `MediaLibraryFilesPage.tsx:2097-2126`). The focused
  `保存并激活` button is removed, leaving keyboard users without the required return point; the new
  E2E tests assert focus only after Cancel, not after successful Save. This is reachable in both
  current Web edit journeys and violates the Slice Operator Journey's keyboard/focus-return rule and
  this Task's menu-focus/narrow-screen scope. Restore focus after known successful edit activation
  (with a truthful fallback if disabling/removing the selected card makes that exact trigger no
  longer available) and cover enabled and disabled success behavior in browser tests.
