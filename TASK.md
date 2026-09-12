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

(Second correction round for the B Review Result below; the first correction's
report remains in Git history at `7cf373541a84e7e66b7f6ac782b23987c551057d`.)

### Changed Files

- `web/src/entities/operations/notification.ts` — new fail-closed
  `normalizeWebhookDefinitionMutation` for the four definition mutations: the
  success document must name the exact submitted Draft `revisionId` and the
  one-shot successor `version` (`expectedVersion + 1`), must carry a
  definition document under the mutation's own response key (`webhook` for
  create/save, `object` for copy/enable/disable), and its `id` must be a
  strict URI-safe segment (`NOTIFICATION_URI_SAFE_SEGMENT`) equal to the exact
  created/edited/toggled identity. A copy is bound to its derived source
  family (a `{source}-copy…` id inside the managed 64-character allocator
  bound) or, when the request pinned `newId`, to that exact identity; the
  copied/toggled `enabled` state must match the requested outcome. A missing
  definition, a missing version, another revision, any other or unsafe
  identity, or a contradictory toggle throws `NotificationNormalizationError`
  and never renders as success.
- `web/src/entities/operations/notification.ts` —
  `normalizeNotificationActivation` now also requires
  `activatedRevisionId`/`activatedVersion` to equal the request binding: the
  activated pair, the `publishedFrom*` echo, the request and the
  `activeConfiguration` block must all describe the same exact Draft
  revision/version (the managed activation preserves the Draft identity as the
  new Active identity). A split-identity activation document fails closed.
- `web/src/shared/api/api-client.ts` — `createWebhookDefinition`,
  `saveWebhookDefinitionDraft`, `copyWebhookDefinition` and
  `setWebhookDefinitionEnabled` pass operation-specific request bindings into
  the new normalizer and return the bound `WebhookDefinitionMutationModel`;
  the create request additionally pre-validates the submitted id as a strict
  URI-safe segment so the server cannot accept an identity the client could
  never render. A malformed/missing/wrong-object/wrong-revision success
  document surfaces as a `malformed_response` rejection, never as success.
- `web/src/features/operations/NotificationNewPage.tsx` — removed the
  `result.model.id ?? webhookId` fallback: navigation uses only the exact
  bound created identity, so a response without the created definition can
  never render navigation as success.
- `web/src/features/operations/NotificationDetailPage.tsx` — the copy
  navigation uses only the exact bound copied identity (no nullable id
  fallback).
- `web/src/entities/operations/notification.test.ts` — the activation happy
  path now submits the truthful managed contract (the Draft identity is the
  new Active identity) and a new hostile case proves a split-identity
  activation (`rev-active-2`/5 vs the reviewed `rev-draft`/4) fails closed;
  the new `webhook definition mutation result` describe covers create/save/
  unpinned copy/pinned copy/enable/disable success bindings plus
  wrong-revision, non-successor version, missing/non-object/wrong/unsafe
  identity, source-or-unrelated copy answers and contradictory toggles
  (29 tests in the file, 55 focused total).
- `web/src/features/operations/NotificationRouter.test.tsx` — the editor
  fixtures now mirror the real managed semantics (the save response carries
  the successor version; the activation preserves the Draft identity), and the
  copy/enable/disable journey advances the exact optimistic fence per stored
  mutation (enable submits v5, disable v6). New
  `Notification definition mutation binding` describe with five built-journey
  hostile cases: a wrong-revision create, a save without the saved
  definition, a wrong-object copy, a contradictory enable toggle and a
  split-identity activation each render rejection with exactly one submitted
  mutation, no follow-up mutation and no false success (25 tests in the file).
- `web/tests/fake-server.mjs` — the `?hostile=1` wrong-object probe now also
  answers the four definition mutations with a wrong-revision create, a save
  without a definition, a wrong-object copy and a contradictory toggle, and
  the activation with a split identity; the truthful responses now mirror the
  real managed contract (copy stores disabled, enable/disable store the
  submitted toggle).
- `web/tests/e2e/notifications.spec.ts` — the hostile built-artifact journey
  now really submits create (wrong-revision create document rejected, no
  navigation as success), copy (wrong-object copy document rejected, the
  detail page stays on the reviewed source) and the split-identity activation
  (rejected once, never replayed, exactly one activation recorded with the
  exact Draft binding) alongside the existing test/recovery probes.
- `TASK.md` — this correction report.

### Implemented

- B blocker 1 (definition-mutation responses not fail-closed): all four
  mutations (`createWebhookDefinition`, `saveWebhookDefinitionDraft`,
  `copyWebhookDefinition`, `setWebhookDefinitionEnabled`) are now bound to the
  exact submitted Draft revision, the expected successor version and the exact
  created/edited/toggled/copied identity with strict URI-safe response
  identities; create no longer falls back to the request id. Hostile typed,
  component and built-artifact evidence proves malformed/missing/wrong-object/
  wrong-revision success documents render rejection with no follow-up
  mutation and no false success.
- B blocker 2 (checked-activation success binding accepted a different Active
  identity): the normalizer now requires `activatedRevisionId`/
  `activatedVersion`, `publishedFromRevisionId`/`publishedFromVersion`, the
  request binding and `activeConfiguration` to describe that same exact
  revision/version; typed, component and built-artifact hostile evidence
  proves a split-identity activation response cannot render success and is
  never replayed.

### Tests and Results

All commands run from the repository root; every gate below was executed for
this correction checkpoint.

- `python3 scripts/check_governance.py` — PASS.
- `env -u NODE_ENV npm --prefix web ci` — PASS (0 vulnerabilities).
- `npm --prefix web run format:check` — PASS.
- `npm --prefix web run typecheck` — PASS.
- `npm --prefix web run lint` — PASS.
- `npm --prefix web run test -- --run` — PASS: 439/439 (34 files), 0 skipped.
- `npm --prefix web run build` — PASS.
- `npm --prefix web run test:e2e -- notifications.spec.ts operations.spec.ts deep-link.spec.ts`
  — PASS: 56 passed.
- `npm --prefix web run test:e2e` — PASS: 118 passed.
- `.venv/bin/python -m unittest tests.test_v2_notification_operations` —
  PASS: 25 tests.
- `.venv/bin/python -m unittest tests.test_webhook_management
  tests.test_notification_delivery_management tests.test_notifications
  tests.test_webhook_url_security tests.test_restart_fault_boundary
  tests.test_configuration_objects tests.test_configuration_management
  tests.test_dashboard tests.test_operations_workspace tests.test_api_security
  tests.test_v2_ui` — PASS: 171 tests.
- `.venv/bin/python -m unittest discover -s tests` (repository-root CWD) —
  1539 tests, 6 failures, 7 skipped: `FAIL / PRE-EXISTING / UNRELATED`
  (details under Risks).
- Isolated clean checkout of committed HEAD `7cf3735` with this correction's
  exact working diff applied (`git worktree`): full `unittest discover` —
  PASS, 1539 tests, 0 failures, 7 skipped.
- `.venv/bin/ruff format --check .` — PASS (309 files).
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS.
- `.venv/bin/mediaflow --config config/strategy.example.json config validate`
  — PASS.
- `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json
  config validate` — PASS.
- `git diff --check` — PASS.
- `python3 scripts/docker_release_security_smoke_test.py` — PASS (Docker
  available; release-security smoke acceptance passed).
- No test was deleted, renamed or weakened; the activation fixture was
  corrected to the truthful managed contract (the passing pre-correction
  happy path encoded the split identity B rejected), fixtures were
  strengthened to the real optimistic-fence semantics, and every added case
  is fail-closed evidence. `node_modules/`, build reports and private
  configuration remain excluded.

### Decisions

- The definition-mutation binding treats the stored mutation as the one-shot
  successor of the submitted Draft version (`expectedVersion + 1`): the real
  managed `edit_draft` publishes exactly `revision.version + 1`, so a document
  at the submitted version, or any version beyond the one-shot successor, is
  wrong-object evidence. The component and browser fakes now advance their
  Draft fence per stored mutation, so every journey submits the exact
  refetched optimistic fence like the real API requires.
- Copy binding uses the managed copy allocator's derived identity family
  (`{source}-copy` within the 64-character bound) when the request did not
  pin `newId`, and the exact pinned identity when it did; the copied-from
  source id and any unrelated id fail closed. The copied document must also
  be disabled, matching the managed copy semantics.
- The activation normalizer now requires the four identity pairs (activated,
  published-from echo, request, activeConfiguration) to be the same exact
  revision/version, matching the real `activate()` path that preserves the
  Draft identity; the pre-correction typed happy path had encoded the
  rejected split identity and was corrected to the truthful contract rather
  than preserved.
- The create request pre-validates the submitted id with
  `NOTIFICATION_URI_SAFE_SEGMENT` (the same rule the response normalizer
  enforces) so the server cannot accept an identity the client would
  immediately have to reject as unrenderable; the canonical server validator
  remains the authority.
- The hostile fake serves wrong-object documents for all six mutation routes
  via the existing `?hostile=1` probe; the evidence body allowlist and all
  truthful fixtures are unchanged apart from aligning copy/enable/disable
  `enabled` semantics with the real managed service.

### Remaining In-Slice Work

- None known to me for RO-6 itself. Slice 33 closure still needs B's
  Required-Outcome sweep over RO-1..RO-8, and Slice 34/35 own the media
  review/recovery and general Configuration journeys this Task only links to.

### Risks / Deviations

- `FAIL / PRE-EXISTING / UNRELATED`: full `unittest discover` at the
  repository-root CWD fails the same 6 tests documented in both previous
  checkpoints (`test_api_credentials` ×2, `test_final_integration` ×1,
  `test_resource_library_pipeline` ×1, `test_runtime_storage_configuration`
  ×2) — root CWD private runtime state (untracked `.mediaflow/` runtime plus
  the CLI resolving the relative `persistence.databasePath` against the CWD).
  Fresh proof for this correction: an isolated worktree at committed HEAD
  `7cf3735` with this correction's exact working diff applied passes full
  discovery (1539 tests, 0 failures, 7 skipped). My diff touches no
  CLI/config-loading code path, and the private state was not deleted or
  altered.
- Docker was available and the release-security smoke passed; nothing was
  inferred.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 35448c2add70ac5b974eeaa33fbeae5e996a8048
```

## B Review Result

```text
Reviewed: 86ad42ff26721ca62f61653e1f0ed9129732cbeb..1305d0790632c5b28029c80cfda7bfa80e9a42a1
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Definition-mutation success responses are still not fail-closed or bound to the exact submitted
  Draft/object. Inspection of `createWebhookDefinition`, `saveWebhookDefinitionDraft`,
  `copyWebhookDefinition` and `setWebhookDefinitionEnabled` shows that each normalizer ignores the
  response `revisionId`/`version`, accepts a missing object, and returns any unvalidated string id;
  create even falls back to the request id and renders navigation as success when the response
  carries no created definition. The independently run focused Web suite passes 63/63 and browser
  suite passes 55/55, but their hostile wrong-object journey covers only test/recovery, not these
  four mutations. Add operation-specific normalization bound to the requested Draft revision,
  expected successor version and exact created/edited/toggled/copied identity (including strict
  URI-safe response identities), and prove malformed/missing/wrong-object/wrong-revision success
  documents render rejection with no follow-up mutation or false success.
- Checked-activation success binding still accepts a different Active revision/version from the
  submitted Draft. The passing `notification activation result` test explicitly submits
  `{revisionId: "rev-draft", version: 4}` while treating activated revision `rev-active-2`
  version 5 as a valid success; the normalizer checks the new
  `publishedFrom*` echo against the request and checks Active against `activated*`, but never
  requires those two identity pairs to be equal. The real managed activation and the Python
  integration test preserve the Draft revision id/version as the new Active identity. Require
  `activatedRevisionId`/`activatedVersion`, `publishedFromRevisionId`/`publishedFromVersion`, the
  request binding and `activeConfiguration` to describe that same exact revision/version, and add
  typed plus built-artifact hostile evidence proving a split-identity activation response cannot
  render success.
