# Task 38.8 — ResourceLibrary/MediaLibrary Page-local Edit and Atomic Activation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md). It is planned under the user-authorized A scope expansion and
is the first implementation unit after the historical Slice 38 B Closure Packet.

```text
Task ID: 38.8
Parent Slice: 38
Status: PLANNED
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
  checks, and a controlled edit open/closed screenshot plus narrow-screen/focus evidence.
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
