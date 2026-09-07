# Task 28.6 — Webhook URL Credential Query Hardening

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 28.6
Parent Slice: 28
Status: PLANNED
Task Base: 0588ce2631bc3dc863b55752c8fe269aded1b935
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Close the P0 blocker recorded by A for Slice 28 RO-5: managed Webhook endpoint configuration must
fail closed when a URL query can carry credential or authorization material, and no such material
may be persisted, serialized or exposed through runtime, API, Web, package, audit or error paths.
The existing deployment-owned `secretEnv` reference remains the only secret authority.

## Why This Task Exists

A Final Review of the complete Slice 28 range reproduced that
`https://example.invalid/hooks?token=TOP_SECRET_VALUE` and
`https://example.invalid/hooks?api_key=TOP_SECRET_VALUE` are accepted by the managed Webhook API
and returned in revision detail. The current domain validator rejects URL userinfo and fragments
but does not reject credential-bearing query parameters; `WebhookDefinition.document()` therefore
allows the unsafe URL to become durable configuration and an operator-visible projection.

This is a focused correction Task because it closes one concrete P0 security invariant across every
existing Webhook input/output boundary. It must cover typed edits, whole-document/package import,
runtime validation and already-invalid projection behavior together so one alternate path cannot
reintroduce the same leak. It does not redesign Webhook delivery or the closed Slice 28 delivery
recovery behavior.

## Implementation Scope

```text
Canonical Webhook URL validation
→ managed Draft import/edit and invalid-document projection
→ runtime loader and package exchange safety
→ API/Web/error/audit redaction
→ security regression, parity and full-gate tests
```

The Task may update only the implementation needed for the following behavior:

- Establish one bounded, shared Webhook endpoint safety rule used by
  `WebhookDefinition.from_document`, managed typed object operations and runtime loading. Keep
  HTTPS, hostname, no userinfo and no fragment requirements. Credential-bearing query components
  (including normalized names such as token, api_key/apikey, access_token, client_secret, secret,
  password, authorization, credential, signature/sig, access_key and secret_key) must be rejected
  before a new managed revision or runtime snapshot can accept them. If unrestricted query
  parameters cannot be proven secret-free, fail closed for the query component rather than
  retaining an unbounded credential-smuggling path.
- Ensure invalid unsafe Webhook input is not echoed in validation errors, API responses, Web
  messages, audit records or logs. Error/recovery evidence remains bounded and identifies the
  affected Draft/revision without exposing the URL query or its values.
- Ensure typed Webhook create/edit/copy/enable/disable, whole-document Draft import and versioned
  configuration-package import all use the same rule and preserve the prior Active/current Draft
  when rejected. Existing safe non-credential endpoint configuration remains compatible.
- Ensure runtime validation rejects an unsafe managed/JSON Webhook URL before activation or worker
  target resolution. `WebhookDefinition.document()` and all configuration/revision/package
  projections serialize only validated safe URLs.
- Handle already-persisted malformed/legacy unsafe Webhook documents without returning their
  credential-bearing URL through revision detail, API/Web projections, export, audit or error
  responses. Keep the revision inspectable and correctable through the existing explicit recovery
  path, and do not silently activate, rewrite or delete it.
- Preserve the existing deployment-owned `secretEnv` reference boundary, HMAC signature semantics,
  explicit bounded definition-test behavior, delivery Outbox/Worker behavior and delivery
  recovery behavior.

Files/areas explicitly frozen unless compatibility glue is strictly required:

- `SLICE.md`, `docs/roadmap.md`, `docs/progress.md`, product requirements, Product Experience and
  Architecture contracts.
- Active/Draft revision authority, checked activation semantics and completed Tasks 28.1–28.5,
  except the shared validation/projection glue required to close this P0.
- Notification delivery state, lease/retry/dead-letter/recovery operations and stable delivery IDs.
- OrganizerExecutor, Storage mutation, Scanner/Parser/Recognition/Metadata/Naming/Classification/
  Planner behavior and all completed media-processing history.
- Docker/Compose release, built-in identity/OIDC, general Secret Store, Provider switching and new
  Storage providers.

## Acceptance Criteria

- [ ] A single canonical Webhook URL rule rejects credential-bearing query parameters and remains
      consistent across `WebhookDefinition.from_document`, managed object validation, runtime
      loader, checked validation/activation and package import. Userinfo, fragment and unsupported
      credential fields remain rejected.
- [ ] Managed typed create/edit/copy/enable/disable and whole-document/package Draft import reject
      unsafe URLs before persistence or activation, return bounded recovery evidence, preserve the
      prior Active/current Draft, and do not silently rewrite or delete user configuration.
- [ ] Revision detail, configuration status, Web projections, configuration export, result/package
      audit and runtime/error paths never return or persist a credential-bearing URL query or its
      value. Already-persisted unsafe documents are suppressed or safely redacted while remaining
      explicitly correctable.
- [ ] Safe Webhook endpoint definitions continue to round-trip with their path and supported
      non-secret fields, and the deployment-owned `secretEnv` reference is preserved without ever
      exposing the environment variable value.
- [ ] The explicit Webhook test and signed delivery worker still use the same validated endpoint
      and signature semantics; this correction does not create deliveries, alter delivery state,
      change Active configuration, mutate Storage or change completed media work.
- [ ] API and Web expose the same rejection, redaction, durable-state and recovery semantics.
      Neither form submission nor Advanced JSON/package import can bypass the canonical rule.
- [ ] Security regression tests cover at least `token`, `api_key`, `apikey`, `access_token`,
      `client_secret`, `secret`, `password`, `authorization`, `credential`, `signature`/`sig`,
      `access_key` and `secret_key` query names, case/separator normalization, bounded errors,
      already-invalid projections and no secret leakage through audit/export/runtime paths.
- [ ] Required focused tests, full supported offline regression, governance, formatting/lint,
      compile, dependency and diff checks pass; unavailable optional/external gates are reported
      explicitly and truthfully.
- [ ] The checkpoint contains only this Task's focused security correction/tests and no private
      configuration, `config/alist.json`, credentials, media or unrelated user work.

## Required Tests

Focused and related tests:

```bash
python3 -m unittest \
  tests.test_webhook_url_security \
  tests.test_webhook_management \
  tests.test_configuration_package_exchange \
  tests.test_configuration_snapshot \
  tests.test_configuration_management \
  tests.test_configuration_objects \
  tests.test_notifications \
  tests.test_operator_ui \
  tests.test_api_credentials \
  tests.test_final_integration
```

The Developer must add focused Webhook URL security tests covering:

- canonical domain/runtime/managed/package validation parity for credential-bearing query names,
  case and separator normalization;
- typed API/Web rejection before persistence and safe bounded error/recovery evidence;
- invalid pre-existing/legacy revision projection and export suppression/redaction;
- Active/Draft preservation, checked-activation failure and runtime-loader fail-closed behavior;
- safe endpoint compatibility and deployment `secretEnv` value redaction;
- audit/log/API/Web/package/result absence of submitted credential values and full unsafe URLs;
- explicit definition-test and signed delivery compatibility with no new delivery or media side
  effects.

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

Tests must use temporary repositories, fake/local transports and sentinel values that are not
production credentials. No production Webhook endpoint, private path or real media is permitted.
The current governance guard may report its existing `Slice FIX REQUIRED` transition limitation
until this Task is planned; that tool result must be reported truthfully and must not be bypassed
by changing the Slice Contract or governance script.

## Non-goals

- Work outside the Slice 28 Contract or any change to its User Goal, Required Outcomes, Required
  Surfaces, Safety Invariants, Base SHA or Explicitly Deferred scope.
- Changing the Webhook delivery protocol, event selection, HMAC signature, Outbox/Worker retry,
  lease, dead-letter or delivery-recovery behavior.
- Adding a general Secret Store, secret rotation, credential query support, arbitrary URL proxying,
  new notification channels or new API permissions.
- Reworking the managed configuration lifecycle, System Settings or package exchange beyond the
  validation/projection/redaction glue required for this P0.
- Docker/Compose production packaging, production serving, Provider switching, built-in identity/
  OIDC, new Storage providers or changes to OrganizerExecutor/media mutation behavior.
- Optional copy polish, broad refactors, unrelated lint cleanup or extra test-only micro-Tasks.

## Developer Completion Report

### Changed Files

- `mediaflow/domain/notification.py` — one canonical Webhook URL rule
  (`webhook_url_validation_error`) used by `WebhookDefinition.__post_init__`/`from_document`: HTTPS
  with hostname, no userinfo, no fragment and fail-closed on ANY query component (an unbounded
  credential-smuggling channel that cannot be proven secret-free). Added the shared
  `WEBHOOK_URL_REDACTED_VALUE` marker plus `webhook_url_hides_value`, `redact_webhook_url_value`,
  `redact_webhook_urls`, `webhook_url_items` and `unsafe_webhook_url_items` helpers for
  already-persisted/legacy unsafe URLs.
- `mediaflow/application/configuration_snapshot.py` — whole-document Draft import and edit now
  reject newly introduced or changed credential-bearing Webhook URLs (`_reject_unsafe_webhook_urls`;
  unchanged legacy unsafe URLs stay correctable), and the raw revision-document projection
  (`_redact_document`) suppresses unsafe Webhook URLs with the bounded marker.
- `mediaflow/application/configuration_objects.py` — `_webhooks_projection` redacts unsafe legacy
  Webhook URLs while keeping the item structurally invalid and correctable; typed object-change
  audits store redacted before/after Webhook values (`_audited_object_value`) so a correction or
  deletion never persists the old credential-bearing URL.
- `mediaflow/domain/package_exchange.py` — configuration export redacts unsafe Webhook URLs to the
  marker (with `redacted_webhook_url` evidence) and package secret inspection flags
  `webhook_url_credential` issues so crafted unsafe packages fail validation closed.
- `mediaflow/interfaces/operator_ui.py` — guided Configuration and Notifications Webhook rows
  explicitly explain a hidden/redacted endpoint URL and that a clean HTTPS URL must be entered to
  correct the Webhook.
- `tests/test_webhook_url_security.py` (new) — focused canonical/typed/legacy/projection/export/
  validation/activation/package/parity security tests with sentinel values.

### Implemented

- One canonical, bounded Webhook endpoint rule is now shared by the domain validator, the runtime
  JSON loader, managed typed-object operations and every projection decision. URLs with userinfo,
  fragment or any query component are rejected before a new managed revision or runtime snapshot can
  accept them; the query component fails closed entirely (all casing/separator spellings of `token`,
  `api_key`/`apikey`, `access_token`, `client_secret`, `secret`, `password`, `authorization`,
  `credential`, `signature`/`sig`, `access_key`, `secret_key` and any unknown parameter are rejected
  because unrestricted query parameters cannot be proven secret-free). Error messages are constant
  and never echo the URL, query or value.
- Typed Webhook create/edit/copy/enable/disable and whole-document Draft/package import all use the
  rule and preserve the prior Active/current Draft when rejected (verified at API level: revision
  versions and stored documents unchanged, responses secret-free).
- Already-persisted/legacy unsafe Webhook documents are not silently rewritten or deleted: the stored
  revision keeps its value, while revision detail (`document`), the guided objects projection, Web
  rows, configuration export and typed-change audits all replace the URL with the bounded
  `***REDACTED***` marker and mark the Webhook structurally invalid with a bounded reason. Such a
  revision remains inspectable and explicitly correctable (fix the URL or delete the Webhook); a
  Draft containing multiple legacy unsafe Webhooks can be corrected one at a time without deadlock,
  and a legacy unsafe Active can be recovered through the normal successor-Draft path.
- Runtime/checked validation and activation fail closed for unsafe URLs (the loader raises a bounded
  error, validate keeps the revision a Draft, and a legacy unsafe Active reports runtime UNAVAILABLE
  with a secret-free status) while safe endpoint definitions round-trip with their path, and the
  deployment-owned `secretEnv` reference remains the only secret authority (name only, never value).
- Explicit definition-test and signed delivery behavior are unchanged and compatible: the focused
  compatibility test publishes and delivers a signed event after activation and confirms no extra
  delivery or Job is created; API/Web expose the same redaction and rejection semantics.

### Tests and Results

```text
python3 -m unittest tests.test_webhook_url_security              -> PASS (13 tests)
python3 -m unittest <all 10 Task focused modules>                -> PASS (220 tests)
python3 -m unittest discover -s tests (project venv python)      -> 1361 run; 2 FAIL
  PRE-EXISTING / UNRELATED:
    - test_governance...test_current_repository_passes_no_active_closed_slice_state
      (whole-repo governance guard fails in the committed Slice-FIX-REQUIRED correction state;
      reproduced at clean Task Base 0588ce2 with "Slice FIX REQUIRED cannot have NO ACTIVE
      IMPLEMENTATION TASK", and again with Task 28.6 planned as "active Task requires committed
      HEAD Slice 28 to be ACTIVE"; the documented guard limitation, not this Task's code)
    - test_storage_browser...test_setup_picker_and_execution_environment_guidance_are_present
      (asserted UI phrase absent at Task Base; unrelated)
  7 SKIP (external profiles absent)
python3 scripts/check_governance.py                              -> FAIL / PRE-EXISTING
  (Slice FIX REQUIRED transition limitation documented in this Task's Required Tests)
ruff format --check .                                            -> FAIL / PRE-EXISTING
  (only tests/test_system_settings_management.py, unformatted at Task Base)
ruff check .                                                     -> FAIL / PRE-EXISTING
  (only E501 in tests/test_system_settings_management.py, present at Task Base)
python3 -m compileall -q mediaflow tests scripts                 -> PASS
python3 -m pip check                                             -> PASS
git diff --check                                                 -> PASS
node --check on the served operator app.js                       -> PASS
```

### Decisions

- The canonical rule fails closed on the whole URL query component rather than only enumerating known
  credential parameter names: any query parameter is an unrestricted credential-smuggling channel
  that a static validator cannot prove secret-free, and the Task's Implementation Scope explicitly
  authorizes failing closed for the query component. Existing safe endpoint configuration carries no
  query and is unaffected.
- Already-persisted legacy unsafe documents are handled as projection/export/audit redaction, not as
  silent rewriting: the durable revision keeps its value (so the operator can see it is correctable
  through the existing recovery flow), while every operator-visible surface returns the shared
  bounded marker. Whole-document Draft edit rejects newly introduced or changed unsafe URLs but
  permits unchanged legacy unsafe URLs so multiple legacy Webhooks can be corrected one at a time.
- Redaction happens after validation so the projection still reports the accurate bounded reason
  ("must not include a query string") rather than a confusing marker-parsing error.
- The `***REDACTED***` value already used for secret fields was reused as the Webhook URL marker so
  operators recognise suppressed material, and it is not a valid endpoint URL (any accidental
  persistence fails validation).

### Remaining In-Slice Work

None inside this Task. This closes the single Slice 28 P0 recorded by A; after B review the
remaining Slice status/closure steps belong to B/A.

### Risks / Deviations

- `scripts/check_governance.py` and `test_governance...test_current_repository_passes_no_active_closed_slice_state`
  fail because the committed `SLICE.md` is in the `FIX REQUIRED` correction state (B's Task 28.6 is
  planned in the working tree). Reproduced at the clean Task Base; this is the guard limitation this
  Task documents and is not introduced or bypassed by this change (no Slice Contract or guard edit).
- `test_storage_browser...test_setup_picker_and_execution_environment_guidance_are_present` fails at
  the Task Base and is unrelated.
- `ruff format --check .` / `ruff check .` report the same pre-existing
  `tests/test_system_settings_management.py` issue present at Task Base; that file was untouched.
- The full suite must run with the project venv (optional extras); system `python3` additionally
  errors on an OpenList module missing `httpx`.
- Seven optional external acceptance tests skip with their standard environment-absent reasons.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 8546ff8fe15386dfbbb5fefb29a66b936ed4613f
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
