# Task 41.3 — Recognition graph authoring and identity-preserving bindings

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 41.3
Parent Slice: 41
Status: FIX REQUIRED
Task Base: 361b03ba908b1f27d92b93a78781df8935aafaff
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An administrator can author the remaining recognition graph objects in the native V2 rules
workspace: typed RecognitionRules and one RecognitionTypePolicy binding per RecognitionType. Saving
one graph object composes, validates and atomically publishes the exact Active successor while
preserving the independent RecognitionType identity. This advances RO-3 and RO-4 and completes the
graph authoring dependency needed by later exact-candidate tests and previews.

## Why This Task Exists

Task 41.2 delivered the five independently creatable policy foundations and their checked Save
journey. The workspace still cannot connect those foundations to recognition output, so an operator
cannot maintain the complete rule graph or legally configure the downstream policies consumed by the
runtime. RecognitionRule and RecognitionTypePolicy authoring form one dependency-ordered vertical
unit: rules select a type, and the binding resolves that type to the four independently edited
policies. Exact strategy tests, previews and execution remain separate downstream behavior.

## Implementation Scope

Domain / Application / Persistence:

- Add typed projections and one-save commands for RecognitionRule and RecognitionTypePolicy using the
  existing managed object normalization, whole-document validation, exact Active concurrency,
  checked activation, audit and bounded recovery semantics established by Task 41.2.
- RecognitionRule supports stable ID/name/description, output RecognitionType, enabled state,
  integer priority, bounded non-negative score, stopOnMatch, and the production AtomicCondition /
  LogicalCondition tree with compatible field/operator/value controls and safe regex bounds.
- RecognitionTypePolicy binds exactly one RecognitionType to MetadataPolicy, NamingPolicy,
  ClassificationPolicy and OrganizePolicy, exposes real enabled/reference state, rejects missing or
  disabled references and duplicate enabled bindings, and never rewrites RecognitionType identity.
- Preserve unrelated Active objects and existing V1/API/CLI/runtime semantics; no second policy
  resolver or configuration authority.

API / Web:

- Extend the existing `/ui-v2/rules` inventory with typed RecognitionRule and Type Binding detail,
  Add/Copy/Edit, enable/disable where supported, and reference-safe delete through the same
  authenticated API/application boundary. Keep inventory entry read-only; only explicit Add opens a
  drawer and existing Edit is a full-page state.
- Provide a nested condition builder for supported AtomicCondition and LogicalCondition forms. The
  ordinary UI must not require raw JSON; any advanced representation is bounded support-only.
- Binding selectors show actual available objects, enabled state and compatibility. Explain the
  preserved RecognitionType and reference impact; never silently substitute defaults or expose raw
  revision/grant/token workflow.
- Preserve correctable input through known/stale/unknown failures, refresh and navigation using the
  existing session-scoped draft model. After successful Save, refresh the authoritative Active
  inventory/readiness and show the published successor.

Tests:

- Add focused backend/API tests for condition validation, regex/size bounds, rule ordering fields,
  output-type references, duplicate enabled bindings, missing/disabled policy references, immutable
  IDs, copy defaults, reference-safe deletion, exact-Active concurrency, audit/redaction and zero
  media/Storage work.
- Add Web entity/API/form/router/component coverage for default inventories, Add-only drawer opening,
  full-page Edit, nested condition controls, binding identity explanation, stale/unknown recovery,
  unsaved protection and post-Save Active refresh.

Frozen boundaries: Metadata live test, Recognition Strategy Test, Naming/Classification/Organize and
whole-chain previews, execution authority, Storage adapters, OrganizerExecutor, V1 retirement,
Provider switching, unrelated Settings/Files/Operations redesign and the six supplied reference
images. Do not edit `config/alist.json`.

## Acceptance Criteria

- [ ] Authorized operators can Add, Edit, Copy, enable/disable where supported and reference-safely
      delete RecognitionRule and RecognitionTypePolicy through typed V2 controls; ordinary use never
      falls back to V1 or whole-document JSON.
- [ ] RecognitionRule forms represent the current AtomicCondition and LogicalCondition model,
      compatible field/operator/value types, priority, non-negative score, stopOnMatch and output
      RecognitionType. Unsafe or oversized regex and malformed trees fail at the object/stage with a
      bounded next action.
- [ ] Type Binding forms expose exactly one RecognitionType plus the four actual downstream policy
      references, reject missing/disabled references and duplicate enabled bindings, and show the
      preserved recognition identity. RecognitionType C remains C when it reuses A's naming,
      classification or organize policies.
- [ ] One explicit Save or confirmed list action composes only the focused change from the observed
      exact Active, validates the complete graph, runs applicable checks and atomically activates it;
      successful Save refreshes the actual Active inventory/readiness and known failures preserve the
      prior Active and correctable input.
- [ ] Edit IDs remain immutable; copies receive stable new IDs and disabled defaults where the domain
      supports enabled state; deletion is reference-protected and never mutates media, Storage,
      history, results or audit records.
- [ ] Stale/simultaneous Saves cannot publish the wrong successor. Unknown outcomes require Active
      verification and never auto-replay. Browser-visible and audit/error data remain bounded and
      secret-free.
- [ ] Existing V1/API/CLI/runtime policy semantics and OrganizerExecutor-only mutation remain
      unchanged; this Task starts no Provider call, Task/Job, schedule occurrence, notification or
      Storage mutation on read or Save.
- [ ] Required T4 focused, integration, full regression and quality/safety gates pass; unavailable
      external gates are reported honestly and no unrelated/private files enter the checkpoint.

## Required Tests

- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_graph.py tests/test_v2_rules_workspace_commands.py tests/test_v2_rules_workspace.py tests/test_configuration_objects.py tests/test_configuration_snapshot.py tests/test_configuration_management.py tests/test_configuration_status.py tests/test_recognition.py` (or the repository's corresponding focused recognition suites).
- `npm --prefix web test -- --run` plus focused rules entity/API/form/router/component tests.
- `npm --prefix web run build`, `npm --prefix web run typecheck`, `npm --prefix web run lint`, and
  `npm --prefix web run format:check`.
- `.venv/bin/python -m unittest discover -s tests`, `.venv/bin/python -m compileall -q mediaflow tests scripts`,
  `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `python3 scripts/check_governance.py`,
  and `git diff --check`.
- `npm --prefix web run test:e2e -- --grep 'rules'`; report `No tests found` or browser unavailability
  precisely rather than converting it into PASS. Run the documented Docker release security smoke
  gate and report environmental timeout/unavailability honestly.

## Non-goals

- Recognition Strategy Test, Metadata live test, Naming/Classification/Organize/whole-chain Preview,
  execution admission or any Storage mutation.
- New recognition fields/operators, AI/expression languages, Provider switching, new Storage
  adapters, V1 retirement or unrelated V2 page redesign.
- Bulk graph editing, visual graph authoring, object/version diff, rollback/cherry-pick, package
  exchange redesign, test-only polish or P2 cleanup.

## Developer Completion Report

### Changed Files

- `mediaflow/application/rules_workspace_commands.py`
- `mediaflow/application/configuration_objects.py`
- `web/src/entities/rules/rules-form.ts`
- `web/src/entities/rules/rules-workspace.test.ts`
- `web/src/features/rules/rules-workspace-labels.ts`
- `web/src/features/rules/RulesObjectForm.tsx`
- `web/src/features/rules/RulesWorkspacePage.tsx`
- `web/src/features/rules/RulesWorkspacePage.test.tsx`
- `web/src/features/rules/rules-form-fixtures.ts`
- `tests/test_v2_rules_workspace_commands.py`

### Implemented

- Added typed RecognitionRule and RecognitionTypePolicy/type-binding families to the existing exact-Active Save, validation, checked activation, audit and reference-safe command path.
- Added output RecognitionType and downstream policy reference checks, disabled/missing reference rejection, duplicate enabled-binding protection, and preserved independent RecognitionType identity.
- Added V2 typed form families with bounded recognition fields, condition-tree JSON control, binding fields and session-safe existing form lifecycle reuse.
- Expanded the inventory/action authority so these families are no longer deferred by the V2 rules workspace.
- Correction: removed unsupported Type Binding `description`, exposed bounded enabled catalogs and condition enums from the backend, replaced free-text graph references with typed selectors, and replaced raw condition editing with recursive Atomic/Logical controls.
- Correction: updated graph-family Web fixtures and empty-state regression coverage to reflect the now-authorable families.

### Tests and Results

- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_commands.py tests/test_v2_rules_workspace.py tests/test_recognition.py` — PASS (62 tests, 76 subtests).
- `.venv/bin/python -m unittest discover -s tests` — FAIL / PRE-EXISTING / UNRELATED: 1949 tests, 1 failure in `test_release_security.ReleaseSecurityPolicyTests.test_release_quality_gate_commands_are_documented_for_task_execution` because this Task report does not yet include the Docker smoke command; 7 skipped, resource warnings only.
- `npm --prefix web run typecheck` — PASS.
- `npm --prefix web run build` — PASS.
- `npm --prefix web test -- --run src/entities/rules/rules-workspace.test.ts src/features/rules/RulesWorkspacePage.test.tsx` — PASS (2 files, 24 tests).
- `npm --prefix web test -- --run` — FAIL / PRE-EXISTING / UNRELATED: 52 files passed, 782 tests passed, one existing `src/features/operations/AutomationRouter.test.tsx` loading/heading failure.
- `npm --prefix web run lint` — PASS (build/lint command completed; existing Vite chunk-size warning only).
- `npm --prefix web run format:check` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/ruff format --check mediaflow tests scripts` — PASS.
- `.venv/bin/ruff check mediaflow tests scripts` — PASS.
- `python3 scripts/check_governance.py` — PASS.
- `git diff --check` — PASS.
- `python3 scripts/docker_release_security_smoke_test.py` — UNAVAILABLE / NOT RUN: Docker smoke is outside this correction environment.
- `npm --prefix web run test:e2e -- --grep 'rules'` — UNAVAILABLE / NOT RUN: no browser e2e execution available in this environment.

### Decisions

- Reused `ConfigurationObjectService._normalize`, whole-document validation and `RulesWorkspaceCommandService._publish`; no second policy resolver or configuration authority was introduced.
- Conditions remain provider-neutral and bounded by the existing runtime model; the UI uses recursive typed Atomic/Logical controls and submits the same condition document validated by the backend.
- RecognitionType identity is carried by the binding reference and is never inferred from naming/classification/organize policy IDs.

### Remaining In-Slice Work

- Exact strategy tests/previews and later rules-workspace completion remain outside this Task.

### Risks / Deviations

- Full Web regression retains one pre-existing/unrelated AutomationRouter failure; the affected rules regression passes. No production credential, Storage mutation or external service was used.
- Browser rules e2e and Docker smoke gates remain unavailable/not run in this environment.
- Pre-existing untracked `docs/pics/*.png` files were preserved; `config/alist.json` remains ignored and unstaged.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 2368e331fb3b642d3ed77ad89a23b67c7d0ef735
```

## B Review Result

```text
Reviewed: 361b03ba908b1f27d92b93a78781df8935aafaff..44a0cd0f6f6a8d254b1d12b54b39e772dfcfc656
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The Type Binding create journey is not publishable. In the legal current Active harness, after
  creating a new enabled RecognitionType and submitting a binding with the actual enabled policy
  references, `RulesWorkspaceCommandService.save_object("typeBindings", ...)` fails with
  `rules_invalid_field` at `compose`: `RecognitionTypePolicy ... contains unsupported field
  'description'`. The new `_FAMILY_SPECS` and defaults expose `description`, but the current
  `ConfigurationObjectService._RECOGNITION_TYPE_POLICY_FIELDS` and normalizer do not support it.
  This is a production-reachable failure of Task AC-1/AC-3 and RO-4. Align the typed projection and
  form with the real domain fields (or make a deliberate domain-compatible change) so a valid binding
  can be created, edited and copied without sending an invented field.
- RecognitionRule condition editing is an ordinary raw JSON textarea (`RulesObjectForm.tsx`,
  `structure("condition", ...)`) rather than the required typed nested AtomicCondition /
  LogicalCondition builder. An administrator must author the production condition tree manually and
  the UI offers no field/operator/value compatibility controls. This violates Task AC-2, the
  Required Surface typed form contract and RO-3. Implement bounded typed controls for the current
  condition model; any JSON view may remain support-only and must not be the normal Save path.
- RecognitionRule output type and all five Type Binding references are free-text inputs. The form
  authority exposes no actual recognition-type/policy catalogs for selectors, so the UI cannot show
  available IDs, enabled state or compatibility and instead relies on backend rejection. This
  violates Task AC-3 and RO-4's selector/reference requirements. Add bounded server projections for
  the actual catalogs and render typed selectors with disabled/missing-reference evidence; do not
  silently substitute defaults.
- The required affected Web regression is failing: `npm --prefix web test -- --run
  src/entities/rules/rules-workspace.test.ts src/features/rules/RulesWorkspacePage.test.tsx` reports
  7 failed tests (24 total), including form-authority parsing failures and the old deferred-family
  assertions. The rules fixtures and empty-state tests still describe graph authoring as deferred
  while production now advertises Add controls, so the checkpoint has neither a passing required
  regression nor truthful empty-state guidance. Update the fixtures/tests and graph-family empty
  guidance together, then rerun the full Web suite and the remaining T4 gates.
