# Task 33.4 — V2 scheduled Automation definition and occurrence journey

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 33.4
Parent Slice: 33
Status: PLANNED
Task Base: 2be1eb0b99d64720aeba81f86eab052788121dea
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 33 RO-5 and the applicable RO-1/RO-2/RO-7/RO-8 boundary: an authorized operator can
use V2 to discover and manage a bounded Automation Task Definition, distinguish editable Draft from
the immutable Active snapshot, validate and Preview the exact definition, checked-activate only its
owned configuration change, explicitly grant or revoke scoped unattended authority, and inspect
schedule/occurrence history with linked Job, Task and Result state.

## Why This Task Exists

Tasks 33.1–33.3 completed the shared Operations workspace, durable Task/Job observation, bounded
Scan/Preview and Web-native manual Organize journey. The Python Application/API and V1 surface
already implement Automation Task Definition lifecycle, exact zero-mutation Preview, managed
revision validation/checked activation, persistent grant/revocation, Scheduler occurrence fencing
and linked work/results, but V2 has no Automation routes, typed model, editor or recovery journey.

Automation is the largest remaining coherent business unit because definition editing, publication,
Preview, unattended authority and occurrence evidence are one safety chain: exposing only one link
would either be unusable or could misrepresent Draft/schedule state as execution authority.
Notification operation is a separate delivery lifecycle and remains the final independent Slice 33
unit.

## Implementation Scope

Deliver the existing Automation authority chain through one bounded vertical slice:

```text
Domain/Persistence (reuse) → Application projection → /api/v1 authority → typed Web → browser proof
```

- Reuse the existing `AutomationTaskDefinition`, managed Configuration revision, Automation Preview,
  unattended grant, Scheduler occurrence, AutomationJob, Task/TaskItem and Result stores and services.
  Do not create a parallel definition store, scheduler, execution pipeline or frontend-owned state
  machine.
- Add only the smallest backward-compatible Application/API projection or action metadata needed for
  V2 to discover the exact Active revision and an eligible owned Draft, render backend-authoritative
  permissions/readiness/versions, and invoke existing definition, validation, checked-activation,
  Preview, grant/revoke and occurrence behaviors. Existing API and V1 routes remain compatible.
- Add refresh-safe V2 Automation list, create/copy, detail/editor, Preview/detail/items and occurrence
  navigation under `/ui-v2/operations`. Link occurrences to the existing exact Job/Task detail and
  safe Library/Result context where authoritative evidence exists; do not require raw revision,
  grant, occurrence, Job or Task identifiers as ordinary entry inputs.
- Provide a forms-first bounded editor for name, enabled state, ResourceLibrary, relative source
  scope, run mode (`scan-only`, `scan-and-plan`, `automatic-organization`), item limit and exactly one
  interval or Cron/timezone schedule. Options and constraints come from authoritative projections;
  the form cannot select per-file Provider, policy, destination or Storage operation.
- Compose successor-Draft creation, optimistic create/edit/copy/enable/disable, validation and
  object-scoped checked activation. The surface must identify the exact Draft and Active snapshots,
  refuse stale/concurrent or unrelated configuration activation, and never label a saved or
  validated Draft as Active.
- Compose the exact zero-mutation Automation Preview, including bounded item paging, independent
  findings/blockers, configuration/definition identity, scope, targets/conflicts/capabilities and
  grant eligibility. Editing, copying, enabling/disabling or changing the referenced revision makes
  older Preview evidence visibly stale and non-authoritative.
- Compose explicit unattended grant and revoke actions for the exact Active definition and eligible
  Preview. The browser does not receive or ask the operator to supply raw grant authority; schedule
  enablement, validation, activation and Preview remain distinct from grant authority. Destructive
  permissions are not inferred.
- Show schedule/timezone/due state, bounded occurrence history and each occurrence's pinned snapshot,
  admission/Job/Task/Result state, independent failures and safe next action. Reading or navigating
  must not emit an occurrence, submit work or mutate Storage.
- Use central typed entities, API helpers and TanStack Query boundaries. Components perform no raw
  `fetch`, cache no authority, derive no permission from hidden controls, and never automatically
  retry a mutation after ambiguity, stale state, 401/403, conflict or malformed data.
- Extend the deterministic Playwright fake with secret-free Automation state and exact method/body
  assertions. Captured evidence excludes Bearer values, raw grant/revision digests, source
  fingerprints, private paths/endpoints, plans and provider payloads.
- If an additive persistence/schema change is genuinely necessary, make it forward-only,
  fail-closed, atomic and restart-tested using temporary copied fixtures.

Frozen for this Task:

- `SLICE.md`, `docs/roadmap.md`, canonical/stable requirements, product-experience and architecture
  authority text, including Slice Base and every A-owned Contract field.
- Notification/Webhook definition, test, activation and delivery operation; that is the next
  independent Slice 33 Task.
- General Configuration/Settings administration, arbitrary object lifecycle, revision comparison,
  evidence administration and import/export owned by Slice 35. The Automation surface may create
  and checked-activate only the narrow successor Draft needed for its owned definition and may hand
  general repair to the current V1 Configuration journey.
- Slice 34 review/recovery actions, failed-item retry, checkpoint continuation, Reprocess and
  uncertain-effect recovery. This Task shows durable state and links truthfully without imitating
  those actions.
- Provider, Storage, recognition, metadata, naming, classification, planning and conflict semantics;
  auth redesign; Node production serving; `config/alist.json` and private runtime state.

## Acceptance Criteria

- [ ] `/ui-v2/operations/automation` is a real list/entry surface linked from Operations and the
      actionable Dashboard; supported list, definition, editor, Preview and occurrence routes are
      refresh-safe, preserve bounded context and use the shared memory-only authentication return.
- [ ] The list/detail projection shows the exact immutable Active revision consumed by runtime and,
      when applicable, a distinct editable Draft with its optimistic version and validation state.
      Missing Active/Draft/runtime, read-only/forbidden and unavailable states offer only a valid
      successor-Draft or V1 Configuration handoff; no Draft is presented as Active.
- [ ] An authorized operator can create, copy and edit a definition and enable/disable its schedule
      through the bounded form. ResourceLibrary and source sub-scope, run mode, item limit, interval
      or Cron/timezone are validated server-side; the request cannot inject arbitrary Storage paths,
      per-file Provider/policy/destination/operation, grant authority or unknown fields.
- [ ] Every definition mutation is bound to the exact Draft revision and expected version. Stale or
      concurrent create/edit/copy/enable/disable is rejected atomically, preserves the winning
      revision and refreshes the operator to durable truth without automatic mutation replay.
- [ ] Validation is explicit and zero-mutation. Checked activation is a separate meaningful action,
      publishes only an eligible revision whose changes are confined to the owned Automation object
      boundary, reports the new exact Active identity, starts no Scan/Job/Task/occurrence, and never
      silently activates unrelated general-configuration changes.
- [ ] The operator can create and inspect a complete exact Automation Preview and page its items.
      Definition/revision/scope identity, selected and independently blocked findings, targets,
      conflicts, capabilities and next actions are visible and bounded; Preview performs zero
      Storage mutation and grants no execution authority.
- [ ] Editing/copying/enabling/disabling the definition or changing its configuration identity makes
      incompatible Preview evidence visibly historical/stale. A stale, incomplete, truncated,
      blocked or wrong-definition Preview cannot become grant eligibility.
- [ ] For an `automatic-organization` Active definition, an authorized operator can explicitly grant
      persistent unattended authority only after an eligible exact Preview and separately revoke it.
      Grant state is definition/scope/mode/snapshot/preview/principal/item-limit bound, audited and
      rechecked; no raw grant secret/identifier is an operator input, and enable/activation/Preview
      alone never authorizes mutation.
- [ ] Grant/revoke is optimistic and exact-object scoped. Stale revision/Preview, changed scope,
      insufficient permission, disabled/missing references, invalid mode, excessive limits or
      concurrent/repeated action fails closed before authority or media mutation; revocation prevents
      future mutation without rewriting completed effects.
- [ ] Definition detail shows truthful schedule type, timezone, enabled/due/next-run state and bounded
      occurrence history. Each occurrence preserves its pinned definition/configuration identity and
      links exact Job/Task/TaskItem/Result evidence already owned by Operations; list/detail reads do
      not emit work, probe adapters or call mutating Storage methods.
- [ ] Occurrence failures distinguish schedule/grant/snapshot/resource/Worker/queue/capability/
      conflict/item outcomes, retain successful siblings and give only a repair, fresh Preview,
      regrant, revoke, exact Operations follow-up, V1 Configuration handoff or Slice 34 recovery
      destination that is valid for the durable state. Uncertain effects are never advertised or
      submitted as safe automatic retry.
- [ ] Typed normalization fails closed on unknown/contradictory revision, status, permission,
      schedule, Preview, grant, occurrence, link or action transport data. Action paths use strict
      URI-safe object identities and exact owned routes/methods; components expose no executable
      control for malformed or mismatched documents.
- [ ] API/model/URL/DOM/console/audit/test artifacts contain no Bearer credential, grant secret,
      configuration digest, source fingerprint/occurrence identity, raw plan/provider payload,
      exception, secret value/reference resolution, private endpoint, adapter root or arbitrary
      absolute path.
- [ ] Backend regressions preserve Scheduler-only due detection, idempotent occurrence emission,
      immutable snapshot pinning, Worker claim/fencing, per-item outcomes, current permission and
      grant rechecks at every mutation boundary, OrganizerExecutor-only Storage mutation, no
      overwrite/delete implication, no link fallback, no uncertain replay and RecognitionType C.
- [ ] V1 `/ui`, existing Automation/configuration/API/CLI clients, Tasks 33.1–33.3 routes and
      Python-only production serving remain compatible; no browser scheduler, API background thread,
      second execution model or Node runtime service is introduced.
- [ ] Component/router and built-artifact evidence covers Active/Draft distinction, create/copy/edit,
      interval and Cron/timezone, validate, checked activate, exact Preview, grant/revoke, occurrence
      and linked-work navigation, permissions, stale/concurrent/malformed/401/403/unavailable states,
      exact methods/bodies, no replay and keyboard-usable narrow/wide layouts.
- [ ] All T4 commands below pass with actual totals/skips/unavailable gates reported. The checkpoint
      contains only this Task plus its Developer report; tests/assertions are not deleted or
      weakened, skips are not hidden and unrelated files are preserved.

## Required Tests

Run and report all of the following from the repository root:

```text
python3 scripts/check_governance.py
env -u NODE_ENV npm --prefix web ci
npm --prefix web run format:check
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web run test -- --run
npm --prefix web run build
npm --prefix web run test:e2e -- automation.spec.ts operations.spec.ts deep-link.spec.ts
npm --prefix web run test:e2e
.venv/bin/python -m unittest tests.test_v2_automation_operations
.venv/bin/python -m unittest tests.test_automation_task_definition tests.test_automation_task_definition_preview tests.test_automation_unattended_grant tests.test_automation_preview_grant_gate tests.test_automation_definition_occurrence tests.test_automation_definition_execution tests.test_automation_authorized_execution_matrix tests.test_automation_admission tests.test_automation_job_fencing tests.test_automation_api tests.test_cron_scheduler tests.test_configuration_objects tests.test_operations_workspace tests.test_api_security tests.test_v2_ui
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/mediaflow --config config/strategy.example.json config validate
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
git diff --check
python3 scripts/docker_release_security_smoke_test.py
```

Create `tests/test_v2_automation_operations.py` and built-artifact browser file
`web/tests/e2e/automation.spec.ts`; add focused typed-entity and router/component tests under the
existing Web boundaries. Docker may be `UNAVAILABLE` only with the observed environmental reason
and must not be inferred as passing.

Focused evidence must prove Draft/Active separation; exact optimistic definition mutations; bounded
interval and Cron/timezone validation; explicit zero-mutation validation/Preview; Preview staleness;
object-scoped checked activation; grant eligibility, binding, revoke and audit; schedule enablement
without authority; idempotent occurrence emission/restart/concurrency; immutable pins and exact
Job/Task/Result links; current-permission and authority recheck; per-item failure isolation;
OrganizerExecutor-only mutation; redaction; exact request methods/bodies; malformed response
fail-closed behavior; no automatic mutation replay; RecognitionType C and V1 compatibility. Use only
temporary SQLite, fake/in-memory Storage/Provider/Worker/Scheduler state and local browser fakes.

If schema changes, add forward-migration, newer-schema rejection, atomic failure and API/Worker/
Scheduler restart tests against temporary copied fixtures. Before checkpointing, inspect and report
`git status --short`, the complete Task Base..Head diff, changed-file manifest, test deletion/rename/
skip/assertion changes and tracked/private configuration. `config/alist.json`, `node_modules`, build
reports, credentials and unrelated files must not enter the checkpoint.

## Non-goals

- Notification/Webhook definition, exact-revision test, activation, delivery inspection or delivery
  recovery; that is the next independent Slice 33 Task.
- General Configuration/Settings administration, arbitrary managed-object editing, revision
  comparison/evidence, import/export or activation outside the Automation object-scoped checked
  flow; these are owned by Slice 35.
- Media review decisions, conflict resolution, Reprocess, checkpoint continuation, failed-item retry,
  reconciliation or uncertain-effect recovery owned by Slice 34.
- New scheduler semantics, manual occurrence emission/run-now, a workflow designer, distributed
  scheduling, new Providers, policy/destination/operation selection, arbitrary paths/bulk execution,
  rollback/undo or automatic uncertain replay.
- Replacing API-principal Bearer authentication, browser credential persistence, built-in identity,
  SSR/BFF/Node serving, V1 retirement, optional analytics/export, copy polish, P2/P3 cleanup or
  unrelated refactoring.

## Developer Completion Report

### Changed Files

- `mediaflow/application/configuration_snapshot.py` — `ManagedConfigurationService` gains two
  read-only Draft helpers: `open_draft_revisions()` (newest-first draft/validated revisions, never
  Active or superseded) and `latest_open_draft_containing(section, object_id)`, so the V2 journey
  discovers the eligible owned Draft from the existing managed-configuration store.
- `mediaflow/interfaces/service_api.py` — the smallest backward-compatible projection surface:
  - new read-only operator routes under `/api/v1/operations/automation/task-definitions…`
    (definitions page, definition detail, per-definition `draft` document, `occurrences` page,
    exact `previews/{previewId}` document and paged `items`) plus one new mutation,
    `POST …/activate-draft`, which composes the existing read-only Storage/strategy/destination
    checks server-side so the browser never handles a revision digest;
  - operator documents (`_automation_definition_operator_document`,
    `_automation_preview_operator_document`, `_automation_occurrence_operator_document`) that are
    stripped of every `*Fingerprint`/`*Digest`/`plan` key, carry bounded `activeConfiguration`,
    `draftState`, `grantEligibility` and permission-aware exact `actions` transports
    (`isSafeActionPath`/exact-owned binding semantics identical to the organize journey);
  - `_automation_grant_eligibility()` extracted from the existing grant-state route (behavior
    preserving) and reused by the detail and preview projections;
  - the raw `/api/v1/automation/*`, `/api/v1/configuration/*` documents and every existing route
    are untouched for V1 clients (proved by a dedicated compatibility test).
- `web/src/entities/operations/action-transport.ts` — new shared fail-closed action-transport
  module (URI-safe segment rule, the one intentional `{itemId}` template segment, exact owned
  route binding, `objectBound` collection actions, `parameter`-pinned `*` segments, PUT support).
- `web/src/entities/operations/organize.ts` — refactored onto the shared transport module with
  identical exports and behavior (organize entity + component suites pass unchanged).
- `web/src/entities/operations/automation.ts` + `automation.test.ts` — typed fail-closed models
  and normalizers for definitions, Draft state, grants, eligibility, previews/items, occurrences
  and the activation result; closed enums, contradiction checks, exact transport binding.
- `web/src/shared/api/api-client.ts` — Automation reads (bounded `OperationsRead` results, thrown
  `OperationsApiError` for 401/403/malformed) and mutations (bounded result objects, exact
  methods, `encodeURIComponent` + `isSafeIdentifier` guards, no automatic retry).
- `web/src/features/operations/automation-query.ts` + six pages — `AutomationListPage`,
  `AutomationNewPage`, `AutomationDetailPage`, `AutomationEditorPage`, `AutomationPreviewPage`,
  `AutomationOccurrencesPage`, all on the shared `AuthorizedReadBoundary`/`StatusBanner`/
  `RefreshControl` shell contract with backend-authoritative availability only.
- `web/src/routes/router.tsx`, `web/src/shared/navigation/destination-model.ts(+.test.ts)` — six
  refresh-safe routes registered centrally; `dynamicInstancePath` now requires exactly the
  declared number of bounded identity segments (unknown deeper routes stay not-found; traversal,
  placeholder and unsafe segments never resolve).
- `web/src/features/operations/OperationsLanding.tsx`, `DashboardView.tsx` — Operations and
  Dashboard entries to `/operations/automation` as bounded navigation aids.
- `web/tests/fake-server.mjs` — deterministic session-scoped Automation state, operator-document
  mirrors, exact routes (including successor/save/validate/activate-draft, grant binding and
  hostile/misbound preview fixtures), `POST /__test__/reset-automation`, evidence fields.
- `web/tests/e2e/automation.spec.ts` — nine built-artifact journey regressions.
- `tests/test_v2_automation_operations.py` — the full-journey Python proof (8 tests).
- `TASK.md` — this report.

### Implemented

1. **Backend-authoritative Automation projections (RO-5, RO-1/RO-2/RO-7/RO-8 boundary).** The V2
   journey consumes bounded, digest-free operator documents: the list shows the exact immutable
   Active identity plus a distinct open successor Draft with its optimistic version and
   validation state; detail adds schedule/timezone/due state, occurrence summary with attention
   rows, the unattended grant state and the shared read-only admission eligibility. Missing
   Active/Draft, read-only and unavailable states render as unavailable-with-reason plus a valid
   successor-Draft or V1 handoff; a Draft is never labelled Active.
2. **Draft → Validate → checked Activate.** Successor-Draft creation, optimistic save (PUT bound
   to the exact revision version), explicit zero-mutation validation and one meaningful checked
   activation are separate advertised actions. Checked activation composes the existing read-only
   Storage/strategy/destination checks server-side (the browser supplies only the Draft's
   optimistic version, never a digest), reports the new exact Active identity and starts no Scan,
   Job, Task or occurrence (proved by test). Stale/concurrent mutations fail 409 atomically with
   the winning revision preserved and no replay.
3. **Exact zero-mutation Preview and staleness.** The Preview page shows definition/revision
   identity, counts, boundary errors and paged per-item findings (targets, conflicts,
   capabilities, blockers, RecognitionType evidence — C stays C). Editing/activating the
   definition makes older Previews visibly historical (`current=false`, stale reason); the grant
   action disappears and a grant submission for the stale Preview is rejected 409 before any
   authority is created. Zero mutation is proved with recording Storage doubles.
4. **Unattended grant/revoke.** Grant is one explicit confirmed operator action for an
   `automatic-organization` Active definition, bound to the exact eligible Preview
   (`previewId` is mandatory server-side), principal/permission rechecked, audited and
   revocable; no raw grant secret or identifier is an operator input, and schedule
   enablement/validation/activation alone never authorize mutation. Revocation is exact-object
   and never rewrites completed effects.
5. **Occurrences.** The occurrence history preserves each occurrence's pinned
   definition/configuration identity and links the exact Job/Task evidence owned by Operations
   through backend-advertised transports; reads are GET-only and never emit an occurrence
   (proved by counting Jobs across reads).
6. **Shared safety machinery.** The action-transport extraction gives the whole codebase one
   exact-route/URI-safe implementation; Automation actions reuse it, and the destination model
   now resolves exactly the declared number of bounded identity segments so deep-link
   continuation works for the two-segment Preview route while unknown deeper routes stay
   not-found.

### Tests and Results

```text
python3 scripts/check_governance.py                                                — PASS
env -u NODE_ENV npm --prefix web ci                                                — PASS
npm --prefix web run format:check                                                  — PASS
npm --prefix web run typecheck                                                     — PASS
npm --prefix web run lint                                                          — PASS
npm --prefix web run test -- --run                                                 — PASS (352/352, 32 files)
npm --prefix web run build                                                         — PASS
npm --prefix web run test:e2e -- automation.spec.ts operations.spec.ts deep-link.spec.ts
                                                                                   — PASS (53/53)
npm --prefix web run test:e2e                                                      — PASS (104/104)
.venv/bin/python -m unittest tests.test_v2_automation_operations                   — PASS (8/8)
.venv/bin/python -m unittest tests.test_automation_task_definition tests.test_automation_task_definition_preview tests.test_automation_unattended_grant tests.test_automation_preview_grant_gate tests.test_automation_definition_occurrence tests.test_automation_definition_execution tests.test_automation_authorized_execution_matrix tests.test_automation_admission tests.test_automation_job_fencing tests.test_automation_api tests.test_cron_scheduler tests.test_configuration_objects tests.test_operations_workspace tests.test_api_security tests.test_v2_ui
                                                                                   — PASS (267/267)
.venv/bin/python -m unittest discover -s tests                                     — 1505 tests, 6 FAIL / PRE-EXISTING / UNRELATED, 7 SKIP
.venv/bin/ruff format --check .                                                    — PASS (308 files)
.venv/bin/ruff check .                                                             — PASS
.venv/bin/python -m compileall -q mediaflow tests scripts                          — PASS
.venv/bin/python -m pip check                                                      — PASS
.venv/bin/mediaflow --config config/strategy.example.json config validate          — PASS
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate — PASS
git diff --check                                                                   — PASS
python3 scripts/docker_release_security_smoke_test.py                              — PASS
```

### Decisions

- **Operator projections instead of reshaping existing documents.** V1 renders
  `definitionFingerprint`/`configuration.digest` from the raw documents, so the V2 surface gets
  new read-only routes whose documents are stripped of every fingerprint/digest/plan key by one
  recursive deny-list filter; the raw surfaces stay byte-compatible for V1 clients and a
  dedicated test pins both sides.
- **One new mutation, everything else reused.** Draft edit/validate/activate flow through the
  existing managed-configuration routes; the single addition (`activate-draft`) exists because
  the existing checked-activation chain requires `expectedDigest` per Storage check, which would
  force the browser to handle a revision digest. The new route keeps the digest server-held —
  the same authority boundary the organize admission uses.
- **Grant requires the explicit `previewId`.** The grant route refuses to resolve the latest
  Preview implicitly (409 `unattended_execution_preview_required`); the V2 pages submit the
  reviewed Preview's identity from the eligibility projection, so stale or wrong-definition
  Previews can never become authority.
- **Shared action-transport module.** The 33.3 exact-route machinery moved to
  `action-transport.ts` and was extended (PUT methods, `objectBound` collection actions,
  `parameter`-pinned `*` segments); organize.ts keeps its exports and its suites pass unchanged,
  so Automation cannot drift from the fail-closed binding semantics B required in Task 33.3.
- **Destination model: exact declared segment count.** `dynamicInstancePath` resolves a concrete
  instance only when it carries exactly the declared number of bounded URI-safe identity
  segments — this makes the two-segment Preview deep link work while preserving the pinned
  "unknown Operations route renders not-found" contract.
- **Mutation responses are V1 contracts.** Read surfaces are digest-free; mutation responses of
  reused routes keep their existing shape and the typed normalizers extract only bounded fields
  (identity + version), so no digest reaches the model or DOM.

### Remaining In-Slice Work

- Notification/Webhook definition, exact-revision test, checked activation, delivery inspection
  and delivery recovery remain the next independent Slice 33 Task.
- Slice 34 owns media review/recovery actions (checkpoint continuation, Reprocess, uncertain-
  effect recovery); Automation shows durable state and truthful destinations only.
- Slice 35 owns general Configuration administration; the Automation surface composes only the
  narrow successor-Draft flow for its owned object.

### Risks / Deviations

- 6 full-discovery failures are `FAIL / PRE-EXISTING / UNRELATED`, the identical set reported by
  every previous Task 33 round: `test_storage_list_does_not_construct_or_connect`,
  `test_storage_check_is_read_only_and_isolates_failures`,
  `test_credential_check_is_redacted_config_only_and_reports_missing`,
  `test_legacy_credential_status_is_supported_without_secret_output`,
  `test_runtime_configuration_and_final_analyze_cli`,
  `test_scan_cli_needs_no_path_or_metadata_token`. They are caused by this workspace's ignored
  local `.mediaflow/` runtime state being resolved instead of the tests' temporary bootstrap
  documents, not by this Task. The focused suites that bind to the changed code (267 + 8 Python
  tests, 352 frontend unit tests, 104 built-artifact tests) pass.
- Running the T4 suite touches the ignored local `.mediaflow/` runtime state only. No tracked
  file, media file or credential was touched; `config/alist.json` does not exist in this
  workspace and nothing private entered the checkpoint. `node_modules/` remains untracked and
  outside the checkpoint.
- The checkpoint contains only this Task plus its report; the diff is additive (no test deleted,
  renamed, skipped or weakened; the two modified existing tests — the destination-model contract
  and its new two-segment assertions — strengthen the pinned safety property).

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: PENDING_COMMIT
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```
