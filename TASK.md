# Task 28.3 — Versioned Configuration and Result Package Exchange

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 28.3
Parent Slice: 28
Status: FIX REQUIRED
Task Base: 4db4be7cdf0211541e1f0470387d5239330431c5
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the versioned, secret-free configuration and result package exchange journey for Slice 28
RO-4: an authenticated operator can export bounded configuration and result packages, import a
supported configuration package as a Draft/recovery candidate, inspect schema/version/validation
state, and recover from stale or invalid imports without exposing secrets, changing Active, changing
completed media work or requiring direct SQLite/raw JSON knowledge.

## Why This Task Exists

Tasks 28.1 and 28.2 complete the forms-first configuration object lifecycle and consumed System
Settings journey, but Slice 28 still lacks the required Web/API package exchange surface. The current
code has managed revision import/bootstrap mechanics and persisted Task/Result records, yet there is
no coherent operator journey for versioned package export/import, no package schema/currentness
projection, no secret-free result export boundary, and no recovery path that proves import failures
leave Active, the current Draft and completed media work intact.

This is the largest reasonable next unit because RO-4 crosses the managed configuration authority,
Task/Result read models, redaction, import validation, application/API behavior, Web controls and
regression tests as one operator-visible package exchange workflow. It is independent of the
remaining Webhook definition/test and delivery recovery outcomes (RO-5/RO-6), which stay out of
scope for later Tasks.

## Implementation Scope

```text
Domain package contract / redaction
→ Application export/import services
→ managed Draft/recovery-candidate persistence and audit
→ versioned API with permissions and bounded errors
→ Operator Web import/export controls and recovery state
→ focused, parity, regression and safety tests
```

The Task may update only the implementation needed for the following behavior:

- Define a deterministic, bounded package contract for configuration export/import and result export.
  The package must include explicit package kind, schema/package version, generated timestamp,
  producer identity, source revision/result scope, digest/currentness evidence and bounded warnings
  where applicable.
- Configuration export must support at least Active and explicit Draft/Validated/Superseded revision
  sources through the managed configuration authority. It must not expose literal secret values,
  authorization material, cookies, passwords, bearer tokens or unrestricted private credentials.
  Deployment-owned secret references may appear only as references (for example environment-variable
  names) with clear redaction/ownership evidence.
- Result export must read persisted Task/Result evidence through repository/application interfaces,
  support bounded task/result scope and pagination or explicit limits, preserve the required result
  identity fields, and redact secret-bearing or unsafe text while retaining enough evidence for
  audit/recovery. Export must not read media files or require Storage/TMDB/Webhook connectivity.
- Configuration import must accept only supported configuration package versions and payload shapes,
  validate schema/version/digest and managed configuration rules, then create or update an explicit
  Draft/recovery candidate through the existing revision authority. It must never silently activate,
  overwrite the current Draft, change Active, change completed media work, start a Scan/Preview/
  Organize/Job/Task/scheduled occurrence, or mutate Storage.
- Import failure, stale currentness, unsupported package version, invalid schema, corrupt package,
  secret-containing payload and validation errors must return bounded recovery details that identify
  durable state, side effects, retry safety, exact revision/current Draft where relevant and next
  action. Prior Active and completed Task/Result history must remain intact.
- Web and API surfaces must use the same application behavior, permissions, validation, redaction,
  state transitions and audit rules. The Web Configuration/Settings administration area may expose
  package exchange as explicit Advanced/support controls, but ordinary forms-first object/settings
  editing must remain the primary path.
- Add durable, redacted audit evidence for export/import attempts and outcomes. Audit/log/error/Web
  responses must not contain recoverable secrets or raw secret payloads.

Files/areas explicitly frozen unless compatibility glue is strictly required:

- `SLICE.md`, `docs/roadmap.md`, `docs/progress.md`, product requirements, Product Experience and
  Architecture contracts.
- Completed Slice 28.1 forms/object lifecycle and Task 28.2 System Settings semantics, except shared
  package-entry links or compatibility reuse.
- Webhook definition management, explicit tests, delivery operations and delivery recovery.
- Storage mutation, OrganizerExecutor, Scanner/Parser/Recognition/Metadata/Naming/Classification/
  Planner behavior, Worker/Scheduler ownership protocol and mutation authority.
- Built-in identity, general Secret Store, Docker/Compose production packaging, Provider switching,
  new Storage providers and any redesign of the closed media-processing pipeline.

## Acceptance Criteria

- [ ] Authenticated API users can export a bounded versioned configuration package for the Active
      revision and an explicit managed revision, including package kind/version, source revision ID,
      revision status, revision version/sequence/digest, generated timestamp, currentness evidence,
      redaction evidence and validation/recovery metadata.
- [ ] Authenticated API users can export bounded persisted result data by supported task/result scope,
      including required result identity/effect fields and deterministic limits/cursors or explicit
      truncation evidence; export reads only durable repository state and never media/Storage.
- [ ] Actual secret values, bearer tokens, authorization headers, cookies, passwords, access keys,
      `secretEnv` values and equivalent credentials never appear in configuration packages, result
      packages, import validation errors, audit records, logs or Web/API responses. Secret references
      remain references only when allowed.
- [ ] Configuration import accepts a supported package, validates schema/version/digest/content and
      creates or updates only an explicit Draft/recovery candidate through the managed revision
      authority. Imported content remains inactive until the normal exact validation and checked
      activation path succeeds.
- [ ] Import does not silently overwrite the current Draft. Stale currentness, existing Draft
      conflicts, unsupported version, invalid schema, digest mismatch, validation errors and secret
      payloads fail closed with bounded recovery details: durable state, side effects `none`, retry
      safety, exact current revision/Draft evidence where relevant and next action.
- [ ] Active and Superseded revisions remain immutable. Export/import never starts Scan, Preview,
      Organize, Job, Task or scheduled occurrences and never mutates Storage or completed media work.
- [ ] Web controls expose configuration/result export and configuration import as explicit
      Advanced/support actions with package schema/version/currentness/recovery state. Web and API
      parity tests prove both surfaces use the same application behavior for success, permission
      denial, stale/invalid import, audit and redaction.
- [ ] Existing Slice 26/27 and Tasks 28.1/28.2 authority, forms-first editing, System Settings,
      Storage/FileIndex, OrganizerExecutor, Task/Result, Worker, Scheduler, RBAC and safety
      regressions remain intact.
- [ ] Required focused tests, full supported offline regression, governance, formatting/lint,
      compile, dependency and diff checks pass; unavailable optional/external gates are reported
      explicitly and truthfully.
- [ ] The checkpoint contains only this Task's coherent implementation/tests and no private
      configuration, `config/alist.json`, credentials, media or unrelated user work.

## Required Tests

Focused and related tests:

```bash
python3 -m unittest \
  tests.test_configuration_package_exchange \
  tests.test_configuration_snapshot \
  tests.test_configuration_management \
  tests.test_configuration_objects \
  tests.test_system_settings_management \
  tests.test_api_credentials \
  tests.test_operator_ui \
  tests.test_final_integration \
  tests.test_processing_recovery_admission \
  tests.test_recovery_continuation
```

The Developer must add focused package exchange tests covering:

- configuration export of Active and explicit Draft/Validated/Superseded revisions;
- result export for bounded Task/Result scope, deterministic ordering/limits and truncation or
  cursor evidence;
- secret-free package payloads, validation errors, audit records, logs and Web/API responses;
- supported import as Draft/recovery candidate, unsupported version, invalid schema, digest mismatch,
  literal-secret rejection and stale/existing-Draft conflicts;
- no Active mutation, no current Draft overwrite without explicit authority, no completed media-work
  changes, no Task/Job/scheduled occurrence creation and no Storage mutation;
- API/Web parity for package export/import success, permission denial, stale/invalid failure and
  recovery details.

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

Tests must use fakes, local repositories and temporary paths. Production Storage, TMDB, Webhook
endpoints, credentials, private paths and real media are not permitted. Any unavailable optional
external dependency or pre-existing local-environment failure must be reported with exact command,
result and evidence that it is unrelated to this Task.

## Non-goals

- Work outside the Slice 28 Contract or any change to its Required Outcomes, Required Surfaces,
  Safety Invariants, Base SHA or Explicitly Deferred scope.
- Re-implementing completed Task 28.1 forms-first configuration object CRUD/cards or Task 28.2
  consumed System Settings, except package-entry links and shared application reuse required by
  this Task.
- Webhook definition management, explicit Webhook connection tests, delivery list/detail changes,
  retry/requeue/dead-letter recovery or notification-channel expansion.
- Docker/Compose production packaging, production serving, restart/upgrade migration E2E, Provider
  switching, built-in identity/OIDC, a general Secret Store or new Storage providers.
- CSV export, bulk historical archive packaging, arbitrary media file export, direct SQLite/raw JSON
  management as the primary user path, automatic activation of imported packages or automatic replay
  of uncertain media mutations.
- Optional copy polish, extra test-only micro-Tasks, broad refactors or any Storage/OrganizerExecutor
  mutation behavior.

## Developer Completion Report

### Changed Files

- `mediaflow/application/package_exchange.py`
- `tests/test_configuration_package_exchange.py`
- `TASK.md` (fix-round status and this report)

### Implemented

B blocker — result package digest computed before final secret redaction:

- `PackageExchangeService.export_results` no longer computes `packageDigest`
  from a pre-sweep `results`/`source` payload. The package now runs the final
  `package_redaction_sweep` first and `packageDigest` is recomputed last from
  the exact secret-free `results`/`source` fields returned to the caller:
  `canonical_digest({"results": package["results"], "source": package["source"]})`.
  Every field covered by the digest is byte-for-byte the field present in the
  returned package, so verifying the returned package reproduces the digest.
- Because the sweep can redact the durable Task command embedded in the
  digest-covered `source`, a changed `source.taskCommand` is now recorded in
  the package's bounded `redaction` evidence (`field: source.taskCommand`,
  `kind: redacted_text`) with `entryCount` updated to match, so the returned
  evidence truthfully accounts for the redaction the caller can observe. The
  evidence list remains capped at `REDACTION_EVIDENCE_LIMIT`.
- Added the regression test B requested: a Task whose command is
  `preview password=hunter2` exports HTTP 200 with `source.taskCommand`
  returned as `preview password=[redacted]`, no secret text anywhere in the
  package, `packageDigest` equal to
  `canonical_digest({"results": package["results"], "source": package["source"]})`
  over the returned package, and `redaction` evidence containing the
  `source.taskCommand` entry.

### Tests and Results

- Reproduction of the reviewed blocker against `697be37` before the fix:
  exporting a Task whose command is `preview password=hunter2` returned HTTP
  200 with `source.taskCommand` redacted but a stale `packageDigest` that did
  not equal
  `canonical_digest({"results": package["results"], "source": package["source"]})`.
  After the fix the digest matches and the redaction evidence records the
  command redaction.
- `.venv/bin/python -m unittest tests.test_configuration_package_exchange` —
  PASS, 13 tests (12 prior + the new
  `test_result_export_digest_covers_secret_redacted_task_command`).
- Required focused/related modules
  (`tests.test_configuration_package_exchange`,
  `tests.test_configuration_snapshot`, `tests.test_configuration_management`,
  `tests.test_configuration_objects`, `tests.test_system_settings_management`,
  `tests.test_api_credentials`, `tests.test_operator_ui`,
  `tests.test_final_integration`,
  `tests.test_processing_recovery_admission`,
  `tests.test_recovery_continuation`) — 249 tests: 246 passed, 3 failed as
  `PRE-EXISTING / UNRELATED` (the same local-`.mediaflow`-store credential/CLI
  failures reported for the first round; each passes in a clean worktree at
  the reviewed checkpoint without that store).
- `.venv/bin/python -m unittest discover -s tests` — 1330 tests: 7 failures
  and 7 skips. All 7 failures are pre-existing/unrelated to this fix: six
  credential/CLI/storage tests pass in a clean worktree at the reviewed
  checkpoint without the local `.mediaflow` store, and one Storage-browser Web
  asset assertion fails identically at the reviewed checkpoint. No failure
  touches package exchange or is introduced by this correction.
- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/ruff check` and `.venv/bin/ruff format --check` on the two
  changed source files — PASS.
- `.venv/bin/ruff check .` — FAIL (pre-existing on Task Base, unchanged):
  `tests/test_system_settings_management.py:347` is already flagged and is not
  touched by this Task.
- `.venv/bin/ruff format --check .` — FAIL (pre-existing on Task Base,
  unchanged): the same `tests/test_system_settings_management.py` file would
  be reformatted.
- `.venv/bin/python -m pip check` — PASS (system `python3` has no `pip`;
  `pip check` was run from the project virtual environment).
- `git diff --check` — PASS after this report is committed.

### Decisions

- The digest is the last field computed in result export, from the exact
  post-sweep `results`/`source` the caller receives; no digest-covered field is
  mutated afterwards.
- The final redaction sweep may alter digest-covered `source` fields, so when
  it redacts the Task command that change is reflected in the bounded redaction
  evidence rather than remaining invisible to the operator.
- Result export still reads only the durable Task/Result repository, performs
  no Storage/workflow mutation, and the redaction evidence list stays capped at
  `REDACTION_EVIDENCE_LIMIT`.

### Remaining In-Slice Work

- Managed Webhook definition management/explicit test (RO-5) and independent
  delivery operations/recovery (RO-6) remain Slice 28 work outside this Task.

### Risks / Deviations

- Full regression and repo-wide lint are not clean in this working directory
  for the same pre-existing reasons reported in the first round: the ignored
  local `.mediaflow` store intercepts six raw-JSON credential/CLI/storage
  tests (each passes in a clean worktree without it), and one Storage-browser
  Web asset assertion fails identically at the reviewed checkpoint. Nothing
  was hidden, skipped, reclassified or fixed out of scope.
- `ruff`/`pip` are unavailable to the bare system `python3`; the available
  `.venv` binaries were used and reported truthfully.
- Test execution emits existing SQLite `ResourceWarning` messages; no
  production data or credentials were used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [pending correction commit]
```

## B Review Result

```text
Reviewed: 697be37e22934206993866cd4eba6f53995a5a69
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Result package integrity is not preserved after secret redaction. `PackageExchangeService.export_results`
  computes `packageDigest` from the unredacted `results`/`source` payload and then applies
  `package_redaction_sweep` to the returned package (`mediaflow/application/package_exchange.py:263-299`).
  Reproduction against the reviewed checkpoint: exporting a Task whose command is
  `preview password=hunter2` returns HTTP 200 with `source.taskCommand` changed to
  `preview password=[redacted]`, but `packageDigest` does not equal
  `canonical_digest({"results": package["results"], "source": package["source"]})`.
  Recompute the digest only after the final secret-free projection, ensure every field included in
  the digest is the exact field returned to the caller, and add a regression test covering a
  secret-shaped Task command plus redaction evidence.
