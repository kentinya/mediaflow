# Task 33.4 — V2 scheduled Automation definition and occurrence journey

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 33.4
Parent Slice: 33
Status: READY FOR B REVIEW
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

- `mediaflow/interfaces/service_api.py` — checked activation now enforces the exact
  definition-identity boundary and the Operations list applies one deterministic combined page
  limit. `_automation_definition_activate_checked_draft` calls the new
  `_require_automation_definition_only_change`, which compares the Active and Draft
  `automationTaskDefinitions` sections as exact id → entry maps and fails closed
  (409 `automation_activation_definition_scope`, digest-free) when any definition other than the
  reviewed one is added, removed or modified; malformed sections (non-object entry, non-string id,
  duplicated id) fail closed under `automation_activation_out_of_scope` because an unverifiable
  boundary is never activated. Creating or copying a definition therefore activates only when that
  exact new/copied definition is the sole Automation change. The Operations list
  (`AUTOMATION_DEFINITIONS_PAGE_LIMIT = 100`) fills the page with Active definitions in document
  order first, lets Draft-only definitions take the remaining capacity, and reports truthful
  `total` (all Active + all distinct Draft-only) and `truncated` semantics after the merge, so the
  merged response can never exceed the frontend normalizer contract again.
- `web/src/features/operations/AutomationListPage.tsx` — the list renders the truthful
  combined-page bound ("Showing the first N of M definitions; the bounded list excludes the rest.")
  whenever the backend reports a truncated merged page.
- `tests/test_v2_automation_operations.py` — four new real-API regressions:
  `test_activation_rejects_sibling_definition_riding_in_same_draft` (edited target plus a sibling
  added, removed, or modified in the same Draft → 409 `automation_activation_definition_scope` with
  Active preserved, sibling never published, Drafts still open, and the same reviewed edit alone
  still activating exactly), `test_created_definition_activates_only_as_sole_automation_change`
  (created definition plus a sibling Active edit → 409; the sole-change Draft activates),
  `test_copied_definition_activates_only_as_sole_automation_change` (copied definition plus its
  source edit → 409; the sole-change copy activates), and
  `test_operator_list_boundary_stays_bounded_with_draft_only_definitions` (100 Active definitions
  built through the real one-definition-per-Draft journey plus one Draft-only definition → exactly
  100 items, `total: 101`, `truncated: true`, the Draft-only definition dropped from the page yet
  still reachable and honestly marked via its detail route). The existing
  create/copy journey now activates the created definition while it is the Draft's sole Automation
  change and copies into a fresh successor Draft.
- `web/src/entities/operations/automation.test.ts` — combined-boundary normalization coverage: a
  100-item page (99 Active + 1 draft-only) with `total: 101, truncated: true` normalizes, and 101
  items still fail closed.
- `web/src/features/operations/AutomationRouter.test.tsx` — component coverage that the list
  renders the truthful bound when the backend reports a truncated combined page.
- `TASK.md` — this report.

### Implemented

1. **Exact-object checked activation (blocker 1).** The section-level confinement could not see a
   second definition riding inside `automationTaskDefinitions`; the new exact-identity comparison
   can. For every definition id in either document, the reviewed definition is the only allowed
   difference: any other id that is added, removed, or byte-modified rejects activation with 409
   before any publication, preserving the Active configuration and the open Drafts. The
   create/copy case is covered by the same rule — the new or copied definition must be the sole
   Automation change in its Draft. Malformed sections fail closed.
2. **One deterministic combined list limit (blocker 2).** The merged Active + Draft-only page was
   previously bounded per source (100 + 100), so 100 Active + 1 Draft-only produced a 101-item page
   the frontend normalizer rejects. The page is now bounded by the one combined limit: Active
   definitions fill it first, Draft-only definitions take the remaining capacity, dropped
   definitions stay counted in a truthful `total` and flip `truncated`, and the response never
   exceeds the exact contract the frontend enforces.
3. **Truthful bounded list surface.** The V2 list states exactly what it shows and what it
   excludes when the merged page is truncated, and a dropped Draft-only definition remains
   reachable and visibly draft-only through its exact detail route.

### Tests and Results

```text
python3 scripts/check_governance.py                                                — PASS
env -u NODE_ENV npm --prefix web ci                                                — PASS (0 vulnerabilities)
npm --prefix web run format:check                                                  — PASS
npm --prefix web run typecheck                                                     — PASS
npm --prefix web run lint                                                          — PASS
npm --prefix web run test -- --run                                                 — PASS (359/359, 32 files)
npm --prefix web run build                                                         — PASS
npm --prefix web run test:e2e -- automation.spec.ts operations.spec.ts deep-link.spec.ts
                                                                                   — PASS (55/55)
npm --prefix web run test:e2e                                                      — PASS (106/106)
.venv/bin/python -m unittest tests.test_v2_automation_operations                   — PASS (17/17)
.venv/bin/python -m unittest tests.test_automation_task_definition tests.test_automation_task_definition_preview tests.test_automation_unattended_grant tests.test_automation_preview_grant_gate tests.test_automation_definition_occurrence tests.test_automation_definition_execution tests.test_automation_authorized_execution_matrix tests.test_automation_admission tests.test_automation_job_fencing tests.test_automation_api tests.test_cron_scheduler tests.test_configuration_objects tests.test_operations_workspace tests.test_api_security tests.test_v2_ui
                                                                                   — PASS (267/267)
.venv/bin/python -m unittest discover -s tests                                     — 1514 tests, 6 FAIL / PRE-EXISTING / UNRELATED, 7 SKIP
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

- **Exact identity maps over section equality.** The section-level check proves no other
  configuration section changed; the new guard proves the `automationTaskDefinitions` section
  changed only at the reviewed definition's identity (id → entry byte equality). Together they
  prove every other section and every other definition is byte-identical to the live Active
  configuration before publication, so activation still publishes no new Storage, strategy or
  destination semantics. The managed activation still revalidates digest, version and document
  loader atomically.
- **`automation_activation_definition_scope` is a distinct code** from the section-level
  `automation_activation_out_of_scope`, so diagnosis can distinguish "changes outside the
  Automation section" from "another definition changed inside it". Both are digest-free, expose no
  sibling identities, and the frontend already renders 409 generically with a refresh action.
- **One definition per Draft is the activatable boundary.** Because a created or copied definition
  activates only as the sole Automation change, a Draft holding both a created and a copied
  definition can activate neither. The existing create/copy journey test was restructured to
  activate the created definition first and copy into a fresh successor Draft — the boundary B
  required is kept rather than weakening the test.
- **Removal staged through the replacement-Draft import path.** Definition deletion is not part of
  this slice's object routes ("Automation Task Definition deletion is not part of this slice"), so
  the removed-sibling state is staged via `import_draft` — a real managed service path seeded from
  the current Active document, pinned to it as base — instead of a synthetic repository write.
  The guard's removal branch is thereby proven against a legitimately reachable state.
- **Active-first deterministic page order.** The combined page keeps the existing Active document
  order and lets Draft-only definitions fill the remaining capacity, so behavior below the limit is
  unchanged and the page remains deterministic.

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
  local `.mediaflow/` runtime state (e.g. a local `HDD_2` Storage) being resolved instead of the
  tests' temporary bootstrap documents, not by this correction. The focused suites that bind to
  the changed code (267 + 17 Python tests, 359 frontend unit tests, 106 built-artifact tests)
  pass.
- Running the T4 suite touches the ignored local `.mediaflow/` runtime state only. No tracked
  file, media file or credential was touched; `config/alist.json` does not exist in this
  workspace and nothing private entered the checkpoint. `node_modules/` remains untracked and
  outside the checkpoint.
- The correction diff is additive or strengthening (no test deleted, renamed, skipped or weakened);
  the one existing journey restructure (activate the created definition before copying) follows
  directly from the now-enforced one-definition-per-Draft activation boundary.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: PENDING_COMMIT
```


## B Review Result

```text
Reviewed: 2be1eb0b99d64720aeba81f86eab052788121dea..2576323857d896c96b6ecb3f80a3648a7e084ec0
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Exact-object checked activation is still not enforced. A real API probe edited `auto-task`, added
  an `unexpected-sibling` definition to the same Draft, validated it, and then called
  `POST /api/v1/operations/automation/task-definitions/auto-task/activate-draft`; the response was
  `200`, `unexpected_sibling_published` was `True`, and the Active definition IDs became
  `['auto-task', 'unexpected-sibling']`. The handler currently rejects changes outside the entire
  `automationTaskDefinitions` section, but does not reject a second definition riding along with
  the reviewed object. Compare Active and Draft at exact definition identity scope and fail closed
  when any other definition is added, removed, or modified; preserve Active and Draft on rejection,
  and add a real regression covering an edited target plus a sibling change. Creating or copying a
  definition may activate only when that exact new/copied definition is the sole Automation change.
- The bounded list contract breaks at the Active/Draft merge boundary. A real API probe with 100
  valid Active definitions plus one Draft-only definition returned `200` with `101` items,
  `total: 101`, and `truncated: false`, while the frontend normalizer rejects any page containing
  more than 100 items. Apply one deterministic combined response limit that matches the frontend
  contract, report truthful `total`/`truncated` semantics after merging Active and Draft-only
  definitions, and add real API plus frontend normalization coverage for the 100-Active +
  1-Draft-only boundary so the page remains usable and truthfully bounded.
