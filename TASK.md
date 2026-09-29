# Task 41.2 — Foundational rule objects with one-save Active publication

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 41.2
Parent Slice: 41
Status: FIX REQUIRED
Task Base: 34dc6e35982c19fbbedb72aba0bc31c6353bc805
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An administrator can build and maintain the independently creatable foundations of the rules graph
in V2—Recognition Types and Metadata, Naming, Classification and Organize Policies—and click one
`保存` action per intended change to validate and atomically publish the exact successor Active
configuration. This advances Slice RO-2, the RecognitionType portion of RO-3, the four typed editors
in RO-5, and the associated RO-7/RO-8 publication and recovery behavior.

## Why This Task Exists

Task 41.1 established the exact-Active, read-only workspace, but its empty-state action still hands
off to the existing configuration UI because V2 has no editor or publication command. The five
families here are the legal building blocks an administrator can create before a RecognitionRule or
type binding completes the graph. They share one high-risk mutation boundary: a focused object
candidate must become a checked immutable Active revision without publishing unrelated Draft work.
Implementing that boundary together with these complete typed object journeys is one coherent
vertical unit. RecognitionRule/type-binding authoring and exact-candidate tests/previews remain the
next dependent in-Slice units, not separate fields or buttons in this Task.

## Implementation Scope

Application / Persistence / API:

- Add a narrowly scoped rules-workspace command for RecognitionType, MetadataPolicy, NamingPolicy,
  ClassificationPolicy and OrganizePolicy create, edit, copy, enable/disable where the domain allows
  it, and reference-safe delete. Reuse managed object normalization, optimistic concurrency,
  reference evidence, audit, whole-document validation, Slice 40 applicable checks and checked
  atomic activation. One explicit final `保存`/confirmed list intent must complete publication;
  never leave a successful action as a hidden unpublished Draft.
- Compose only the focused change from one exact Active snapshot. Verify the submitted observed
  Active authority against that snapshot, including its version/digest internally; fail closed on
  stale authority. Keep unrelated saved Drafts and existing pinned work untouched. Do not expose a
  revision ID, digest, grant or secret as an ordinary user step.
- Provide bounded, allowlisted Active detail/edit data for these five families, actual available
  MediaLibrary/provider references and secret readiness, and reference impact needed for safe
  enable/disable/delete. Preserve existing V1 `/api/v1/configuration/*` behavior and use the same
  application permissions and semantics for the new V2 command.
- Return explicit success, validation/evidence/reference/stale/permission/activation failure and
  unknown-outcome recovery data: affected object/stage, whether Active changed, durable candidate
  state if any, what input can be corrected, and the safe next action. Verify current managed Active
  before any manual retry of an unknown Save outcome; never automatically resubmit it. Audit
  bounded before/after and result without secrets.

Web:

- Keep every family entry as the existing complete full-width inventory with no selected object,
  editor or drawer. Only its explicit `添加xx` action opens a create drawer; row selection, search,
  filter, tab change and refresh stay read-only. An explicit Edit action opens a refresh-safe
  full-page state for an existing object. Copy opens a new-ID candidate; list-level enable/disable
  and reference-safe delete have a clear explicit final intent.
- Build purpose-built typed forms for the five families using their current domain fields and
  compatibility. RecognitionType has stable ID/name/description/enabled state and incoming rule/
  binding impact. MetadataPolicy shows configured provider, media/query mode, locale, thresholds,
  timeout/retry/request limits and secret readiness without returning credentials. NamingPolicy
  shows actual Movie and TV templates, supported variables/formatting, missing-variable behavior
  and component length. ClassificationPolicy edits ordered supported conditions and separate
  MediaLibrary ID plus safe relative path. OrganizePolicy shows operation, conflict, attachment,
  duplicate, rollback and cleanup settings with explicit overwrite/delete/cleanup risk; it has no
  invented enabled toggle or implicit operation fallback.
- Show Active separately from unsaved form input and any labelled failed-Save candidate. Save
  progress, publication result, validation blockers, stale authority, reference impact and safe
  recovery remain visible. Preserve correctable input across failed Save, refresh, navigation,
  reconnect and stale recovery, or warn before discarding it. Do not ask users to perform separate
  Draft Save, Validate, Activate or raw revision-token transfer.
- After a known successful Save, refetch the server Active inventory/readiness and make the new
  object or change visible. Settings/V1/API and new admissions must observe the same immutable
  published authority; page entry and inspection still create no Draft/work/Provider call or
  Storage mutation.

Tests:

- Cover the five-family empty-Active onboarding sequence and real Active successor publication;
  each operation's allowed and rejected states; exact-Active stale writers and concurrency;
  field/reference/template/path/secret failures; copy identity and default-disabled behavior where
  supported; reference-protected deletion; correctable known and unknown Save outcomes; RBAC,
  audit/redaction and zero media/Storage work.
- Cover drawer-only Add, explicit full-page Edit, no automatic opening from inventory actions,
  unsaved-input protection, accessible narrow/keyboard operation, typed API/error normalization,
  and the post-Save Active refetch. Use temporary roots, fakes and local servers, never real media
  or production provider credentials.

Frozen boundaries: RecognitionRule/type-binding authoring and Strategy Test; Metadata live test,
Naming/Classification/Organize/whole-chain previews; rule-engine/policy-resolver semantics;
Storage adapters and OrganizerExecutor; other V2 pages except a necessary factual Settings
readiness/return integration. Do not edit the six supplied reference images or `config/alist.json`.

## Acceptance Criteria

- [ ] From the existing `/ui-v2/rules` inventory, an authorized administrator can Add, Edit, Copy,
      enable/disable where supported, and reference-safely delete each of the five included object
      families through typed V2 controls. Default inventory, drawer and full-page Edit behavior
      match Slice AC-1; no ordinary step requires V1 or whole-document JSON for these five families.
- [ ] One explicit `保存` or confirmed list action composes only the intended object change from the
      observed exact Active, validates the complete successor, runs applicable checks and atomically
      activates it. Success visibly shows the new actual Active and refreshes inventory/readiness;
      reads, selection and navigation have zero configuration or media side effects.
- [ ] Every form represents current backend fields and references accurately. Invalid fields,
      duplicate IDs, unknown variables, unsafe templates/paths, missing/disabled references,
      unavailable provider secret and unsupported effects fail with the relevant object/stage and
      an actionable next step. No frontend policy authority or invented fallback appears.
- [ ] Edit keeps ID immutable; copy has a new stable ID and defaults disabled for kinds supporting
      enabled state. Enable/disable/delete show actual reference impact, and referenced deletion is
      blocked. Destructive policy settings are explicit but create no execution grant or media work.
- [ ] Stale or simultaneous Saves cannot publish the wrong successor; known failures preserve the
      prior Active and correctable input/candidate. Unknown outcomes prompt Active verification and
      never auto-replay. Browser-visible and audit/error data are bounded and secret-free.
- [ ] V1/API/CLI, Files and Automation retain the same backend policy semantics and immutable pins;
      no new Storage mutation path, Provider call on read/Save, Task/Job, schedule occurrence or
      notification is introduced by this workspace.
- [ ] T4 focused, integration, full regression, browser and quality/safety gates below pass, with
      unavailable environmental gates reported honestly. The checkpoint contains only this Task's
      coherent changes and preserves pre-existing user files.

## Required Tests

- New focused Python tests for the rules Save composition/detail/reference boundary, plus
  `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace.py tests/test_configuration_objects.py tests/test_configuration_snapshot.py tests/test_configuration_successor_draft.py tests/test_configuration_naming.py tests/test_configuration_classification.py tests/test_configuration_organize.py tests/test_configuration_management.py tests/test_configuration_status.py`.
- New focused Web entity/API/form/router tests and `npm --prefix web test -- --run` for all affected
  regression tests.
- `npm --prefix web run build`, `npm --prefix web run typecheck`, `npm --prefix web run lint`,
  `npm --prefix web run format:check`, and focused
  `npm --prefix web run test:e2e -- --grep 'rules'` browser journey tests. If browser binaries or
  Docker are unavailable, report the actual unavailable gate; do not turn it into PASS or skip.
- `.venv/bin/python -m unittest discover -s tests`,
  `.venv/bin/python -m compileall -q mediaflow tests scripts`,
  `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`,
  `python3 scripts/check_governance.py`, and `git diff --check`.
- `scripts/docker_release_security_smoke_test.py` using the repository's documented invocation;
  report environmental unavailability precisely if the isolated Compose harness cannot start.

## Non-goals

- RecognitionRule nested condition editing, rule priority/score/ambiguity UX, and
  RecognitionTypePolicy binding authoring. These dependent graph objects remain in this Slice.
- Recognition Strategy Test, Metadata live test, Naming Preview, Classification Preview and
  Organize/whole-chain authority Preview; no preview-driven execution authority.
- Provider switching, new Metadata Provider, naming variable or classification condition, media
  execution, new Storage adapter, V1 retirement, unrelated Settings/Files/Automation redesign.
- Test-only polish, additional sample data or optional visual tuning unrelated to this journey.

## Developer Completion Report

### Changed Files

- `mediaflow/application/configuration_objects.py`
- `mediaflow/application/rules_workspace_commands.py`
- `mediaflow/domain/configuration_management.py`
- `mediaflow/infrastructure/metadata_provider_bootstrap.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_v2_rules_workspace_commands.py`
- `web/src/entities/rules/rules-form.ts`, `rules-workspace.ts` and tests
- `web/src/features/rules/RulesWorkspacePage.tsx`, `RulesEditPage.tsx`, `RulesObjectDrawer.tsx`, `RulesObjectForm.tsx`, fixtures, labels and tests
- `web/src/routes/router.tsx`
- `web/src/shared/api/api-client.ts`, navigation destination model/tests and UI styles

### Implemented

- Added typed, bounded form authority and object projections for RecognitionType, MetadataPolicy,
  NamingPolicy, ClassificationPolicy and OrganizePolicy, including real references, impact and
  secret-readiness metadata without credential values.
- Added one focused Save-and-activate application command per object operation. It composes from the
  exact observed Active revision, preserves immutable edit IDs, allocates disabled new-ID copies,
  blocks unsupported or referenced operations, and returns bounded recovery/error state.
- Added authenticated API routes and typed frontend clients/forms for Add, Edit, Copy, enable/disable
  where supported, reference-safe delete, explicit drawer/full-page editor flows and post-save Active
  refresh. RecognitionRule and type-binding authoring remain deferred as required by this Task.
- Added focused backend and Web regression coverage for onboarding, validation, concurrency, impact,
  redaction, zero side effects and the RecognitionType identity invariant.
- Correction loop: MetadataPolicy publication now fails closed when the effective Provider has no
  approved credential environment variable; the prior Active remains authoritative with bounded
  recovery evidence.
- Correction loop: edit candidates are persisted in session-scoped browser storage, remain intact
  through unknown-outcome Active verification unless explicitly discarded, and successful Save clears
  them only after publication. Successful edit also refetches the shared Active inventory.
- Correction loop: ClassificationPolicy rule controls now cover enabled, description, confidence,
  category, subcategory and mediaTypes; OrganizePolicy controls cover hash limits and all source
  cleanup limits/patterns.

### Tests and Results

- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_commands.py tests/test_v2_rules_workspace.py tests/test_configuration_objects.py tests/test_configuration_snapshot.py tests/test_configuration_successor_draft.py tests/test_configuration_naming.py tests/test_configuration_classification.py tests/test_configuration_organize.py tests/test_configuration_management.py tests/test_configuration_status.py` — PASS (206 tests, 219 subtests).
- Correction rerun: `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_commands.py` — PASS (38 tests, 31 subtests), including missing Provider secret fail-closed.
- Correction rerun: `.venv/bin/python -m unittest discover -s tests` — PASS (1949 tests, 7 skipped).
- `npm --prefix web test -- --run` — PASS (53 test files, 783 tests; jsdom emits existing `scrollTo` diagnostics).
- `npm --prefix web run build`, `npm --prefix web run typecheck`, `npm --prefix web run lint`, `npm --prefix web run format:check` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts`, `.venv/bin/ruff check ...`, `.venv/bin/ruff format --check ...`, `python3 scripts/check_governance.py`, `git diff --check` — PASS.
- `npm --prefix web run test:e2e -- --grep 'rules'` — UNAVAILABLE / no matching browser tests in the repository (`No tests found`).
- `python3 scripts/docker_release_security_smoke_test.py` — UNAVAILABLE: isolated Compose stack timed out waiting for all services healthy after 150 seconds.

### Decisions

- Reused the existing managed configuration object normalization, whole-document validation,
  checked activation and runtime binding instead of creating a second configuration authority.
- OrganizePolicy exposes no invented enabled toggle or implicit operation fallback; all destructive
  effects remain explicit policy fields and no media/storage execution path is introduced.
- Unknown transport or response outcomes are recovery states requiring Active verification and are
  never automatically replayed.

### Remaining In-Slice Work

- RecognitionRule and RecognitionTypePolicy authoring, exact-candidate tests/previews and the other
  rule-graph surfaces remain in Slice 41 but outside this Task.

### Risks / Deviations

- The four pre-existing untracked `docs/pics/*.png` files were preserved untouched and excluded from
  this checkpoint. `config/alist.json` remains ignored and unstaged.
- Full Web test execution initially failed only because its existing destination-model expectation did
  not include the newly required dynamic rules editor route; the expectation was updated and the
  final full-suite rerun passed (53 files, 783 tests).
- Docker and browser e2e gates are unavailable for the environment for the reasons recorded above.
- B correction blockers were reproduced and addressed in the same Task; no unrelated refactor or
  contract change was made.
- No production credentials, external accounts, real media or Storage mutations were used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 6075bb0d9755b8f2a9a49e602b8a770bbdeefcb9
```

## B Review Result

```text
Reviewed: 34dc6e35982c19fbbedb72aba0bc31c6353bc805..067bef916ff48a6cf2cbd7a251a700b490177465
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The required provider-secret failure is not enforced. In a legal production assembly with
  `TMDB_ACCESS_TOKEN` and `TMDB_TOKEN` unset, the current command still publishes a MetadataPolicy
  with `providerId: tmdb` as Active (reproduced with the Task test harness; result was `PUBLISHED
  active`). `_validate_references` only checks the provider ID and the checked publication path does
  not reject the unavailable credential. This violates Acceptance Criteria 3 and the bounded
  provider-readiness failure required by RO-5/RO-7. Make the shared Save/applicability gate reject an
  unavailable effective provider secret with object/stage/durable-state/next-action evidence, while
  retaining the prior Active.
- Full-page Edit does not preserve the correctable candidate across a browser refresh and can erase
  it during recovery. `web/src/features/rules/rules-workspace-labels.ts` stores drafts only in a
  module `Map`, so a real page refresh/reconnect loses them; `RulesEditPage.tsx` writes `{}` instead
  of clearing only after explicit discard (including after successful Save and `reloadActive`), and
  `reloadActive` replaces the form immediately after an unknown outcome. This violates the Task
  scope/Acceptance requirement to preserve input across failed Save, refresh, navigation and stale or
  unknown recovery. Use a refresh-safe session-scoped candidate lifecycle and keep the candidate until
  the operator explicitly discards it or confirms the verified Active result.
- The typed policy editors do not represent all current backend fields. `RulesObjectForm.tsx` exposes
  only duplicate-detection mode, rollback enabled and cleanup mode for OrganizePolicy, omitting the
  current size/threshold, cleanup-created-directories, max-parent, ignore-pattern and max-entry
  fields; its ClassificationPolicy rule editor also omits current rule enabled/confidence/
  description and result category/subcategory fields. Existing hidden values are merely preserved,
  so an administrator cannot maintain them through this required V2 editor. This violates the typed
  editor and current-field accuracy criteria. Add controls/round-trip validation for every current
  field, with no invented fallback or silent value loss.
- A successful full-page Edit does not refetch the server Active inventory/readiness. After
  `editRuleObject` succeeds, `RulesEditPage.tsx` only installs the command response into local form
  state; it never requests the authoritative inventory/readiness successor required by Acceptance
  Criteria 2 and the post-Save test requirement. Refetch the shared Active projection/inventory and
  readiness after known success, then show the refreshed result without requiring a manual V1 or
  whole-document configuration step.
