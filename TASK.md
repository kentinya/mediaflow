# Task 28.5 — Independent Webhook Delivery Operations and Recovery

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 28.5
Parent Slice: 28
Status: PLANNED
Task Base: a053905b538d832cebe64a7db192d24ca7c53f0b
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 28 RO-6: an authenticated operator can inspect each Webhook delivery through the
Web/API Notifications surface and explicitly recover the affected delivery through the permitted
dead-letter requeue or stale-delivery recovery action, with durable lease/staleness, attempt,
response/failure, effect certainty, audit and next-action evidence. Successful and unrelated
deliveries remain independently visible and completed media work is unchanged.

## Why This Task Exists

Task 28.4 completed managed Webhook definitions and the explicit bounded definition test, while the
existing Outbox/Worker already persists delivery state and supports internal dead-letter requeue.
The current operator surface still exposes only a bounded delivery list and a status filter. It does
not provide a delivery-specific detail/recovery journey, does not expose stale lease state as an
operator decision, and does not provide shared permission-aware Web/API actions for safely resolving
one affected delivery.

This is the largest remaining coherent unit for RO-6 because delivery recovery crosses the existing
durable notification repository, application recovery semantics, API authorization/audit and the
Notifications Web view. It must reuse the existing Outbox/Worker and preserve at-least-once and
duplicate-delivery implications; it must not be split into isolated route, label or test Tasks.

## Implementation Scope

```text
Delivery detail/recovery model and durable state projection
→ application delivery-operations/recovery service
→ permission-aware API detail and action routes
→ Notifications Web list/detail/recovery journey
→ redacted audit, parity, concurrency, recovery and regression tests
```

The Task may update only the implementation needed for the following behavior:

- Expose a bounded delivery detail projection for one delivery, including delivery identity,
  Webhook/event identity, status, attempts, timestamps, response status, failure category, lease
  ownership/staleness, effect certainty or known-effect statement, retry safety and explicit next
  action. The projection must not expose delivery body credentials, secrets, authorization headers,
  cookies or remote response bodies.
- Provide one shared application authority for delivery operations. It must validate the selected
  delivery's current durable version/state under concurrency before mutating it, preserve all
  unrelated delivery rows, and return bounded durable recovery evidence when the requested state is
  stale, already resolved, missing or otherwise not eligible.
- Provide explicit Web/API operations authorized through the existing API permission model for the
  supported operator recovery paths: requeue an eligible dead-letter delivery, and resolve an
  eligible stale/in-progress delivery only through an explicitly named action whose
  at-least-once/duplicate-delivery implication is visible. Do not turn ordinary refresh, list,
  detail or status filtering into a mutation. Do not silently retry a delivery, silently reset
  attempts, or silently convert a non-eligible state.
- Keep automatic Worker retry behavior intact. Manual recovery must not enqueue a second delivery
  identity, alter the Webhook definition, activate a Draft, start a Task/Job/Scheduler occurrence,
  mutate Storage or change completed Task/Result/media history.
- Make API and Web use the same application validation, authorization, state transition, audit,
  redaction and recovery semantics. The Web journey must show the selected delivery's durable state,
  known effects, retry/requeue safety and next action before a duplicate-prone recovery action, then
  refresh the same delivery and keep sibling outcomes visible.
- Record redacted audit evidence for detail access where required by the existing security boundary,
  denied actions, successful recovery, rejected/stale recovery and resulting durable state. Audit,
  API errors, Web messages and logs must use bounded categories and never include secret material or
  remote response content.
- Preserve bounded pagination/filter behavior and deterministic ordering for the delivery list.
  Detail and recovery must be scoped to the exact delivery identity and may not use a bulk or
  unbounded mutation path.

Files/areas explicitly frozen unless compatibility glue is strictly required:

- `SLICE.md`, `docs/roadmap.md`, `docs/progress.md`, product requirements, Product Experience and
  Architecture contracts.
- Completed Tasks 28.1–28.4, managed configuration/Settings/package/Webhook-definition authorities
  and exact Active revision semantics.
- Webhook definition lifecycle and explicit definition-test semantics; definition tests remain
  separate from durable delivery records.
- OrganizerExecutor, Storage mutation, Scanner/Parser/Recognition/Metadata/Naming/Classification/
  Planner behavior, Worker/Scheduler ownership protocol and completed media-processing history.
- Docker/Compose release, built-in identity/OIDC, general Secret Store, Provider switching and new
  Storage providers.

## Acceptance Criteria

- [ ] Authenticated API users with the existing applicable read authority can retrieve one
      bounded delivery detail and see identity, event, state, attempts, lease/staleness,
      response/failure category, known effects, retry safety and next action. Missing or malformed
      delivery IDs return the existing bounded error/recovery shape.
- [ ] Authenticated API users with the existing applicable explicit recovery authority can perform
      each supported recovery action on one eligible delivery. The action is authorized,
      state-checked and durable; ineligible, stale-version, already-resolved and concurrent
      requests fail closed without changing the delivery or siblings.
- [ ] The Notifications Web view provides a discoverable list-to-detail journey and shows the same
      durable delivery evidence and recovery actions as the API. Refreshing, filtering and opening
      detail perform no mutation; recovery requires an explicit user action and visibly reports
      durable state, side effects, duplicate-delivery implication and next action.
- [ ] Manual recovery preserves the stable delivery identity and at-least-once semantics, does not
      create a second delivery row, does not hide or overwrite successful/unrelated deliveries, and
      does not change Webhook definitions, Active/Draft configuration, Task/Job/Scheduler records,
      Storage or completed media work.
- [ ] Automatic Worker retry, lease claim fencing, stale detection and dead-letter behavior remain
      compatible with the new operator operations. A delivery that is not eligible for manual
      recovery remains visibly actionable with an explicit reason rather than being silently reset.
- [ ] API/Web permissions, validation, concurrency, state transitions, audit, redaction and
      recovery evidence are parity-tested through the shared application behavior. No required
      RO-6 path depends on CLI-only knowledge, direct SQLite access or raw JSON editing.
- [ ] Secret safety is preserved in delivery detail, recovery responses, audit, logs, Web messages
      and tests: no secret values, bearer tokens, authorization headers, cookies, private endpoint
      credentials or remote response bodies are returned or persisted.
- [ ] Required focused tests, full supported offline regression, governance, formatting/lint,
      compile, dependency and diff checks pass; unavailable optional/external gates are reported
      explicitly and truthfully.
- [ ] The checkpoint contains only this Task's coherent implementation/tests and no private
      configuration, `config/alist.json`, credentials, media or unrelated user work.

## Required Tests

Focused and related tests:

```bash
python3 -m unittest \
  tests.test_notification_delivery_management \
  tests.test_notifications \
  tests.test_webhook_management \
  tests.test_configuration_snapshot \
  tests.test_configuration_management \
  tests.test_configuration_objects \
  tests.test_system_settings_management \
  tests.test_configuration_package_exchange \
  tests.test_api_credentials \
  tests.test_operator_ui \
  tests.test_final_integration
```

The Developer must add focused delivery-operations tests covering:

- bounded API/Web delivery detail projection and deterministic list/detail identity;
- permission denial for detail and each recovery action;
- delivered, pending, retry, delivering, stale and dead-letter visibility;
- explicit dead-letter requeue and stale-delivery recovery, including ineligible-state rejection;
- optimistic/concurrent recovery rejection, durable state preservation and independent sibling
  delivery outcomes;
- stable delivery identity, attempt/effect evidence, at-least-once and duplicate-delivery wording;
- audit success/denial/conflict and secret/response-body redaction;
- no new delivery, Task, Job, schedule occurrence, Storage mutation or completed media-history
  change from detail or manual recovery;
- API/Web parity using the same application service and exact recovery payloads;
- compatibility regressions for Worker retry, lease/stale claim fencing and existing definition-test
  isolation.

T4 quality and regression gates:

```bash
python3 scripts/check_governance.py
python3 -m unittest discover -s tests
ruff format --check .
ruff check .
python3 -m compileall -q mediaflow tests scripts
python3 -m pip check
git diff --check
```

Tests must use temporary SQLite repositories, fakes and local transports. Production Webhook
endpoints, credentials, private paths and real media are not permitted. Any unavailable optional
external dependency or pre-existing local-environment failure must be reported with the exact
command, result and evidence that it is unrelated to this Task.

## Non-goals

- Work outside the Slice 28 Contract or any change to its Required Outcomes, Required Surfaces,
  Safety Invariants, Base SHA or Explicitly Deferred scope.
- Re-implementing managed Webhook definition lifecycle or explicit bounded definition testing from
  Task 28.4.
- Creating a new notification engine, delivery queue, delivery identity scheme or replacement for
  the existing Outbox/Worker/repository authorities.
- Automatic replay beyond the existing Worker retry policy, bulk recovery, arbitrary delivery-body
  editing, event regeneration, secret rotation or general Secret Store behavior.
- Changing Webhook event selection, endpoint validation, signature format or definition activation.
- Docker/Compose production packaging, production serving, Provider switching, built-in identity/
  OIDC, new Storage providers or changes to OrganizerExecutor/media mutation behavior.
- Optional copy polish, extra test-only micro-Tasks, broad refactors or changes to closed processing
  pipelines.

## Developer Completion Report

### Changed Files

- `mediaflow/domain/notification.py` — delivery recovery domain: `NotificationDeliveryConflict`
  exception carrying bounded current-row evidence, `resolve_stale_delivery` repository authority and
  the optional `expected_updated_at` concurrency guard on dead-letter requeue in the
  `NotificationRepository` protocol; shared `DELIVERY_LEASE_DEFAULT_SECONDS`.
- `mediaflow/infrastructure/sqlite_runtime.py` — `requeue_dead_letter` now optionally guards on the
  exact durable `updated_at`; new atomic `resolve_stale_delivery` transition (delivering +
  expired-lease boundary + exact observed timestamp → pending, attempts preserved).
- `mediaflow/application/notification_delivery.py` (new) — shared `NotificationDeliveryService`:
  bounded delivery detail projection (lease/staleness, known effects, retry safety, next action,
  available recovery actions) and the two recovery authorities (dead-letter requeue, stale resolve)
  with optimistic concurrency, redacted service audit and no body/secret exposure.
- `mediaflow/interfaces/service_api.py` — delivery detail route
  `GET /api/v1/notifications/{deliveryId}` (READ); explicit recovery routes
  `POST /api/v1/notifications/{deliveryId}/requeue` and
  `POST /api/v1/notifications/{deliveryId}/resolve-stale` (MANAGE_CONFIGURATION); the shared
  service instance; a `notification_delivery_conflict` 409 handler carrying the current durable
  delivery projection; and the lease-window resolver (managed runtime config with domain default).
- `mediaflow/interfaces/operator_ui.py` — Notifications deliveries list is a discoverable
  list-to-detail journey (clickable rows), with a delivery detail view showing durable state, lease,
  known effects, retry safety, next action and the explicit recovery action, plus a confirmation
  showing the at-least-once / duplicate-delivery implication before submitting the exact
  `expectedStatus`/`expectedUpdatedAt` payload; after recovery the same delivery is refreshed and
  the sibling list stays reachable.
- `tests/test_notification_delivery_management.py` (new) — focused delivery detail, permission,
  status/lease visibility, recovery success/ineligible/stale/conflict, concurrency, audit,
  redaction, no-side-effect, Worker-compat and API/Web parity tests.
- `tests/test_operator_ui.py` — the scheduler/notification bounded-view test now also asserts the
  delivery detail + explicit per-delivery recovery surface and exact recovery payloads.

### Implemented

- One bounded delivery detail projection per exact delivery identity. It exposes deliveryId,
  Webhook/event identity, status, attempts, created/updated/delivered/next-attempt timestamps,
  failure category, response status, lease/staleness evidence (claimedAt, lease window, expiry,
  active/expired state), a known-effects statement, retry safety, a deterministic next action and
  the explicitly available recovery actions with per-action durable state, side effects, retry
  safety, duplicate-delivery implication and next action. Delivery bodies, event payloads, secrets,
  authorization material and remote response content are never projected; unknown or malformed
  delivery ids return the existing bounded 404 shape.
- One shared application authority (`NotificationDeliveryService`) used by the API and, through the
  same endpoints, by the Web for every read and recovery. Recovery is optimistic-concurrency bound
  to the exact durable `status` + `updatedAt` the operator observed and is applied atomically in the
  repository (status + timestamp guarded SQL), so ineligible, already-resolved, stale-version and
  concurrent requests fail closed with a 409 carrying the current durable delivery projection and a
  next action, without changing the delivery or any sibling row.
- Two explicit Web/API recovery operations: `requeue-dead-letter` (dead-letter → pending, attempts
  reset, Worker sends again) and `resolve-stale` (expired-lease delivering → pending, attempts
  deliberately preserved, never silently reset). Both keep the same delivery identity and row,
  never create a second delivery, never touch unrelated deliveries and never alter Webhook
  definitions, Draft/Active configuration, Jobs, schedules, Storage or completed Task/Result/media
  history. Automatic Worker retry, lease claim fencing and stale reclamation remain untouched and
  compatible (verified by Worker-compat tests that deliver after each manual recovery).
- Redacted audit: successful recovery appends a bounded `notification-recovery` security audit with
  delivery identity/action/status transition; denied (403) and conflicting (409) actions are
  audited by the API security boundary. Detail reads are covered by the existing per-request API
  audit; notification route identity is path-redacted like the rest of the API audit.
- Web parity: the Notifications view lists deliveries, opens the exact delivery detail, shows the
  same durable evidence and recovery action before an explicit confirmation (including the
  duplicate-delivery implication), posts the exact `expectedStatus`/`expectedUpdatedAt` payload used
  by the API, refreshes the same delivery afterwards and keeps sibling outcomes visible through the
  list. Refreshing, filtering and opening detail perform no mutation.

### Tests and Results

```text
python3 -m unittest tests.test_notification_delivery_management       -> PASS (10 tests)
python3 -m unittest <all 11 Task focused modules>                     -> PASS (239 tests)
python3 -m unittest discover -s tests (project venv python)           -> 1348 run; 1 FAIL
  PRE-EXISTING / UNRELATED (tests.test_storage_browser); 7 SKIP (external profiles absent)
python3 scripts/check_governance.py                                   -> PASS
ruff format --check .                                                 -> FAIL / PRE-EXISTING
  (only tests/test_system_settings_management.py, unformatted at Task Base)
ruff check .                                                          -> FAIL / PRE-EXISTING
  (only E501 in tests/test_system_settings_management.py, present at Task Base)
python3 -m compileall -q mediaflow tests scripts                      -> PASS
python3 -m pip check                                                  -> PASS
git diff --check                                                      -> PASS
node --check on the served operator app.js                            -> PASS
```

### Decisions

- Manual recovery is gated by the existing `manage_configuration` permission, the same applicable
  authority the Webhook definition/test action already uses (Task 28.4), rather than a new
  permission; read detail is gated by the `read` authority shared with the delivery list.
- The durable concurrency token is the row's `status` + `updatedAt` (the schema's persisted change
  marker) instead of a new numeric column: the delivery schema has no version column and the runtime
  `SCHEMA_VERSION` marker is shared with the frozen Worker claim-fencing protocol whose tests bind
  registered workers to the current marker. The repository applies both guards atomically in SQL so
  worker-vs-operator and operator-vs-operator races fail closed without a schema migration.
- Recovery is strictly per-delivery and per-state: dead-letter requeue resets attempts (existing
  requeue semantics), while stale-delivery recovery returns the row to pending and deliberately
  preserves attempts so an operator action never silently resets the attempt budget. Both paths
  preserve the delivery identity/row and surface the at-least-once/duplicate-delivery implication.
- Staleness uses the delivery lease window consumed by the Notification Worker (managed Active
  runtime `notifications.deliveryLeaseSeconds`, falling back to the shared 300 s default when no
  Active snapshot is available to the surface), so the operator projection agrees with Worker claim
  fencing.
- Detail reads do not add a second application audit record: the existing per-request API security
  audit already covers delivery detail access (the file/scan read-only suppression does not apply to
  notifications), matching the read-only notification list boundary.

### Remaining In-Slice Work

None inside this Task. RO-6 delivery detail/recovery is implemented through the shared
Notifications Web/API journey; other Slice 28 units remain separate Tasks.

### Risks / Deviations

- `tests.test_storage_browser.test_setup_picker_and_execution_environment_guidance_are_present`
  fails at the Task Base (verified on `HEAD:mediaflow/interfaces/operator_ui.py`, where the asserted
  phrase is absent too) and is unrelated to this Task.
- `ruff format --check .` and `ruff check .` each report the same pre-existing issue in
  `tests/test_system_settings_management.py` present at the Task Base; that file was left untouched.
- The full suite must be run with the project venv (optional extras such as `httpx`). With the
  system interpreter, `test_runtime_strategy_configuration...openlist...` additionally errors with
  `ModuleNotFoundError: No module named 'httpx'`; with the venv that module passes and only the
  pre-existing storage-browser failure remains.
- Seven optional external acceptance tests skip with their standard environment-absent reasons (no
  real SMB/OpenList/S3/TMDB endpoints).
- No schema migration was performed and `SCHEMA_VERSION` was not bumped; the recovery concurrency
  token is the durable `status` + `updatedAt` (see Decisions).

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
finds a genuinely independent business goal. This result does not close the Slice or update
Roadmap.
