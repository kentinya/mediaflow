# Task 28.4 — Managed Webhook Definitions and Explicit Test

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 28.4
Parent Slice: 28
Status: PLANNED
Task Base: ec8e57b25fa51f0e6583b17d752fcfdba101fe64
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 28 RO-5: an authenticated operator can manage the canonical Webhook definitions
through the shared Web/API configuration journey, inspect validation/reference/readiness state, and
run an explicit bounded test against the exact intended revision without exposing secret material or
creating an unrequested notification delivery.

## Why This Task Exists

Slice 28 already has the signed HTTPS Outbox, delivery worker, durable delivery state and read-only
notification list foundation, but Webhook definitions are still supplied by lower-level runtime
configuration rather than managed through the day-2 Web/API administration journey. An operator
cannot yet create or edit a definition in a successor Draft, see whether its deployment-owned
secret reference is ready, or explicitly test the intended endpoint with the same validation,
permission and exact-revision authority used by the rest of Configuration.

This is the largest reasonable next unit because RO-5 crosses the managed configuration graph,
typed Web/API object management, secret-reference readiness, bounded outbound test semantics,
redacted audit and operator recovery as one user-visible behavior. RO-6 delivery list/detail and
retry/requeue/dead-letter recovery remains a separate unit because it operates on durable delivery
state rather than on Webhook definition configuration.

## Implementation Scope

```text
Managed Webhook definition model/validation
→ configuration persistence and reference/readiness projection
→ application lifecycle and exact-revision test service
→ permission-aware API routes
→ Configuration/Notifications Web forms/cards and recovery state
→ redacted audit, parity, safety and regression tests
```

The Task may update only the implementation needed for the following behavior:

- Add Webhook definitions to the canonical managed configuration graph using the existing Draft,
  optimistic-concurrency, validation, checked-activation and immutable Active authorities. Support
  discoverable list/detail forms/cards and create, edit, copy where applicable, enable, disable and
  delete actions with shared application behavior for API and Web.
- Validate and project only supported Webhook configuration: HTTPS endpoint without credentials or
  fragment, valid unique identifier, non-empty unique supported event selection, bounded timeout
  and retry settings, and a deployment-owned environment-variable secret reference. Literal
  secrets, token fields, authorization material and arbitrary execution fields are rejected.
- Expose bounded reference impact and readiness state. Readiness may report whether the referenced
  environment variable is present and whether the definition is structurally valid, but must never
  return the secret value or equivalent recoverable credential. Referenced deletion remains blocked
  or requires the existing explicit safe recovery path; it must not silently remove durable
  configuration or delivery history.
- Provide an explicit, permission-aware Web/API test action for one selected Webhook definition and
  exact revision identity (revision ID/version/digest). The test sends at most one bounded HTTPS
  request using the existing signed transport semantics, has no automatic retry or scheduler
  admission, does not enqueue a durable notification delivery, does not start media work and does
  not mutate Storage or completed Task/Result history.
- Return bounded success/failure/recovery evidence for the test, including target identity,
  response category/status when safe, timeout or transport category, exact revision evidence,
  durable state, side effects, retry safety and next action. Remote response bodies and exception
  text must be redacted or reduced to safe categories.
- Add redacted audit evidence for create/edit/copy/enable/disable/delete/readiness/test attempts and
  outcomes. API errors, Web messages, logs and audit records must not contain secret values,
  bearer tokens, authorization headers, cookies or private credentials.
- Keep the ordinary Configuration journey forms-first. Any Advanced JSON representation remains
  explicitly labelled and uses the same validation, permission, concurrency, redaction and exact
  revision rules.
- Preserve the existing signed Outbox/Worker delivery behavior and make no changes to delivery
  retry, requeue, dead-letter or delivery-detail operations beyond compatibility required for the
  managed definition and explicit test path.

Files/areas explicitly frozen unless compatibility glue is strictly required:

- `SLICE.md`, `docs/roadmap.md`, `docs/progress.md`, product requirements, Product Experience and
  Architecture contracts.
- Completed Tasks 28.1–28.3 and their configuration, System Settings, package exchange and exact
  Active snapshot authorities, except shared object-management integration required here.
- Durable delivery retry/requeue/dead-letter semantics and RO-6 list/detail/recovery workflow.
- Storage mutation, OrganizerExecutor, Scanner/Parser/Recognition/Metadata/Naming/Classification/
  Planner behavior, Worker/Scheduler ownership protocol and completed media-processing work.
- Built-in identity, general Secret Store, Docker/Compose release, Provider switching and new
  Storage providers.

## Acceptance Criteria

- [ ] Authenticated API users with the required configuration permission can list, inspect, create,
      edit, copy where applicable, enable, disable and delete managed Webhook definitions through
      typed object operations. Unauthorized users receive the existing bounded permission response.
- [ ] Web users can reach the same Webhook definition lifecycle from the Configuration/Notifications
      administration surface, with visible current Draft/Active status, validation state, reference
      impact, readiness and explicit recovery actions. Viewing or refreshing never sends a test or
      creates a delivery.
- [ ] Webhook changes are Draft-only until normal exact checked activation; optimistic concurrency,
      exact revision ID/version/digest evidence, immutable Active/Superseded behavior and stale
      recovery remain intact.
- [ ] Validation fails closed for non-HTTPS or credential-bearing URLs, invalid identifiers or
      environment names, empty/duplicate/unsupported events, invalid bounds and literal secret or
      authorization fields. The returned state identifies the durable Draft/revision and next
      action without revealing secret material.
- [ ] Readiness exposes only structural validity and deployment-owned secret-reference readiness.
      No secret value, token, header, cookie or equivalent credential appears in configuration
      documents, API/Web responses, audit records, logs or exception text.
- [ ] An explicit Web/API test action is available only with the required permission and exact
      revision identity, sends no more than one bounded signed request, performs no automatic retry,
      does not enqueue a durable delivery or start any media/workflow/Storage mutation, and returns
      bounded redacted outcome and recovery details.
- [ ] Test success, timeout, transport failure, non-2xx response, missing secret reference, invalid
      definition and stale revision all have deterministic failure/recovery semantics, including
      durable state, side effects, retry safety, exact revision evidence and next action.
- [ ] API and Web use the same application behavior and permissions for lifecycle, validation,
      readiness, exact-revision test, failure recovery and redaction; focused parity tests prove
      this.
- [ ] Existing signed Webhook Outbox/Worker behavior, notification persistence and Slice 26/27 plus
      Tasks 28.1–28.3 regressions remain intact.
- [ ] Required focused tests, full supported offline regression, governance, formatting/lint,
      compile, dependency and diff checks pass; unavailable optional/external gates are reported
      explicitly and truthfully.
- [ ] The checkpoint contains only this Task's coherent implementation/tests and no private
      configuration, `config/alist.json`, credentials, media or unrelated user work.

## Required Tests

Focused and related tests:

```bash
python3 -m unittest \
  tests.test_webhook_management \
  tests.test_notifications \
  tests.test_configuration_snapshot \
  tests.test_configuration_management \
  tests.test_configuration_objects \
  tests.test_system_settings_management \
  tests.test_configuration_package_exchange \
  tests.test_api_credentials \
  tests.test_operator_ui \
  tests.test_final_integration
```

The Developer must add focused Webhook management tests covering:

- typed API/Web lifecycle for create, edit, copy, enable, disable, delete, reference impact and
  permission denial;
- exact Draft/Active/Superseded revision authority, optimistic stale update/test rejection and
  immutable Active preservation;
- HTTPS/event/bounds/secret-reference validation, missing-secret readiness and secret-free
  documents, errors, audit, logs and Web/API responses;
- explicit bounded test success, timeout/transport failure/non-2xx failure, no retry, no Outbox
  delivery, no Task/Job/scheduled occurrence creation and no Storage mutation;
- API/Web parity for lifecycle, readiness, exact-revision test, failure recovery and redaction.

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

Tests must use fakes, local repositories and a local HTTPS-capable or transport-fake test boundary.
Production Webhook endpoints, credentials, private paths and real media are not permitted. Any
unavailable optional external dependency or pre-existing local-environment failure must be reported
with the exact command, result and evidence that it is unrelated to this Task.

## Non-goals

- Work outside the Slice 28 Contract or any change to its Required Outcomes, Required Surfaces,
  Safety Invariants, Base SHA or Explicitly Deferred scope.
- Re-implementing the completed forms-first configuration lifecycle, System Settings semantics or
  package exchange, except shared Webhook object integration required by RO-5.
- RO-6 delivery list/detail enrichment, retry/requeue/dead-letter recovery, lease repair or
  notification-channel expansion.
- Automatic scheduled delivery, bulk Webhook testing, arbitrary HTTP methods, redirect following,
  secret rotation or a general Secret Store.
- Docker/Compose production packaging, production serving, Provider switching, built-in identity/
  OIDC, new Storage providers or changes to OrganizerExecutor/media mutation behavior.
- Optional copy polish, extra test-only micro-Tasks, broad refactors or changes to closed processing
  pipelines.

## Developer Completion Report

### Changed Files

- `mediaflow/domain/notification.py` — canonical `WebhookDefinition` validation/normalization
  (`from_document`/`document`), bounded retry/timeout constants, HTTPS and secret-reference rules.
- `mediaflow/domain/configuration_management.py` — new `ConfigurationObjectKind.WEBHOOK_DEFINITION`.
- `mediaflow/infrastructure/runtime_configuration.py` — runtime loader accepts the canonical root
  `webhooks` section (and still reads legacy `notifications.webhooks`); Webhook parsing delegated to
  the shared domain validator.
- `mediaflow/application/configuration_objects.py` — Webhook definitions are managed objects in the
  Draft document (create/edit/copy/enable/disable/delete), with legacy-nested → canonical-root
  migration on edit, reference handling and a secret-free readiness/structural-validity projection.
- `mediaflow/application/notification.py` — shared signed-request helpers reused by the worker;
  delivery behavior unchanged.
- `mediaflow/application/webhook_test.py` (new) — exact-revision bounded Webhook test service:
  one signed request, no retry, no Outbox/Task/Job/schedule/Storage side effects, redacted audit.
- `mediaflow/interfaces/service_api.py` — `webhooks` guided object kind, webhook test route
  `POST /api/v1/configuration/revisions/{id}/objects/webhooks/{webhookId}/test`, projection-field
  stripping and injectable webhook transport.
- `mediaflow/interfaces/operator_ui.py` — Webhook guided forms/list in the Configuration journey and
  an Active Webhook definition surface with readiness and explicit test in the Notifications view.
- `tests/test_webhook_management.py` (new) — focused lifecycle, authority, validation/redaction,
  explicit-test, parity and audit tests.
- `tests/test_configuration_management.py` — expected managed object-kind set now includes the new
  Webhook kind.

### Implemented

- Webhook definitions are first-class typed objects in the canonical managed configuration graph
  (root `webhooks` section). Legacy `notifications.webhooks` documents remain readable and migrate
  to the canonical spelling on the first typed edit.
- Validation is shared between the runtime loader and the managed object graph: HTTPS URL without
  credentials/fragment, bounded ids and environment-variable names, non-empty unique supported
  events, bounded timeout/retry settings, and rejection of literal secret, authorization or
  arbitrary execution fields.
- Web/API surfaces expose the same Draft-only lifecycle (create/edit/copy/enable/disable/delete),
  optimistic exact-version concurrency, immutable Active/Superseded behavior, per-object reference
  impact, and a readiness projection reporting only env-var SET/UNSET state plus structural
  validity — never secret values.
- A permission-aware exact-revision test action (`expectedVersion` + `expectedDigest`) sends one
  bounded signed request using the existing signature/transport semantics. It never retries, never
  enqueues a durable delivery, never creates Tasks/Jobs/scheduled occurrences and never mutates
  Storage. Deterministic failure/recovery evidence includes durable state, side effects `none`,
  retry safety, exact revision identity and next action; remote bodies and exception text are
  reduced to safe categories.
- Redacted audit coverage: CRUD flows record Draft-edit object-change audits through the managed
  revision authority; test outcomes append a redacted security audit record; every request is also
  audited by the API boundary.
- Notifications view shows Active Webhook definitions bound to the exact Active revision with
  readiness and an explicit test action; the Configuration view provides the typed forms lifecycle.

### Tests and Results

```text
python3 -m unittest tests.test_webhook_management            -> PASS (7 tests)
python3 -m unittest tests.test_notifications                 -> PASS
python3 -m unittest tests.test_configuration_snapshot        -> PASS
python3 -m unittest tests.test_configuration_management      -> PASS
python3 -m unittest tests.test_configuration_objects         -> PASS
python3 -m unittest tests.test_system_settings_management    -> PASS
python3 -m unittest tests.test_configuration_package_exchange -> PASS
python3 -m unittest tests.test_api_credentials               -> PASS (clean workspace)
python3 -m unittest tests.test_operator_ui                   -> PASS
python3 -m unittest tests.test_final_integration             -> PASS (clean workspace)
python3 -m unittest <all 10 focused modules above>           -> PASS (228 tests)
python3 -m unittest discover -s tests                        -> 1337 run; 1 FAIL
  PRE-EXISTING / UNRELATED (tests.test_storage_browser); 7 SKIP (external profiles absent)
python3 scripts/check_governance.py                          -> PASS
ruff format --check .                                        -> FAIL / PRE-EXISTING
  (only tests/test_system_settings_management.py, already unformatted at Task Base)
ruff check .                                                 -> FAIL / PRE-EXISTING
  (only E501 in tests/test_system_settings_management.py, present at Task Base)
python3 -m compileall -q mediaflow tests scripts             -> PASS
python3 -m pip check                                         -> PASS
git diff --check                                             -> PASS
node --check on the served operator app.js                   -> PASS
```

Note on the full-suite gate: the full regression and CLI-based focused tests were executed from a
workspace without the pre-existing ignored `.mediaflow/mediaflow.sqlite3` runtime artifact. That
stale DB (left by earlier sessions in this workspace) makes CLI commands resolve an old managed
Active configuration and caused environment-only failures in `test_api_credentials`,
`test_final_integration`, `test_resource_library_pipeline` and `test_runtime_storage_configuration`;
from a clean workspace state (equivalent to a fresh checkout) those modules pass. The artifact was
preserved and restored afterwards and is not part of this checkpoint.

### Decisions

- Managed Webhook definitions are stored in a canonical root `webhooks` section of the Draft
  document, mirroring the existing `automationTaskDefinitions` pattern. The runtime loader accepts
  the canonical root and the legacy `notifications.webhooks` spelling, but rejects a document that
  defines both, keeping the Active definition unambiguous.
- Webhook validation/normalization lives in the domain (`WebhookDefinition.from_document`) so the
  JSON runtime loader, typed object edits and the readiness projection cannot disagree.
- Bounds were tightened for timeout/attempts/retry to fail closed as required; the shipped example
  and all existing fixtures stay inside the new bounds.
- The explicit test uses the same signature/transport scheme as the delivery worker but sends its
  own bounded `webhook.test` payload and never touches the durable delivery repository, so a test
  cannot be mistaken for a real delivery by a receiver.
- Exact-revision enforcement (version + digest) happens in the application service before any
  request is sent; stale or corrupt identities fail closed with bounded recovery details.
- Webhook deletion is allowed (RO-5 requires it). Delivery history is never cascade-deleted and the
  UI states that unresolved deliveries then fail closed as configuration dead-letters.

### Remaining In-Slice Work

- RO-6 delivery list/detail enrichment and retry/requeue/dead-letter recovery operate on durable
  delivery state and remain a separate unit outside this Task's scope.

### Risks / Deviations

- `tests/test_storage_browser.test_setup_picker_and_execution_environment_guidance_are_present`
  fails at the Task Base (verified on a clean `ec8e57b` checkout) and is unrelated to this Task; it
  asserts an operator-asset phrase that is not present in the shipped UI.
- `ruff format --check` and `ruff check` each report one pre-existing issue in
  `tests/test_system_settings_management.py` (line 216 formatting / line 347 E501) present at the
  Task Base; that file was intentionally left untouched.
- A stale ignored `.mediaflow` runtime database in this workspace causes environment-only CLI test
  failures; the full suite passes from a clean workspace state (evidence above).
- No optional external gates are available (real OpenList/SMB/S3/endurance acceptance); the 7
  affected tests skip with their standard "BLOCKED: ... environment absent" reasons.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [pending commit]
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update
Roadmap.
