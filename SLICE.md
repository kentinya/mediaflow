# Slice 28 — Web-first Configuration and Operations Administration

This is the A-owned Slice Contract. B and Developer may not expand or weaken it. Detailed lifecycle
rules are defined only in [`docs/development-workflow.md`](docs/development-workflow.md).

```text
Slice ID: 28
Owner: A — Slice Owner / Architect / Final Reviewer
Status: READY FOR A REVIEW
Base SHA: 957a4ebcb0fde03e64be9c406fbcdfed9a12501d
Implementation Head: 8546ff8fe15386dfbbb5fefb29a66b936ed4613f
```

The Base is the Slice 27 closure/documentation-reconciliation checkpoint and the real repository
commit immediately before Slice 28 implementation begins. Contract and Task-planning commits may
follow this Base, but the Base must not move. A Final Review will cover the complete Base..Head
implementation range rather than only the final Task.

## User Goal

On an authenticated self-hosted MediaFlow instance with an Active runtime, an operator can safely
administer day-2 configuration, runtime settings, configuration/result packages and signed Webhook
operations through the Web/API management boundary. The operator can create a successor Draft from
the exact Active snapshot, manage referenced objects through discoverable forms, inspect impact and
validation state, activate only an exact checked revision, and recover from invalid or stale changes
without changing the currently consumed runtime or completed media work.

The same journey lets the operator manage Webhook definitions and delivery recovery: configure an
environment-owned secret reference without exposing the secret, run an explicit bounded test, inspect
delivery state, and retry or requeue an affected delivery without hiding successful or unrelated
deliveries.

This Slice completes the day-2 Web/API administration journey. It does not package MediaFlow for
Docker or redesign the closed media-processing, Storage, Task, Worker or Scheduler engines.

## Vertical Journey

```text
Authenticated operator
→ Configuration / Settings / Notifications
→ inspect exact Active identity and current Draft
→ create successor Draft from Active
→ edit typed configuration forms and use explicitly labelled Advanced JSON when needed
→ inspect references, validation and exact-revision safe-test evidence
→ validate and checked-activate the intended revision
→ observe the exact immutable runtime snapshot consumed by new work
→ recover stale/invalid/imported configuration without disturbing prior Active

Notifications branch:
Webhook definition
→ explicit bounded test
→ delivery list/detail and readiness
→ retry/requeue or dead-letter recovery for the affected delivery only
```

Every operator-facing path must expose the user goal, entry point, visible state, available action,
success outcome, failure outcome and recovery path. Viewing or refreshing a page must not activate a
Draft, send an unrequested delivery, start media work or mutate Storage.

## Current Foundation

- Slice 26 is `PASS / CLOSED` and provides the management-only bootstrap, guided configuration for
  all V1 Storage kinds, provider-neutral read-only setup evidence, Storage-relative path selection,
  exact checked activation and the immutable Active runtime snapshot.
- Slice 27 is `PASS / CLOSED` and provides the current Files/FileIndex distinction, manual operations,
  per-item lifecycle/disposition and recovery, plus Processing Worker readiness and fenced ownership.
- Managed Configuration already persists Draft/Validated/Active/Superseded revisions, exact version and
  digest evidence, optimistic updates, reference protection, redacted audit and shared API/Web
  application behavior. The current Web entry remains JSON-first and does not yet provide the complete
  day-2 forms-first administration journey.
- The signed HTTPS Webhook Outbox, delivery leases, retry/dead-letter state and read-only delivery
  operations already exist as infrastructure/application foundations. Web/API definition management,
  explicit test semantics and complete delivery recovery remain unfinished.
- The current System view is status-only. A consumed, managed System Settings object and its complete
  Web/API lifecycle are not yet delivered.

## Current Gap

An operator can use the existing managed revision and delivery foundations, but cannot yet complete
the promised day-2 administration journey without whole-document JSON or lower-level operational
knowledge. In particular, the natural Active-to-successor-Draft flow, consistent forms-first object
management, consumed System Settings, versioned configuration/result package exchange, Webhook
definition management/test and delivery-specific recovery are not one complete Web/API journey.

## Required Outcomes

| ID | Required Outcome | Initial State |
|---|---|---|
| RO-1 | **Forms-first successor Draft and object lifecycle.** Authenticated Web/API users can create a successor Draft from the exact Active revision and manage the canonical managed configuration graph through discoverable typed forms/cards. Create, edit, copy, enable, disable, delete, reference impact and safe recovery use shared application behavior; referenced deletion remains blocked by default. Whole-document JSON is an explicitly labelled Advanced/import/export/support surface, not the ordinary required path. | Managed revisions and many object operations exist, but the Web journey is JSON-first and inconsistent across object families. |
| RO-2 | **Exact revision authority remains end-to-end.** Draft edits use optimistic concurrency; validation and applicable safe-test evidence are bound to exact revision ID/version/digest; checked activation rechecks that identity and publishes only the immutable snapshot actually consumed by runtime. Stale, invalid or failed activation preserves the prior Active and a correctable Draft with bounded audit and recovery evidence. | Slice 26 provides the core authority; Slice 28 must expose and complete the day-2 management journey without weakening it. |
| RO-3 | **Consumed System Settings.** Web/API users can view and edit the supported System Settings through a permission-aware typed surface, including database/work/cache/log/export locations where permitted, locale/timezone, log level, retention, concurrency and retry policy. Values are validated, audited and consumed from the same exact Active/pinned authority as runtime work. Bootstrap-owned database location and any restart/deployment boundary remain explicit; the UI must not claim an Active setting is consumed when runtime is using another value. | System status exists, but System Settings are not a complete consumed managed-object journey. |
| RO-4 | **Versioned, secret-free configuration and result package exchange.** Web/API users can export bounded versioned configuration and result data, import a supported package as a Draft or recovery candidate, inspect schema/version and validation errors, and recover from stale/invalid imports. Actual secret values never enter packages; import never silently activates, overwrites the current Draft, changes Active or changes completed media work. | JSON bootstrap/import and result persistence exist, but the required versioned Web/API exchange and recovery journey is incomplete. |
| RO-5 | **Managed Webhook definitions and explicit test.** Authenticated Web/API users can create, edit, copy where applicable, enable, disable and delete Webhook definitions, select supported events, configure HTTPS endpoint and deployment-owned secret reference, inspect reference/validation/readiness state and run an explicit bounded connection/test action. Secret values, authorization material and private credentials remain redacted. | Signed HTTPS delivery infrastructure and read-only delivery views exist; definition management and test are not complete through Web/API. |
| RO-6 | **Independent delivery operations and recovery.** Notifications surfaces expose bounded deterministic delivery list/detail state, including delivery identity, event, attempts, lease/staleness, response/failure category and next action. Retry/requeue/dead-letter recovery is explicit, permission-aware, audited and isolated to the affected delivery; at-least-once behavior and duplicate-delivery implications remain visible without changing completed media work. | Durable delivery states and repository recovery primitives exist, but the complete Web/API operator recovery journey is unfinished. |

## Required Surfaces

The following user-visible/API surfaces are required for Slice completion:

1. **Configuration Web view and versioned API**
   - Exact Active/Draft/Validated/Superseded status, revision ID, version, digest and authority.
   - Natural `Edit Active by creating Draft` flow with no mutation of Active.
   - Typed forms/cards for the canonical managed configuration graph, consistent CRUD/copy/enable/
     disable/delete actions, reference/dependent impact and safe recovery.
   - Explicitly labelled Advanced JSON, import/export and support paths with the same validation and
     permission rules as forms.
   - Validation, applicable safe tests, diff/currentness, checked activation and failure recovery.

2. **System Settings Web view and versioned API**
   - Typed settings editing, exact Active consumption identity, permission and audit state.
   - Clear handling for invalid, stale, restart-required, bootstrap-owned or deployment-owned values.
   - No false success when the running process has not consumed the selected settings snapshot.

3. **Configuration/result exchange surface**
   - Bounded versioned export, import, schema validation, preview/currentness and recovery.
   - Secret-free package and result projections with durable import/export audit.
   - Imported content remains a Draft/recovery candidate until the normal exact validation and
     checked-activation path succeeds.

4. **Notifications/Webhook Web view and versioned API**
   - Webhook definition list/detail/forms, event selection, secret-reference handling and readiness.
   - Explicit bounded test with a visible result, failure category, side-effect statement and next
     action.
   - Delivery list/detail, lease/stale/dead-letter state, retry/requeue action, audit and recovery.

5. **Shared application and security boundary**
   - Web and API use identical validation, permissions, state transitions, audit, redaction, bounds
     and recovery semantics.
   - Existing Dashboard, Task/Job/Result, operational log and security-audit surfaces continue to
     link to the relevant configuration, setting, Webhook or delivery state where applicable.

## Safety Invariants

- `Active` means the exact immutable configuration snapshot consumed by runtime. A Draft, database row,
  JSON file or stale process snapshot must never be displayed as Active.
- Active and Superseded revisions are immutable. Editing always creates or updates a Draft; stale
  writers fail closed and cannot silently overwrite a newer Draft.
- Import, form editing, validation, diff, configuration preview and result export perform no media
  Storage mutation and grant no execution authority. Webhook tests are explicit, bounded and separate
  from media execution authority.
- Scanner, Parser, Recognition, Metadata, Naming, Classification and Planner remain zero-mutation;
  only OrganizerExecutor may invoke mutating Storage operations. Slice 28 does not alter this boundary.
- No silent overwrite, source deletion, directory cleanup, operation fallback or authority escalation.
- Web/API permission, validation, state, audit, redaction and recovery behavior must be shared; a
  convenience endpoint or UI action may not bypass the managed revision or execution gates.
- Deployment-owned secret references may be edited only as references. Secret values, tokens,
  passwords, cookies, authorization headers and private endpoint credentials must not appear in
  configuration payloads, exports, audits, results, logs, errors or Web responses.
- Webhook delivery retry/requeue is never automatic recovery by implication. The operator must see the
  durable delivery state, known attempts/effects, retry safety and explicit next action. One delivery
  must not hide, overwrite or block the diagnosis of another.
- Activation, settings edits, package import/export and Webhook definition changes do not start a
  media Scan, Preview, Organize, Task, Job or scheduled occurrence merely by being viewed or saved.
- Existing Active/pinned configuration identity, Task/TaskItem/Result history and completed media work
  remain intact when a Draft, package, setting or delivery action fails.
- `config/alist.json` remains ignored, untracked and unstaged. Tests use fakes, local servers and
  temporary roots; no production credentials or media are required.

## Explicitly Deferred

- Slice 29 Docker/Compose production packaging, production WSGI serving, `/data` lifecycle, non-root
  container operation, restart/upgrade integration and deployment migration E2E.
- Metadata Provider switching, additional production Providers and arbitrary Provider plugins.
- Built-in username/password identity, database-managed sessions and OIDC.
- A general Secret Store, automatic secret rotation and Docker Secrets-specific ingestion.
- Specialized email, chat and media-server notification channels; Slice 28 owns the existing signed
  HTTPS Webhook management and delivery journey only.
- Automatic replay of uncertain media mutations, complete historical/crash rollback, distributed
  Worker coordination and any redesign of the closed processing pipeline.
- Mutation-based Storage capability probes, arbitrary host-path access and new Storage-provider
  certification beyond the already documented boundaries.
- A parallel configuration, notification or media-task engine. Existing revision, Outbox,
  Task/TaskItem/Result, Worker and OrganizerExecutor authorities must be reused.

## Slice Acceptance Criteria

Slice 28 is complete only when all of the following are true:

1. RO-1 through RO-6 are demonstrated as complete Web/API user journeys, each with goal, entry,
   visible state, action, success, failure and recovery.
2. The ordinary Configuration journey is forms-first and supports an explicit Active-to-successor-
   Draft action; Advanced JSON and package import/export are clearly labelled and cannot become an
   implicit Active authority.
3. System Settings are validated, audited, exact-snapshot-bound and actually consumed by every
   applicable runtime component, or their restart/deployment limitation is explicit and fail-closed.
4. Webhook definition management and delivery recovery work through Web/API with redacted secrets,
   explicit test/retry/requeue authority and independently visible delivery outcomes.
5. Web and API behavior is parity-tested for permissions, validation, concurrency, state, audit,
   redaction, failure and recovery. No required outcome depends on direct SQLite, raw JSON editing or
   CLI-only knowledge.
6. Slice 26/27 Active snapshot, Storage, FileIndex, OrganizerExecutor, Task/Result, Worker, RBAC and
   safety behavior remains regression-free; no deferred Slice 29 or post-V1 capability is a hidden
   dependency.
7. No unresolved P0/P1 defect remains. P2/P3 wording, optional proof and future improvements do not
   block Slice completion.

## Final Validation Expectations

- Governance preflight and final validation pass using `scripts/check_governance.py`; the committed
  Slice Contract and Roadmap status remain authoritative and the Task parent matches Slice 28.
- Focused automated tests cover successful, invalid, stale-concurrency, reference, permission,
  redaction, import/export, settings-consumption, Webhook-test, delivery-recovery and failure paths.
- API/Web parity tests prove the same application behavior and durable state for every required surface.
- Configuration/import/export/result tests prove bounded deterministic output, supported version/schema
  handling, no secret values and no accidental Active mutation.
- Settings tests prove exact Active consumption, bootstrap/restart boundaries, invalid-value failure,
  recovery and no false Active/readiness claims.
- Webhook tests use fake/local HTTPS-capable transports or local servers and prove event selection,
  bounded test behavior, lease/stale/dead-letter handling, explicit retry/requeue and secret safety.
- Existing focused Slice 26/27 regressions, full supported offline test suite, formatting/lint,
  compile checks, package/dependency checks, Markdown/link checks, private-config checks and
  `git diff --check` pass, with external-service skips reported truthfully.
- No production SMB/OpenList/S3/TMDB service, credential, private endpoint, user path or real media
  root is required for automated validation.

## B Closure Packet

```text
Slice: 28 — Web-first Configuration and Operations Administration
Base SHA: 957a4ebcb0fde03e64be9c406fbcdfed9a12501d
Head SHA: 8546ff8fe15386dfbbb5fefb29a66b936ed4613f

Required Outcomes:
- RO-1 COMPLETE — Forms-first successor Draft and managed object lifecycle are available through
  shared Web/API application behavior with reference impact and safe recovery.
- RO-2 COMPLETE — Exact Active/Draft revision identity, optimistic concurrency, checked activation
  and exact Webhook-test evidence remain bound to immutable revision snapshots.
- RO-3 COMPLETE — Supported System Settings have typed Web/API editing, validation, audit and
  exact Active/pinned runtime consumption evidence with explicit bootstrap/restart boundaries.
- RO-4 COMPLETE — Versioned bounded configuration/result package export and Draft/recovery import
  are secret-free, validated and never silently activate or overwrite current work.
- RO-5 COMPLETE — Managed Webhook definitions, readiness, lifecycle, redaction and explicit
  bounded exact-revision signed tests are available through Web/API.
- RO-6 COMPLETE — Notification delivery list/detail and per-delivery dead-letter/stale recovery
  expose durable state, attempts, lease/staleness, failure/effect evidence, audit and
  at-least-once implications without changing completed media work.

Required Surfaces:
- Configuration Web view and versioned API COMPLETE.
- System Settings Web view and versioned API COMPLETE.
- Configuration/result exchange surface COMPLETE.
- Notifications/Webhook Web view and versioned API COMPLETE.
- Shared application and security boundary COMPLETE.

Implemented:
- Forms-first managed successor Draft and canonical configuration object lifecycle.
- Consumed System Settings with exact Active snapshot evidence and recovery boundaries.
- Versioned secret-free configuration and result package exchange.
- Managed Webhook definition lifecycle, readiness projection, exact-revision signed test and
  fail-closed endpoint query credential hardening.
- Independent notification delivery detail, stale/dead-letter recovery, API/Web parity and
  redacted audit evidence.

Tasks completed:
- Task 28.1 — final implementation head fa02ae6fd6d82cf98d6804536b7baa2b3591a0fb.
- Task 28.2 — final implementation head ab8a90e98c4518716ad153044b6785a669071f57.
- Task 28.3 — final implementation head 0e750a46584696563d86861828c2cc0a6908cbe4.
- Task 28.4 — final implementation head 3f0e89ee9a96a9cc5af61cd2614f1fbef3a0da3c.
- Task 28.5 — B PASS at implementation head 0b96b3f92a666a345aac8fc07f326150ce248a8e.
- Task 28.6 — B PASS at implementation head 8546ff8fe15386dfbbb5fefb29a66b936ed4613f.

Final Tests:
- Prior Slice 28 final focused modules at the original closure checkpoint — PASS, 239 tests.
- `.venv/bin/python -m unittest tests.test_webhook_url_security ... tests.test_final_integration`
  for Task 28.6 focused/related modules — PASS, 220 tests.
- `.venv/bin/python -W ignore -m unittest discover -s tests` during Task 28.6 review — 1361 tests,
  2 failures limited to the correction-loop governance state and a pre-existing Storage Browser UI
  wording assertion, 7 optional external-profile skips, 0 errors.
- `.venv/bin/python scripts/check_governance.py` during Task 28.6 review — FAIL only because the
  repository was in the A `FIX REQUIRED` correction loop with an active Task; the governance script
  itself was unchanged and this handback restores the no-active-Task `READY FOR A REVIEW` state.
- `.venv/bin/ruff format --check .` — only pre-existing formatting findings in
  `tests/test_system_settings_management.py`.
- `.venv/bin/ruff check .` — only pre-existing E501 in
  `tests/test_system_settings_management.py`.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS.
- `git diff --check` — PASS.
- `node --check` on the served operator `APP_JS` asset — PASS.
- Previously recorded package/build/link/FFprobe audits remain unchanged by Task 28.6 and are not
  expanded here; A should re-run any desired Slice-final packaging checks during re-review.

Safety Evidence:
- Configuration, settings, package, Webhook definition and delivery recovery reads/analysis do
  not invoke media Storage mutation or grant media execution authority.
- Active/Superseded revisions remain immutable; Draft edits and recovery actions use exact bounded
  state/revision checks and preserve prior Active and completed media history.
- Webhook explicit tests send at most one bounded signed request, do not create durable deliveries,
  and remain separate from media Task/Job/Scheduler and Storage mutation.
- Delivery recovery is atomic and per-delivery, preserves the stable delivery row/identity,
  protects against stale/concurrent state changes, and leaves sibling deliveries unchanged.
- Delivery/API/Web projections omit bodies, secrets, authorization material, cookies and remote
  response content; `config/alist.json` is ignored, untracked and unstaged.
- Webhook endpoint configuration now fails closed for userinfo, query-string and fragment
  credential channels; already-persisted unsafe URLs are redacted in revision detail, Web/API,
  export and audit projections while remaining explicitly correctable.

Known Non-blocking Issues:
- One pre-existing unrelated `tests.test_storage_browser` UI wording failure remains.
- `tests/test_system_settings_management.py` has the same pre-existing formatter and E501 findings
  recorded at the Task Base.
- Seven optional external acceptance profiles are unavailable in this environment and therefore
  remain skipped.

Explicitly Deferred: SEE CONTRACT ABOVE
Documentation Reconciliation Needed:
- A should reconcile factual Slice 28 completion/status references in `docs/roadmap.md`,
  `docs/progress.md`, `docs/product-experience.md`, `docs/requirements.md`, `docs/architecture.md`,
  the Chinese product requirements specification and README as appropriate during A Final Review.
  This is documentation truthfulness reconciliation only and must not expand scope.
Decision: SLICE READY FOR A REVIEW
```

## A Final Review

```text
Reviewed Range: 957a4ebcb0fde03e64be9c406fbcdfed9a12501d..0b96b3f92a666a345aac8fc07f326150ce248a8e
Decision: FIX REQUIRED
P0/P1 Blockers:
- P0 — RO-5 / secret-free Safety Invariants: managed Webhook validation accepts credential-bearing
  HTTPS URL query parameters and returns them in configuration/API/Web projections. Evidence:
  submitting `https://example.invalid/hooks?token=TOP_SECRET_VALUE` and
  `https://example.invalid/hooks?api_key=TOP_SECRET_VALUE` through the managed Webhook API returned
  HTTP 200, and the subsequent revision detail returned the same secret value in `url`. The
  validator at `mediaflow/domain/notification.py:93-101` rejects userinfo and fragments but does not
  reject credential-bearing queries; `WebhookDefinition.document()` then persists/returns the URL.
  Correction direction: fail closed on credential-bearing Webhook URL query parameters before
  persistence/projection, preserve the deployment-owned `secretEnv` reference boundary, and add API,
  Web, export/audit and runtime-loader regression tests proving the submitted secret never appears
  in durable configuration or any operator response.
```

## Review State

```text
Slice Status: READY FOR A REVIEW
Implementation Head: 8546ff8fe15386dfbbb5fefb29a66b936ed4613f
P0/P1 Defects: A P0 CORRECTION IMPLEMENTED BY TASK 28.6; READY FOR A RE-REVIEW
Decision: RETURNED TO A FINAL REVIEW
```
