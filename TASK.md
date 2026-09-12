# Task 33.5 — V2 Notification definition, test, activation and delivery recovery journey

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 33.5
Parent Slice: 33
Status: PLANNED
Task Base: 86ad42ff26721ca62f61653e1f0ed9129732cbeb
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 33 RO-6 and the applicable RO-1/RO-7/RO-8 boundary: an authorized operator can use
V2 to discover and manage a bounded Webhook Definition, distinguish its editable Draft from the
immutable Active snapshot, explicitly test and checked-activate only that exact definition, inspect
durable Notification deliveries, and invoke only an eligible exact-delivery recovery while secret
values, uncertain effects and completed media work remain isolated.

## Why This Task Exists

Task 33.4 completed the scheduled Automation journey at implementation checkpoint
`e7f29164dcfe7eb286952af17b2bf30bedcd6e9a`. Slice 33 still lacks RO-6: V2 has no Notification
routes, typed model, Webhook editor/test journey, delivery list/detail, or delivery recovery
controls, and Dashboard notification counts/failures do not lead to the exact Notification state.

The Python Application/API and V1 surface already provide managed Webhook object mutations,
exact-revision signed tests, durable Outbox delivery state, lease/dead-letter reasoning and
optimistic per-delivery recovery. This Task composes that one existing authority chain into V2.
Definition publication, explicit endpoint testing and delivery recovery are one coherent
Notification safety boundary; splitting them would leave an unusable or misleading operator
journey. No new notification channel or media-processing behavior is needed.

## Implementation Scope

Deliver the Notification journey through one bounded vertical slice:

```text
Domain/Persistence (reuse) → Application projection → /api/v1 authority → typed Web → browser proof
```

- Reuse the existing `WebhookDefinition`, managed Configuration revision/object services,
  `WebhookTestService`, Notification Outbox/repository, `NotificationDeliveryService`, Worker
  lease/retry semantics and security audit. Do not create a second Webhook store, delivery queue,
  Worker, retry engine or frontend-owned authority model.
- Add the smallest backward-compatible operator projections and action metadata needed for V2 to
  discover Webhook Definitions in the exact Active revision and eligible successor Draft, inspect
  secret-reference readiness without exposing secret values, and operate existing definition,
  validation, exact test, checked-activation and delivery behaviors.
- Add refresh-safe V2 Notification routes under `/ui-v2/operations` for the bounded definition
  list/entry, create and editor/detail journey, delivery list/filter/page and exact delivery detail.
  Link Operations and actionable Dashboard notification counts/failures to the relevant bounded
  route without placing credentials, secret references, endpoint values, optimistic versions or
  recovery authority in URLs.
- Provide a forms-first bounded Webhook editor for identifier/name-equivalent display, HTTPS
  endpoint, deployment-owned `secretEnv` reference, supported event selection, enabled state,
  timeout, attempt count and retry bounds. Persist only the canonical Webhook fields; reject unknown
  fields and literal secret/token/authorization input server-side.
- Compose successor-Draft creation and exact optimistic create/edit/copy/enable/disable behavior
  needed by the Webhook journey. A saved or validated Draft must remain visibly distinct from the
  immutable Active definition consumed by the Notification Worker.
- Provide a separate explicit Webhook test action for one exact advertised revision/version. The
  server retains any configuration digest and resolved secret; the browser neither receives nor
  submits them. One test sends at most one signed request, never retries automatically, never
  creates/updates a delivery, never activates configuration and never touches Task, Job, schedule,
  Storage or media state. Results expose only bounded outcome category/status and a valid next
  action, never response bodies, raw exceptions, secret values or credential-bearing endpoints.
- Add Webhook-object-scoped checked activation bound to the exact advertised Draft revision and
  optimistic version. It must fail closed if another Webhook Definition or any other configuration
  section changed, preserve Active and Draft on rejection, publish no unrelated change, start no
  delivery or media work, and report the resulting exact Active identity without a digest.
- Compose bounded delivery list filtering/paging and exact detail for
  `pending`/`delivering`/`retry`/`delivered`/`dead-letter`. Show attempts, lease state,
  bounded failure/status evidence, known/unknown receiver effects, at-least-once duplicate
  implications and the smallest valid next action without exposing the stored body or secret.
- Offer only backend-advertised recovery actions: an exact optimistic dead-letter requeue and an
  exact expired-lease stale resolution. Require explicit user intent where another outbound request
  may occur; never automatically replay either mutation after stale state, ambiguity, 401/403,
  malformed data or network failure. A transition keeps the same delivery identity, does not alter
  sibling deliveries or Webhook definitions, and cannot submit/replay media work.
- Keep current permissions authoritative: reads require the appropriate read permission;
  definition/test/activation and delivery recovery controls require their existing backend
  permissions and are absent or disabled with a truthful reason otherwise. UI visibility never
  grants permission.
- Use central route metadata, typed entity normalization, shared API helpers and TanStack Query
  boundaries. Components perform no raw `fetch`, cache no authority and fail closed on malformed,
  contradictory or misbound definitions, revisions, tests, deliveries, cursors or action
  transports.
- Extend the deterministic browser fake with secret-free Notification state and exact method/body
  assertions. Tests use fake transports and temporary SQLite/configuration state only; no real
  endpoint, production credential, user media or Internet access is permitted.
- If an additive persistence/schema change is genuinely necessary, make it forward-only,
  fail-closed, atomic and restart-tested using temporary copied fixtures.

Frozen for this Task:

- `SLICE.md`, `docs/roadmap.md`, canonical/stable requirements, product-experience and
  architecture authority text, including Slice Base and all A-owned Contract fields.
- Automation, manual Scan/Preview/Organize, Task/Job and Library behavior already completed by
  Tasks 33.1–33.4 except the minimal route/cross-link integration required for Notification.
- General Configuration/Settings administration, arbitrary managed-object lifecycle, revision
  comparison/evidence, import/export and activation outside the exact Webhook-object flow; those
  remain Slice 35.
- Media review/recovery actions owned by Slice 34. Notification recovery may not imitate
  Reprocess, checkpoint continuation or failed-item retry.
- Notification Worker delivery/retry semantics, new channels/providers, payload design, arbitrary
  replay, auth redesign, Node production serving, `config/alist.json` and private runtime state.

## Acceptance Criteria

- [ ] `/ui-v2/operations/notifications` is a real entry surface linked from Operations and the
      actionable Dashboard; supported Webhook definition/editor and delivery list/detail routes are
      refresh-safe and use the shared memory-only authentication continuation.
- [ ] Definition list/detail shows the exact immutable Active configuration and a distinct eligible
      Draft with its optimistic version/validation state. Missing Active/Draft/runtime,
      read-only/forbidden and unavailable states offer only a valid successor-Draft or V1
      Configuration handoff; no Draft is labeled Active.
- [ ] An authorized operator can create, copy, edit and enable/disable a bounded Webhook Definition.
      HTTPS endpoint, deployment-owned secret reference, supported unique events, enabled state,
      timeout, max attempts and retry bounds use the canonical server validator; unknown fields,
      literal secrets/tokens/authorization, credential-bearing URL components and unsafe schemes
      fail closed without changing the Draft.
- [ ] Every definition mutation is bound to the exact Draft revision and expected version.
      Stale/concurrent create/edit/copy/enable/disable is rejected atomically, preserves the winning
      revision and refreshes durable truth without automatic mutation replay.
- [ ] An explicit test is bound to the exact displayed definition and revision/version while digest
      and resolved secret remain server-side. It sends exactly one signed test request and performs
      no retry, delivery enqueue/change, activation, Task/Job/schedule action, media work or Storage
      mutation. Success, HTTP rejection, rate-limit/server error, timeout, transport failure,
      invalid definition, missing secret and stale revision return bounded recovery evidence.
- [ ] Checked activation is a separate meaningful action and publishes only an eligible revision
      whose sole change is the reviewed Webhook Definition. A sibling Webhook add/remove/edit or
      any non-Webhook configuration change returns a bounded conflict, preserves Active and Draft,
      and activates nothing. Success reports the new exact Active identity and creates no delivery.
- [ ] Delivery list/filter/paging and exact detail truthfully distinguish all durable statuses,
      attempts, response category/status, due time and active/expired lease. Stored bodies, signed
      headers, secret values, raw exceptions and private endpoint material never enter the API
      operator model, browser, DOM, URL, console, audit or captured test artifact.
- [ ] Only an eligible dead-letter delivery advertises requeue, and only an eligible expired
      `delivering` lease advertises stale resolution. Each action submits the exact delivery
      identity plus observed status/update fence, requires current permission and explicit intent,
      preserves the same row identity, and reports at-least-once/possible-duplicate consequences.
- [ ] Stale/concurrent/repeated/wrong-status recovery, an unexpired lease, insufficient permission,
      malformed action evidence, 401/403 and ambiguous transport failure fail closed without an
      automatic mutation replay. The latest durable delivery is shown with a valid refresh or
      repair action.
- [ ] Delivery recovery changes neither sibling deliveries, Webhook definitions, Active/Draft
      configuration, completed Task/Job/Result state nor media/Storage. A read, render, navigation,
      definition test or checked activation never emits or replays a normal delivery.
- [ ] Notification failures link to exact delivery state when safe; endpoint/definition repair
      hands off truthfully to the owned Webhook Draft journey or V1 Configuration until Slice 35.
      Completed and automatic-retry deliveries do not advertise manual recovery.
- [ ] Typed normalization rejects unknown/contradictory definition, revision, readiness, test,
      delivery, lease, cursor, permission or action transport data. Definition and delivery
      identities are strict URI-safe values; exact routes/methods/bodies are enforced by API and
      browser tests.
- [ ] V1 `/ui`, existing Webhook/configuration/notification API and CLI clients, Tasks 33.1–33.4
      routes, Notification Worker behavior and Python-only production serving remain compatible.
- [ ] Component/router and built-artifact evidence covers definition create/copy/edit/enable state,
      Active/Draft distinction, exact test and checked activation, delivery filtering/detail and
      eligible recovery, Dashboard links, permissions, stale/concurrent/malformed/401/403/
      unavailable states, no replay and keyboard-usable narrow/wide layouts.
- [ ] All T4 commands below pass with actual totals/skips/unavailable gates reported. The checkpoint
      contains only this Task plus its Developer report; no test/assertion is deleted or weakened,
      skips are not hidden and all unrelated/private files remain excluded.

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
npm --prefix web run test:e2e -- notifications.spec.ts operations.spec.ts deep-link.spec.ts
npm --prefix web run test:e2e
.venv/bin/python -m unittest tests.test_v2_notification_operations
.venv/bin/python -m unittest tests.test_webhook_management tests.test_notification_delivery_management tests.test_notifications tests.test_webhook_url_security tests.test_restart_fault_boundary tests.test_configuration_objects tests.test_configuration_management tests.test_dashboard tests.test_operations_workspace tests.test_api_security tests.test_v2_ui
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

Create `tests/test_v2_notification_operations.py` and
`web/tests/e2e/notifications.spec.ts`; add focused typed-entity and router/component tests under
the existing Web boundaries. Docker may be `UNAVAILABLE` only with the observed environmental
reason and must never be inferred as passing.

Focused evidence must cover exact Draft/Active separation and optimistic mutation; canonical
Webhook validation/redaction; digest-free exact-revision test binding and one-request/no-delivery
isolation; Webhook-object-scoped checked activation including sibling and general-configuration
rejection; all delivery/lease statuses; bounded filter/paging; permission-gated exact recovery;
stale/repeated/concurrent action fencing; sibling/configuration/media isolation; at-least-once
explanation; Dashboard/deep-link behavior; malformed contract fail-closed behavior; V1/API/CLI
compatibility; Notification Worker restart persistence; no mutation replay; and secret/private
artifact scanning. Use only temporary databases/configuration, local fake transports and synthetic
delivery rows.

If schema changes, add forward-migration, newer-schema rejection, atomic failure and API/
Notification Worker restart tests against temporary copied fixtures. Before checkpointing, inspect
and report `git status --short`, the complete Task Base..Head diff, name/status/stat, any test
deletion/rename/skip/assertion change, and tracked/private configuration. `config/alist.json`,
`node_modules`, build reports, credentials and unrelated files must not enter the checkpoint.

## Non-goals

- General Configuration/Settings administration, revision comparison/evidence, import/export or
  activation outside the exact Webhook-object flow owned here.
- Automation changes, manual media operation/recovery, Task/Job controls or Slice 34 review and
  recovery behavior.
- Definition deletion unless existing shared behavior is required internally for a focused
  activation-scope regression; deletion is not a promised V2 action in this Task.
- New notification event types, email/chat/media-server channels, payload customization, arbitrary
  replay, bulk recovery, automatic uncertain replay or changes to Worker retry/backoff semantics.
- A general Secret Store, showing/resolving secret values, built-in identity/OIDC, Node/SSR/BFF
  serving, V1 retirement, optional copy polish, P2/P3 cleanup or unrelated refactoring.

## Developer Completion Report

### Changed Files

- `mediaflow/interfaces/service_api.py` — new bounded `/api/v1/operations/notifications/*`
  projections: Webhook definitions list/detail/draft reads, digest-free exact-revision Webhook
  test, Webhook-object-scoped checked activation, permission-aware delivery detail alias; audit
  route normalization; `NOTIFICATION_DEFINITIONS_PAGE_LIMIT`.
- `tests/test_v2_notification_operations.py` — new focused Python integration/security evidence
  (24 tests).
- `web/src/entities/operations/notification.ts` (+ `.test.ts`) — fail-closed typed Notification
  models, action transport contracts and page/draft/test/delivery/recovery normalizers.
- `web/src/entities/operations/action-transport.ts` — additive bounded `sideEffects` tokens
  (`one_signed_test_request`, `delivery_queue_state_only`).
- `web/src/shared/api/api-client.ts` — Notification reads/mutations over the projections and the
  existing managed-configuration/notification routes.
- `web/src/features/operations/notification-query.ts`, `NotificationListPage.tsx`,
  `NotificationNewPage.tsx`, `NotificationDetailPage.tsx`, `NotificationEditorPage.tsx`,
  `DeliveryListPage.tsx`, `DeliveryDetailPage.tsx`, `NotificationRouter.test.tsx` — new V2
  Notification journey surface and component/router evidence.
- `web/src/routes/router.tsx`, `web/src/shared/navigation/destination-model.ts` (+ test) — six
  refresh-safe routes with the shared auth continuation; deliveries route keeps its hyphenated
  status filter in the deep-link allowlist.
- `web/src/features/dashboard/DashboardView.tsx`, `OperationsLanding.tsx` — Dashboard
  dead-letter count and notification failure link the exact delivery state; Operations workspaces
  nav links the Notification workspace.
- `web/tests/fake-server.mjs`, `web/tests/e2e/notifications.spec.ts` — deterministic
  Notification fake state/evidence and 8 built-artifact browser proofs.
- `TASK.md` — this Task definition plus this report.

### Implemented

- Definitions list/detail/draft operator documents with the exact immutable Active identity, a
  visibly distinct Draft (including Draft-only definitions), secret-reference readiness (env name
  + SET/UNSET only), canonical validator redaction and backend-authoritative action metadata
  gated on the connected principal.
- Create/edit/copy/enable/disable composed over the existing managed-configuration object routes
  with exact optimistic version fencing; stale/concurrent mutation is rejected atomically and
  preserves the winning revision; unknown fields and literal secret/token/authorization input are
  rejected server-side by the canonical validator.
- Explicit Webhook test bound to the exact advertised revision id + version: the configuration
  digest is resolved server-side and never enters the browser (the V1 test route keeps its digest
  contract), one signed request per action, no retry, no delivery, no activation and no
  Task/Job/schedule/Storage/media effect; bounded outcome categories for success, HTTP
  rejection, 429/5xx, timeout, transport failure, invalid definition, missing secret and stale
  revision.
- Webhook-object-scoped checked activation bound to the exact Draft revision + version and the
  pinned Active base: section confinement (with the legacy `notifications.webhooks` spelling
  normalized so the managed spelling migration is not misread as an unrelated change) plus
  per-definition identity comparison reject sibling Webhook and any general-configuration
  change; success reports the new exact Active identity without a digest and creates no delivery.
- Delivery list/filter/paging and exact detail reuse the existing durable Notification routes;
  the operations detail alias adds permission-aware recovery action metadata. Recovery is
  eligible-only (dead-letter requeue, expired-lease stale resolution), confirmation-gated,
  optimistic on the observed status/update fence, identity-preserving, sibling/configuration/
  media-isolated and never replayed automatically after stale/conflict/401/403/malformed or
  transport failure.
- Dashboard: notification failures link the exact delivery detail route when the identifier is a
  bounded URI-safe segment; the dead-letter count links the filtered deliveries route. Operations
  landing links the workspace. All routes are refresh-safe deep links under the shared
  memory-only auth continuation.

### Tests and Results

All commands run from the repository root; every gate below was executed for this checkpoint.

- `python3 scripts/check_governance.py` — PASS.
- `env -u NODE_ENV npm --prefix web ci` — PASS (0 vulnerabilities).
- `npm --prefix web run format:check` — PASS.
- `npm --prefix web run typecheck` — PASS.
- `npm --prefix web run lint` — PASS.
- `npm --prefix web run test -- --run` — PASS: 398/398 (34 files), 0 skipped.
- `npm --prefix web run build` — PASS.
- `npm --prefix web run test:e2e -- notifications.spec.ts operations.spec.ts deep-link.spec.ts`
  — PASS: 52 passed.
- `npm --prefix web run test:e2e` — PASS: 114 passed.
- `.venv/bin/python -m unittest tests.test_v2_notification_operations` — PASS: 24 tests.
- `.venv/bin/python -m unittest tests.test_webhook_management
  tests.test_notification_delivery_management tests.test_notifications
  tests.test_webhook_url_security tests.test_restart_fault_boundary
  tests.test_configuration_objects tests.test_configuration_management tests.test_dashboard
  tests.test_operations_workspace tests.test_api_security tests.test_v2_ui` — PASS: 195 tests.
- `.venv/bin/python -m unittest discover -s tests` (repository-root CWD) — 1538 tests,
  6 failures, 7 skipped: `FAIL / PRE-EXISTING / UNRELATED` (details under Risks).
- Isolated clean checkout of the Task Base (`git worktree` at `86ad42f`): full
  `unittest discover` — PASS, 1538 tests, 7 skipped, 0 failures.
- `.venv/bin/ruff format --check .` — PASS (309 files).
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS.
- `.venv/bin/mediaflow --config config/strategy.example.json config validate` — PASS.
- `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` — PASS.
- `git diff --check` — PASS.
- `python3 scripts/docker_release_security_smoke_test.py` — PASS (Docker available; release-
  security smoke acceptance passed).
- No test was deleted, renamed or weakened; the destination-model contract test was extended with
  the six new destinations; the shared `ACTION_SIDE_EFFECTS` enum gained two additive tokens.
  `node_modules/`, build reports and private configuration remain excluded.

### Decisions

- The operations projections reuse `_automation_active_configuration`/`_automation_draft_state`
  shapes so the two object-scoped journeys stay structurally identical for operators and
  normalizers.
- The checked-activation confinement canonicalizes the legacy `notifications.webhooks` spelling
  on both documents before the section comparison, because the managed Webhook edit path itself
  migrates that spelling to the root `webhooks` section; without this, the first Webhook-only
  edit inside a legacy-spelled Active document would be falsely rejected (and, conversely, the
  identity comparison always reads the effective webhook section).
- The digest-free test route resolves the exact revision server-side and hands the digest to the
  existing `WebhookTestService`; the response's `revision.digest` is dropped only on this
  surface, keeping the V1 route's existing contract intact.
- Delivery recovery transports are advertised on a new `/api/v1/operations/notifications/
  deliveries/{id}` read alias that composes the shared `NotificationDeliveryService` document
  with permission-aware action metadata, so the UI can hide controls truthfully instead of
  guessing from a 403.
- The shared `ACTION_SIDE_EFFECTS` contract gained two bounded tokens instead of weakening
  normalizers to free text.

### Remaining In-Slice Work

- None known to me for RO-6 itself. Slice 33 closure still needs B's Required-Outcome sweep over
  RO-1..RO-8 (Dashboard/Operations links and cross-surface recovery wording are A/B acceptance
  calls), and Slice 34/35 own the media review/recovery and general Configuration journeys this
  Task only links to.

### Risks / Deviations

- `FAIL / PRE-EXISTING / UNRELATED`: full `unittest discover` at the repository-root CWD fails 6
  tests (`test_api_credentials` ×2, `test_final_integration` ×1,
  `test_resource_library_pipeline` ×1, `test_runtime_storage_configuration` ×2). Root cause is
  the existing root-CWD private runtime state (untracked `.mediaflow/` managed runtime plus the
  CLI resolving the relative `persistence.databasePath` against the CWD), which makes the CLI
  print the deployment's real Active state instead of the fixture. Proof: the Task Base commit
  `86ad42f` run against the same CWD fails the same 6 tests identically, and the isolated clean
  checkout of the same Base passes full discovery. My diff touches none of the affected
  CLI/config-loading code paths. The private state was not deleted or altered (running the suite
  at root CWD appends scan Task records to it — a pre-existing property of the root-CWD suite,
  identical at Base).
- Docker was available and the release-security smoke passed; nothing was inferred.
- The e2e delivery-recovery evidence records bounded request fields only; the fake's evidence
  field allowlist gained the additive keys `action`, `deliveryId`, `expectedStatus`,
  `expectedUpdatedAt`, `webhookId`.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: PENDING_COMMIT
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
