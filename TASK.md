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

(Correction round for the B Review Result below; the first checkpoint's report
remains in Git history at `58d17f6678c6c794a108bff19355c6f7706be30e`.)

### Changed Files

- `mediaflow/interfaces/service_api.py` — the operations Webhook test now binds to the exact
  currently advertised revision before any transport invocation: after the optimistic version
  check, `_notification_webhook_operator_test` resolves the definition via
  `_notification_webhook_resolution` and rejects any revision that is neither the Active revision
  containing this definition nor the eligible open successor Draft containing it (409
  `configuration_version_conflict`, digest-free, `durableState: "no test request was sent"`). The
  checked-activation success document now additionally echoes the exact reviewed Draft identity
  (`publishedFromRevisionId`, `publishedFromVersion`) so the Web client can bind the success
  document to the submitted mutation.
- `web/src/features/operations/NotificationNewPage.tsx` — removed the client-side
  `/(secret|token|authorization|execute)/i` value-substring rejection from both the identifier and
  the `secretEnv` value (the canonical deployment-owned reference
  `MEDIAFLOW_WEBHOOK_SECRET` is accepted again). The canonical environment-name shape check, the
  URI-safe identifier check, the HTTPS endpoint checks and the server-side canonical validator
  (unknown fields, forbidden literal field names, unsafe schemes, credential-bearing URL
  components) remain authoritative.
- `web/src/entities/operations/notification.ts` — fail-closed identity and request-binding
  boundary: strict URI-safe segment validation (`NOTIFICATION_URI_SAFE_SEGMENT`) for definition,
  Draft-document, delivery, webhook and event identities; delivery detail now fails closed on a
  lease window inconsistent with the durable status (lease ⟺ `delivering`), on requeue
  eligibility without `dead-letter`, on stale-resolution eligibility without `delivering` +
  expired lease, and on recovery evidence not advertised in `availableActions`;
  `normalizeWebhookTestResult`, `normalizeNotificationActivation` and
  `normalizeNotificationRecoveryResult` take a required request binding and fail closed when the
  success document names another Webhook/revision/version, another delivery/action, an observed
  fence that differs from the request, an impossible transition, or an inconsistent Active
  identity.
- `web/src/shared/api/api-client.ts` — the test, checked-activation and recovery mutations pass
  their exact request identity into the normalizers, so a misbound response surfaces as a
  `malformed_response` rejection instead of rendered success.
- `tests/test_v2_notification_operations.py` — new
  `test_superseded_revision_is_rejected_before_any_request` regression (activate a successor
  Draft, then post the superseded predecessor's exact id and version → 409, `no test request was
  sent`, zero transport requests, while the exact current Active revision still tests with one
  request) plus `publishedFrom*` echo assertions in the activation journey; 25 tests total.
- `web/src/entities/operations/notification.test.ts` — binding tests and hostile contract cases:
  wrong-object test outcomes (other webhook/revision/version, unsafe identity), activation
  responses answering another webhook or reviewed revision or an inconsistent Active identity or
  a missing definition, recovery results about another delivery/action/transition, unsafe
  delivery/webhook/event identities, and status/lease/eligibility contradictions.
- `web/src/features/operations/NotificationRouter.test.tsx` — real submission journeys for
  create (canonical body with `MEDIAFLOW_WEBHOOK_SECRET` accepted, exact Draft version), copy,
  enable and disable with exact optimistic version bodies, a wrong-object test outcome that must
  not render success, and contradictory delivery documents (requeue transport on a delivered
  status, transport bound to another delivery) that render the fail-closed boundary with zero
  mutations; the signed-test fixture now echoes the requested revision.
- `web/tests/fake-server.mjs` — hostile wrong-object probe (`reset-notifications?hostile=1`)
  serving test/recovery success documents about another Webhook/delivery, the truthful activation
  echo fields, and a generalized Webhook detail route so the copied definition's detail journey
  resolves; the bounded evidence allowlist is unchanged.
- `web/tests/e2e/notifications.spec.ts` — the editor journey now really clicks Save (and asserts
  the `notification_webhook_save` evidence), plus three new built-artifact journeys: create
  inside the open Draft, copy + enable + disable toggles with exact version fences, and the
  hostile wrong-object contract probe (test and requeue success documents never render success;
  the delivery keeps its truthful state).
- `TASK.md` — this correction report.

### Implemented

- B blocker 1 (unresolvable checkpoint): the correction checkpoint below is created without
  amending reviewed history, and its exact full SHA is recorded by a follow-up `docs(task)`
  checkpoint generated from `git rev-parse HEAD` (never hand-transcribed) and verified with
  `git cat-file -e`.
- B blocker 2 (create journey rejected the canonical secret reference): removed the
  value-substring rejection; the component create journey and a browser create journey now
  actually submit the canonical form with `MEDIAFLOW_WEBHOOK_SECRET`, and the editor journey
  really saves; component and browser suites exercise create, edit/save, copy and enable/disable
  end to end with exact revision/version bodies.
- B blocker 3 (superseded revision testable): the operations test route now rejects any revision
  that is not the exact advertised Active revision (for a definition it contains) or the eligible
  open successor Draft before transport invocation, with a same-version/superseded regression
  proving zero requests; the Web success normalizers are bound to the requested
  Webhook/revision/version.
- B blocker 4 (typed identity/contradiction boundary): strict URI-safe identities, delivery
  detail eligibility/lease contradiction fail-closed enforcement, and cross-field/request binding
  for test, activation and recovery responses, each covered by hostile typed, component and
  browser contract cases.

### Tests and Results

All commands run from the repository root; every gate below was executed for this correction
checkpoint.

- `python3 scripts/check_governance.py` — PASS.
- `env -u NODE_ENV npm --prefix web ci` — PASS (0 vulnerabilities).
- `npm --prefix web run format:check` — PASS.
- `npm --prefix web run typecheck` — PASS.
- `npm --prefix web run lint` — PASS.
- `npm --prefix web run test -- --run` — PASS: 422/422 (34 files), 0 skipped.
- `npm --prefix web run build` — PASS.
- `npm --prefix web run test:e2e -- notifications.spec.ts operations.spec.ts deep-link.spec.ts`
  — PASS: 55 passed.
- `npm --prefix web run test:e2e` — PASS: 117 passed.
- `.venv/bin/python -m unittest tests.test_v2_notification_operations` — PASS: 25 tests.
- `.venv/bin/python -m unittest tests.test_webhook_management
  tests.test_notification_delivery_management tests.test_notifications
  tests.test_webhook_url_security tests.test_restart_fault_boundary
  tests.test_configuration_objects tests.test_configuration_management tests.test_dashboard
  tests.test_operations_workspace tests.test_api_security tests.test_v2_ui` — PASS: 171 tests
  (the first checkpoint's report listed 195 for this command; the actual total of the eleven
  named modules is 171, and 195 equals 171 plus the 24 focused tests counted in the adjacent
  line — reported here as measured).
- `.venv/bin/python -m unittest discover -s tests` (repository-root CWD) — 1539 tests,
  6 failures, 7 skipped: `FAIL / PRE-EXISTING / UNRELATED` (details under Risks).
- Isolated clean checkout of committed HEAD `8ef7d3b` with this correction's working diff
  applied (`git worktree`): full `unittest discover` — PASS, 1539 tests, 7 skipped, 0 failures.
- `.venv/bin/ruff format --check .` — PASS (309 files).
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS.
- `.venv/bin/mediaflow --config config/strategy.example.json config validate` — PASS.
- `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` — PASS.
- `git diff --check` — PASS.
- `python3 scripts/docker_release_security_smoke_test.py` — PASS (Docker available; release-
  security smoke acceptance passed).
- No test was deleted, renamed or weakened; existing fixtures were strengthened (the signed-test
  fixture now echoes the requested revision) and every added case is fail-closed evidence.
  `node_modules/`, build reports and private configuration remain excluded.

### Decisions

- The advertised-revision set for testing is computed as: the Active configuration revision when
  it contains this exact definition, plus the open successor Draft when
  `latest_open_draft_containing` returns one. A Draft-only definition is testable at its Draft
  revision; a definition removed from an open Draft is only testable at Active, mirroring exactly
  what the detail/draft reads advertise.
- The checked-activation response gained the additive `publishedFromRevisionId`/
  `publishedFromVersion` echo so the client can bind the success document to the submitted
  mutation; the response shape change is additive and V1/CLI clients are untouched. The client
  also cross-checks `activeConfiguration` against the activated identity and requires the
  activated definition to be present (a removal activation is unreachable from V2, whose
  activate action requires an open Draft containing the definition).
- Mutation normalizers take the request binding as a required parameter (not an optional
  override) so a future caller cannot forget it; violations throw
  `NotificationNormalizationError`, which `submitAutomationMutation` maps to a truthful
  `malformed_response` rejection rendered as a rejection — never as success.
- Both value-substring checks (identifier and `secretEnv`) were removed as one root cause: the
  canonical validator rejects forbidden field names, not values, so the identifier check was the
  same false rejection against an id like a secret-free word while the env-name shape check
  remains the real contract for the reference.
- The hostile fake injects wrong-object success documents via `reset-notifications?hostile=1`
  and the evidence body allowlist is unchanged; the create journey asserts the created identity
  through the bounded `objectId` evidence field.

### Remaining In-Slice Work

- None known to me for RO-6 itself. Slice 33 closure still needs B's Required-Outcome sweep over
  RO-1..RO-8, and Slice 34/35 own the media review/recovery and general Configuration journeys
  this Task only links to.

### Risks / Deviations

- `FAIL / PRE-EXISTING / UNRELATED`: full `unittest discover` at the repository-root CWD fails
  the same 6 tests documented in the first checkpoint (`test_api_credentials` ×2,
  `test_final_integration` ×1, `test_resource_library_pipeline` ×1,
  `test_runtime_storage_configuration` ×2) — root CWD private runtime state (untracked
  `.mediaflow/` runtime plus the CLI resolving the relative `persistence.databasePath` against
  the CWD). Fresh proof for this correction: an isolated worktree at committed HEAD `8ef7d3b`
  with this correction's exact working diff applied passes full discovery (1539 tests, 0
  failures, 7 skipped). My diff touches no CLI/config-loading code path, and the private state
  was not deleted or altered.
- Docker was available and the release-security smoke passed; nothing was inferred.
- The module-list regression total is reported as measured (171); see Tests and Results for the
  reconciliation note against the first checkpoint's 195.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 1305d0790632c5b28029c80cfda7bfa80e9a42a1
```

## B Review Result

```text
Reviewed: 86ad42ff26721ca62f61653e1f0ed9129732cbeb..58d17f6678c6c794a108bff19355c6f7706be30e
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The reported checkpoint cannot be resolved: `git cat-file -e
  58d17f68695d1ae0d8cbfd60950ce1d7ee148e53^{commit}` exits 128, while the actual implementation
  commit after Task Base is `58d17f6678c6c794a108bff19355c6f7706be30e`. Create a correction checkpoint without amending
  reviewed history and report its exact full committed SHA so the next review has one truthful,
  resolvable Head.
- The authorized create journey rejects the canonical deployment-owned secret reference used by
  this Task's own fixtures. `NotificationNewPage.tsx` applies
  `/(secret|token|authorization|execute)/i` to the `secretEnv` value, so
  `MEDIAFLOW_WEBHOOK_SECRET` always produces a form issue even though
  `WebhookDefinition.from_document` accepts that environment-variable name. Remove this
  value-substring rejection while retaining the canonical environment-name and server-side
  literal-field validation. Add component/router and built-artifact journeys that actually submit
  create, edit/save, copy and enable/disable with exact revision/version bodies; the current 39
  focused Web tests and 52 browser tests pass, but the browser "editor journey saves" test never
  clicks Save and neither suite exercises create/copy/enable/disable end to end.
- Exact displayed-revision test binding fails closed only on a missing revision or wrong version,
  not on a valid historical revision. A real API probe activated a successor, then posted the
  superseded predecessor's exact id/version to
  `POST /api/v1/operations/notifications/webhooks/operations-webhook/test`; it returned `200`,
  reported revision status `superseded`, and sent one signed request. Reject any revision that is
  not the exact currently advertised Active revision or eligible open successor Draft for that
  definition before transport invocation, and add a same-version/different-or-superseded revision
  regression proving zero requests. Also bind the Web client success normalizers to the requested
  Webhook/revision/version so a misbound response cannot render success.
- Typed delivery/test/activation/recovery normalization does not meet the required fail-closed
  identity and contradiction boundary. Delivery identities use bounded text rather than strict
  URI-safe segments; delivery detail accepts recovery eligibility/transport inconsistent with the
  durable status or lease; and test, activation and recovery mutation responses are not checked
  against the requested Webhook, revision, delivery and action/transition. Enforce those
  cross-field/request bindings before any control or success state is rendered, and add hostile
  typed/component/browser contract cases for unsafe identities, wrong-object responses and
  status/lease/action contradictions.
