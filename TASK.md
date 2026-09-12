# Task 33.3 — Web-native exact manual Organize admission and outcome journey

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 33.3
Parent Slice: 33
Status: FIX REQUIRED
Task Base: e1dba1f87bb32cdcd573f565b6772e3da21823bf
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 33 RO-4 and the applicable RO-7/RO-8 boundary: starting from recognizable V2 Library
or Operations context, an authorized operator can create and edit a durable manual intent, review
and select exact immutable Preview items, give meaningful mutation/destructive confirmation, admit
the reviewed work through backend-bound one-shot authority, and follow independent durable outcomes
without issuing, seeing or copying a CLI execution token or supplying paths/plans to the request.

## Why This Task Exists

Task 33.2 completed bounded manual Scan and full zero-mutation Preview, including server-resolved
current-source identity and durable findings. The existing Python V1 foundation already provides
manual intent/choice persistence, exact Preview versioning, one-shot authorization, source/
capability/conflict revalidation, OrganizerExecutor-only mutation and per-item Result/effect
evidence. V2 currently exposes none of the intent, choice, authorization, execution or outcome
journey.

The current file-level manual execute endpoint also performs OrganizerExecutor work synchronously
inside the API request. That cannot satisfy the Slice contract that admitted long work receive a
durable identity promptly and remain followable without holding the browser request open. The
manual Organize journey is therefore one coherent high-risk vertical boundary: splitting the form,
authority, admission or outcome into separate Tasks would leave an unusable or misleading mutation
surface. Automation and Notification remain later independent Slice 33 Tasks.

## Implementation Scope

The implementation boundary is:

```text
existing manual intent / immutable Preview / one-shot execution domain and SQLite state
→ backend-authoritative Web-native authorization and queued admission
→ existing Processing Worker and OrganizerExecutor-only execution
→ bounded backward-compatible /api/v1/* operator projections
→ strict V2 intent / choice / authorization / execution entities and mutations
→ Library / Operations manual Organize routes and durable outcome follow-up
→ Python, component/router and built-artifact browser safety tests
```

- Add a complete refresh-safe V2 manual Organize route family reachable from current FileIndex
  detail, ResourceLibrary Operations scope and executable Preview detail. Register it centrally so
  deep-link authentication continuation, titles, active navigation and bounded return context follow
  the shared shell contract. Durable identifiers may appear only as route identities needed to
  reopen state, never as values the operator must discover or paste.
- Extend the backend manual action/readiness projection so Organize is offered only for the exact
  principal, current FileIndex/ResourceLibrary scope, loaded Active runtime and available services.
  The frontend must not infer execute permission, source currentness, Preview eligibility,
  capability, destructive authority or queue readiness from route or cached state.
- Reuse `ManualOrganizeIntentService` as the single intent and choice authority. Create intents from
  server-resolved current FileIndex selections, expose only enabled/permitted recognition, metadata
  and policy choices from the pinned runtime, and update one item with optimistic intent/item
  versions. Choice edits invalidate prior Preview evidence. Requests cannot submit a raw
  occurrence/fingerprint, configuration digest, arbitrary source/target path, provider payload,
  operation or unadvertised policy identity.
- Reuse `ManualOrganizePreviewService` for every initial or regenerated exact Preview. The operator
  can select only current, complete, untruncated, executable Preview items and can inspect the
  Task-33.2 findings plus the precise operation, attachments, conflict/capability state and whether
  Overwrite or source cleanup/destruction would be authorized. Blocked/unselected siblings remain
  independently visible and do not gain authority.
- Provide a Python Application/API admission boundary for the routine Web journey that obtains and
  binds short-lived one-shot authority on the server to the authenticated principal, permission,
  exact intent/Preview/configuration/item versions, selected items, allowed effects and expiry. The
  browser never receives, submits, persists or logs a raw execution token/secret or digest. Existing
  CLI/remote-token compatibility may remain, but it is not called or linked by V2.
- Treat meaningful Execute confirmation as one operator action. The backend may internally create
  and consume an authorization record, but it must not force a second confirmation or make the
  operator transfer an implementation credential when no new intent boundary exists. Explicit
  Overwrite and source cleanup/delete choices are separate, default false, shown only when the exact
  selected plans require them, and rejected unless policy, permission and confirmation all allow
  them.
- Admit the selected exact work durably and return execution plus Job/Task identity before
  OrganizerExecutor work completes. Use the resident Processing Worker/claim/fencing boundary, not
  an API-owned background thread or second executor. Admission atomically consumes or rejects the
  one-shot authority, is idempotent/concurrency-safe, survives restart, and never creates duplicate
  Tasks or mutation attempts for repeated/concurrent submission.
- The Worker reconstructs execution only from persisted immutable Preview data, pinned runtime and
  server-held authority, rechecking source occurrence/fingerprint, conflicts, capabilities, limits,
  locks and allowed effects immediately before each not-yet-performed mutation. Only
  `OrganizerExecutor` mutates Storage. HardLink/SoftLink never falls back; Overwrite/delete/cleanup
  is never inferred; RecognitionType C remains C.
- Keep existing manual execution/Task/TaskItem/Result/checkpoint records as the durable outcome
  model. Add bounded operator projections and V2 progress/detail that distinguish admission, Worker
  ownership, aggregate state, independent selected/unselected/blocked item state, known completed
  effects, effect certainty, Result linkage and current next action without publishing raw paths,
  fingerprints, plan payloads, authority material or exceptions.
- Pre-admission invalid/stale intent, changed source, stale Preview/item/configuration,
  expired/consumed authority, insufficient permission, limits, queue pressure, unavailable Worker,
  conflict/capability and concurrent admission must yield no mutation and a fresh-read/re-preview/
  reauthorization action. Partial or uncertain effects remain truthful and never auto-replayed;
  link them to V1 or Slice 34 Review & Recovery without implementing recovery here.
- Use centralized typed entities, API functions and TanStack Query boundaries. Components issue no
  raw `fetch`, cache no domain authority, never automatically retry a mutation after ambiguity/
  401/403/conflict/malformed response, and clear unsubmitted choices and authenticated mutation
  state on disconnect or rejected authentication.
- Extend the local Playwright fake with deterministic, secret-free intent/choice/Preview/admission/
  Worker/outcome state. Reject unsupported methods/bodies, prove one meaningful Execute action, and
  record only bounded request evidence without Bearer values, authority, digests, fingerprints,
  paths or raw plans.
- Preserve V1 `/ui`, existing synchronous/manual and remote-token API compatibility routes, Task
  33.1 Task/Job controls, Task 33.2 Scan/Preview and Python-only production serving. If queued manual
  execution needs an additive runtime schema change, make it forward-only, fail-closed and restart/
  migration-tested with temporary copied fixtures.

Frozen for this Task:

- `SLICE.md`, `docs/roadmap.md`, canonical/stable requirements, product-experience and architecture
  authority text, including Slice Base and every A-owned Contract field.
- Recognition/Metadata/Classification review decisions, conflict resolution, Reprocess,
  checkpoint continuation, failed-item retry, reconciliation controls and uncertain-effect recovery
  owned by Slice 34. This Task shows durable state and a truthful destination only.
- Automation definitions/activation/schedules/grants/occurrences and Notification definitions/
  tests/deliveries; these remain later Slice 33 Tasks.
- General Configuration/Settings editing or activation owned by Slice 35. A broken dependency may
  hand off to the current V1 Configuration surface.
- Provider, Storage, recognition, metadata, naming, classification, planning and conflict semantics;
  auth redesign; arbitrary bulk execution; Node production serving; `config/alist.json` and private
  runtime state.

## Acceptance Criteria

- [ ] From V2 FileIndex, ResourceLibrary Operations context or an eligible Preview, an authorized
      operator can enter/refresh one complete manual Organize journey, create or reopen its durable
      intent, inspect recognizable sources and return safely without handling an internal ID as an
      input or losing useful Library/Operations context.
- [ ] The backend action projection is authoritative for the exact principal, source/scope, Active
      runtime, service/Worker/queue readiness and limits. Viewer/forbidden, stale, unavailable or
      unsupported states render no executable control.
- [ ] Intent creation and choice editing use only server-resolved current FileIndex sources and
      enabled pinned options. Optimistic versions reject stale/cross-intent/cross-item edits
      atomically, preserve siblings, invalidate old Preview items and accept no raw fingerprint,
      digest, path, provider payload, operation or arbitrary policy/target.
- [ ] A fresh immutable Preview is required after each relevant choice/source/configuration change.
      The UI renders exact selected/unselected and independently blocked items, complete existing
      findings, targets, attachments, operations, conflicts, capabilities and destructive
      implications without treating Preview as execution authority.
- [ ] Only current, complete, untruncated and executable Preview items can be selected. Item and
      batch limits are backend-enforced; blocked or unselected siblings remain visible and cannot be
      silently included.
- [ ] One explicit Web Execute action creates and atomically consumes/rejects short-lived one-shot
      backend authority bound to principal, permission, exact intent/Preview/configuration/item
      versions, selected set, expiry and allowed effects. No CLI step, raw token/secret, digest or
      avoidable second confirmation appears.
- [ ] Overwrite and source cleanup/delete remain default-denied and separately explained/confirmed
      only when required. Missing policy/permission/intent fails before mutation. HardLink/SoftLink
      capability failure never falls back to Copy or Move.
- [ ] Successful admission returns durable execution and Job/Task identity promptly without waiting
      for OrganizerExecutor completion. Repeated/concurrent submission consumes authority once,
      creates at most one execution/Task, and survives API/Worker restart without duplicate mutation.
- [ ] The Processing Worker alone claims admitted manual execution through the durable lease/fence
      boundary and reconstructs the exact persisted Preview plan. It rechecks source, snapshot,
      policy, conflict, capability, locks, limits and authority before each pending mutation; only
      OrganizerExecutor reaches mutating Storage methods.
- [ ] Execution detail distinguishes admitted/running/terminal aggregate state and every selected,
      unselected or blocked item, including Task/TaskItem/Result links, known effects, effect
      certainty, failure category and next action. Successful siblings remain terminal; partial/
      uncertain effects are never presented or submitted as safe automatic retry.
- [ ] Stale, authority, conflict/capability, permission, limit/queue/Worker, concurrency, malformed,
      not-found, 401/403 and unavailable failures retain durable truth and offer only an applicable
      refresh, edit, fresh Preview, reauthorization, readiness/configuration handoff or Slice 34/V1
      recovery destination.
- [ ] Typed normalization fails closed on unknown/contradictory authority, version, selection,
      destructive, execution, item/effect or action data. Components perform no raw fetch, hold no
      domain authority and never automatically retry admission/execution after ambiguity/rejection.
- [ ] API/model/URL/DOM/console/audit/test artifacts contain no Bearer credential, raw execution
      token/secret, authorization digest, fingerprint/occurrence identity, raw plan/provider payload
      or exception, private endpoint, absolute host/adapter root or arbitrary path.
- [ ] Safety tests cover zero-mutation intent/edit/Preview reads, exact one-shot/expiry/principal/
      version/item/effect binding, concurrent consumption, pre-mutation rejection, all four
      operations, attachments, overwrite/delete/cleanup authority, no link fallback, no uncertain
      replay and RecognitionType C preservation.
- [ ] V1 `/ui`, legacy manual intent/Preview/execution and remote-token clients, existing API,
      Task 33.1/33.2 routes and Python-only deployment remain compatible. No API background thread,
      second execution model or Node runtime service is introduced.
- [ ] Component/router and built-artifact evidence covers Library/Operations/Preview entry,
      authenticated/unauthenticated refresh, intent/choice editing, fresh Preview, exact selection,
      destructive confirmation, one Web-native admission, Worker/outcome follow-up, failure states,
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
npm --prefix web run test:e2e -- manual-organize.spec.ts manual-operations.spec.ts operations.spec.ts library-file-detail.spec.ts deep-link.spec.ts
npm --prefix web run test:e2e
.venv/bin/python -m unittest tests.test_v2_manual_organize
.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_execution_authorization tests.test_queued_job_execution_boundary tests.test_organizer_mutation_authority tests.test_manual_operations tests.test_operations_workspace tests.test_api_security tests.test_v2_ui
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

Create `tests/test_v2_manual_organize.py` and built-artifact browser file
`web/tests/e2e/manual-organize.spec.ts`; run any additional focused modules as well. Docker may be
`UNAVAILABLE` only with the observed environmental reason and must not be inferred as passing.

Focused tests must prove server-resolved selection/options; optimistic intent/item concurrency;
Preview invalidation and exact selection; prompt durable queued admission; one-shot principal/
permission/version/item/effect/expiry binding; concurrent submission; Worker claim/fence and
restart; no API-thread OrganizerExecutor call; pre-mutation source/snapshot/conflict/capability
rejection; explicit destructive authority; all operation types with no link fallback; independent
sibling outcomes; uncertain-effect no-replay; redaction and V1 compatibility. Use temporary SQLite
and fake/in-memory Storage/Provider/Worker state only.

If schema changes, add forward-migration, newer-schema rejection, atomic failure and API/Worker
restart tests against temporary copied fixtures. Before checkpointing, inspect and report
`git status --short`, complete Task Base..Head diff, changed-file manifest, test deletion/rename/
skip/assertion changes and tracked/private configuration. `config/alist.json`, `node_modules`, build
reports, credentials and unrelated files must not enter the checkpoint.

## Non-goals

- Automation definition/revision/Preview/grant/schedule/occurrence operation or Notification
  definition/test/delivery operation; these are later Slice 33 units.
- Recognition/Metadata/Classification review decisions, conflict resolution, Reprocess,
  checkpoint continuation, failed-item retry, execution reconciliation or uncertain-effect recovery
  owned by Slice 34.
- General Configuration/Settings administration or activation outside a truthful V1 handoff; these
  are owned by Slice 35.
- Changing provider/Storage/pipeline/planning/conflict semantics, adding providers, arbitrary paths
  or bulk execution, file edit/delete/upload/download, rollback/undo or automatic uncertain replay.
- Replacing API-principal Bearer authentication, persisting browser credentials, adding built-in
  users/sessions/OIDC, redesigning legacy remote-token support, SSR/BFF/Node serving, V1 retirement
  or unrelated refactoring.
- Optional analytics/export, unnecessary polling, copy polish, P2/P3 cleanup or extra proof not
  required by these Acceptance Criteria.

## Developer Completion Report

> Correction loop (B Decision: FIX REQUIRED, Next: SAME TASK FIX LOOP). This report replaces the
> third correction's report. Every blocker B listed is implemented here; this is a new correction
> commit after the reviewed checkpoint — no accepted history was amended.

### Changed Files

Fourth correction commit on top of the reviewed checkpoint
`c4b8c2d60153fd20cec97c48e53d37d80e267270`:

- `web/src/entities/operations/organize.ts` — action route validation now enforces the promised
  URI-safe object identity. `SAFE_ACTION_SEGMENT` is strict (`A-Za-z0-9_.-`, no braces, no angle
  brackets) and validates every real object identity and every real path segment; the one
  intentional `{itemId}` route-template segment the backend publishes for the per-item choice
  route is modelled separately (`ACTION_TEMPLATE_SEGMENT`) and is accepted only in the contract's
  declared `*` parameter position. `isSafeActionPath()` was rewritten from a whole-path character
  class to per-segment validation (bounded `/api/v1/` relative route, no empty or traversal
  segment, every segment strict-safe or exactly the template), so the coarse gate is no looser
  than the exact-owned binding. A path whose identity is missing, unsafe, or names another object
  is malformed by construction.
- `web/src/entities/operations/organize.test.ts` — new focused entity regressions: B's isolated
  probe (`identity="<preview>"` with
  `POST /api/v1/operations/organize/previews/<preview>/execute`) now throws; a safe identity with
  an unsafe path segment throws; an unsafe identity with a safe path throws; braces/angle brackets
  outside the template segment throw; the template outside its parameter position throws; the
  still-valid cases are pinned (the `{itemId}` choice template, a real per-item segment, the
  transport-less recovery handoff) alongside the still-rejected cases (wrong suffix, wrong method,
  another object's route, transport-less `intent-execute`).
- `web/src/features/operations/OrganizeRouter.test.tsx` — the wrong-transport Execute regression
  adds two non-URI-safe path variants (`<preview>` identity segment, `{execute}` suffix segment)
  and still asserts the malformed-read state with no Execute control. The execution fixture helper
  now restores the masked durable identities (`taskId` and the Task action route) so every
  document it renders names the exact real objects the backend emits — the checked-in fixture
  masks durable identities as `<uuid>`, which strict validation correctly refuses.
- `TASK.md` — this report plus B's review of the third correction.

### Implemented

1. **URI-safe object identity separated from the `{itemId}` template (blocker).** Both
   `SAFE_ACTION_PATH` and `SAFE_ACTION_SEGMENT` allowed raw `<`, `>`, `{` and `}`, so a document
   claiming `previewId="<preview>"` with a matching Execute route normalized successfully and the
   exact-object binding was meaningless. Actual object identities are now validated by one strict
   URI-safe segment rule, and the single intentional `{itemId}` route-template segment is a
   separate named constant allowed only where the contract declares a parameter. The rejection is
   layered: the coarse path gate rejects any non-URI-safe segment, and the exact-owned binding
   independently rejects any identity that is not one strict segment, so B's probe fails closed at
   both layers.
2. **Coverage kept strictly additive.** The now-passing exact-suffix and transport-less recovery
   coverage from the previous corrections is pinned at entity level in the new
   `organize.test.ts` and extended (not weakened) in the component suite; no existing test,
   assertion or fixture was deleted, renamed, skipped or loosened. The only test-helper change
   adapts the checked-in masked fixture to the real-object form the helper already used for the
   execution detail route.

### Tests and Results

```text
python3 scripts/check_governance.py                                                — PASS
env -u NODE_ENV npm --prefix web ci                                                — PASS
npm --prefix web run format:check                                                  — PASS
npm --prefix web run typecheck                                                     — PASS
npm --prefix web run lint                                                          — PASS
npm --prefix web run test -- --run                                                 — PASS (335/335, 30 files)
npm --prefix web run build                                                         — PASS
npm --prefix web run test:e2e -- manual-organize.spec.ts manual-operations.spec.ts operations.spec.ts library-file-detail.spec.ts deep-link.spec.ts
                                                                                   — PASS (60/60)
npm --prefix web run test:e2e                                                      — PASS (95/95)
.venv/bin/python -m unittest tests.test_v2_manual_organize                         — PASS (23/23)
.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_execution_authorization tests.test_queued_job_execution_boundary tests.test_organizer_mutation_authority tests.test_manual_operations tests.test_operations_workspace tests.test_api_security tests.test_v2_ui
                                                                                   — PASS (153/153)
.venv/bin/python -m unittest discover -s tests                                     — 1497 tests, 6 FAIL / PRE-EXISTING / UNRELATED, 7 SKIP
.venv/bin/ruff format --check .                                                    — PASS (307 files)
.venv/bin/ruff check .                                                             — PASS
.venv/bin/python -m compileall -q mediaflow tests scripts                          — PASS
.venv/bin/python -m pip check                                                      — PASS
.venv/bin/mediaflow --config config/strategy.example.json config validate          — PASS
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate — PASS
git diff --check                                                                   — PASS
python3 scripts/docker_release_security_smoke_test.py                              — PASS
```

### Decisions

- The separation is implemented as two named validators: `isSafeActionSegment()` (strict; the
  object identity and every real segment) and `isSafeActionPathSegment()` (strict plus exactly
  `{itemId}`; path segments and the `*` parameter). The template is therefore confined to the
  parameter position by construction: a path whose identity segment is `{itemId}` fails the
  owned-prefix binding, and a fixed suffix can never be a template.
- `isSafeActionPath()` moved from a whole-path character class to per-segment validation because
  the template exception is segment-shaped; the previous coarse gate was strictly looser than the
  exact-owned check, which let B's probe reach the exact check with unsafe characters and pass.
- No backend change was needed: the real backend publishes strictly URI-safe durable identities,
  and the only non-URI-safe segment it ever publishes is the `{itemId}` choice-route template.
  The `<uuid>`/`<hex-id>` values in the checked-in fixture are masking artifacts of
  `tests/test_manual_operations_contract.py` (`_canonical`), not API values, so the component
  helper restores real-shaped identities for the documents it renders.
- The focused no-replay/rejection assertions live at the normalizer boundary because that is where
  B's probe was made; the component suite additionally renders the hostile transports to prove no
  executable control appears.

### Remaining In-Slice Work

- Automation definition/occurrence and Notification operation remain later Slice 33 Tasks.
- Slice 34 owns conflict-resolution UI, checkpoint continuation and uncertain-effect recovery; this
  Task shows durable state and truthful destinations only.

### Risks / Deviations

- 6 full-discovery failures are `FAIL / PRE-EXISTING / UNRELATED`, the identical set reported by
  every previous round: `test_storage_list_does_not_construct_or_connect`,
  `test_storage_check_is_read_only_and_isolates_failures`,
  `test_credential_check_is_redacted_config_only_and_reports_missing`,
  `test_legacy_credential_status_is_supported_without_secret_output`,
  `test_runtime_configuration_and_final_analyze_cli`,
  `test_scan_cli_needs_no_path_or_metadata_token`. They are caused by this workspace's ignored
  local `.mediaflow/` runtime state being resolved instead of the tests' temporary bootstrap
  document, not by this frontend-only correction. The focused suites that bind to the changed code
  (153 + 23 Python tests, 335 frontend unit tests, 95 built-artifact tests) pass.
- Running the T4 suite touches the ignored local `.mediaflow/` runtime state only. No tracked
  file, media file or credential was touched; `config/alist.json` does not exist in this
  workspace and nothing private entered the checkpoint. `node_modules/` remains untracked and
  outside the checkpoint.
- The checkpoint contains only this correction plus its report and B's recorded review; the diff
  is additive (no test deleted, renamed, skipped or weakened).

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 11555c648dbd1b032b03d09fdef39f94dbec5257
```

## B Review Result

```text
Reviewed: e1dba1f87bb32cdcd573f565b6772e3da21823bf..c4b8c2d60153fd20cec97c48e53d37d80e267270
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The exact-route correction still does not enforce the promised URI-safe object identity. Both
  `SAFE_ACTION_PATH` and `SAFE_ACTION_SEGMENT` allow raw `<`, `>`, `{` and `}` in an object's identity;
  consequently B's isolated Vitest probe passed `identity="<preview>"` with
  `POST /api/v1/operations/organize/previews/<preview>/execute`, expected the normalizer to reject it,
  and failed with `AssertionError: expected [Function] to throw an error`. Separate actual object-ID
  validation from the one intentional `{itemId}` route-template segment, reject non-URI-safe object
  identities/action segments fail-closed, and add a focused regression without weakening the now-
  passing exact-suffix and transport-less recovery coverage.
