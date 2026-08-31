# Task 24.2 — Durable Manual-Organize Intent, Bounded Selection, and Validated Choices

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 24.2
Parent Slice: 24 — Files / Media Detail and Manual Organize
Status: READY FOR B REVIEW
Task Base: b24e4c107d61c053d3a93e31dc95d9e2e2c4dec6
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the durable manual-organize intent and bounded selection portion of Slice Required Outcome
RO-2, including the choice and configuration-binding portion of RO-7: an authenticated operator can
start manual work from one File/Media detail or a bounded Files selection, see the exact immutable
runtime configuration snapshot pinned to that work, keep configured defaults or choose only valid
per-item overrides, and reload the same auditable durable state without editing Active configuration
or supplying arbitrary paths, operations, or provider payloads.

The user journey for this Task is:

```text
File detail or bounded Files selection
-> create manual intent
-> inspect pinned snapshot and item choices
-> keep defaults or choose a validated compatible option
-> persist and reload the intent
-> continue to a later Preview or recover from a correctable validation failure
```

Preview generation, exact plan persistence, stale Preview invalidation, execution authority and real
mutation are later Tasks in this Slice.

## Why This Task Exists

Slice 24.1 now provides the bounded File/Media explanation and inbound navigation needed to choose
the next action, but there is no durable operator-owned manual-organize object that records exactly
which indexed source identities were selected, which immutable runtime configuration snapshot owns
the work, or which normalized choices are intended for each item. Existing CLI and pipeline entry
points are broader processing controls and must not be reused as an implicit free-form manual plan.

This is the largest reasonable next unit because it establishes the admission and choice contract
that a later Preview can consume without guessing the source, configuration, policy ownership or
operator decision. It belongs inside the current Slice because it completes the manual-work entry
and selection outcome while preserving the existing managed configuration, FileIndex, recognition,
metadata, naming, classification, organize-policy, RBAC, audit and Task authorities.

## Implementation Scope

Implement one coherent vertical intent/selection journey:

```text
Domain contracts
-> restart-safe SQLite persistence and migration
-> shared manual-organize application service
-> authenticated versioned API
-> Operator Web entry, choices, confirmation and reload
-> automated validation, concurrency, RBAC and safety tests
```

- Define a provider-neutral durable manual-organize intent with a stable identity, bounded item set,
  source FileIndex identities, immutable configuration snapshot ID/digest, lifecycle/version
  information, per-item choice state, actor/audit attribution and bounded failure/recovery state.
  The source identity must retain the exact indexed Storage, ResourceLibrary and relative path
  relationship needed to reject stale or ambiguous selection.
- Create intent from one File/Media detail or a bounded Files selection only after authenticated
  permission checks and FileIndex resolution. Reject missing, stale, duplicate, ambiguous,
  over-limit or cross-authority selections without creating a misleading partial intent.
- Resolve and pin the exact runtime-consumable Active configuration snapshot through the existing
  configuration authority. Store and display its immutable identity and digest; fail closed when
  the snapshot is unavailable, corrupt, or no longer matches the runtime resolver. Never fall back
  to a JSON file, a later Active revision, or a process-local draft.
- Project only enabled, configured and compatibility-checked choices under the pinned snapshot:
  configured RecognitionTypes, normalized Metadata identities or existing candidate/review
  references, and Naming/Classification/Organize policy identities. Keep configured defaults
  available and allow per-item overrides only through normalized IDs/references accepted by the
  application service.
- Validate choice combinations against the pinned RecognitionType policy and source/evidence state.
  Preserve RecognitionType independently from downstream policies, including RecognitionType C
  remaining C while it uses downstream Naming/Classification/Organize policy A. Reject disabled,
  deleted, incompatible, cross-snapshot, arbitrary-path, arbitrary-operation and raw-provider
  payload input.
- Persist creation, selection and choice changes with optimistic concurrency and deterministic
  ordering. A failed validation or concurrent update must leave the previous durable intent
  unchanged and return the current version plus a concrete refresh/reopen/cancel next action.
  Audit accepted changes atomically with the affected intent state using the existing redacted audit
  authority; do not mutate Active configuration as a side effect.
- Expose the same application projection through API and Web. The Web must provide an entry from
  File detail and bounded Files selection, show pinned configuration and per-item choices/status,
  require explicit confirmation for creating or changing the intent, show success after reload, and
  show item-specific failure/recovery without hiding unaffected selected items.
- Keep this journey side-effect free with respect to media operations: no Storage mutation, no
  OrganizerExecutor call, no Provider construction/request, no plan execution, no execution
  authorization, and no new Preview result. Existing FileIndex and persisted evidence/configuration
  reads may be used for validation and option projection.
- Update architecture/operator documentation only where required to describe the new CURRENT
  manual-intent boundary. Do not change the Slice Contract, Required Outcomes, Required Surfaces,
  Safety Invariants, Roadmap boundary, or Explicitly Deferred scope.

## Acceptance Criteria

- [ ] An authenticated operator with the required manual-work permission can start intent from one
      File/Media detail and from a bounded Files selection; an unauthorized, missing, stale,
      ambiguous, duplicate or over-limit source selection is rejected with no partial intent.
- [ ] The durable intent binds every selected item to its exact indexed source identity and
      records a stable version, actor and bounded per-item state. Restart/reopen returns the same
      selection and choices in deterministic order.
- [ ] Intent creation resolves one runtime-consumable immutable Active configuration snapshot and
      persists its exact ID and digest. Missing, corrupt, changed or non-runtime-consumable
      configuration fails closed and never falls back to JSON, Draft or a later Active revision.
- [ ] The API and Web show the pinned snapshot identity/digest, configured defaults, available
      normalized option references and each selected item's current choice/status; no raw Provider
      DTO, credential, private configuration, arbitrary path or unconfigured policy is exposed.
- [ ] Keeping defaults and selecting per-item overrides both work through the shared application
      service. RecognitionType, Metadata identity and Naming/Classification/Organize policy
      combinations are validated against the pinned snapshot and source/evidence state.
- [ ] RecognitionType C remains C throughout intent creation, option projection, override
      persistence and reload while downstream Naming/Classification/Organize policy A remains
      visibly owned by A.
- [ ] Disabled, removed, incompatible, cross-snapshot, malformed, duplicate or unauthorized
      choices are rejected with a bounded explanation and a safe refresh/reopen/cancel recovery
      action. A failed update does not overwrite a prior valid item or sibling item.
- [ ] Optimistic concurrency rejects stale intent versions and duplicate/concurrent writes, returns
      current durable state, and does not silently merge conflicting operator decisions.
- [ ] Accepted intent/selection/choice changes and their actor attribution are audited atomically
      with the corresponding SQLite state; Active configuration remains byte-for-byte unchanged.
- [ ] A bounded mixed selection preserves independent per-item choice/status/error state and one
      invalid item does not erase, block diagnosis of, or rewrite valid siblings.
- [ ] Opening, refreshing or reviewing manual intent performs no Storage mutation, Provider
      request, OrganizerExecutor call, Preview execution, plan persistence or execution-authority
      creation. Real media mutation remains impossible within this Task.
- [ ] API and Web use the same application projection, RBAC, validation, concurrency and recovery
      semantics, and all visible responses remain bounded, deterministic and secret-free.
- [ ] All T4 Required Tests pass, `config/alist.json` remains ignored/untracked/unstaged, no
      existing safety regression is weakened, and the checkpoint contains only this Task's coherent
      implementation and completion report.

## Required Tests

Run and report every command below with temporary SQLite databases, temporary Local roots and
fake/in-memory ports only. No production Storage, Provider credentials or user media is permitted.

1. Focused manual intent, selection, choice validation, RBAC, concurrency, migration, audit and
   zero-side-effect coverage:

   ```bash
   .venv/bin/python -m unittest tests.test_manual_organize_intent
   ```

   Cover single and bounded batch entry, stale/missing/ambiguous sources, exact Active snapshot
   pinning, default and per-item choices, Type C with downstream policy A, invalid combinations,
   optimistic concurrency, atomic rollback, restart/reload, redaction, and spies that fail on
   Storage mutation, Provider access, plan/execution, or authorization creation.

2. Directly affected detail, Files, configuration, task and API/Web regressions:

   ```bash
   .venv/bin/python -m unittest \
     tests.test_file_media_detail \
     tests.test_file_catalog \
     tests.test_file_catalog_api \
     tests.test_operator_ui \
     tests.test_configuration_snapshot \
     tests.test_configuration_management \
     tests.test_task_persistence \
     tests.test_execution_authorization \
     tests.test_file_recognition_request \
     tests.test_file_metadata_re_match \
     tests.test_file_replan_request
   ```

3. Complete offline regression:

   ```bash
   .venv/bin/python -m unittest discover -s tests
   ```

4. Quality, safety, configuration and dependency gates:

   ```bash
   .venv/bin/ruff format --check .
   .venv/bin/ruff check .
   .venv/bin/python -m compileall -q mediaflow tests scripts
   .venv/bin/python -m pip check
   .venv/bin/mediaflow --config config/strategy.example.json config validate
   .venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
   test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"
   git diff --check
   ```

5. Build and isolated installed-wheel smoke test because this Task adds a persisted operator
   workflow and may advance the runtime schema:

   ```bash
   mediaflow_release_dir=$(mktemp -d /tmp/mediaflow-task-24.2-release.XXXXXX)
   .venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w "$mediaflow_release_dir"
   .venv/bin/python scripts/wheel_smoke_test.py "$mediaflow_release_dir"/mediaflow-*.whl
   ```

Before checkpointing, inspect `git status --short`, the complete Task Base..Head diff and exact
manifest; confirm no deleted/weakened tests, hidden skips, unrelated files, secrets/private paths,
or tracked/staged `config/alist.json`.

## Non-goals

- Generating or persisting a new manual Preview/OrganizePlan, plan explanation or stale Preview
  invalidation (RO-3/RO-4).
- Granting or consuming execution authority, real execution admission, OrganizerExecutor calls,
  Storage mutation, overwrite/delete/cleanup, source/target reconciliation or new recovery
  execution semantics (RO-5/RO-6).
- Replacing FileIndex, managed configuration, Recognition/Metadata/Naming/Classification/
  Organize policy authorities, Task/TaskItem/Result, RBAC or audit with parallel models.
- Calling TMDB or another Provider, accepting raw Provider payloads, editing Active configuration,
  accepting arbitrary source/destination paths or arbitrary operation choices.
- Provider switching, playback/media-server catalog work, automation scheduling, notifications,
  or anything Explicitly Deferred by `SLICE.md`.
- Work outside the parent Slice Contract, the next Task or next Slice, optional proof/copy polish,
  P2 cleanup, or unrelated refactoring.

## Developer Completion Report

### Changed Files

- `mediaflow/domain/manual_organize.py`: bounded immutable intent, source identity, normalized
  choice/configuration option and audit contracts with Type C policy ownership preserved.
- `mediaflow/domain/manual_organize_intent.py`: compatibility import for the domain boundary.
- `mediaflow/application/manual_organize.py`: shared authenticated-service-facing intent admission,
  managed snapshot pinning, default/override validation, source/concurrency checks, source-linked
  metadata authority validation and recovery projections without Storage/Provider/Task/execution
  side effects.
- `mediaflow/application/manual_organize_intent.py`: compatibility import for the application
  service.
- `mediaflow/infrastructure/sqlite_runtime.py`: additive restart-safe manual intent/item/audit
  tables and atomic optimistic-concurrency persistence on the existing runtime repository.
- `mediaflow/interfaces/service_api.py`: versioned bounded manual-intent API routes, aliases, RBAC,
  exact request allowlists and redacted error/recovery projections.
- `mediaflow/interfaces/operator_ui.py`: Files selection and File detail entry points, explicit
  create/choice/cancel confirmations, pinned snapshot and per-item choice/reload views.
- `mediaflow/domain/security.py`: explicit manual-organize permission name as a backwards-compatible
  alias of the existing bounded DryRun operator permission.
- `tests/test_manual_organize_intent.py`: focused durable selection, snapshot, Type C, disabled and
  malformed choice, concurrency, audit, cancellation, RBAC and zero-side-effect coverage.

### Implemented

- Created a bounded (maximum 100) durable manual-organize intent from one indexed File or a Files
  selection, retaining exact Storage/ResourceLibrary/path/file facts and deterministic item order.
- Resolved managed Active runtime configuration only, persisted its exact revision ID/digest and
  normalized enabled options, and rejected JSON bootstrap/process-local authority, unavailable or
  corrupt snapshots without fallback.
- Applied configured defaults and validated allowlisted per-item choices, including RecognitionType
  C remaining C while its downstream Naming/Classification/Organize policy ownership remains A.
- Grounded metadata identity overrides in the selected source's exact durable Result/evidence or
  source-linked bounded metadata review candidates/resolutions; unlinked or mismatched identities
  now fail closed before persistence with a bounded recovery action.
- Added atomic SQLite creation, choice update, cancellation and audit writes with intent/item
  optimistic concurrency and durable reload projections.
- Added API and Operator Web entry, review, normalized metadata identity input, reload and
  item-specific bounded recovery messaging; no Preview, Plan, Task, Provider, execution authority
  or Storage mutation is reachable from this boundary.

### Tests and Results

- `.venv/bin/python -m unittest tests.test_manual_organize_intent` — PASS (7 tests).
- `.venv/bin/python -m unittest tests.test_file_media_detail tests.test_file_catalog
  tests.test_file_catalog_api tests.test_operator_ui tests.test_configuration_snapshot
  tests.test_configuration_management tests.test_task_persistence tests.test_execution_authorization
  tests.test_file_recognition_request tests.test_file_metadata_re_match
  tests.test_file_replan_request` — PASS (134 tests).
- `.venv/bin/python -m unittest discover -s tests` — PASS (967 tests, 7 skipped; existing
  ResourceWarning output only).
- `.venv/bin/ruff format --check .` — PASS (331 files already formatted).
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS (`No broken requirements found`).
- `.venv/bin/mediaflow --config config/strategy.example.json config validate` — PASS.
- `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` — PASS.
- `test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"` — PASS (no matches).
- `git diff --check` — PASS.
- `.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w <temporary directory>` and
  `scripts/wheel_smoke_test.py <wheel>` — PASS (schema 27 backup/rehearsal/restore/preflight).
- B reproduction with an unlinked or mismatched metadata identity — PASS (returns
  `metadata_unverified`, preserves intent version and does not persist a choice).

### Decisions

- Manual intent tables are additive and idempotent on the existing runtime repository; the public
  schema marker remains `27` so existing migration/backup consumers and compatibility tests retain
  their established marker while older databases gain the new tables on open.
- The explicit `MANAGE_MANUAL_ORGANIZE` permission name aliases the existing operator `submit_dry_run`
  authority; this task admits analysis-only intent and never grants or consumes execution authority.
- Persisted options and choices are allowlisted normalized projections. Runtime policy mappings are
  authoritative, so a C RecognitionType cannot be rewritten as A merely because downstream A
  policies are reused.
- Metadata overrides use only read-only repository authorities: source-keyed normalized Results,
  bounded PipelineEvidence metadata identities/candidates, and source-linked metadata review
  candidates/resolutions. Candidate references are deterministic `reviewId:rank` (with a slash
  compatibility form); no Provider is constructed or queried.

### Remaining In-Slice Work

- Manual Preview/exact plan persistence and stale-evidence invalidation.
- Exact reviewed-plan execution admission, one-shot authority, OrganizerExecutor mutation, results
  and checkpoint-aware post-failure recovery.

### Risks / Deviations

- No production Provider, Storage or user media was used; all focused checks use in-memory FileIndex
  and temporary SQLite roots. The full suite has 7 existing skipped external/acceptance tests.
- Metadata identity input that is not represented by source-linked durable evidence is now rejected
  even when its policy fields are otherwise valid; operators must use the linked Result/evidence or
  review candidate authority and the returned refresh/retry action.
- The full suite emits existing ResourceWarning messages for unrelated unclosed SQLite handles, but
  completed successfully and introduced no new skip or failure.
- The runtime schema marker remains 27 because this is an additive table migration and changing the
  marker breaks established migration/backup compatibility checks; the wheel smoke test confirms
  backup/rehearsal/restore/preflight behavior.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: be395a3bd66a23a52e0dec475478a54d0625a087
```

## B Review Result

```text
Reviewed: b24e4c107d61c053d3a93e31dc95d9e2e2c4dec6..2bda4b6e24bebbfb3ae2e30b53d1c825f767a681
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Metadata identity overrides are not validated against the selected source's durable evidence or
  an existing source-linked candidate/review. `mediaflow/application/manual_organize.py:811-900`
  explicitly discards the `record` argument, so a choice such as
  `{"provider":"tmdb","providerId":"999999","mediaType":"movie","title":"Unverified"}` is accepted
  and persisted for a file with no matching Result, candidate or review. Reproduction with the
  temporary SQLite fixture printed
  `UNEXPECTED_ACCEPT {'provider': 'tmdb', 'providerId': '999999', 'mediaType': 'movie', 'title': 'Unverified'}`.
  Validate metadata choices against the exact source-linked normalized Result/evidence or a bounded
  candidate/review reference authority, reject unlinked arbitrary identities with a bounded
  recovery response, and add focused negative application/API tests without constructing a Provider
  or accepting raw Provider payloads.
