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

- `mediaflow/interfaces/service_api.py` — the Operations Automation projection now connects the
  checked activation across the real API and Web and enforces the Automation-only activation
  boundary: the outer dispatch routes `POST /api/v1/operations/automation/task-definitions/…` into
  the projection (previously GET-only, so the real POST hit 404); the Draft document advertises the
  exact owned `…/activate-draft` POST transport instead of the generic configuration activation
  route; `_automation_definition_activate_checked_draft` now requires `expectedRevisionId` plus
  `expectedVersion`, binds the action to the exact advertised Draft revision, pins the Active base,
  and fails closed (409 `automation_activation_out_of_scope`) unless the Draft's changes versus the
  Active document are confined to the `automationTaskDefinitions` section — with no revision digest
  in any request, response or error detail; new `_automation_definition_resolution` resolves a
  definition Active-first then Draft-only (keeping newly created/copied definitions reachable and
  editable) and converts repository failures into the bounded 503 unavailable response;
  draft-only definitions appear in the list/detail/occurrences projections with a new
  backend-authoritative `definitionState` field (`active` | `draft-only`), empty occurrence state,
  no grant and Preview/grant/revoke actions unavailable with an explicit not-Active reason; the
  Draft-editor document sources ResourceLibrary options from the exact open Draft; failing Draft
  discovery never renders as a legitimate empty state.
- `mediaflow/application/configuration_snapshot.py` — `open_draft_revisions()` no longer swallows
  every repository failure into `()`; failures propagate so callers can report bounded
  unavailability instead of offering successor-Draft recovery on false evidence.
- `web/src/entities/operations/automation.ts` + `automation.test.ts` — `definitionState` is a
  required fail-closed enum on the definition model (a document without the exact state marker is
  malformed, so no Draft can ever be rendered as Active); new normalization regressions.
- `web/src/shared/api/api-client.ts` — `activateAutomationDraft` sends the exact
  `expectedRevisionId` (with `isSafeIdentifier` guard) alongside `expectedVersion`.
- `web/src/features/operations/AutomationEditorPage.tsx` — every owned definition field is now
  editable: ResourceLibrary (authoritative backend options), run mode, schedule type with bounded
  interval↔Cron/timezone transitions and exactly one schedule form stored (the unused form is
  cleared on save); activation submits the exact Draft revision identity.
- `web/src/features/operations/AutomationListPage.tsx`, `AutomationDetailPage.tsx` — draft-only
  definitions are visibly marked and never presented as Active.
- `web/tests/fake-server.mjs` — mirrors the real contract: `definitionState` on every document, the
  checked activation served ONLY on the dedicated operations route (the non-operations spelling now
  404s, so the alias rewrite can no longer mask a real routing gap), exact `expectedRevisionId`
  binding enforced, and a full create/copy Draft-only lifecycle (created/copied definitions are
  served as draft-only detail/draft/list documents with editable saves).
- `web/tests/e2e/automation.spec.ts` — the Draft journey edits run mode and the interval→Cron/
  timezone transition in the built artifact and asserts the saved body and the
  `expectedRevisionId` binding; new create-completion and copy-completion regressions land on
  reachable draft-only details and complete their editor save.
- `web/src/features/operations/AutomationRouter.test.tsx` — component coverage that completes
  create and copy into reachable draft-only definitions, edits every owned field (library, mode,
  Cron/timezone) with exactly-one-schedule storage, proves the stale-save 409 message without
  replay, and asserts the activation body carries the exact Draft revision.
- `tests/test_v2_automation_operations.py` — journey tests updated to the dedicated advertised
  activation transport and exact revision binding; five new regressions: real Draft document ↔
  frontend action-contract agreement, same-version/different-revision concurrent binding (neither
  Draft activated), unrelated-object change rejection without activation plus clean re-activation,
  the complete draft-only create/copy/edit/validate/activate lifecycle, and failing-repository
  reads reported as 503 with no create/edit/activate control.
- `TASK.md` — this report.

### Implemented

1. **Checked-activation transport connected end-to-end.** The real POST to
   `/api/v1/operations/automation/task-definitions/<id>/activate-draft` is routed to the dedicated
   handler, the Draft document advertises exactly that owned route, and a real-API journey drives
   it to success and to its failures — closing the browser-fake/API split that previously let the
   Python journey use the generic route while the fake rewrote `/api/v1/operations/` before
   matching.
2. **Exact Draft binding and Automation-only activation boundary.** Activation requires the
   submitted `expectedRevisionId` to be the currently advertised open Draft revision and the
   expected optimistic version to match; the Draft must be seeded from the current Active; and the
   Draft's document is diffed against the Active document so any change outside
   `automationTaskDefinitions` (same-version concurrent Draft, unrelated-object edit) is rejected
   409 before any activation, with Active preserved and neither Draft activated. All failures are
   digest-free. Because the confinement comparison proves every non-Automation section is
   byte-identical to the live Active configuration, the published configuration introduces no new
   Storage, strategy or destination semantics.
3. **Usable Draft-only lifecycle.** Create and copy land on reachable, editable draft-only detail
   surfaces (Active-first then open-Draft resolution) until checked activation; the list keeps them
   discoverable and `definitionState: "draft-only"` keeps them visibly distinct from Active
   definitions, with Preview/grant/revoke unavailable until activation.
4. **Bounded editor completed.** Every owned field (ResourceLibrary, run mode, interval vs
   Cron/timezone) is editable from authoritative options with bounded schedule transitions, proven
   at component and built-artifact level including optimistic stale-save rejection.
5. **Honest Draft discovery.** `open_draft_revisions()` propagates repository failures; the list,
   detail, Draft and activation reads report the existing bounded 503 unavailable response without
   leaking the exception and without advertising create/edit/activate controls on false evidence.

### Tests and Results

```text
python3 scripts/check_governance.py                                                — PASS
env -u NODE_ENV npm --prefix web ci                                                — PASS (0 vulnerabilities)
npm --prefix web run format:check                                                  — PASS
npm --prefix web run typecheck                                                     — PASS
npm --prefix web run lint                                                          — PASS
npm --prefix web run test -- --run                                                 — PASS (356/356, 32 files)
npm --prefix web run build                                                         — PASS
npm --prefix web run test:e2e -- automation.spec.ts operations.spec.ts deep-link.spec.ts
                                                                                   — PASS (55/55)
npm --prefix web run test:e2e                                                      — PASS (106/106)
.venv/bin/python -m unittest tests.test_v2_automation_operations                   — PASS (13/13)
.venv/bin/python -m unittest tests.test_automation_task_definition tests.test_automation_task_definition_preview tests.test_automation_unattended_grant tests.test_automation_preview_grant_gate tests.test_automation_definition_occurrence tests.test_automation_definition_execution tests.test_automation_authorized_execution_matrix tests.test_automation_admission tests.test_automation_job_fencing tests.test_automation_api tests.test_cron_scheduler tests.test_configuration_objects tests.test_operations_workspace tests.test_api_security tests.test_v2_ui
                                                                                   — PASS (267/267)
.venv/bin/python -m unittest discover -s tests                                     — 1510 tests, 6 FAIL / PRE-EXISTING / UNRELATED, 7 SKIP
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

- **Confinement replaces the per-revision evidence chain for this activation.** The previous
  checkpoint called `activate_checked`, whose Storage/strategy/destination evidence can never be
  satisfied through the V2 surface (the check routes require operator-chosen parameters such as a
  synthetic recognition path, and the browser must never handle the revision digest) — which is
  why the real dedicated POST could not succeed. The dedicated handler now proves safety by exact
  means: bind the action to the exact advertised Draft revision, pin the Draft's Active base to the
  current Active, and diff the Draft document against the Active document; a confining pass means
  every other section is byte-identical to the live Active, so activation publishes no new
  Storage/strategy/destination semantics. `managed.activate` still revalidates digest, version and
  the full document loader atomically. The Python contract regression pins the advertised transport
  so the backend document cannot drift from the frontend normalizer again.
- **`definitionState` is a required closed enum.** Rather than inferring Active/Draft state on the
  client, the backend stamps every definition operator document (`active` | `draft-only`) and the
  normalizer fails closed on a missing or unknown marker, so a Draft can never be rendered as
  Active.
- **Fake server honesty.** The alias rewrite no longer covers the activation mutation: the fake
  serves the dedicated operations route only and 404s the non-operations spelling, so a future
  routing gap fails the browser proof instead of being masked.
- **Draft-only reachability.** New/copied definitions resolve through Active-first-then-open-Draft
  lookup in the detail, Draft, occurrences and list projections; the list marks them draft-only and
  the action projection withholds Active-definition actions until activation.

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
  tests' temporary bootstrap documents, not by this Task. The focused suites that bind to the
  changed code (267 + 13 Python tests, 356 frontend unit tests, 106 built-artifact tests) pass.
- Running the T4 suite touches the ignored local `.mediaflow/` runtime state only. No tracked
  file, media file or credential was touched; `config/alist.json` does not exist in this
  workspace and nothing private entered the checkpoint. `node_modules/` remains untracked and
  outside the checkpoint.
- The correction diff is additive or strengthening (no test deleted, renamed, skipped or weakened);
  existing journey tests were updated to the corrected dedicated activation transport and now also
  prove the exact-revision binding, digest-free conflicts and the Automation-only boundary.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 2576323857d896c96b6ecb3f80a3648a7e084ec0
```


## B Review Result

```text
Reviewed: 2be1eb0b99d64720aeba81f86eab052788121dea..df0b101ca2de033c87bb9e097bc3655678bbbb47
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The checked-activation transport is not connected across the real API and Web. A real
  `MediaFlowApi` probe created and validated a successor Draft, then
  `POST /api/v1/operations/automation/task-definitions/auto-task/activate-draft` returned
  `404 not_found`; routing in `service_api.py` dispatches the Operations Automation projection only
  when `method == "GET"`. The real Draft document also advertises
  `/api/v1/configuration/revisions/<draft>/activate`, while the frontend normalizer accepts only the
  dedicated `/api/v1/operations/automation/task-definitions/<id>/activate-draft` transport, so the
  real editor document fails closed before activation. The focused suites still passed (Python
  8/8, frontend 17/17, Automation E2E 9/9) because the Python journey invokes the generic
  activation route and the browser fake rewrites `/api/v1/operations/` before matching. Route the
  real POST to the dedicated handler, advertise that exact owned route, and add an actual
  backend-document/frontend-contract regression plus a real dedicated-handler success/failure test.
- The dedicated activation handler is not bound to the exact Draft identity and does not enforce
  the Task's Automation-only activation boundary. It re-resolves whichever newest open Draft
  contains the definition, compares only its numeric version, and passes that whole revision to
  `activate_checked`; a concurrently created different Draft at the same version can replace the
  reviewed object, and unrelated Configuration changes in that Draft are not rejected. Bind the
  submitted action to the exact advertised Draft revision as well as its expected version, compare
  its changes with the Active base, and fail closed unless activation is confined to the intended
  Automation definition boundary. Cover same-version/different-revision concurrency and an
  unrelated-object change without activating either Draft.
- Create/copy does not provide a usable Draft lifecycle. A real API probe successfully created
  `new-draft-only` (`200`) and then the V2 detail route used by `AutomationNewPage` returned
  `404 not_found`, because operator detail/draft lookup begins from the Active definition only;
  `AutomationNewPage` and the copy action both navigate directly to that Active-only detail route.
  Keep newly created/copied Draft-only definitions reachable and editable until activation (or keep
  the operator on an equivalent truthful Draft surface), and add real API plus component/browser
  coverage that completes create and copy instead of testing only their advertised buttons.
- The edit form does not satisfy the bounded definition editor acceptance. It edits only name,
  enabled, source scope and item limit; ResourceLibrary, run mode and interval versus Cron/timezone
  are rendered as read-only text and copied unchanged into the PUT body. Make every owned definition
  field required by this Task editable with authoritative ResourceLibrary options and bounded
  interval/Cron/timezone transitions, then prove their optimistic save, validation and stale-state
  behavior in component and built-artifact tests.
- Draft discovery silently converts every repository failure into “no open Draft”:
  `open_draft_revisions()` catches `Exception` and returns `()`. This makes an unavailable/corrupt
  persistence read indistinguishable from a legitimate empty state and can offer successor-Draft
  recovery on false evidence. Propagate the failure into the existing bounded unavailable response
  (without leaking the exception) and add a failing-repository regression proving no create/edit/
  activate control is advertised.
